"""
Budget Tracker — production-grade NiceGUI dashboard.
"""

from __future__ import annotations

import io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from nicegui import ui

from parser import parse_csv, prepare_transactions
from categorizer import CATEGORIES, categorize_transactions

# ═══════════════════════════════════════════════════════════════════════════
# Design system
# ═══════════════════════════════════════════════════════════════════════════

_CAT_COLORS: dict[str, str] = {
    "Dining & Drinks":          "#f87171",
    "Groceries & Essentials":   "#34d399",
    "Transport":                "#60a5fa",
    "Shopping":                 "#fbbf24",
    "Travel":                   "#a78bfa",
    "Subscriptions & Services": "#f472b6",
    "Entertainment":            "#22d3ee",
    "Fees & Charges":           "#a3e635",
    "Uncategorized":            "#71717a",
}

# ═══════════════════════════════════════════════════════════════════════════
# Global state
# ═══════════════════════════════════════════════════════════════════════════

raw_df: pd.DataFrame | None = None
categorized_df: pd.DataFrame | None = None
_api_key: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# Charts (plotly with dark template)
# ═══════════════════════════════════════════════════════════════════════════

_PLOTLY_TEMPLATE = go.layout.Template()
_PLOTLY_TEMPLATE.layout.update(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#a1a1aa", size=11, family="Inter, system-ui, sans-serif"),
    xaxis=dict(gridcolor="#27272a", zeroline=False),
    yaxis=dict(gridcolor="#27272a", zeroline=False),
    margin=dict(l=0, r=0, t=0, b=0),
    hoverlabel=dict(bgcolor="#18181b", font_size=12, font_family="Inter"),
)


def _bar_chart(df: pd.DataFrame, x: str, y: str, *, color: str | None = None, height: int = 300) -> go.Figure:
    kwargs = {"color": color, "color_discrete_map": _CAT_COLORS} if color else {}
    fig = px.bar(df, x=x, y=y, orientation="h", text=df[x].apply(_fmt_dollar), **kwargs)
    fig.update_traces(
        textposition="outside",
        textfont=dict(color="#a1a1aa", size=11),
        marker=dict(line=dict(width=0)),
        hovertemplate="%{y}: %{x:$,.2f}<extra></extra>",
    )
    fig.update_layout(
        template=_PLOTLY_TEMPLATE,
        showlegend=False,
        height=height,
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(title=None, tickfont=dict(size=11, color="#a1a1aa"), fixedrange=True),
    )
    fig.update_xaxes(showgrid=False)
    return fig


def _area_chart(df: pd.DataFrame, x: str, y: str, color: str, *, height: int = 300) -> go.Figure:
    fig = px.area(df, x=x, y=y, color=color, color_discrete_map=_CAT_COLORS)
    fig.update_traces(
        line=dict(width=0),
        hovertemplate="%{x|%b %Y}: %{y:$,.0f}<extra>%{fullData.name}</extra>",
    )
    fig.update_layout(
        template=_PLOTLY_TEMPLATE,
        height=height,
        xaxis=dict(title=None, tickfont=dict(size=11, color="#a1a1aa"), fixedrange=True, dtick="M1", tickformat="%b"),
        yaxis=dict(title=None, tickfont=dict(size=11, color="#a1a1aa"), fixedrange=True, tickprefix="$"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=11, color="#a1a1aa")),
        hovermode="x unified",
    )
    return fig


