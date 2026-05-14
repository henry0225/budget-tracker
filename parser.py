"""
Parser for credit card transaction CSV exports.
Supports Robinhood and Capital One formats.

Also extracts Venmo/Zelle activity from Capital One 360 Checking exports
(a different schema than the credit card format).
"""

from __future__ import annotations

import re

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STATE_CODES: set[str] = {
    "TX", "CA", "NY", "FL", "NV", "UT", "WA", "IL", "PA", "OH",
    "GA", "NC", "MI", "NJ", "VA", "AZ", "MA", "TN", "IN", "MO",
    "MD", "WI", "MN", "CO", "AL", "SC", "LA", "KY", "OR", "OK",
    "CT", "IA", "MS", "KS", "AR", "NM", "NE", "WV", "ID", "HI",
    "ME", "NH", "RI", "MT", "DE", "SD", "AK", "ND", "VT", "WY",
    "DC", "JP", "PL",
}
_STATE_ALT = "|".join(sorted(_STATE_CODES, key=len, reverse=True))

# Payment-processor / platform prefixes to strip (Robinhood + Capital One)
_NOISE_PREFIX_RE = re.compile(
    r"^(?:"
    # ── US point-of-sale terminals ────────────────────────────────────────
    # Square, Toast, Shopify Payments, Clover (Fiserv), WePay, Intuit GoPayment
    r"SQ\s*\*|TST\*?|SP\s*\*|CLOVER\s*\*|WPY\s*\*|INT\s*\*|"
    # iZettle / Zettle by PayPal, SumUp
    r"IZ\s*\*|ZETTLE[_\s]*\*?|IZETTLE\s*\*?|SUMUP\s*\*|"
    # Restaurant-specific ordering / reservation platforms
    r"OLO\s*\*|RESY\s*\*|TOCK\s*\*|"
    # ── Subscription & SaaS billing platforms ─────────────────────────────
    # PayPal (as gateway), Stripe, Braintree, Digital River
    r"PAYPAL\s*\*?|STRIPE\s*\*|BRAINTREE\s*\*|DRI\s*\*?|"
    # Paddle / Paddle.net, FastSpring (indie software common)
    r"PADDLE(?:\.NET)?\s*\*|FASTSPRING\s*\*|"
    # Patreon, Substack, Recurly
    r"PATREON\s*\*|SUBSTACK\s*\*|RECURLY\s*\*|"
    # ── Major platform sub-brand prefixes ─────────────────────────────────
    # Amazon marketplace / retail, Google (Play / Workspace), Microsoft
    r"AMAZON\s+(?:MKTPL|RETA)\s*\*?|AMZN\s*\*?|"
    r"GOOGLE\s*\*|GOOG\s*\*|MSFT\s*\*|"
    # Lyft, Uber, OpenAI
    r"LYFT\s*\*|UBER\s*\*|OPENAI\s*\*|"
    # ── Events & ticketing ────────────────────────────────────────────────
    # Eventbrite, Etix, AXS, Ticketmaster (TMCO / TKTMSTR), DICE
    r"EB\s*\*|ETIX\s*\*|AXS\s*\*|AXSED\s*\*|TMCO\s*\*|TKTMSTR\s*\*|DICE\s*\*|"
    # ── Marketplace / e-commerce gateways ─────────────────────────────────
    # Etsy (seller-side billing), Shopify (long form), WooPayments
    r"ETSY\s*\*|SHOPIFY\s*\*|WOO\s*\*|"
    # ── Payment infrastructure ────────────────────────────────────────────
    # Checkout.com, Adyen, Worldpay, Heartland, Shift4, Elavon
    r"CKO\s*\*|ADYEN\s*\*|WORLDPAY\s*\*|HEARTLAND\s*\*|SHIFT4\s*\*|ELAVON\s*\*|"
    # Flywire and TouchNet (university / education payments)
    r"FLYWIRE\s*\*|TOUCHNET\s*\*|"
    # ── Miscellaneous / legacy prefixes ───────────────────────────────────
    r"FUNNEL\s*\*?|PY\s*\*|UEP\s*\*?|SNACK\s*\*?|PAR\s*\*?|CPI\s*\*?|CTLP\s*\*?|"
    # ── International mobile payment platforms ────────────────────────────
    # WeChat Pay and AliPay (China)
    r"WEIXIN\s*\*?|ALP\s*\*?|"
    # GrabPay (SE Asia), Razorpay (India), PayMe/HSBC (HK), Kakao Pay (Korea)
    r"GRABPAY\s*\*|RAZORPAY\s*\*|PAYME\s*\*|KAKAOPAY\s*\*"
    r")\s*",
    re.IGNORECASE,
)

