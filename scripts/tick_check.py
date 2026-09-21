import argparse, json, os, sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state import load, save, plan_tick, commit_tick, default_state_path, ensure_state


def main():
    ap = argparse.ArgumentParser(description="习惯监督 tick 判定（轮次/幂等/免打扰/上限的唯一事实源）")
    ap.add_argument("--now", help='ISO 时间（含时区偏移），如 "2026-09-21T07:00:00+08:00"；缺省为当前时间')
    ap.add_argument("--commit", action="store_true", help="写回 nudge_state/tick_log 并落库（原子写）")
    ap.add_argument("--state", help="状态文件路径（缺省 $PECK_SKILL_STATE 或 ~/.peck-skill/habits.json）")
    args = ap.parse_args()

    path = ensure_state(args.state or default_state_path())
    state = load(path)
    tz = ZoneInfo(state["user"]["timezone"])
    if args.now:
        now = datetime.fromisoformat(args.now)
        if now.tzinfo is None:
            sys.exit("--now 必须带时区偏移，如 2026-09-21T07:00:00+08:00")
        now = now.astimezone(tz)
    else:
        now = datetime.now(tz)

    actions = plan_tick(state, now)
    if args.commit:
        commit_tick(state, actions, now)
        save(path, state)
    print(json.dumps({"now": now.isoformat(), "actions": actions}, ensure_ascii=False))

if __name__ == "__main__":
    main()
