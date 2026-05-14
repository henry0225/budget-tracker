from __future__ import annotations

import asyncio
import calendar
import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncGenerator

import pandas as pd
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from categorizer import categorize_transactions
from parser import (
    parse_csv,
    parse_p2p_csv,
    prepare_p2p_for_dashboard,
    prepare_transactions,
    summarize_p2p,
)

app = FastAPI(title="Budget Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Session store ──────────────────────────────────────────────────────────────
# A session can hold credit-card data (awaiting LLM categorization) and/or
# Venmo/Zelle P2P data (pre-categorized — deterministic from descriptions).
# Evicted after 2 hours of inactivity.
#
# Schema:
#   prepared:       pd.DataFrame | None  — CC rows, columns from prepare_transactions
#   prepared_p2p:   pd.DataFrame | None  — raw P2P rows from parse_p2p_csv
#   p2p_summary:    dict | None          — pre-computed insight payload
#   categorized:    pd.DataFrame | None  — final merged CC+P2P with Category column
#   created_at:     datetime
_sessions: dict[str, dict] = {}


def _evict_old_sessions() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
    stale = [k for k, v in _sessions.items() if v["created_at"] < cutoff]
    for k in stale:
        del _sessions[k]


def _new_session(
    *,
    prepared: pd.DataFrame | None = None,
    prepared_p2p: pd.DataFrame | None = None,
    p2p_summary: dict | None = None,
) -> str:
    sid = str(uuid.uuid4())
    _sessions[sid] = {
        "prepared": prepared,
        "prepared_p2p": prepared_p2p,
        "p2p_summary": p2p_summary,
        "categorized": None,
        "created_at": datetime.now(timezone.utc),
    }
    return sid


def _require_session(session_id: str) -> dict:
    _evict_old_sessions()
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "Session not found — please re-upload the CSV")
    return session


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _df_to_transactions(df: pd.DataFrame, *, include_category: bool = False) -> list[dict]:
    cols = ["Date", "Merchant", "Description", "Amount"]
    if include_category:
        cols = [*cols, "Category"]
    out = df[cols].copy()
    out["Date"] = pd.to_datetime(out["Date"]).dt.strftime("%Y-%m-%d")
    return out.rename(columns=str.lower).to_dict("records")


def _session_counts(session: dict) -> dict:
    cc = session.get("prepared")
    p2p = session.get("prepared_p2p")
    cc_count = int(len(cc)) if cc is not None else 0
    p2p_summary = session.get("p2p_summary") or {}
    p2p_sent_count = int(p2p_summary.get("sent_count", 0))
    return {
        "cc_count": cc_count,
        "p2p_count": int(len(p2p)) if p2p is not None else 0,
        "p2p_sent_count": p2p_sent_count,
        "transaction_count": cc_count + p2p_sent_count,
    }


def _session_preview(session: dict) -> list[dict]:
    """Up to 12 rows blending CC and P2P, sorted by date desc."""
    parts: list[pd.DataFrame] = []
    cc = session.get("prepared")
    p2p = session.get("prepared_p2p")
    if cc is not None and not cc.empty:
        parts.append(cc[["Date", "Merchant", "Description", "Amount"]])
    if p2p is not None and not p2p.empty:
        sent = p2p[p2p["Direction"] == "sent"]
        if not sent.empty:
            parts.append(
                sent[["Date", "Counterparty", "Description", "Amount"]]
                .rename(columns={"Counterparty": "Merchant"})
            )
    if not parts:
        return []
    combined = pd.concat(parts, ignore_index=True).sort_values("Date", ascending=False).head(12)
    out = combined.copy()
    out["Date"] = pd.to_datetime(out["Date"]).dt.strftime("%Y-%m-%d")
    return out.rename(columns=str.lower).to_dict("records")


