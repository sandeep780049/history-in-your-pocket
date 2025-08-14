#!/usr/bin/env python3
"""
generate_full_history.py

Generates full_history_ddmm.json : a mapping DD-MM -> list of event objects.

Each event object:
{
  "year": 1947,
  "title": "India gains independence",
  "description": "Full text...",
  "type": "event" | "birth" | "death",
  "source_url": "https://en.wikipedia.org/..."
}

Features:
- Uses Wikipedia REST 'onthisday' endpoints (events,births,deaths)
- Filters to MIN_YEAR (default 1800)
- Polite delay and retries
- Resume support via a partial temp file
- Optionally merge in a curated JSON (curated.json) that has DD-MM keys
- Prioritizes Indian-related items (simple keyword heuristics)
- Configurable TOP_N per day
"""

import argparse
import json
import os
import time
import sys
import math
from datetime import datetime
try:
    import requests
except ImportError:
    print("Please pip install requests")
    sys.exit(1)

try:
    from tqdm import tqdm
    HAVE_TQDM = True
except Exception:
    HAVE_TQDM = False

WIKI_BASE = "https://en.wikipedia.org/api/rest_v1/feed/onthisday"
TYPES = [("events","event"), ("births","birth"), ("deaths","death")]

DEFAULT_OUT = "full_history_ddmm.json"
TEMP_OUT = "full_history_ddmm.partial.json"
USER_AGENT = "HistoryInYourPocketGenerator/1.0 (contact: your-email@example.com)"

INDIAN_KEYWORDS = [
    " india ", "indian ", "bharat", "mohandas", "gandhi", "nehru",
    "tamil", "hindi", "sikhs", "maharaja", "raj", "ashoka", "tagore",
    "subhas", "netaji", "bhagat singh", "rajiv", "indira", "ambedkar",
    "mumbai", "bombay", "delhi", "kolkata", "madras", "chennai",
    "punjab", "gujarat", "rajasthan", "karnataka", "maharashtra",
]

def parse_args():
    p = argparse.ArgumentParser(description="Generate full_history_ddmm.json from Wikipedia onthisday")
    p.add_argument("--min-year", type=int, default=1800, help="Only include events with year >= MIN_YEAR")
    p.add_argument("--top-n", type=int, default=10, help="Max events to keep per day")
    p.add_argument("--delay", type=float, default=0.6, help="Seconds delay between requests")
    p.add_argument("--out", type=str, default=DEFAULT_OUT, help="Output JSON filename")
    p.add_argument("--temp", type=str, default=TEMP_OUT, help="Temp (partial) filename")
    p.add_argument("--merge-curated", type=str, default=None, help="Path to curated JSON to merge (curated keys: DD-MM)")
    p.add_argument("--resume", action="store_true", help="Resume from temp file if it exists")
    return p.parse_args()

def mm_dd_iter():
    for month in range(1,13):
        for day in range(1,32):
            try:
                datetime(year=2000, month=month, day=day)  # validate day
            except ValueError:
                continue
            yield day, month

def safe_request_json(url, retries=3, timeout=20):
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            else:
                # for 429 or 5xx, wait and retry
                wait = 1 + attempt * 2
                time.sleep(wait)
        except Exception:
            time.sleep(1 + attempt * 2)
    return None

def is_indian_text(s):
    if not s:
        return False
    s2 = s.lower()
    for k in INDIAN_KEYWORDS:
        if k in s2:
            return True
    return False

def extract_item(item, kind, min_year):
    # item typically has 'year', 'text', 'pages'
    year = item.get("year")
    if year is None:
        return None
    try:
        year_int = int(year)
    except Exception:
        return None
    if year_int < min_year:
        return None

    text = item.get("text") or ""
    title = None
    source_url = None
    pages = item.get("pages") or []
    if pages and isinstance(pages, list) and len(pages) > 0:
        first = pages[0]
        title = first.get("normalizedtitle") or first.get("title") or None
        try:
            source_url = first.get("content_urls", {}).get("desktop", {}).get("page")
        except Exception:
            source_url = None

    if not title:
        title = (text[:100] + "...") if len(text) > 100 else text

    return {
        "year": year_int,
        "title": title,
        "description": text,
        "type": kind,
        "source_url": source_url
    }

