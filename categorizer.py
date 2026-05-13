"""
DeepSeek LLM-powered transaction categorizer with local JSON caching.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORIES: list[str] = [
    "Dining & Drinks",
    "Groceries & Essentials",
    "Transport",
    "Shopping",
    "Travel",
    "Subscriptions & Services",
    "Entertainment",
    "Fees & Charges",
]

ENDPOINT: str = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL: str = "deepseek-v4-flash"
CACHE_PATH: str = os.path.expanduser("~/.budget-tracker-cache.json")
BATCH_SIZE: int = 20

_CATEGORY_PROMPT: str = """You are a personal finance categorizer. Classify each transaction into exactly one of these 8 categories:

1. "Dining & Drinks" – restaurants, fast food, coffee, boba/tea shops, bars, food delivery (Uber Eats, DoorDash), bakeries, ice cream
2. "Groceries & Essentials" – grocery stores, supermarkets, pharmacies (CVS, Walgreens), household supplies, liquor stores, Costco/Walmart when used for groceries
3. "Transport" – ride share (Lyft, Uber rides only), transit passes, gas stations (Shell, Chevron), parking, Waymo, public transit
4. "Shopping" – general retail (Amazon, Target, Etsy), clothing, electronics, department stores, online shopping
5. "Travel" – airlines, hotels, Airbnb, travel bookings, airport purchases (duty-free, Hudson News), tourism attractions
6. "Subscriptions & Services" – streaming (Spotify, Netflix), software subscriptions (ChatGPT/OpenAI), insurance (Lemonade), membership fees, cloud services
7. "Entertainment" – movies, events, concerts, sporting goods, parks, museums, rec centers, amusement parks, theater
8. "Fees & Charges" – bank/card fees, annual fees, returned payment fees, late fees

Rules:
- Use the merchant name AND description together to decide. The description often has extra detail that clarifies ambiguous merchants.
- "Uber Eats" and food delivery go to "Dining & Drinks", but "Uber" rides go to "Transport".
- Gas stations (Shell, Chevron, Exxon) go to "Transport".
- Pharmacies (CVS, Walgreens) go to "Groceries & Essentials".
- Costco and Walmart are "Groceries & Essentials" unless the description clearly indicates something else (e.g., electronics, furniture).
- Airport shops (Hudson News) go to "Travel".
- If genuinely unsure, pick the most likely category. Do NOT invent new categories.

