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

# ---------------------------------------------------------------------------
# Task 3: tick 判定引擎（轮次 / 幂等 / 免打扰 / 断链 / 周报 / 熔断 / 上限）
# ---------------------------------------------------------------------------

STAGES_STRICT = ["remind", "first", "warn", "final"]   # 低→高优先级（PRD §4.2「提醒 1 + 催促 3」）
STAGES_CHILL = ["remind", "lastcall"]                  # 低→高优先级（chill 两轮）
DAILY_NUDGE_CAP = 4            # PRD §4.2-1：单习惯单日提醒/催促类 ≤ 4 条
TICK_GRID_MIN = 30             # PRD §3.1/§3.4：cron 每 30 分钟一个 tick
DAY_CLOSE_TIME = time(23, 30)  # strict 断链日结时刻
HISTORY_DAYS = 90              # records 只保留最近 90 天（由 tick 清理）
TICK_LOG_KEEP = 50             # tick_log 只保留最近 50 条
GLOBAL_KEY_ID = "global"       # 全局动作（周报）在 per_habit_day 里的伪习惯 id

def _at(day, hhmm, tz):
    return datetime.combine(day, hhmm, tzinfo=tz)

def _quiet_range(state):
    q = state["user"].get("quiet_hours") or ["22:30", "07:00"]
    return _parse_hhmm(q[0]), _parse_hhmm(q[1])

def _in_quiet(t, state):
    """免打扰区间判断：晚间段 [22:30, 24:00) 与清晨段 [00:00, 07:00) 都算（PRD §4.2-3）。"""
    qs, qe = _quiet_range(state)
    if qs <= qe:                       # 非跨零点配置（如 13:00–15:00）：整段都算
        return qs <= t < qe
    return t >= qs or t < qe           # 跨零点：晚间段或清晨段

