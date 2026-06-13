"""
Fetch 5 years (2020-01-01 → 2024-12-31) of REAL daily OHLCV stock data for
15 NSE-listed Indian companies from Yahoo Finance's chart API and store in
MongoDB.

API:  https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}
Cost: Completely FREE — no API key required.
Rate: 1 request / company; sleep 2 s between requests to avoid 429s.

NSE symbols use the ".NS" suffix on Yahoo Finance (e.g., RELIANCE.NS).

Run from backend/:
    python -m app.scripts.ingest_stock
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import time
import datetime as dt
import requests
from app.config.database import db

stock_collection = db["stock_data"]

_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# Browser-like headers to avoid bot-detection by Yahoo Finance
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://finance.yahoo.com/",
}

# 15 major NSE-listed companies covering diverse sectors
COMPANIES: list[dict] = [
    {"company": "Reliance Industries",       "symbol": "RELIANCE.NS",   "sector": "Energy"},
    {"company": "Tata Consultancy Services", "symbol": "TCS.NS",        "sector": "IT"},
    {"company": "Infosys",                   "symbol": "INFY.NS",       "sector": "IT"},
    {"company": "HDFC Bank",                 "symbol": "HDFCBANK.NS",   "sector": "Banking"},
    {"company": "ICICI Bank",                "symbol": "ICICIBANK.NS",  "sector": "Banking"},
    {"company": "Wipro",                     "symbol": "WIPRO.NS",      "sector": "IT"},
    {"company": "HCL Technologies",          "symbol": "HCLTECH.NS",    "sector": "IT"},
    {"company": "Bajaj Finance",             "symbol": "BAJFINANCE.NS", "sector": "Finance"},
    {"company": "Kotak Mahindra Bank",       "symbol": "KOTAKBANK.NS",  "sector": "Banking"},
    {"company": "Hindustan Unilever",        "symbol": "HINDUNILVR.NS", "sector": "FMCG"},
    {"company": "State Bank of India",       "symbol": "SBIN.NS",       "sector": "Banking"},
    {"company": "ITC",                       "symbol": "ITC.NS",        "sector": "FMCG"},
    {"company": "Maruti Suzuki",             "symbol": "MARUTI.NS",     "sector": "Automobile"},
    {"company": "Bharti Airtel",             "symbol": "BHARTIARTL.NS", "sector": "Telecom"},
    {"company": "Sun Pharmaceutical",        "symbol": "SUNPHARMA.NS",  "sector": "Pharma"},
]


def _fetch_company(info: dict, period1: int, period2: int) -> list[dict]:
    """Request OHLCV history from Yahoo Finance for one NSE symbol."""
    url = _CHART_URL.format(symbol=info["symbol"])
    params = {
        "period1":  period1,
        "period2":  period2,
        "interval": "1d",
        "events":   "history",
        "includePrePost": "false",
    }
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    chart_results = data.get("chart", {}).get("result")
    if not chart_results:
        error_msg = data.get("chart", {}).get("error", {})
        raise ValueError(f"No chart data returned: {error_msg}")

    result     = chart_results[0]
    timestamps = result.get("timestamp", [])
    quote      = result.get("indicators", {}).get("quote", [{}])[0]

    opens   = quote.get("open",   [])
    highs   = quote.get("high",   [])
    lows    = quote.get("low",    [])
    closes  = quote.get("close",  [])
    volumes = quote.get("volume", [])

    # Strip ".NS" suffix for the stored symbol field
    clean_symbol = info["symbol"].replace(".NS", "")
    records: list[dict] = []

    for i, ts in enumerate(timestamps):
        close = closes[i] if i < len(closes) else None
        if close is None:
            continue   # Skip days with missing close (holiday/halt)

        open_p  = opens[i]   if i < len(opens)   and opens[i]   is not None else close
        high    = highs[i]   if i < len(highs)   and highs[i]   is not None else close
        low     = lows[i]    if i < len(lows)    and lows[i]    is not None else close
        volume  = int(volumes[i]) if i < len(volumes) and volumes[i] is not None else 0

        date_str   = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).strftime("%Y-%m-%d")
        change_pct = round(((close - open_p) / open_p) * 100, 2) if open_p else None

        records.append({
            "company":        info["company"],
            "symbol":         clean_symbol,
            "sector":         info["sector"],
            "date":           date_str,
            "open":           round(open_p, 2),
            "high":           round(high,   2),
            "low":            round(low,    2),
            "close":          round(close,  2),
            "volume":         volume,
            "change_percent": change_pct,
        })

    return records


def main() -> None:
    print("Dropping existing stock_data collection …")
    stock_collection.drop()

    print("Creating indexes on (company, date) and (symbol, date) …")
    stock_collection.create_index([("company", 1), ("date", 1)], unique=True)
    stock_collection.create_index([("symbol",  1), ("date", 1)])

    # Unix timestamps for the 5-year window
    period1 = int(dt.datetime(2020, 1,  1, tzinfo=dt.timezone.utc).timestamp())
    period2 = int(dt.datetime(2025, 1,  1, tzinfo=dt.timezone.utc).timestamp())

    grand_total = 0

    for info in COMPANIES:
        print(f"  Fetching {info['company']} ({info['symbol']}) from Yahoo Finance …", end=" ", flush=True)
        try:
            records = _fetch_company(info, period1, period2)
            if records:
                stock_collection.insert_many(records, ordered=False)
                grand_total += len(records)
                print(f"{len(records):,} trading days inserted.")
            else:
                print("no records returned.")
        except requests.HTTPError as exc:
            print(f"HTTP {exc.response.status_code} — {exc}")
        except ValueError as exc:
            print(f"Parse error — {exc}")
        except Exception as exc:
            print(f"ERROR — {exc}")

        time.sleep(2)  # Respect Yahoo Finance's informal rate limit

    print(f"\nStock ingestion complete — {grand_total:,} real records in MongoDB.")


if __name__ == "__main__":
    main()