def _fmt_dollar(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"${v/1_000:.0f}k"
    return f"${v:,.0f}"


# ═══════════════════════════════════════════════════════════════════════════
# HTML components (pixel-perfect where Quasar falls short)
# ═══════════════════════════════════════════════════════════════════════════

def _metric_card(label: str, value: str, *, accent: str = "") -> ui.html:
    accent_attr = f'style="color:{accent}"' if accent else ""
    return ui.html(f"""
        <div class="metric-card">
            <span class="metric-label">{label}</span>
            <span class="metric-value" {accent_attr}>{value}</span>
        </div>
    """)


def _insight_card(emoji: str, title: str, body: str) -> ui.html:
    return ui.html(f"""
        <div class="insight-card">
            <div class="insight-emoji">{emoji}</div>
            <div>
                <span class="insight-title">{title}</span>
                <p class="insight-body">{body}</p>
            </div>
        </div>
    """)


def _cat_badge(category: str) -> str:
    color = _CAT_COLORS.get(category, "#71717a")
    return f'<span class="cat-badge"><span class="cat-dot" style="background:{color}"></span>{category}</span>'


# ═══════════════════════════════════════════════════════════════════════════
# Event handlers
# ═══════════════════════════════════════════════════════════════════════════

async def _handle_upload(e: ui.upload.UploadEventArguments):
    global raw_df, categorized_df
    try:
        raw_df = parse_csv(io.BytesIO(e.content.read()))
        categorized_df = None
        e.sender.reset()
        _render()
        ui.notify(f"Loaded {len(raw_df):,} transactions", type="positive", position="top")
    except Exception as ex:
        ui.notify(f"Parse error: {ex}", type="negative", position="top")


async def _handle_categorize():
    global categorized_df, raw_df, _api_key
    if raw_df is None or not _api_key:
        ui.notify("Upload a CSV and enter your API key first", type="warning", position="top")
        return

    progress_label.set_text("Categorizing…")
    progress_bar.props("indeterminate")
    try:
        prepared = prepare_transactions(raw_df)

        def on_progress(done: int, total: int):
            progress_label.set_text(f"{done}/{total} merchants")
            progress_bar.props.remove("indeterminate")
            progress_bar.props(f"value={done/total*100}")

        categorized_df = categorize_transactions(prepared, _api_key, on_progress=on_progress)
        progress_label.set_text(f"Done — {len(categorized_df):,} transactions")
        _render()
    except Exception as ex:
        progress_label.set_text(f"Error: {ex}")
        progress_bar.props("value=0 indeterminate=false")


def _on_api_change(e):
    global _api_key
    _api_key = e.value or ""


# ═══════════════════════════════════════════════════════════════════════════
# Render
# ═══════════════════════════════════════════════════════════════════════════

def _render():
    """Rebuild the main content area."""
    main.clear()

    with main:
        if raw_df is None:
            _render_landing()
            return
        if categorized_df is None:
            _render_preview()
            return
        _render_dashboard()


def _render_landing():
    with ui.column().classes("items-center justify-center").style("min-height: 70vh"):
        ui.html("""
            <div style="text-align:center">
                <div style="font-size:4rem;margin-bottom:1.5rem;opacity:.6">●</div>
                <h1 style="font-size:1.75rem;font-weight:600;color:#fafafa;margin:0 0 .5rem;letter-spacing:-0.02em">Budget Tracker</h1>
                <p style="color:#a1a1aa;max-width:340px;line-height:1.6;font-size:.9rem">
                    Drop a Robinhood credit card CSV in the sidebar.
                    Enter your DeepSeek API key.
                    Click <strong style="color:#e4e4e7">Categorize</strong>.
                </p>
            </div>
        """)


def _render_preview():
    with ui.column().classes("w-full gap-0"):
        ui.html(f"""
            <h2 style="font-size:1.25rem;font-weight:600;color:#fafafa;margin:0 0 .25rem">Transaction Preview</h2>
            <p style="color:#a1a1aa;margin:0 0 1.5rem;font-size:.875rem">
                {len(raw_df):,} transactions · {raw_df['Merchant'].nunique()} unique merchants
            </p>
        """)

        preview = raw_df.head(12)[["Date", "Merchant", "Description", "Amount"]].copy()
        preview["Date"] = preview["Date"].astype(str)

        columns = [
            {"name": "Date", "label": "Date", "field": "Date", "align": "left", "sortable": True},
            {"name": "Merchant", "label": "Merchant", "field": "Merchant", "align": "left", "sortable": True},
            {"name": "Description", "label": "Description", "field": "Description", "align": "left"},
            {"name": "Amount", "label": "Amount", "field": "Amount", "align": "right", "sortable": True, ":format": "value => '$' + value.toFixed(2)"},
        ]
        ui.table(columns=columns, rows=preview.to_dict("records"), pagination=12).classes("w-full")


def _render_dashboard():
    pos = categorized_df[categorized_df["Amount"] > 0]
    total = pos["Amount"].sum()
    count = len(pos)
    avg = total / count if count else 0
    cat_totals = pos.groupby("Category")["Amount"].sum().sort_values(ascending=False)
    top_cat = cat_totals.index[0]

    # ── Metric cards ──
    with ui.row().classes("w-full gap-3 q-mb-md"):
        _metric_card("Total spending", _fmt_dollar(total))
        _metric_card("Transactions", f"{count:,}")
        _metric_card("Average", _fmt_dollar(avg))
        _metric_card("Top category", top_cat, accent=_CAT_COLORS.get(top_cat, ""))

    # ── Charts ──
    with ui.row().classes("w-full gap-3 q-mb-md").style("min-height: 340px"):
        with ui.element("div").classes("col").style("background:#18181b;border:1px solid #27272a;border-radius:12px;padding:1.25rem"):
            ui.html('<h3 style="font-size:.85rem;font-weight:600;color:#a1a1aa;margin:0 0 1rem;text-transform:uppercase;letter-spacing:.05em">Spending by Category</h3>')
            cat_data = cat_totals.reset_index(name="Total").sort_values("Total", ascending=True)
            ui.plotly(_bar_chart(cat_data, x="Total", y="Category", color="Category")).classes("w-full")

        with ui.element("div").classes("col").style("background:#18181b;border:1px solid #27272a;border-radius:12px;padding:1.25rem"):
            ui.html('<h3 style="font-size:.85rem;font-weight:600;color:#a1a1aa;margin:0 0 1rem;text-transform:uppercase;letter-spacing:.05em">Monthly Trend</h3>')
            monthly = (
                pos
                .assign(Month=lambda d: pd.to_datetime(d["Date"]).dt.to_period("M").dt.to_timestamp())
                .groupby(["Month", "Category"], as_index=False)["Amount"]
                .sum()
            )
            ui.plotly(_area_chart(monthly, x="Month", y="Amount", color="Category")).classes("w-full")

    # ── Tabs ──
    with ui.tabs().classes("q-mt-lg") as tabs:
        tx_tab = ui.tab("Transactions")
        ins_tab = ui.tab("Insights")
    with ui.tab_panels(tabs, value=tx_tab).classes("w-full"):
        with ui.tab_panel(tx_tab):
            _render_transactions(pos)
        with ui.tab_panel(ins_tab):
            _render_insights(pos)


def _render_transactions(pos: pd.DataFrame):
    rows_all = (
        pos[["Date", "Merchant", "Description", "Amount", "Category"]]
        .sort_values("Date", ascending=False)
        .copy()
    )
    rows_all["Date"] = rows_all["Date"].astype(str)

    with ui.row().classes("w-full gap-3 q-mb-md items-end"):
        cat_select = ui.select(
            {c: c for c in sorted(pos["Category"].unique())},
            value=list(pos["Category"].unique()),
            multiple=True,
            label="Category",
        ).classes("col-3").props('use-chips outlined dense bg-color="transparent"')
        search_input = ui.input("Search", placeholder="Merchant or description…").classes("col").props('outlined dense bg-color="transparent"')

    columns = [
        {"name": "Date", "label": "Date", "field": "Date", "align": "left", "sortable": True},
        {"name": "Merchant", "label": "Merchant", "field": "Merchant", "align": "left", "sortable": True},
        {"name": "Description", "label": "Description", "field": "Description", "align": "left"},
        {"name": "Amount", "label": "Amount", "field": "Amount", "align": "right", "sortable": True, ":format": "value => '$' + value.toFixed(2)"},
        {"name": "Category", "label": "Category", "field": "Category", "align": "left", "sortable": True, ":format": f"value => `{_cat_badge('$' + '{value}')}`"},
    ]

    table = ui.table(
        columns=columns,
        rows=rows_all.to_dict("records"),
        pagination={"rowsPerPage": 25, "sortBy": "Date", "descending": True},
    ).classes("w-full")

    def _filter():
        rows = rows_all.copy()
        cats = cat_select.value
        if cats:
            rows = rows[rows["Category"].isin(cats)]
        q = (search_input.value or "").lower()
        if q:
            mask = rows["Merchant"].str.lower().str.contains(q, na=False)
            mask |= rows["Description"].str.lower().str.contains(q, na=False)
            rows = rows[mask]
        table.update_rows(rows.to_dict("records"))
        total_label.set_text(f"{len(rows)} of {len(rows_all)} transactions — filtered total ${rows['Amount'].sum():,.2f}")

    cat_select.on("update:model-value", _filter)
    search_input.on("update:model-value", _filter)

    total_label = ui.label("").classes("text-grey-6 q-mt-sm")
    _filter()


def _render_insights(pos: pd.DataFrame):
    cat_totals = pos.groupby("Category")["Amount"].sum().sort_values(ascending=False)
    top_cat = cat_totals.index[0]
    top_amt = cat_totals.iloc[0]
    top_pct = (top_amt / cat_totals.sum()) * 100

    cards = [
        ("🍽️", "Top category", f"{top_cat} — {_fmt_dollar(top_amt)} ({top_pct:.0f}% of spending)"),
    ]

    travel = cat_totals.get("Travel", 0)
    if travel:
        cards.append(("✈️", "Travel", _fmt_dollar(travel)))

    # Recurring
    subs = []
    for m in pos.groupby("Merchant").filter(lambda g: len(g) >= 2)["Merchant"].unique():
        mtx = pos[pos["Merchant"] == m]
        amt = mtx["Amount"]
        if amt.std() < amt.mean() * 0.25 or amt.nunique() <= 2:
            subs.append((m, amt.sum(), len(mtx), amt.iloc[0]))
    if subs:
        body = " · ".join(f"{n} ({c}× ~{_fmt_dollar(t)})" for n, s, c, t in sorted(subs, key=lambda x: x[0].lower()))
        cards.append(("🔄", "Recurring payments", body))

    if "Date" in pos.columns:
        daily = pos.groupby(pd.to_datetime(pos["Date"]).dt.date)["Amount"].sum()
        cards.append(("📅", "Busiest day", f"{daily.idxmax()} — {_fmt_dollar(daily.max())}"))

        largest = pos.loc[pos["Amount"].idxmax()]
        cards.append(("🏆", "Largest purchase", f"{largest['Merchant']} — {_fmt_dollar(largest['Amount'])} on {largest['Date'].strftime('%b %d, %Y')}"))

        days = (pd.to_datetime(pos["Date"]).max() - pd.to_datetime(pos["Date"]).min()).days or 1
        cards.append(("💸", "Daily average", f"{_fmt_dollar(pos['Amount'].sum() / days)}/day"))

        mt = pos.assign(Month=lambda d: pd.to_datetime(d["Date"]).dt.to_period("M")).groupby("Month")["Amount"].sum().sort_index()
        if len(mt) >= 2:
            pct = ((mt.iloc[-1] - mt.iloc[-2]) / mt.iloc[-2]) * 100
            direction = "↑" if pct > 0 else "↓"
            cards.append(("📈", "Month-over-month", f"{direction} {abs(pct):.0f}% ({mt.index[-1]} vs {mt.index[-2]})"))

    with ui.row().classes("w-full gap-3"):
        for emoji, title, body in cards:
            _insight_card(emoji, title, body)


# ═══════════════════════════════════════════════════════════════════════════
# App shell
# ═══════════════════════════════════════════════════════════════════════════

def _build():
    ui.dark_mode().enable()

    # ── Inter font ──
    ui.add_head_html("""
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    """)

    # ── Base CSS ──
    ui.add_css("""
        /* ── Reset & base ── */
        * { font-family: 'Inter', system-ui, -apple-system, sans-serif !important; }
        body { background: #09090b !important; -webkit-font-smoothing: antialiased; }

        /* ── Header ── */
        .q-header { background: #09090b !important; border-bottom: 1px solid #27272a !important; }

        /* ── Drawer ── */
        .q-drawer { background: #0f0f12 !important; border-right: 1px solid #27272a !important; }
        .q-drawer .q-uploader {
            background: #18181b !important; border: 1px dashed #3f3f46 !important;
            border-radius: 12px !important; box-shadow: none !important;
        }
        .q-drawer .q-uploader__header { background: transparent !important; color: #a1a1aa !important; }
        .q-drawer .q-field--outlined .q-field__control {
            background: #18181b !important; border-color: #27272a !important;
            border-radius: 8px !important; box-shadow: none !important;
        }
        .q-drawer .q-field--outlined.q-field--focused .q-field__control { border-color: #818cf8 !important; }
        .q-drawer .q-field__native, .q-drawer .q-field__label { color: #a1a1aa !important; }
        .q-drawer .q-field__native { color: #e4e4e7 !important; }

        /* ── Buttons ── */
        .q-btn { border-radius: 8px !important; font-weight: 500 !important; text-transform: none !important; box-shadow: none !important; }
        .q-btn.bg-primary { background: #818cf8 !important; }
        .q-btn.bg-primary:hover { background: #6366f1 !important; }
        .q-btn[disabled] { opacity: .4 !important; background: #27272a !important; color: #71717a !important; }

        /* ── Progress ── */
        .q-linear-progress__model { background: #818cf8 !important; }

        /* ── Separator ── */
        .q-separator { background: #27272a !important; }

        /* ── Tabs ── */
        .q-tab { color: #71717a !important; text-transform: none !important; font-weight: 500 !important; font-size: .875rem !important; min-height: 40px !important; }
        .q-tab--active { color: #fafafa !important; }
        .q-tabs__indicator { background: #818cf8 !important; height: 2px !important; }
        .q-tab-panels { background: transparent !important; }

        /* ── Tables ── */
        .q-table { background: transparent !important; border-radius: 12px !important; overflow: hidden !important; }
        .q-table thead { background: #18181b !important; }
        .q-table thead tr th { color: #71717a !important; font-weight: 500 !important; font-size: .7rem !important; text-transform: uppercase !important; letter-spacing: .06em !important; padding: .75rem 1rem !important; border-color: #27272a !important; }
        .q-table tbody td { color: #d4d4d8 !important; font-size: .8125rem !important; padding: .65rem 1rem !important; border-color: #1f1f23 !important; }
        .q-table tbody tr:hover td { background: rgba(255,255,255,.02) !important; }
        .q-table__bottom { border-top: 1px solid #27272a !important; color: #71717a !important; }
        .q-table__bottom .q-btn { color: #a1a1aa !important; }

        /* ── Metric cards ── */
        .metric-card {
            background: #18181b; border: 1px solid #27272a; border-radius: 12px;
            padding: 1.25rem; display: flex; flex-direction: column; gap: .5rem;
            flex: 1; min-width: 0;
        }
        .metric-card:hover { border-color: #3f3f46; }
        .metric-label {
            font-size: .7rem; font-weight: 500; color: #71717a;
            text-transform: uppercase; letter-spacing: .06em;
        }
        .metric-value { font-size: 1.5rem; font-weight: 600; color: #fafafa; letter-spacing: -0.02em; }

        /* ── Insight cards ── */
        .insight-card {
            background: #18181b; border: 1px solid #27272a; border-radius: 12px;
            padding: 1.25rem; display: flex; gap: .85rem; align-items: flex-start;
            flex: 1; min-width: 0;
        }
        .insight-emoji { font-size: 1.25rem; flex-shrink: 0; line-height: 1.4; }
        .insight-title {
            display: block; font-size: .7rem; font-weight: 500; color: #71717a;
            text-transform: uppercase; letter-spacing: .06em; margin-bottom: .35rem;
        }
        .insight-body { margin: 0; font-size: .875rem; color: #d4d4d8; line-height: 1.5; font-weight: 450; }

        /* ── Category badges ── */
        .cat-badge { display: inline-flex; align-items: center; gap: .4rem; font-size: .8rem; color: #d4d4d8; }
        .cat-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex-shrink: 0; }

        /* ── Notifications ── */
        .q-notification { background: #18181b !important; border: 1px solid #27272a !important; border-radius: 12px !important; box-shadow: 0 4px 24px rgba(0,0,0,.5) !important; }
        .q-notification__message { color: #d4d4d8 !important; }

        /* ── Select chips ── */
        .q-chip { background: #27272a !important; color: #d4d4d8 !important; border-radius: 6px !important; }
        .q-chip .q-icon { color: #71717a !important; }

        /* ── Inputs in main area ── */
        .q-field--outlined .q-field__control {
            background: #18181b !important; border-color: #27272a !important;
            border-radius: 8px !important; box-shadow: none !important;
        }
        .q-field--outlined.q-field--focused .q-field__control { border-color: #818cf8 !important; }
    """)

    # ── Header ──
    with ui.header().classes("row items-center q-px-xl").style("height:56px"):
        ui.html("""
            <span style="font-size:1rem;font-weight:600;color:#fafafa;letter-spacing:-0.01em;display:flex;align-items:center;gap:.5rem">
                <span style="color:#818cf8">●</span> Budget Tracker
            </span>
        """)

    # ── Sidebar ──
    global progress_label, progress_bar, main

    with ui.left_drawer(value=True, bordered=False).style("width:300px") as drawer:
        with ui.column().classes("q-pa-lg gap-4 w-full"):
            ui.upload(
                label="Drop CSV here",
                on_upload=_handle_upload,
                auto_upload=True,
            ).classes("w-full").props('accept=".csv"')

            ui.input(
                "DeepSeek API key",
                password=True,
                password_toggle_button=True,
                on_change=_on_api_change,
            ).classes("w-full")

            ui.button(
                "Categorize transactions",
                on_click=_handle_categorize,
                icon="auto_awesome",
            ).classes("w-full")

            ui.separator()

            progress_label = ui.label("").classes("text-caption")
            progress_label.style("color:#71717a")
            progress_bar = ui.linear_progress(value=0).classes("w-full q-mt-xs")

            ui.space()
            ui.html("""
                <div style="font-size:.75rem;color:#52525b;line-height:1.6">
                    DeepSeek V4 · NiceGUI · Plotly
                </div>
            """)

    # ── Main content ──
    with ui.element("div").classes("q-pa-xl").style("width:100%;max-width:1200px;margin:0 auto") as main:
        _render()


_build()
ui.run(title="Budget Tracker", dark=True, reload=False, port=8080)
