# tests/test_checkin.py
import os, sys, unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from state import empty_state, apply_checkin, effective_level, is_due

TZ = ZoneInfo("Asia/Shanghai")
def mkstate():
    st = empty_state("老板", "Asia/Shanghai")
    st["habits"].append({
        "id": "h_run", "name": "跑步", "emoji": "🏃",
        "schedule": {"days": [1,2,3,4,5,6,0], "window": ["06:00","22:00"]},
        "level": None, "require_proof": False, "weekly_goal": 3,
        "stats": {"current_streak": 0, "best_streak": 0, "total": 0, "week_count": 0},
        "records": [], "pauses": [], "freeze_left": 2})
    return st

class TestCheckin(unittest.TestCase):
    def test_effective_level_inherits_global(self):
        st = mkstate(); self.assertEqual(effective_level(st, st["habits"][0]), "chill")

    def test_ontime_checkin_grows_streak(self):
        st = mkstate()
        r = apply_checkin(st, "h_run", date(2026,9,18), "5km", True,
                          datetime(2026,9,18,7,0,tzinfo=TZ))
        self.assertTrue(r["ok"]); self.assertEqual(r["streak"], 1)
        self.assertFalse(r["late"])

    def test_late_checkin_keeps_streak_marks_late(self):
        st = mkstate()
        r = apply_checkin(st, "h_run", date(2026,9,18), "", False,
                          datetime(2026,9,18,23,0,tzinfo=TZ))   # 窗口 22:00 结束后
        self.assertTrue(r["ok"]); self.assertTrue(r["late"]); self.assertEqual(r["streak"], 1)

    def test_double_checkin_same_day_rejected(self):
        st = mkstate()
        apply_checkin(st, "h_run", date(2026,9,18), "", False, datetime(2026,9,18,8,0,tzinfo=TZ))
        r = apply_checkin(st, "h_run", date(2026,9,18), "", False, datetime(2026,9,18,9,0,tzinfo=TZ))
        self.assertFalse(r["ok"]); self.assertEqual(r["reason"], "already checked in")

    def test_makeup_yesterday_costs_freeze_only_in_chill(self):
        st = mkstate()
        r = apply_checkin(st, "h_run", date(2026,9,17), "补卡", False,
                          datetime(2026,9,18,9,0,tzinfo=TZ))
        self.assertTrue(r["ok"]); self.assertTrue(r["makeup"])
        self.assertEqual(st["habits"][0]["freeze_left"], 1)
        st["global_level"] = "strict"
        r2 = apply_checkin(st, "h_run", date(2026,9,16), "补卡", False,
                           datetime(2026,9,18,9,0,tzinfo=TZ))
        self.assertFalse(r2["ok"]); self.assertIn("strict", r2["reason"])

    def test_makeup_needs_freeze_ticket(self):
        st = mkstate(); st["habits"][0]["freeze_left"] = 0
        r = apply_checkin(st, "h_run", date(2026,9,17), "", False,
                          datetime(2026,9,18,9,0,tzinfo=TZ))
        self.assertFalse(r["ok"])

    def test_pause_day_not_due(self):
        st = mkstate()
        st["habits"][0]["pauses"].append({"from":"2026-09-18","to":"2026-09-18","reason":"病"})
        self.assertFalse(is_due(st["habits"][0], date(2026,9,18)))

if __name__ == "__main__":
    unittest.main()
