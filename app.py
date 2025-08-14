from flask import Flask, render_template, request, jsonify, send_from_directory, abort, url_for
from datetime import datetime
from pathlib import Path
from flask import send_from_directory
from generate_full_history import generate_full_history
import json
import random
import os

app = Flask(__name__)
@app.route('/robots.txt')
def robots_txt():
    return send_from_directory(app.static_folder, 'robots.txt')

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "events.json"

# Load events
if not DATA_PATH.exists():
    raise RuntimeError(f"Missing data file: {DATA_PATH}")

with open(DATA_PATH, "r", encoding="utf-8") as f:
    EVENTS = json.load(f)

# Normalize events and create helper fields
YEARS = set()
CATEGORIES = set()
for ev in EVENTS:
    # standard fields: date (YYYY-MM-DD) or year-only
    date = ev.get("date", "") or ""
    year = ev.get("year")
    if date and len(date) >= 10:
        ev["yyyy"] = int(date[:4])
        ev["mmdd"] = date[5:10]     # "MM-DD"
    elif year:
        ev["yyyy"] = int(year)
        ev["mmdd"] = "__NA__"
    else:
        ev["yyyy"] = int(ev.get("yyyy", 0))
        ev["mmdd"] = ev.get("mmdd", "__NA__")

    ev["category"] = (ev.get("category") or "General").title()
    ev["region"] = ev.get("region") or ""
    ev["tags"] = ev.get("tags") or []
    # search blob for simple search
    ev["search_blob"] = " ".join([
        ev.get("title",""),
        ev.get("description",""),
        ev.get("category",""),
        ev.get("region",""),
        " ".join(ev.get("tags", []))
    ]).lower()

    YEARS.add(ev["yyyy"])
    CATEGORIES.add(ev["category"])

YEARS = sorted([y for y in YEARS if y > 0])
CATEGORIES = sorted(CATEGORIES)


# Utilities
def events_by_mmdd(mmdd):
    return [e for e in EVENTS if e.get("mmdd") == mmdd]

def filter_events(q=None, category=None, start_year=None, end_year=None, mmdd=None):
    results = EVENTS
    if mmdd:
        results = [e for e in results if e.get("mmdd") == mmdd]
    if q:
        ql = q.lower()
        results = [e for e in results if ql in e.get("search_blob","")]
    if category and category.lower() != "all":
        results = [e for e in results if e.get("category","").lower() == category.lower()]
    if start_year:
        try:
            sy = int(start_year)
            results = [e for e in results if e.get("yyyy", 0) >= sy]
        except:
            pass
    if end_year:
        try:
            ey = int(end_year)
            results = [e for e in results if e.get("yyyy", 0) <= ey]
        except:
            pass
    # sort by year ascending then by date if available
    results = sorted(results, key=lambda x: (x.get("yyyy", 0), x.get("date","")))
    return results

@app.route("/full-history")
def genrate_full_history():
    history_data = generate_full_history()
    return render_template("full_history.html", history=history_data)

# Routes
@app.route("/")
def index():
    today = datetime.utcnow().date()
    today_mmdd = today.strftime("%m-%d")
    todays = events_by_mmdd(today_mmdd)
    # show a few example categories and the earliest/latest year for UI hints
    year_min = min(YEARS) if YEARS else None
    year_max = max(YEARS) if YEARS else None
    return render_template("index.html",
                           categories=CATEGORIES,
                           todays_events=todays,
                           today_str=today.strftime("%B %d"),
                           year_min=year_min,
                           year_max=year_max)


