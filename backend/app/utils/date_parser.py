"""
Shared date / temporal entity extraction used by WeatherService,
StockService, and NewsService.

Centralising this eliminates the duplicated _MONTH_MAP / _MONTH_PATTERN /
_extract_date_range blocks that previously lived in each service file.
"""

import re
import calendar

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

MONTH_MAP: dict[str, str] = {
    "january": "01", "february": "02", "march": "03",
    "april":   "04", "may":      "05", "june":   "06",
    "july":    "07", "august":   "08", "september": "09",
    "october": "10", "november": "11", "december":  "12",
}

MONTH_PATTERN: str = (
    r"January|February|March|April|May|June|July|August"
    r"|September|October|November|December"
)

# Indian meteorological seasons → calendar months (zero-padded strings)
_SEASONS: dict[str, list[str]] = {
    "winter":  ["12", "01", "02"],
    "summer":  ["04", "05", "06"],
    "hot":     ["04", "05", "06"],
    "monsoon": ["06", "07", "08", "09"],
    "rainy":   ["06", "07", "08", "09"],
    "autumn":  ["10", "11"],
    "fall":    ["10", "11"],
    "spring":  ["02", "03", "04"],
}

# Phrases that signal a trend / pattern query rather than a specific date
_TREND_WORDS: frozenset[str] = frozenset({
    "usually", "normally", "typically", "generally", "average",
    "trend", "historically", "how hot", "how cold", "how rainy",
    "how humid", "what is", "what are", "hottest", "coldest",
    "wettest", "driest", "rainiest", "like in", "like during",
    "usually like",
})

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def extract_date_range(
    question: str,
    default_start: str,
    default_end: str,
) -> tuple[str, str]:
    """Return (start_date, end_date) as 'YYYY-MM-DD' strings.

    Recognises four patterns (in priority order):
      1. ISO date          "2023-03-23"
      2. Day Month Year    "23 March 2023"
      3. Month Year        "March 2023"  →  full month
      4. Bare year         "in 2022"     →  full year

    Falls back to the given defaults when no date is found.
    """
    # 1) ISO date
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", question)
    if m:
        d = m.group(1)
        return d, d

    # 2) "23 March 2023"
    m = re.search(
        rf"\b(\d{{1,2}})\s+({MONTH_PATTERN})\s+(\d{{4}})\b",
        question, re.IGNORECASE,
    )
    if m:
        day   = m.group(1).zfill(2)
        month = MONTH_MAP[m.group(2).lower()]
        year  = m.group(3)
        d     = f"{year}-{month}-{day}"
        return d, d

    # 3) "March 2023"
    m = re.search(rf"\b({MONTH_PATTERN})\s+(\d{{4}})\b", question, re.IGNORECASE)
    if m:
        month = MONTH_MAP[m.group(1).lower()]
        year  = m.group(2)
        last  = calendar.monthrange(int(year), int(month))[1]
        return f"{year}-{month}-01", f"{year}-{month}-{last:02d}"

    # 4) Bare year
    m = re.search(r"\b(20[12]\d)\b", question)
    if m:
        year = m.group(1)
        return f"{year}-01-01", f"{year}-12-31"

    return default_start, default_end


def extract_month_only(question: str) -> str | None:
    """Detect a bare month name with NO attached year.

    "How hot is Delhi in June?"          →  "06"
    "Mumbai weather in March 2023"       →  None  (year present; handled by extract_date_range)
    """
    # If a year immediately follows the month, extract_date_range handles it
    if re.search(rf"\b(?:{MONTH_PATTERN})\s+\d{{4}}\b", question, re.IGNORECASE):
        return None
    m = re.search(rf"\b({MONTH_PATTERN})\b", question, re.IGNORECASE)
    if m:
        return MONTH_MAP[m.group(1).lower()]
    return None


def extract_season_months(question: str) -> list[str] | None:
    """Detect a season keyword and return its associated months.

    "Delhi weather in winter"  →  ["12", "01", "02"]
    Returns None when no season keyword is found.
    """
    q = question.lower()
    for season, months in _SEASONS.items():
        if season in q:
            return months
    return None


def is_trend_query(question: str) -> bool:
    """Return True when the question asks about typical or historical patterns."""
    q = question.lower()
    return any(w in q for w in _TREND_WORDS)
