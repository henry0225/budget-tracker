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
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from categorizer import categorize_transactions
from parser import parse_csv, prepare_transactions

app = FastAPI(title="Budget Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Session store ──────────────────────────────────────────────────────────────
# Keyed by session UUID; values hold the prepared + categorized DataFrames.
# Evicted after 2 hours of inactivity.
_sessions: dict[str, dict] = {}


def _evict_old_sessions() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
    stale = [k for k, v in _sessions.items() if v["created_at"] < cutoff]
    for k in stale:
        del _sessions[k]


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


# ── Dashboard computation ──────────────────────────────────────────────────────

def _compute_dashboard(df: pd.DataFrame) -> dict:
    total = float(df["Amount"].sum())
    count = len(df)

    cat_series = df.groupby("Category")["Amount"].sum().sort_values(ascending=False)
    category_totals = [
        {"category": str(cat), "amount": float(amt)}
        for cat, amt in cat_series.items()
    ]

    # Wide-format monthly series: [{month, "Cat A": n, "Cat B": n, ...}]
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
        "insights": _compute_insights(df, cat_series, total),
    }


def _fmt_period(period_str: str) -> str:
    year, mon = period_str.split("-")
    return f"{calendar.month_abbr[int(mon)]} {year}"


def _compute_insights(df: pd.DataFrame, cat_series: pd.Series, total: float) -> list[dict]:
    cards: list[dict] = []

    # 1. Category breakdown — proportional data for stacked bar
    top_cat = str(cat_series.index[0])
    top_amt = float(cat_series.iloc[0])
    all_cats = [
        {"category": str(cat), "amount": float(amt), "pct": float(amt) / total * 100}
        for cat, amt in cat_series.items()
    ]
    cards.append({
        "type": "top_category",
        "title": "Spending breakdown",
        "data": {"category": top_cat, "amount": top_amt, "pct": top_amt / total * 100, "all_cats": all_cats},
    })

    # 2. Spending by day of week — bar chart data
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

    # 3. Largest single purchase
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

    # 4. Month-over-month comparison
    monthly_totals = (
        df.assign(m=lambda d: pd.to_datetime(d["Date"]).dt.strftime("%Y-%m"))
        .groupby("m")["Amount"]
        .sum()
        .sort_index()
    )
    if len(monthly_totals) >= 2:
        prev, curr = float(monthly_totals.iloc[-2]), float(monthly_totals.iloc[-1])
        pct = (curr - prev) / prev * 100
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

    # 5. Recurring charges (3+ consistent-amount transactions)
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

    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "prepared": prepared,
        "categorized": None,
        "created_at": datetime.now(timezone.utc),
    }

    return {
        "session_id": session_id,
        "transaction_count": len(prepared),
        "merchant_count": int(prepared["Merchant"].nunique()),
        "preview": _df_to_transactions(prepared.head(12)),
    }


@app.post("/api/merge")
async def merge_sessions(body: dict) -> dict:
    session_ids: list[str] = body.get("session_ids", [])
    if not session_ids:
        raise HTTPException(400, "No session IDs provided")

    dfs: list[pd.DataFrame] = []
    for sid in session_ids:
        session = _require_session(sid)
        dfs.append(session["prepared"])

    combined = dfs[0].copy() if len(dfs) == 1 else pd.concat(dfs, ignore_index=True)
    combined = combined.sort_values("Date", ascending=False).reset_index(drop=True)

    merged_id = str(uuid.uuid4())
    _sessions[merged_id] = {
        "prepared": combined,
        "categorized": None,
        "created_at": datetime.now(timezone.utc),
    }

    return {
        "session_id": merged_id,
        "transaction_count": len(combined),
        "merchant_count": int(combined["Merchant"].nunique()),
        "preview": _df_to_transactions(combined.head(12)),
    }


@app.get("/api/categorize/{session_id}")
async def categorize(session_id: str, api_key: str) -> StreamingResponse:
    session = _require_session(session_id)
    prepared: pd.DataFrame = session["prepared"]

    queue: asyncio.Queue[dict] = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def on_progress(done: int, total: int) -> None:
        loop.call_soon_threadsafe(
            queue.put_nowait, {"type": "progress", "done": done, "total": total}
        )

    async def _run() -> None:
        try:
            result = await loop.run_in_executor(
                None,
                lambda: categorize_transactions(prepared.copy(), api_key, on_progress=on_progress),
            )
            _sessions[session_id]["categorized"] = result
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
    return _compute_dashboard(categorized)


# ── Static files (production build) ───────────────────────────────────────────
_static = Path(__file__).parent / "frontend" / "dist"
if _static.exists():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
