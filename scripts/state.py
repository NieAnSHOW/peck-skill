import json, os, tempfile

REQUIRED_TOP = ["version", "user", "global_level", "habits", "nudge_state",
                "persona_state", "achievements", "tick_log"]
REQUIRED_USER = ["id", "name", "timezone", "quiet_hours"]
REQUIRED_HABIT = ["id", "name", "emoji", "schedule", "level", "require_proof",
                  "weekly_goal", "stats", "records", "pauses", "freeze_left"]
LEVELS = {"strict", "chill", "free"}

def empty_state(name, tz):
    return {"version": 1,
            "user": {"id": "default", "name": name, "timezone": tz,
                     "quiet_hours": ["22:30", "07:00"]},
            "global_level": "chill", "habits": [],
            "nudge_state": {"per_habit_day": {}, "no_response_days": {}},
            "persona_state": {"recent_templates": [], "recent_memes": []},
            "achievements": [], "tick_log": []}

def validate(st):
    errs = []
    for k in REQUIRED_TOP:
        if k not in st: errs.append(f"missing top key: {k}")
    if errs: return errs
    for k in REQUIRED_USER:
        if k not in st["user"]: errs.append(f"user missing {k}")
    if st["global_level"] not in LEVELS: errs.append("global_level invalid")
    for h in st["habits"]:
        for k in REQUIRED_HABIT:
            if k not in h: errs.append(f"habit {h.get('id','?')} missing {k}")
        if h.get("level") is not None and h["level"] not in LEVELS:
            errs.append(f"habit {h.get('id','?')} level invalid")
        win = h.get("schedule", {}).get("window")
        if not (isinstance(win, list) and len(win) == 2):
            errs.append(f"habit {h.get('id','?')} window invalid")
    return errs

def load(path):
    with open(path, encoding="utf-8") as f: return json.load(f)

def save(path, state):
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.remove(tmp)
