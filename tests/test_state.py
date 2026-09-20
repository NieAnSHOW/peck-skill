import json, os, tempfile, unittest
import sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from state import load, save, validate, empty_state

class TestStateCore(unittest.TestCase):
    def test_empty_state_valid(self):
        self.assertEqual(validate(empty_state("老板", "Asia/Shanghai")), [])

    def test_validate_catches_missing_top_keys(self):
        st = empty_state("老板", "Asia/Shanghai"); del st["nudge_state"]
        errs = validate(st)
        self.assertTrue(any("nudge_state" in e for e in errs))

    def test_validate_catches_bad_level(self):
        st = empty_state("老板", "Asia/Shanghai")
        st["global_level"] = "tyrant"
        errs = validate(st)
        self.assertTrue(any("global_level" in e for e in errs))

    def test_validate_catches_habit_fields(self):
        st = empty_state("老板", "Asia/Shanghai")
        st["habits"].append({"id": "h_x"})  # 缺字段
        self.assertTrue(validate(st))

    def test_save_is_atomic_and_readable(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.json")
            save(p, empty_state("老板", "Asia/Shanghai"))
            self.assertEqual(load(p)["user"]["name"], "老板")
            self.assertFalse(os.path.exists(p + ".tmp"))  # 临时文件已清理

if __name__ == "__main__":
    unittest.main()
