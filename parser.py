"""
Parser for credit card transaction CSV exports.
Supports Robinhood and Capital One formats.
"""

from __future__ import annotations

import re
from typing import Any

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
    # Square, Toast, Shopify, SumUp — common small-business POS systems
    r"SQ\s*\*|TST\*?|SP\s*\*|SUMUP\s*\*|"
    # PayPal, Stripe, Digital River — general payment processors
    r"PAYPAL\s*\*?|STRIPE\s*\*|DRI\*?|"
    # Misc POS / platform prefixes seen in the wild
    r"PY\s*\*|UEP\*?|SNACK\*?|PAR\*?|EB\s*\*|CPI\*?|CTLP\*?|FUNNEL\*?|"
    # Major merchants that embed their own prefix in descriptions
    r"AMAZON\s+(?:MKTPL|RETA)\*?|AMZN\*?|LYFT\s*\*|UBER\s*\*|OPENAI\s*\*|"
    # Chinese mobile payment platforms (AliPay, WeChat Pay)
    r"WEIXIN\*?|ALP\*?"
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

def parse_csv(source: str | Any) -> pd.DataFrame:
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
