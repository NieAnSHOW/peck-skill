import json, os, tempfile
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

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

# ---------------------------------------------------------------------------
# Task 2: 打卡业务逻辑（streak 重建 / 迟到 / 补卡券 / 请假 / 周计数）
# ---------------------------------------------------------------------------

def _tz(state):
    return ZoneInfo(state["user"]["timezone"])

def _parse_hhmm(s):
    h, m = str(s).split(":")
    return time(int(h) % 24, int(m))

def _window(habit):
    w = habit["schedule"]["window"]
    return _parse_hhmm(w[0]), _parse_hhmm(w[1])

def effective_level(state, habit):
    """有效档位 = habit["level"] or state["global_level"]（PRD §4.2）。"""
    return habit.get("level") or state["global_level"]

def find_habit(state, name):
    """按 id 精确匹配 → 名称精确匹配 → 名称模糊匹配；找不到返回 None。"""
    if not name:
        return None
    for h in state["habits"]:
        if h.get("id") == name:
            return h
    for h in state["habits"]:
        if h.get("name") == name:
            return h
    for h in state["habits"]:
        if name in h.get("name", "") or h.get("name", "") in name:
            return h
    return None

def _in_pause(habit, day):
    for p in habit.get("pauses", []):
        try:
            f, t = date.fromisoformat(p["from"]), date.fromisoformat(p["to"])
        except (KeyError, TypeError, ValueError):
            continue
        if f <= day <= t:
            return True
    return False

def is_due(habit, day):
    """schedule.days 含该周几（周一=1 … 周六=6，周日=0）且 day 不在任何 pause 闭区间。"""
    if ((day.weekday() + 1) % 7) not in habit.get("schedule", {}).get("days", []):
        return False
    return not _in_pause(habit, day)

def _records(habit):
    return {r["date"]: r for r in habit.get("records", [])}

def recompute_streak(habit, upto):
    """从 upto 往回逐日走：due 且有 record → +1 继续；due 无 record → 停；非 due 日跳过。"""
    rec = _records(habit)
    n, d = 0, upto
    for _ in range(3660):  # 安全上限：非 due 习惯不会无限回溯
        if is_due(habit, d):
            if d.isoformat() not in rec:
                break
            n += 1
        d -= timedelta(days=1)
    return n

def _week_count(habit, day):
    """本周（周一为界）已完成次数——按 day 所在 ISO 周统计 records。"""
    y, w, _ = day.isocalendar()
    return sum(1 for r in habit.get("records", [])
               if date.fromisoformat(r["date"]).isocalendar()[:2] == (y, w))

def _refresh_stats(habit, day):
    st = habit.setdefault("stats", {})
    st["current_streak"] = recompute_streak(habit, day)
    st["best_streak"] = max(st.get("best_streak", 0), st["current_streak"])
    st["total"] = st.get("total", 0) + 1
    st["week_count"] = _week_count(habit, day)

def _reject(reason, streak=0):
    return {"ok": False, "reason": reason, "streak": streak, "late": False, "makeup": False}

def apply_checkin(state, habit_id, day, note, proof, now):
    """记账并直接改 state（调用方负责 save）。返回 {"ok","reason","streak","late","makeup"}。"""
    now = now.astimezone(_tz(state))
    today = now.date()
    habit = find_habit(state, habit_id)
    if habit is None:
        return _reject("habit not found")
    cur = habit.get("stats", {}).get("current_streak", 0)
    if day > today:
        return _reject("out of range", cur)
    if day.isoformat() in _records(habit):
        return _reject("already checked in", cur)

    _, w_end = _window(habit)
    makeup = False
    if day == today:
        late = now.time() > w_end          # 窗口结束后、当日 24:00 前 = 迟到
        entry = {"date": day.isoformat(), "proof": bool(proof), "note": note, "late": late}
    else:
        lvl = effective_level(state, habit)
        if lvl != "chill":                 # 严厉/自由档无补卡（PRD §4.1）
            return _reject(f"makeup not allowed for level={lvl}", cur)
        if day != today - timedelta(days=1):
            return _reject("out of range", cur)
        if habit.get("freeze_left", 0) <= 0:
            return _reject("no freeze ticket left", cur)
        habit["freeze_left"] -= 1
        makeup, late = True, False
        entry = {"date": day.isoformat(), "proof": False, "note": note or "补卡", "late": False}

    habit["records"].append(entry)
    _refresh_stats(habit, day)
    return {"ok": True, "reason": None, "streak": habit["stats"]["current_streak"],
            "late": late, "makeup": makeup}

def reset_monthly_freeze(state, today):
    """每月 1 号把每个 habit 的 freeze_left 回 2（当日幂等，tick 每次调用）。"""
    if today.day != 1:
        return
    for h in state["habits"]:
        h["freeze_left"] = 2
