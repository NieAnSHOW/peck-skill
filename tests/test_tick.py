# tests/test_tick.py
import os, sys, unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from state import empty_state, plan_tick, commit_tick

TZ = ZoneInfo("Asia/Shanghai")
def mkstate(level="strict"):
    st = empty_state("老板", "Asia/Shanghai"); st["global_level"] = level
    st["habits"].append({
        "id": "h_run", "name": "跑步", "emoji": "🏃",
        "schedule": {"days":[1,2,3,4,5,6,0],"window":["06:00","22:00"]},
        "level": None, "require_proof": False, "weekly_goal": 3,
        "stats": {"current_streak":4,"best_streak":12,"total":30,"week_count":2},
        "records": [], "pauses": [], "freeze_left": 2})
    return st

def t(h, m): return datetime(2026,9,21,h,m,tzinfo=TZ)  # 2026-09-21 是周一

class TestTick(unittest.TestCase):
    def test_strict_window_open_remind(self):
        acts = plan_tick(mkstate("strict"), t(6,0))
        self.assertIn("remind", [a["stage"] for a in acts if a["type"]=="nudge"])

    def test_strict_first_warn_final_stages(self):
        self.assertIn("first", [a["stage"] for a in plan_tick(mkstate("strict"), t(7,0))])
        self.assertIn("warn", [a["stage"] for a in plan_tick(mkstate("strict"), t(9,0))])
        self.assertIn("final", [a["stage"] for a in plan_tick(mkstate("strict"), t(21,30))])

    def test_idempotent_same_stage_once(self):
        st = mkstate("strict")
        acts1 = plan_tick(st, t(7,0)); commit_tick(st, acts1, t(7,0))
        acts2 = plan_tick(st, t(7,30))
        self.assertNotIn("first", [a["stage"] for a in acts2 if a["type"]=="nudge"])

    def test_daily_cap_four(self):
        st = mkstate("strict")
        for hm in [(6,0),(7,0),(9,0),(21,30)]:   # remind+first+warn+final 恰好用满 4 条
            commit_tick(st, plan_tick(st, t(*hm)), t(*hm))
        extra = plan_tick(st, t(21,59))
        self.assertEqual([a for a in extra if a["type"]=="nudge"], [])

    def test_quiet_hours_block_and_strict_pulls_final_earlier(self):
        st = mkstate("strict")
        st["habits"][0]["schedule"]["window"] = ["21:00", "23:00"]  # final 名义时刻 22:30 撞免打扰
        self.assertIn("final", [a["stage"] for a in plan_tick(st, t(22,0))])  # 积压 stage 合并后提前补发
        self.assertEqual([a for a in plan_tick(mkstate("strict"), t(23,0)) if a["type"]=="nudge"], [])

    def test_chill_midday_and_lastcall(self):
        st = mkstate("chill")  # 窗口 06-22：中点 14:00，结束前 1h = 21:00
        self.assertEqual([a["stage"] for a in plan_tick(st, t(14,0)) if a["type"]=="nudge"], ["remind"])
        self.assertEqual([a for a in plan_tick(st, t(10,0)) if a["type"]=="nudge"], [])
        self.assertIn("lastcall", [a["stage"] for a in plan_tick(st, t(21,0)) if a["type"]=="nudge"])

    def test_daily_close_breaks_streak_strict(self):
        st = mkstate("strict")
        acts = plan_tick(st, t(23,50))
        closes = [a for a in acts if a["type"]=="daily_close"]
        self.assertTrue(closes)  # 当日 due 未打卡 → 断链日结动作

    def test_weekly_report_saturday_ten(self):
        # 2026-09-26 是周六
        acts = plan_tick(mkstate("chill"), datetime(2026,9,26,10,0,tzinfo=TZ))
        self.assertIn("weekly_report", [a["type"] for a in acts])

    def test_level_down_after_three_silent_days(self):
        st = mkstate("strict")
        st["nudge_state"]["no_response_days"] = {"h_run": 3}
        acts = plan_tick(st, t(8,0))
        self.assertIn("level_down", [a["type"] for a in acts])

if __name__ == "__main__":
    unittest.main()