# Trailing "CITY ST" patterns
_TRAILING_LOCATION_RE = re.compile(
    rf"\s+[A-Z][A-Za-z]*\s+(?:{_STATE_ALT})\s*$"
)

# Domain-like suffixes
_DOMAIN_RE = re.compile(r"\s+\S+\.(?:com|org|net|gov|edu|io|co|jp)\S*", re.IGNORECASE)

# Cryptic order codes (all caps + digits, no meaningful words)
_ORDER_CODE_RE = re.compile(r"^[A-Z0-9]{6,}$")

# Trailing order code appended after a space (e.g. "Spotify P3DCEA9B48")
_TRAILING_CODE_RE = re.compile(r"\s+[A-Z0-9]{6,}\s*$")


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def _detect_format(df: pd.DataFrame) -> str:
    cols = set(df.columns)
    if {"Transaction Date", "Posted Date", "Debit"}.issubset(cols):
        return "capital_one"
    if {"Status", "Type", "Merchant"}.issubset(cols):
        return "robinhood"
    raise ValueError(
        "Unrecognized CSV format. "
        "Supported formats: Robinhood credit card, Capital One credit card."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_csv(source) -> pd.DataFrame:
    """Read a credit card CSV export and return a normalized DataFrame.

    Auto-detects Robinhood and Capital One formats. The returned DataFrame
    always has: Date (datetime), Time (str), Amount (float), Merchant (str),
    Description (str), Status (str), Type (str).
    """
    df = pd.read_csv(source, keep_default_na=False)
    fmt = _detect_format(df)
    if fmt == "capital_one":
        return _normalize_capital_one(df)
    return _normalize_robinhood(df)


def prepare_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to posted purchases and add derived columns.

    Returns a DataFrame with columns:
    Date, Time, Amount, Merchant, Description, Month, ParsedDescription
    — sorted by Date descending.
    """
    mask = (df["Status"] == "Posted") & (df["Type"] == "Purchase") & (df["Amount"] > 0)
    out = df.loc[mask].copy()

    out["Month"] = out["Date"].dt.strftime("%Y-%m")
    out["ParsedDescription"] = [
        _clean_description(m, d)
        for m, d in zip(out["Merchant"], out["Description"])
    ]
    out = out.sort_values("Date", ascending=False).reset_index(drop=True)
    return out[["Date", "Time", "Amount", "Merchant", "Description", "Month", "ParsedDescription"]]


# ---------------------------------------------------------------------------
# Format normalizers
# ---------------------------------------------------------------------------

def _normalize_robinhood(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["Cardholder", "Merchant", "Description", "Status", "Type", "Time"]:
        if col not in df.columns:
            df[col] = ""
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    return df


def _normalize_capital_one(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"Transaction Date": "Date"})
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
    df["Debit"] = pd.to_numeric(df["Debit"], errors="coerce").fillna(0)
    df["Amount"] = df["Debit"]
    # Strip payment-processor prefixes from the display merchant name
    df["Merchant"] = (
        df["Description"]
        .str.replace(_NOISE_PREFIX_RE, "", regex=True)
        .str.strip(" -.,*#")
    )
    # Fall back to original if cleaning wiped too much
    too_short = df["Merchant"].str.len() < 3
    df.loc[too_short, "Merchant"] = df.loc[too_short, "Description"]
    df["Time"] = ""
    df["Status"] = "Posted"
    # Mark payment/credit rows so prepare_transactions filters them out
    is_payment = (df["Amount"] == 0) | (df["Category"] == "Payment/Credit")
    df["Type"] = "Purchase"
    df.loc[is_payment, "Type"] = "Payment"
    return df


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean_description(merchant: str, description: str) -> str:
    """Clean a transaction description for downstream categorization."""
    desc = description or merchant
    if not desc:
        return merchant

    # 1. Strip payment-processor prefixes
    desc = _NOISE_PREFIX_RE.sub("", desc, count=1)

    # 2. Strip trailing location ("HOUSTON TX", "MINATO JP")
    for _ in range(2):
        desc = _TRAILING_LOCATION_RE.sub("", desc)

    # 3. Strip domain references
    desc = _DOMAIN_RE.sub("", desc)

    # 4. Strip trailing order codes ("Spotify P3DCEA9B48" → "Spotify")
    desc = _TRAILING_CODE_RE.sub("", desc)

    # 5. Collapse whitespace
    desc = re.sub(r"\s+", " ", desc).strip(" -.,*#")

    # 6. Fall back to merchant if the result is a cryptic order code or empty
    if not desc or len(desc) < 2 or _ORDER_CODE_RE.match(desc):
        desc = merchant

    return desc


# ---------------------------------------------------------------------------
# Capital One 360 Checking — Venmo/Zelle extraction
# ---------------------------------------------------------------------------

_ZELLE_SENT_RE = re.compile(r"^\s*Zelle\s+money\s+sent\s+to\s+(.+?)\s*$", re.IGNORECASE)
_ZELLE_RECEIVED_RE = re.compile(r"^\s*Zelle\s+money\s+received\s+from\s+(.+?)\s*$", re.IGNORECASE)
_VENMO_CASHOUT_RE = re.compile(r"VENMO\s+CASHOUT", re.IGNORECASE)
_VENMO_PAYMENT_RE = re.compile(r"VENMO\s+PAYMENT", re.IGNORECASE)

_CHECKING_REQUIRED_COLS = {
    "Transaction Description",
    "Transaction Date",
    "Transaction Type",
    "Transaction Amount",
}


def parse_p2p_csv(source) -> pd.DataFrame:
    """Parse a Capital One 360 Checking CSV and keep only Venmo/Zelle rows.

    Returns a DataFrame with columns:
    Date (datetime), Service, Direction, Counterparty, Amount (float), Description.
    Sorted by Date descending.
    """
    df = pd.read_csv(source, keep_default_na=False)
    if not _CHECKING_REQUIRED_COLS.issubset(df.columns):
        raise ValueError(
            "Unrecognized checking CSV format. Expected a Capital One 360 "
            "Checking export with columns: Transaction Description, "
            "Transaction Date, Transaction Type, Transaction Amount."
        )

    df = df.rename(
        columns={
            "Transaction Description": "Description",
            "Transaction Date": "Date",
            "Transaction Type": "Type",
            "Transaction Amount": "Amount",
        }
    )
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%y", errors="coerce")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

    parsed = df["Description"].apply(_parse_p2p_description)
    df["Service"] = [p[0] if p else None for p in parsed]
    df["Direction"] = [p[1] if p else None for p in parsed]
    df["Counterparty"] = [p[2] if p else None for p in parsed]

    # Cross-check direction against the bank's debit/credit flag.
    # Debit = money out of checking (sent); Credit = money in (received).
    bank_dir = df["Type"].str.lower().map({"debit": "sent", "credit": "received"})
    df["Direction"] = df["Direction"].where(df["Direction"].notna(), bank_dir)

    out = df[df["Service"].notna() & df["Date"].notna() & df["Amount"].notna()].copy()
    out = out.sort_values("Date", ascending=False).reset_index(drop=True)
    return out[["Date", "Service", "Direction", "Counterparty", "Amount", "Description"]]


def _parse_p2p_description(desc: str) -> tuple[str, str, str] | None:
    """Return (service, direction, counterparty) or None if not Venmo/Zelle."""
    if not desc:
        return None

    m = _ZELLE_SENT_RE.match(desc)
    if m:
        return ("Zelle", "sent", _normalize_name(m.group(1)))
    m = _ZELLE_RECEIVED_RE.match(desc)
    if m:
        return ("Zelle", "received", _normalize_name(m.group(1)))
    if _VENMO_CASHOUT_RE.search(desc):
        return ("Venmo", "received", "Venmo (cashout to bank)")
    if _VENMO_PAYMENT_RE.search(desc):
        return ("Venmo", "sent", "Venmo (payment from bank)")
    return None


def _normalize_name(name: str) -> str:
    """Title-case all-caps names; preserve mixed-case and numeric strings."""
    name = name.strip(" -.,")
    if not name or any(c.islower() for c in name):
        return name
    return name.title()


def prepare_p2p_for_dashboard(df_p2p: pd.DataFrame) -> pd.DataFrame:
    """Convert P2P parser output into the standard transaction schema.

    Both directions are returned with the same category ``Venmo & Zelle``.
    Sent rows keep their amount as-is; received rows are *negated*, so when
    the dashboard sums the category it gets the true net spend (sent minus
    received) instead of double-counting reimbursements as inflow.

    The counterparty is used as the Merchant so people / businesses appear
    in the dashboard's transaction table just like any other purchase.
    """
    cols = ["Date", "Time", "Amount", "Merchant", "Description", "Month", "ParsedDescription", "Category"]
    if df_p2p.empty:
        return df_p2p.assign(
            Time="", Month="", ParsedDescription="", Category="Venmo & Zelle", Merchant="",
        )[cols]

    out = df_p2p.copy()
    out["Merchant"] = out["Counterparty"]
    out["Time"] = ""
    out["Month"] = out["Date"].dt.strftime("%Y-%m")
    out["ParsedDescription"] = out["Description"]
    out["Category"] = "Venmo & Zelle"
    # Received rows are inflow — store as a negative spending amount so the
    # category sum nets them out automatically.
    received_mask = out["Direction"] == "received"
    out.loc[received_mask, "Amount"] = -out.loc[received_mask, "Amount"].abs()

    out = out.sort_values("Date", ascending=False).reset_index(drop=True)
    return out[cols]


def summarize_p2p(df_p2p: pd.DataFrame) -> dict:
    """Compute a P2P summary (sent/received totals, by-counterparty, etc.).

    Used to build the dashboard's "Venmo & Zelle activity" insight card.
    """
    if df_p2p.empty:
        return {}

    sent = df_p2p[df_p2p["Direction"] == "sent"]
    received = df_p2p[df_p2p["Direction"] == "received"]

    def _by_party(frame: pd.DataFrame) -> list[dict]:
        if frame.empty:
            return []
        agg = (
            frame.groupby("Counterparty")["Amount"]
            .agg(["sum", "count"])
            .sort_values("sum", ascending=False)
            .reset_index()
        )
        return [
            {"name": str(r["Counterparty"]), "amount": float(r["sum"]), "count": int(r["count"])}
            for _, r in agg.iterrows()
        ]

    by_service = []
    for svc in ["Venmo", "Zelle"]:
        s = df_p2p[df_p2p["Service"] == svc]
        if s.empty:
            continue
        by_service.append({
            "service": svc,
            "sent": float(s[s["Direction"] == "sent"]["Amount"].sum()),
            "received": float(s[s["Direction"] == "received"]["Amount"].sum()),
        })

    return {
        "sent_total": float(sent["Amount"].sum()),
        "received_total": float(received["Amount"].sum()),
        "sent_count": int(len(sent)),
        "received_count": int(len(received)),
        "by_service": by_service,
        "top_sent": _by_party(sent)[:8],
        "top_received": _by_party(received)[:8],
    }