Return ONLY a JSON object with this exact structure (no markdown, no extra text):
{"results": [{"merchant": "M1", "description": "D1", "category": "Cat1"}, ...]}"""


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_key(merchant: str, description: str) -> str:
    return f"{merchant or ''}||{description or ''}"


def _load_cache() -> dict[str, str]:
    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH) as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_cache(cache: dict[str, str]) -> None:
    tmp = CACHE_PATH + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(cache, f, indent=2, sort_keys=True)
        os.replace(tmp, CACHE_PATH)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def categorize_transactions(
    df: "pd.DataFrame",  # noqa: F821
    api_key: str,
    model: str = DEFAULT_MODEL,
    on_progress: Callable[[int, int], None] | None = None,
) -> "pd.DataFrame":  # noqa: F821
    """Add a ``Category`` column using DeepSeek + local cache.

    Groups by unique (Merchant, ParsedDescription) pairs and categorizes
    in batches.  Already-cached pairs skip the API entirely.

    *on_progress* — optional callback ``(done, total)`` for UI feedback.
    """
    if df.empty:
        df["Category"] = "Uncategorized"
        return df

    pairs = (
        df[["Merchant", "ParsedDescription"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    total = len(pairs)

    # Build mapping: load cache once, fill uncached via API
    cache = _load_cache()
    mapping: dict[str, str] = {}
    uncached_items: list[dict[str, str]] = []

    for _, row in pairs.iterrows():
        key = _cache_key(row["Merchant"], row["ParsedDescription"])
        if key in cache:
            mapping[key] = cache[key]
        else:
            uncached_items.append({
                "merchant": row["Merchant"],
                "description": row["ParsedDescription"],
            })

    # Batch-call API for uncached items
    for start in range(0, len(uncached_items), BATCH_SIZE):
        chunk = uncached_items[start : start + BATCH_SIZE]
        batch_results = _categorize_batch(chunk, api_key, model, cache)
        mapping.update(batch_results)

        if on_progress:
            on_progress(
                len(mapping),
                total,
            )

    _save_cache(cache)

    # Vectorized join — much faster than df.apply(axis=1)
    df["_key"] = df["Merchant"].astype(str) + "||" + df["ParsedDescription"].astype(str)
    df["Category"] = df["_key"].map(mapping).fillna("Uncategorized")
    df.drop(columns=["_key"], inplace=True)

    return df


def get_category(
    merchant: str,
    description: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """Categorize a single (merchant, description) pair."""
    key = _cache_key(merchant, description)
    cache = _load_cache()
    if key in cache:
        return cache[key]

    results = _categorize_batch(
        [{"merchant": merchant, "description": description}],
        api_key,
        model,
        cache,
    )
    if results:
        _save_cache(cache)
    return results.get(key, "Uncategorized")


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _categorize_batch(
    items: list[dict[str, str]],
    api_key: str,
    model: str,
    cache: dict[str, str],
) -> dict[str, str]:
    """Categorize a batch in one API call.  *cache* is mutated in-place."""
    results: dict[str, str] = {}

    # Separate already-cached
    uncached: list[dict[str, str]] = []
    for item in items:
        key = _cache_key(item["merchant"], item.get("description", ""))
        if key in cache:
            results[key] = cache[key]
        else:
            uncached.append(item)

    if not uncached:
        return results

    # Build prompt
    item_list = "\n".join(
        f'{i+1}. Merchant: "{it["merchant"]}"  Description: "{it.get("description", "")}"'
        for i, it in enumerate(uncached)
    )
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": _CATEGORY_PROMPT},
            {"role": "user", "content": f"Classify these transactions:\n{item_list}"},
        ],
        "temperature": 0.0,
        "max_tokens": max(256, len(uncached) * 40),
        "thinking": {"type": "disabled"},
    }

    response = _call_api(api_key, payload)
    if response is None:
        for it in uncached:
            key = _cache_key(it["merchant"], it.get("description", ""))
            cache[key] = "Uncategorized"
            results[key] = "Uncategorized"
        return results

    if response.status_code == 401:
        raise ValueError("Invalid DeepSeek API key — check your key at platform.deepseek.com")
    if response.status_code == 402:
        raise ValueError("Insufficient DeepSeek credits — please top up at platform.deepseek.com")
    if response.status_code >= 400:
        raise ValueError(f"DeepSeek API error ({response.status_code})")

    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        for entry in parsed.get("results", []):
            key = _cache_key(entry["merchant"], entry.get("description", ""))
            cat = entry["category"]
            cache[key] = cat
            results[key] = cat if cat in CATEGORIES else cat
    except (KeyError, json.JSONDecodeError, TypeError):
        for it in uncached:
            key = _cache_key(it["merchant"], it.get("description", ""))
            cache[key] = "Uncategorized"
            results[key] = "Uncategorized"

    return results


def _call_api(
    api_key: str,
    payload: dict[str, Any],
    retries: int = 1,
) -> requests.Response | None:
    """POST to DeepSeek with one retry on transient errors."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        try:
            resp = requests.post(ENDPOINT, headers=headers, json=payload, timeout=60)
            if resp.status_code < 500:
                if resp.status_code >= 400:
                    print(f"DeepSeek HTTP {resp.status_code}: {resp.text[:500]}")
                return resp
            last_exc = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as exc:
            last_exc = exc
        if attempt < retries:
            time.sleep(1.0 * (attempt + 1))

    print(f"DeepSeek API error after {retries + 1} attempts: {last_exc}")
    return None