def prioritize_events(events):
    # Indian-first, then others; sort within groups by year ascending (old -> recent)
    indian = [e for e in events if is_indian_text(e.get("description","") or e.get("title",""))]
    others = [e for e in events if e not in indian]
    indian_sorted = sorted(indian, key=lambda x: x["year"])
    others_sorted = sorted(others, key=lambda x: x["year"])
    return indian_sorted + others_sorted

def load_json_if_exists(path):
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return None

def merge_curated(result_map, curated_map):
    """ curated_map: { 'DD-MM': [ {year,title,description,type,source_url?}, ... ] } """
    for ddmm, curated_list in curated_map.items():
        if not isinstance(curated_list, list):
            continue
        exist = result_map.get(ddmm, [])
        # ensure curated entries come first and avoid exact duplicates (title+year)
        seen = {(e.get("title"), e.get("year")) for e in exist}
        prepended = []
        for c in curated_list:
            key = (c.get("title"), c.get("year"))
            if key not in seen:
                prepended.append(c)
                seen.add(key)
        result_map[ddmm] = prepended + exist
    return result_map

def save_partial(result_map, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result_map, fh, ensure_ascii=False, indent=2)

def save_final(result_map, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result_map, fh, ensure_ascii=False, indent=2)

def main():
    args = parse_args()
    min_year = args.min_year
    top_n = args.top_n
    delay = args.delay
    out_file = args.out
    temp_file = args.temp

    # Resume or fresh
    if args.resume and os.path.exists(temp_file):
        print("Resuming from partial file:", temp_file)
        result = load_json_if_exists(temp_file) or {}
    else:
        result = {}

    curated = None
    if args.merge_curated:
        if os.path.exists(args.merge_curated):
            curated = load_json_if_exists(args.merge_curated)
            print("Loaded curated file:", args.merge_curated, "keys:", len(curated) if isinstance(curated, dict) else "N/A")
        else:
            print("Curated file not found:", args.merge_curated)

    # iterate dates
    dates = list(mm_dd_iter())
    if HAVE_TQDM:
        iterator = tqdm(dates, desc="Dates")
    else:
        iterator = dates

    for day, month in iterator:
        ddmm = f"{day:02d}-{month:02d}"
        if ddmm in result and isinstance(result[ddmm], list) and len(result[ddmm])>0:
            # skip already fetched (resume behavior)
            continue

        items = []
        for kind, kind_label in TYPES:
            url = f"{WIKI_BASE}/{kind}/{month:02d}/{day:02d}"
            data = safe_request_json(url)
            if not data:
                time.sleep(delay)
                continue
            # wikipedia returns key 'events' for that endpoint (but for births/deaths it returns 'births' or 'deaths')
            list_items = data.get(kind) or data.get("events") or []
            for it in list_items:
                extracted = extract_item(it, kind_label, min_year)
                if extracted:
                    items.append(extracted)
            time.sleep(delay)

        # if no items found (rare), try a second pass with no year filter (include older)
        if not items:
            for kind, kind_label in TYPES:
                url = f"{WIKI_BASE}/{kind}/{month:02d}/{day:02d}"
                data = safe_request_json(url)
                if not data:
                    continue
                list_items = data.get(kind) or data.get("events") or []
                for it in list_items:
                    year = it.get("year")
                    try:
                        y = int(year)
                    except:
                        continue
                    title = None
                    pages = it.get("pages") or []
                    if pages and len(pages)>0:
                        title = pages[0].get("normalizedtitle") or pages[0].get("title")
                        source_url = pages[0].get("content_urls", {}).get("desktop", {}).get("page")
                    else:
                        title = (it.get("text") or "")[:120]
                        source_url = None
                    items.append({
                        "year": y,
                        "title": title,
                        "description": it.get("text") or "",
                        "type": kind_label,
                        "source_url": source_url
                    })
                time.sleep(delay)

        merged = prioritize_events(items)
        # keep top N
        result[ddmm] = merged[:top_n]

        # write partial every date
        save_partial(result, temp_file)

    # merge curated (if provided)
    if curated and isinstance(curated, dict):
        result = merge_curated(result, curated)
        # and re-trim top_n after merge
        for k in list(result.keys()):
            if isinstance(result[k], list):
                result[k] = result[k][:top_n]

    # final save
    save_final(result, out_file)
    # cleanup partial
    if os.path.exists(temp_file):
        try:
            os.remove(temp_file)
        except:
            pass

    print("Done. Wrote:", out_file)

if __name__ == "__main__":
    main()