def _last_sendable(day, state, tz):
    """晚间免打扰开始前最后一个可发 tick（30 分钟网格），如 22:30 → 22:00。"""
    qs, _ = _quiet_range(state)
    last = (qs.hour * 60 + qs.minute - 1) // TICK_GRID_MIN * TICK_GRID_MIN
    return datetime.combine(day, time(last // 60, last % 60), tzinfo=tz)

def _quiet_clamp(nominal, state, tz):
    """strict 档 stage 名义时刻撞免打扰时的落点（PRD §4.2-3）：
    清晨段 → 免打扰结束（窗口开启提醒顺延至 ≥max(窗口起, quiet_end)）；晚间段 → 免打扰前最后一个 tick。"""
    qs, qe = _quiet_range(state)
    if qs <= qe or nominal.time() < qe:
        return datetime.combine(nominal.date(), qe, tzinfo=tz)
    return _last_sendable(nominal.date(), state, tz)

def _rounds(habit, day, level, tz):
    """该档位当日的轮次表 [(stage, 名义时刻, mood)]。"""
    w_start, w_end = _window(habit)
    start, end = _at(day, w_start, tz), _at(day, w_end, tz)
    if end <= start:
        end += timedelta(days=1)          # 跨零点窗口（如 21:00–01:00）
    if level == "strict":
        # warn 名义 = 窗口起 +3h，但必须留在窗口内且早于 final（窗口末 -30min），
        # 否则窄窗口（窗口长 < 3.5h）下 warn 会被 final 吞掉，催促进程从 4 级退化成 3 级。
        warn_at = min(start + timedelta(hours=3), end - timedelta(hours=1))
        return [("remind", start, "urge"),
                ("first", start + timedelta(hours=1), "urge"),
                ("warn", warn_at, "disappointed"),
                ("final", end - timedelta(minutes=30), "angry")]
    return [("remind", start + (end - start) / 2, "cute"),     # 窗口中点
            ("lastcall", end - timedelta(hours=1), "cute")]    # 窗口结束前 1h

def _due_rounds(habit, now, level, sent, tz, state):
    """本轮到点且未发过的 stage（低→高优先级）。

    已发过更高优先级的 stage 之后，不再补发更低优先级：窄窗口（窗口长 < 3.5h）下
    warn 的名义时刻（窗口起 +3h）会落在 final（窗口末 -30min）之后，若不过滤就会出现
    "最后通牒"发完又来一句"我再提醒一次"的倒序催促。
    """
    rounds = _rounds(habit, now.date(), level, tz)
    max_sent = max((i for i, (s, _, _) in enumerate(rounds) if s in sent), default=-1)
    ready = []
    for idx, (stage, nominal, mood) in enumerate(rounds):
        if stage in sent or idx <= max_sent:
            continue
        if _in_quiet(nominal.time(), state):
            # PRD §4.2-3：名义时刻落入免打扰 → strict 顺延/提前到免打扰外的 tick；
            # 宽松/自由档作废（不提前、不补发）。
            if level != "strict":
                continue
            nominal = _quiet_clamp(nominal, state, tz)
        if nominal > now:
            continue
        ready.append((stage, mood))
    return ready

def _slots(state, habit, streak, deadline, week_rate, reason=None):
    """填槽字段与模板变量一一对应：{{name}} {{habit}} {{streak}} {{deadline}} {{week_rate}}。"""
    s = {"name": state["user"].get("name", ""),
         "habit": habit.get("name", "") if habit else "",
         "streak": streak, "deadline": deadline, "week_rate": week_rate}
    if reason:
        s["reason"] = reason
    return s

def _week_rate(habit):
    return f"{habit.get('stats', {}).get('week_count', 0)}/{habit.get('weekly_goal', 0)} 次"

def _report_rate(state):
    return "、".join(f"{h.get('name', '')} {h.get('stats', {}).get('week_count', 0)}/{h.get('weekly_goal', 0)}"
                     for h in state["habits"]) or "无习惯"

def _has_today(habit, today):
    return today.isoformat() in _records(habit)

def plan_tick(state, now):
    """纯函数（不改 state）：算出本轮该发的 actions，交给 commit_tick 记账。"""
    tz = _tz(state)
    now = now.astimezone(tz)
    today = now.date()
    per = state["nudge_state"].get("per_habit_day", {})
    no_resp = state["nudge_state"].get("no_response_days", {})
    quiet = _in_quiet(now.time(), state)
    actions = []

    for h in state["habits"]:
        lvl = effective_level(state, h)
        if lvl == "free":
            continue                       # free 档（零提醒/不判定）属 M2，不实现
        key = f"{h['id']}@{today.isoformat()}"
        entry = per.get(key) or {}
        sent, count = set(entry.get("stages", [])), entry.get("count", 0)
        due, checked = is_due(h, today), _has_today(h, today)
        deadline = h["schedule"]["window"][1]

        # 1. 熔断：连续 3 天零打卡回应 → 降一档（strict → chill），commit 落库
        if lvl == "strict" and no_resp.get(h["id"], 0) >= 3 \
                and "level_down" not in sent and not quiet:
            actions.append({"type": "level_down", "habit_id": h["id"], "stage": "none", "mood": "cute",
                            "slots": _slots(state, h, h.get("stats", {}).get("current_streak", 0), deadline,
                                            _week_rate(h), reason="连续 3 天无打卡回应，降为宽松档")})

        # 2/3. 免打扰内不发提醒/催促（PRD §4.2-3 优先级最高）；到点轮次合并为最高优先级一条
        if due and not checked and not quiet and count < DAILY_NUDGE_CAP:
            ready = _due_rounds(h, now, lvl, sent, tz, state)
            if ready:
                stage, mood = ready[-1]
                actions.append({"type": "nudge", "habit_id": h["id"], "stage": stage, "mood": mood,
                                "slots": _slots(state, h, h.get("stats", {}).get("current_streak", 0),
                                                deadline, _week_rate(h))})

        # 4. 断链日结（仅 strict）：静默记账——免打扰豁免，且无 mood（不发消息、不配图）；
        #    commit 时把 streak 归零。用户可见的处刑在周日公审周报（M2 起为次日日报）。
        if lvl == "strict" and due and not checked and now.time() >= DAY_CLOSE_TIME \
                and "daily_close" not in sent:
            actions.append({"type": "daily_close", "habit_id": h["id"], "stage": "none",
                            "slots": _slots(state, h, h.get("stats", {}).get("current_streak", 0),
                                            deadline, _week_rate(h))})

    # 5. 周报（全局一条，习惯无关；报告类不受 ≤4 条限制）
    gkey = f"{GLOBAL_KEY_ID}@{today.isoformat()}"
    gsent = set((per.get(gkey) or {}).get("stages", []))
    glvl = state["global_level"]
    wd, hm = today.weekday(), now.time()
    if not quiet and "weekly_report" not in gsent and glvl in ("chill", "strict"):
        hit = (glvl == "chill" and wd == 5 and hm >= time(10, 0)) or \
              (glvl == "strict" and wd == 6 and hm >= time(21, 0))
        if hit:
            best = max([h.get("stats", {}).get("current_streak", 0) for h in state["habits"]] or [0])
            actions.append({"type": "weekly_report", "habit_id": None, "stage": "none",
                            "mood": "celebrate" if glvl == "chill" else "angry",
                            "slots": _slots(state, None, best, "", _report_rate(state))})
    return actions

def commit_tick(state, actions, now):
    """把已发出的动作写回 nudge_state / tick_log，并维护 records、熔断计数、每月补卡券。"""
    tz = _tz(state)
    now = now.astimezone(tz)
    today = now.date()
    per = state["nudge_state"].setdefault("per_habit_day", {})
    no_resp = state["nudge_state"].setdefault("no_response_days", {})
    # no_response_days 每日只累加一次（以 tick_log 里当日是否已有 tick 判定）
    first_tick_today = not any(str(e.get("ts", ""))[:10] == today.isoformat()
                               for e in state.get("tick_log", []))
    reset_monthly_freeze(state, today)

    log = []
    for a in actions:
        h = find_habit(state, a.get("habit_id")) if a.get("habit_id") else None
        key = f"{a['habit_id']}@{today.isoformat()}" if a.get("habit_id") \
            else f"{GLOBAL_KEY_ID}@{today.isoformat()}"
        entry = per.setdefault(key, {"count": 0, "stages": []})
        if a["type"] == "nudge":
            order = STAGES_STRICT if (h is not None and effective_level(state, h) == "strict") \
                else STAGES_CHILL
            idx = order.index(a["stage"]) if a["stage"] in order else 0
            for s in order[:idx + 1]:       # 同轮被合并掉的 stage 一并记位：不补发
                if s not in entry["stages"]:
                    entry["stages"].append(s)
            entry["count"] += 1
            log.append(f"nudge {a['habit_id']} stage={a['stage']}")
        else:
            if a["type"] not in entry["stages"]:
                entry["stages"].append(a["type"])       # 幂等位用的是动作类型
            extra = f" reason={a['slots'].get('reason')}" if a["type"] == "level_down" else ""
            log.append(f"{a['type']} {a.get('habit_id') or GLOBAL_KEY_ID}{extra}")
            if a["type"] == "level_down" and h is not None:
                h["level"] = "chill"        # 降档落库（PRD §4.2-2）
                log.append(f"level {a['habit_id']} -> chill")
            elif a["type"] == "daily_close" and h is not None:
                h["stats"]["current_streak"] = 0   # 断链归零（PRD §4.2：24:00 未打卡即断链）

    # 熔断计数：当日有 record 归 0，否则（当日首个 tick）累加
    for h in state["habits"]:
        if not is_due(h, today):
            continue
        if _has_today(h, today):
            no_resp[h["id"]] = 0
        elif first_tick_today:
            no_resp[h["id"]] = no_resp.get(h["id"], 0) + 1

    cutoff = (today - timedelta(days=HISTORY_DAYS)).isoformat()
    for h in state["habits"]:
        h["records"] = [r for r in h.get("records", []) if str(r.get("date", "")) >= cutoff]

    state.setdefault("tick_log", []).append({"ts": now.isoformat(), "actions": log})
    del state["tick_log"][:-TICK_LOG_KEEP]


# ---- 状态文件定位（单技能分发版：状态不住在技能目录里） ----

def default_state_path():
    """PECK_FOOD_STATE 环境变量优先；缺省 ~/.peck-food/habits.json。"""
    env = os.environ.get("PECK_FOOD_STATE")
    if env:
        return env
    return os.path.join(os.path.expanduser("~"), ".peck-food", "habits.json")


def ensure_state(path=None):
    """路径不存在时初始化合法空状态（首次运行友好）。"""
    p = path or default_state_path()
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        save(p, empty_state("老板", "Asia/Shanghai"))
    return p