@app.route("/results")
def results():
    # Accept either 'date' (YYYY-MM-DD) or 'mmdd' (MM-DD) or search query
    date_param = request.args.get("date")
    mmdd = request.args.get("mmdd")
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "All")
    start_year = request.args.get("start_year")
    end_year = request.args.get("end_year")

    if date_param:
        try:
            dt = datetime.strptime(date_param, "%Y-%m-%d")
            mmdd = dt.strftime("%m-%d")
        except:
            mmdd = None

    events = filter_events(q=q or None, category=category or None,
                           start_year=start_year or None, end_year=end_year or None,
                           mmdd=mmdd or None)

    return render_template("results.html",
                           events=events,
                           q=q,
                           category=category,
                           categories=CATEGORIES,
                           start_year=start_year,
                           end_year=end_year,
                           selected_mmdd=mmdd)


@app.route("/timeline")
def timeline():
    # Show events for a year or a range
    year = request.args.get("year")
    if year:
        try:
            y = int(year)
            year_events = [e for e in EVENTS if e.get("yyyy") == y]
            year_events = sorted(year_events, key=lambda x: x.get("date",""))
        except:
            year_events = []
    else:
        year_events = []
    return render_template("timeline.html",
                           year=year,
                           year_events=year_events,
                           years=YEARS)


@app.route("/quiz")
def quiz_page():
    # quiz page UI. Frontend will call /api/quiz for questions.
    mmdd = request.args.get("mmdd")
    return render_template("quiz.html", mmdd=mmdd)


@app.route("/bookmarks")
def bookmarks_page():
    return render_template("bookmarks.html")


@app.route("/notes")
def notes_page():
    return render_template("notes.html")


# API endpoints
@app.route("/api/events")
def api_events():
    mmdd = request.args.get("mmdd")
    q = request.args.get("q")
    category = request.args.get("category")
    start_year = request.args.get("start_year")
    end_year = request.args.get("end_year")
    limit = min(int(request.args.get("limit", 200)), 200)
    events = filter_events(q=q, category=category,
                           start_year=start_year, end_year=end_year, mmdd=mmdd)
    # return minimal fields
    out = []
    for e in events[:limit]:
        out.append({
            "title": e.get("title"),
            "description": e.get("description"),
            "date": e.get("date"),
            "year": e.get("yyyy"),
            "category": e.get("category"),
            "region": e.get("region"),
            "tags": e.get("tags")
        })
    return jsonify({"count": len(out), "events": out})


@app.route("/api/quiz")
def api_quiz():
    """
    Generate a simple MCQ quiz.
    Modes:
      - mmdd=MM-DD  -> quiz about events on that date (year questions)
      - count=N     -> number of questions (default 5)
    Each question asks: "In which year did <title> happen?" with 4 options.
    """
    mmdd = request.args.get("mmdd")
    try:
        count = max(1, min(int(request.args.get("count", 5)), 20))
    except:
        count = 5

    pool = EVENTS
    if mmdd:
        pool = [e for e in EVENTS if e.get("mmdd") == mmdd]
    # only those with valid year
    pool = [e for e in pool if e.get("yyyy") and e.get("yyyy") > 0]
    if not pool:
        # fallback to random events from whole dataset
        pool = [e for e in EVENTS if e.get("yyyy") and e.get("yyyy") > 0]

    chosen = random.sample(pool, min(count, len(pool)))
    questions = []
    all_years = sorted(list({e["yyyy"] for e in EVENTS if e.get("yyyy") and e.get("yyyy") > 0}))
    for ev in chosen:
        correct = ev["yyyy"]
        # prepare 3 wrong years
        wrong_choices = set()
        attempts = 0
        while len(wrong_choices) < 3 and attempts < 50:
            cand = random.choice(all_years)
            if cand != correct:
                wrong_choices.add(cand)
            attempts += 1
        options = list(wrong_choices) + [correct]
        random.shuffle(options)
        questions.append({
            "id": f"q{len(questions)+1}",
            "question": f"In which year did this happen? — {ev.get('title')}",
            "description": ev.get("description"),
            "correct": correct,
            "options": options
        })
    return jsonify({"count": len(questions), "questions": questions})


# robots.txt
@app.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt')


# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