def _session_merchant_count(session: dict) -> int:
    merchants: set[str] = set()
    cc = session.get("prepared")
    p2p = session.get("prepared_p2p")
    if cc is not None and not cc.empty:
        merchants.update(cc["Merchant"].astype(str).unique())
    if p2p is not None and not p2p.empty:
        sent = p2p[p2p["Direction"] == "sent"]
        merchants.update(sent["Counterparty"].astype(str).unique())
    return len(merchants)


# ── Dashboard computation ──────────────────────────────────────────────────────

def _compute_dashboard(df: pd.DataFrame, *, p2p_summary: dict | None = None) -> dict:
    total = float(df["Amount"].sum())
    count = len(df)

    cat_series = df.groupby("Category")["Amount"].sum().sort_values(ascending=False)
    category_totals = [
        {"category": str(cat), "amount": float(amt)}
        for cat, amt in cat_series.items()
    ]

    monthly_wide = (
        df.assign(month=lambda d: pd.to_datetime(d["Date"]).dt.strftime("%Y-%m"))
        .groupby(["month", "Category"])["Amount"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )
    monthly_wide.columns = [str(c) for c in monthly_wide.columns]
    monthly_series = monthly_wide.to_dict("records")

    return {
        "transactions": _df_to_transactions(df, include_category=True),
        "category_totals": category_totals,
        "monthly_series": monthly_series,
        "metrics": {
            "total": total,
            "count": count,
            "average": total / count if count else 0.0,
            "top_category": str(cat_series.index[0]) if not cat_series.empty else "",
        },
        "insights": _compute_insights(df, cat_series, total, p2p_summary=p2p_summary),
    }


def _fmt_period(period_str: str) -> str:
    year, mon = period_str.split("-")
    return f"{calendar.month_abbr[int(mon)]} {year}"


def _compute_insights(
    df: pd.DataFrame,
    cat_series: pd.Series,
    total: float,
    *,
    p2p_summary: dict | None = None,
) -> list[dict]:
    cards: list[dict] = []

    if not cat_series.empty:
        top_cat = str(cat_series.index[0])
        top_amt = float(cat_series.iloc[0])
        all_cats = [
            {"category": str(cat), "amount": float(amt), "pct": (float(amt) / total * 100) if total else 0.0}
            for cat, amt in cat_series.items()
        ]
        cards.append({
            "type": "top_category",
            "title": "Spending breakdown",
            "data": {"category": top_cat, "amount": top_amt, "pct": (top_amt / total * 100) if total else 0.0, "all_cats": all_cats},
        })

    # P2P card — show right after the category breakdown so it's prominent
    if p2p_summary:
        cards.append({
            "type": "p2p_summary",
            "title": "Venmo & Zelle activity",
            "data": p2p_summary,
        })

    dates = pd.to_datetime(df["Date"])
    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dow_agg = (
        df.assign(dow=dates.dt.dayofweek)
        .groupby("dow")["Amount"]
        .agg(["sum", "count"])
        .reindex(range(7), fill_value=0)
    )
    peak_dow = int(dow_agg["sum"].idxmax())
    cards.append({
        "type": "day_of_week",
        "title": "Spending by day",
        "data": {
            "days": [
                {"day": dow_names[i], "amount": float(row["sum"]), "count": int(row["count"])}
                for i, row in dow_agg.iterrows()
            ],
            "peak_day": dow_names[peak_dow],
        },
    })

    largest = df.loc[df["Amount"].idxmax()]
    cards.append({
        "type": "largest_purchase",
        "title": "Largest purchase",
        "data": {
            "merchant": str(largest["Merchant"]),
            "amount": float(largest["Amount"]),
            "date": pd.to_datetime(largest["Date"]).strftime("%b %d, %Y"),
            "category": str(largest.get("Category", "")),
        },
    })

    monthly_totals = (
        df.assign(m=lambda d: pd.to_datetime(d["Date"]).dt.strftime("%Y-%m"))
        .groupby("m")["Amount"]
        .sum()
        .sort_index()
    )
    if len(monthly_totals) >= 2:
        prev, curr = float(monthly_totals.iloc[-2]), float(monthly_totals.iloc[-1])
        pct = (curr - prev) / prev * 100 if prev else 0.0
        pm, cm = str(monthly_totals.index[-2]), str(monthly_totals.index[-1])
        direction = "up" if pct > 0 else "down"
        cards.append({
            "type": f"mom_{direction}",
            "title": "Month-over-month",
            "data": {
                "curr_month": _fmt_period(cm),
                "curr_amount": curr,
                "prev_month": _fmt_period(pm),
                "prev_amount": prev,
                "pct": abs(pct),
                "direction": direction,
            },
        })

    recurring: list[dict] = []
    for merchant, grp in df.groupby("Merchant"):
        if len(grp) < 3:
            continue
        amounts = grp["Amount"]
        mean = float(amounts.mean())
        std = float(amounts.std(ddof=0))
        if std < mean * 0.25 or int(amounts.nunique()) <= 2:
            recurring.append({
                "name": str(merchant),
                "count": len(grp),
                "avg": mean,
                "total": float(amounts.sum()),
            })
    if recurring:
        items = sorted(recurring, key=lambda x: x["total"], reverse=True)
        grand_total = sum(r["total"] for r in items)
        cards.append({
            "type": "recurring",
            "title": "Recurring charges",
            "data": {"items": items, "grand_total": grand_total},
        })

    return cards


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files are supported")

    raw = await file.read()
    try:
        df = parse_csv(io.BytesIO(raw))
        prepared = prepare_transactions(df)
    except Exception as exc:
        raise HTTPException(422, str(exc))

    if prepared.empty:
        raise HTTPException(422, "No posted purchase transactions found in this CSV")

    session_id = _new_session(prepared=prepared)
    session = _sessions[session_id]
    counts = _session_counts(session)

    return {
        "session_id": session_id,
        "transaction_count": counts["transaction_count"],
        "cc_count": counts["cc_count"],
        "p2p_count": counts["p2p_sent_count"],
        "merchant_count": _session_merchant_count(session),
        "preview": _session_preview(session),
        "kind": "cc",
    }


@app.post("/api/upload-p2p")
async def upload_p2p(
    file: UploadFile = File(...),
    session_id: str | None = Form(None),
) -> dict:
    """Parse a Capital One 360 Checking CSV and attach Venmo/Zelle activity.

    Classification is fully deterministic — no API key, no LLM round-trip.
    Sent rows become "Venmo & Zelle" purchases in the dashboard; received
    rows are surfaced as a separate insight card (they are inflow, not
    spending).

    If ``session_id`` is provided, the P2P data is attached to that session
    (alongside any existing credit-card data).  Otherwise a fresh session
    is created.
    """
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files are supported")

    raw = await file.read()
    try:
        df_p2p = parse_p2p_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(422, str(exc))

    if df_p2p.empty:
        raise HTTPException(422, "No Venmo or Zelle transactions found in this CSV")

    p2p_summary = summarize_p2p(df_p2p)

    if session_id:
        session = _require_session(session_id)
        session["prepared_p2p"] = df_p2p
        session["p2p_summary"] = p2p_summary
        # Invalidate stale categorization so the dashboard rebuilds with P2P
        session["categorized"] = None
        sid = session_id
    else:
        sid = _new_session(prepared_p2p=df_p2p, p2p_summary=p2p_summary)

    session = _sessions[sid]
    counts = _session_counts(session)
    return {
        "session_id": sid,
        "transaction_count": counts["transaction_count"],
        "cc_count": counts["cc_count"],
        "p2p_count": counts["p2p_sent_count"],
        "merchant_count": _session_merchant_count(session),
        "preview": _session_preview(session),
        "kind": "p2p",
        "p2p_summary": p2p_summary,
    }


@app.post("/api/merge")
async def merge_sessions(body: dict) -> dict:
    session_ids: list[str] = body.get("session_ids", [])
    if not session_ids:
        raise HTTPException(400, "No session IDs provided")

    cc_dfs: list[pd.DataFrame] = []
    p2p_dfs: list[pd.DataFrame] = []
    for sid in session_ids:
        session = _require_session(sid)
        cc = session.get("prepared")
        if cc is not None and not cc.empty:
            cc_dfs.append(cc)
        p2p = session.get("prepared_p2p")
        if p2p is not None and not p2p.empty:
            p2p_dfs.append(p2p)

    cc_combined = (
        pd.concat(cc_dfs, ignore_index=True).sort_values("Date", ascending=False).reset_index(drop=True)
        if cc_dfs else None
    )
    p2p_combined = (
        pd.concat(p2p_dfs, ignore_index=True)
        .drop_duplicates(subset=["Date", "Description", "Amount"])
        .sort_values("Date", ascending=False)
        .reset_index(drop=True)
        if p2p_dfs else None
    )
    p2p_sum = summarize_p2p(p2p_combined) if p2p_combined is not None else None

    merged_id = _new_session(
        prepared=cc_combined,
        prepared_p2p=p2p_combined,
        p2p_summary=p2p_sum,
    )
    session = _sessions[merged_id]
    counts = _session_counts(session)

    return {
        "session_id": merged_id,
        "transaction_count": counts["transaction_count"],
        "cc_count": counts["cc_count"],
        "p2p_count": counts["p2p_sent_count"],
        "merchant_count": _session_merchant_count(session),
        "preview": _session_preview(session),
    }


@app.get("/api/categorize/{session_id}")
async def categorize(session_id: str, api_key: str | None = None) -> StreamingResponse:
    """LLM-categorize CC rows and merge with already-categorized P2P rows.

    ``api_key`` is only required when the session has credit-card data.
    Sessions that contain only Venmo/Zelle skip the LLM step entirely.
    """
    session = _require_session(session_id)
    prepared: pd.DataFrame | None = session.get("prepared")
    p2p: pd.DataFrame | None = session.get("prepared_p2p")

    has_cc = prepared is not None and not prepared.empty
    has_p2p = p2p is not None and not p2p.empty

    if not has_cc and not has_p2p:
        raise HTTPException(400, "Session has no transactions to categorize")

    if has_cc and not api_key:
        raise HTTPException(400, "API key required to categorize credit-card transactions")

    queue: asyncio.Queue[dict] = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def on_progress(done: int, total: int) -> None:
        loop.call_soon_threadsafe(
            queue.put_nowait, {"type": "progress", "done": done, "total": total}
        )

    async def _run() -> None:
        try:
            parts: list[pd.DataFrame] = []
            if has_cc:
                cat_cc = await loop.run_in_executor(
                    None,
                    lambda: categorize_transactions(prepared.copy(), api_key, on_progress=on_progress),
                )
                parts.append(cat_cc)
            if has_p2p:
                cat_p2p = prepare_p2p_for_dashboard(p2p)
                if not cat_p2p.empty:
                    parts.append(cat_p2p)
            if not parts:
                await queue.put({"type": "error", "message": "No transactions to categorize"})
                return
            merged = pd.concat(parts, ignore_index=True, sort=False)
            merged = merged.sort_values("Date", ascending=False).reset_index(drop=True)
            _sessions[session_id]["categorized"] = merged
            await queue.put({"type": "done"})
        except Exception as exc:
            await queue.put({"type": "error", "message": str(exc)})

    asyncio.create_task(_run())

    async def _stream() -> AsyncGenerator[str, None]:
        while True:
            msg = await queue.get()
            yield f"data: {json.dumps(msg)}\n\n"
            if msg["type"] in ("done", "error"):
                break

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/dashboard/{session_id}")
async def dashboard(session_id: str) -> dict:
    session = _require_session(session_id)
    categorized: pd.DataFrame | None = session.get("categorized")
    if categorized is None:
        raise HTTPException(400, "Categorization not complete")
    return _compute_dashboard(categorized, p2p_summary=session.get("p2p_summary"))


# ── Static files (production build) ───────────────────────────────────────────
_static = Path(__file__).parent / "frontend" / "dist"
if _static.exists():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
