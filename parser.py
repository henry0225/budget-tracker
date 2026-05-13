"""
Parser for Robinhood credit card transaction CSV exports.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# US state codes + common country codes for trailing location stripping
_STATE_CODES: set[str] = {
    "TX", "CA", "NY", "FL", "NV", "UT", "WA", "IL", "PA", "OH",
    "GA", "NC", "MI", "NJ", "VA", "AZ", "MA", "TN", "IN", "MO",
    "MD", "WI", "MN", "CO", "AL", "SC", "LA", "KY", "OR", "OK",
    "CT", "IA", "MS", "KS", "AR", "NM", "NE", "WV", "ID", "HI",
    "ME", "NH", "RI", "MT", "DE", "SD", "AK", "ND", "VT", "WY",
    "DC", "JP", "PL",
}
_STATE_ALT = "|".join(sorted(_STATE_CODES, key=len, reverse=True))

# Payment-processor / platform prefixes to strip
_NOISE_PREFIX_RE = re.compile(
    r"^(?:TST\*?|SQ\s?\*|PY\s?\*|UEP\*?|SNACK\*?|PAR\*?|"
    r"SUMUP\s?\*|EB\s?\*|CPI\*?|CTLP\*?|"
    r"AMAZON\s+(?:MKTPL|RETA)\*?|LYFT\s?\*|UBER\s?\*|"
    r"FUNNEL\*?|OPENAI\s?\*)\s*",
)

# Trailing "CITY ST" patterns
_TRAILING_LOCATION_RE = re.compile(
    rf"\s+[A-Z][A-Za-z]*\s+(?:{_STATE_ALT})\s*$"
)

# Domain-like suffixes (e.g. " WWW.AMAZON.COWA", " LYFT.COM CA")
_DOMAIN_RE = re.compile(r"\s+\S+\.(?:com|org|net|gov|edu|io|co|jp)\S*", re.IGNORECASE)

# Cryptic order codes (all caps + digits, no meaningful words)
_ORDER_CODE_RE = re.compile(r"^[A-Z0-9]{6,}$")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_csv(source: str | Any) -> pd.DataFrame:
    """Read a Robinhood credit card CSV export.

    Returns a DataFrame with all original columns; ``Date`` is parsed as
    datetime, ``Amount`` as float.
    """
    df = pd.read_csv(
        source,
        dtype={
            "Cardholder": str,
            "Merchant": str,
            "Description": str,
            "Status": str,
            "Type": str,
        },
        keep_default_na=False,
    )
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    return df


def prepare_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to posted purchases and add derived columns.

    Returns a DataFrame with columns:
    ``Date``, ``Time``, ``Amount``, ``Merchant``, ``Description``,
    ``Month``, ``ParsedDescription`` — sorted by Date descending.
    """
    mask = (df["Type"] == "Purchase") & (df["Status"] == "Posted") & (df["Amount"] > 0)
    out = df.loc[mask].copy()

    out["Month"] = out["Date"].dt.strftime("%Y-%m")
    out["ParsedDescription"] = [
        _clean_description(m, d)
        for m, d in zip(out["Merchant"], out["Description"])
    ]
    out = out.sort_values("Date", ascending=False).reset_index(drop=True)

    return out[["Date", "Time", "Amount", "Merchant", "Description", "Month", "ParsedDescription"]]


def get_summary_stats(df: pd.DataFrame) -> dict[str, Any]:
    """Compute summary statistics from prepared transaction data."""
    if df.empty:
        return {
            "total_spending": 0.0,
            "transaction_count": 0,
            "date_range": {"min": None, "max": None},
            "monthly_totals": {},
            "top_merchants": [],
        }

    monthly = df.groupby("Month")["Amount"].sum().round(2).to_dict()

    merchant_agg = (
        df.groupby("Merchant")
        .agg(total=("Amount", "sum"), count=("Amount", "count"))
        .sort_values("total", ascending=False)
        .head(20)
        .reset_index()
    )
    merchant_agg["total"] = merchant_agg["total"].round(2)

    return {
        "total_spending": round(df["Amount"].sum(), 2),
        "transaction_count": len(df),
        "date_range": {
            "min": df["Date"].min().strftime("%Y-%m-%d"),
            "max": df["Date"].max().strftime("%Y-%m-%d"),
        },
        "monthly_totals": monthly,
        "top_merchants": merchant_agg.to_dict("records"),
    }


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

    # 4. Collapse whitespace
    desc = re.sub(r"\s+", " ", desc).strip(" -.,*#")

    # 5. Fall back to merchant if the result is a cryptic order code or empty
    if not desc or len(desc) < 2 or _ORDER_CODE_RE.match(desc):
        desc = merchant

    return desc
