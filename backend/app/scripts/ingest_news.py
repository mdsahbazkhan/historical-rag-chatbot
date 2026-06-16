"""
Fetch 2 years (2024-01-01 → 2025-12-31) of REAL India-related news articles
from The Guardian Open Platform API and store in MongoDB.

API:  https://open-platform.theguardian.com/documentation/
Cost: Completely FREE — developer tier allows 5,000 calls/day.
Key:  Register at https://open-platform.theguardian.com/access/ (instant, free).
      Add  GUARDIAN_API_KEY=<your_key>  to your .env file.

Strategy:
  - We iterate month by month (24 months), fetching up to PAGE_LIMIT pages
    of 50 articles each, filtered to India content.
  - This yields ~2,400–4,000 real Indian news articles over the 2-year window.

Run from backend/:
    python -m app.scripts.ingest_news
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import time
import calendar
import requests
from datetime import date
from app.config.database import db
from app.config.settings import GUARDIAN_API_KEY

news_collection = db["news_data"]

_BASE_URL  = "https://content.guardianapis.com/search"
_PAGE_SIZE = 50     
_PAGE_LIMIT = 4     

_SECTION_MAP: dict[str, str] = {
    "world":                "Politics",
    "politics":             "Politics",
    "india":                "Politics",
    "business":             "Business",
    "money":                "Economy",
    "economics":            "Economy",
    "global-development":   "Economy",
    "sport":                "Sports",
    "cricket":              "Sports",
    "technology":           "Technology",
    "science":              "Science",
    "media":                "Technology",
    "environment":          "Environment",
    "cities":               "Environment",
    "film":                 "Entertainment",
    "culture":              "Entertainment",
    "music":                "Entertainment",
    "stage":                "Entertainment",
    "books":                "Entertainment",
    "healthcare-network":   "Health",
    "society":              "Health",
    "education":            "Education",
}


def _section_to_category(section_id: str) -> str:
    return _SECTION_MAP.get(section_id.lower(), "General")


def _fetch_month(year: int, month: int) -> list[dict]:
    """Fetch up to PAGE_LIMIT pages of India-related articles for one month."""
    last_day = calendar.monthrange(year, month)[1]
    from_date = f"{year}-{month:02d}-01"
    to_date   = f"{year}-{month:02d}-{last_day:02d}"

    if not GUARDIAN_API_KEY:
        raise RuntimeError(
            "GUARDIAN_API_KEY is not set.\n"
            "  1. Register for a free key at https://open-platform.theguardian.com/access/\n"
            "  2. Add   GUARDIAN_API_KEY=<your_key>   to backend/.env\n"
            "  3. Re-run this script."
        )

    records: list[dict] = []

    for page in range(1, _PAGE_LIMIT + 1):
        params = {
            "q":           "india",
            "from-date":   from_date,
            "to-date":     to_date,
            "page-size":   _PAGE_SIZE,
            "page":        page,
            "show-fields": "trailText",       # brief article summary
            "order-by":    "relevance",
            "api-key":     GUARDIAN_API_KEY,
        }

        try:
            resp = requests.get(_BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json().get("response", {})
        except requests.HTTPError as exc:
            print(f"      HTTP {exc.response.status_code} on page {page} — skipping")
            break
        except Exception as exc:
            print(f"      Error on page {page}: {exc} — skipping")
            break

        results   = data.get("results", [])
        total_pgs = data.get("pages", 1)

        for item in results:
            pub_date = item.get("webPublicationDate", "")[:10]  # "YYYY-MM-DD"
            section  = item.get("sectionId", "world")
            title    = item.get("webTitle", "").strip()
            summary  = (item.get("fields") or {}).get("trailText", "").strip()

            if not title or not pub_date:
                continue

            records.append({
                "date":     pub_date,
                "title":    title,
                "summary":  summary,
                "category": _section_to_category(section),
                "source":   "The Guardian",
                "tags":     ["india", section, str(year)],
            })

        if page >= total_pgs:
            break   

        time.sleep(0.3)  

    return records


def main() -> None:
    print("Dropping existing news_data collection …")
    news_collection.drop()

    print("Creating indexes on date and (category, date) …")
    news_collection.create_index([("date", 1)])
    news_collection.create_index([("category", 1), ("date", 1)])

    grand_total = 0

    for year in (2024, 2025):
        for month in range(1, 13):
            month_label = date(year, month, 1).strftime("%B %Y")
            print(f"  Fetching {month_label} …", end=" ", flush=True)

            try:
                records = _fetch_month(year, month)
                if records:
                    news_collection.insert_many(records, ordered=False)
                    grand_total += len(records)
                    print(f"{len(records)} articles inserted.")
                else:
                    print("0 articles.")
            except RuntimeError as exc:
                print(f"\n\n[ERROR] {exc}\n")
                sys.exit(1)
            except Exception as exc:
                print(f"ERROR — {exc}")

            time.sleep(1)   # 1 s between months

    print(f"\nNews ingestion complete — {grand_total:,} real articles in MongoDB.")


if __name__ == "__main__":
    main()
