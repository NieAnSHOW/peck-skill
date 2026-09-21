# tests/test_save_meme.py — save_meme() 入库/去重/拒收（hermetic：tempfile，零网络零子进程）
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from save_meme import save_meme, sniff_image

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


def mkpng(d, name, data=PNG):
    p = os.path.join(d, name)
    with open(p, "wb") as f:
        f.write(data)
    return p


class TestSaveMeme(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.lib = os.path.join(self._tmp.name, "memes")       # 表情包库
        self.inbox = os.path.join(self._tmp.name, "inbox")     # 模拟 curl 下载落点
        os.makedirs(self.inbox)

    def tearDown(self):
        self._tmp.cleanup()

    def _idx(self):
        with open(os.path.join(self.lib, "_index.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_sniff_magic_bytes(self):
        p = mkpng(self.inbox, "a.png", JPG)  # 扩展名撒谎也不影响判定
        self.assertEqual(sniff_image(p), "jpg")
        p = mkpng(self.inbox, "b.png", b"<html>not an image</html>")
        self.assertIsNone(sniff_image(p))

    def test_save_files_by_hash_and_updates_index(self):
        p = mkpng(self.inbox, "tmp.png")
        r = save_meme(p, "urge", caption="快去打卡", tags=["催促", " "], memes_dir=self.lib)
        self.assertTrue(r["ok"]); self.assertFalse(r["dedup"])
        self.assertTrue(r["file"].startswith("urge/") and r["file"].endswith(".png"))
        # 源文件已被收编（不再留在 inbox）
        self.assertFalse(os.path.exists(p))
        self.assertTrue(os.path.exists(os.path.join(self.lib, r["file"])))
        idx = self._idx()
        self.assertEqual(len(idx), 1)
        self.assertEqual(idx[0]["mood"], "urge")
        self.assertEqual(idx[0]["tags"], ["催促"])  # 空白 tag 被清洗

    def test_same_content_dedups_no_index_dup(self):
        r1 = save_meme(mkpng(self.inbox, "a.png"), "cute", memes_dir=self.lib)
        r2 = save_meme(mkpng(self.inbox, "b.png"), "cute", memes_dir=self.lib)  # 同内容不同文件
        self.assertTrue(r1["ok"] and r2["ok"])
        self.assertFalse(r1["dedup"]); self.assertTrue(r2["dedup"])
        self.assertEqual(r1["file"], r2["file"])
        self.assertEqual(len(self._idx()), 1)

    def test_reject_unknown_mood(self):
        r = save_meme(mkpng(self.inbox, "a.png"), "smug", memes_dir=self.lib)
        self.assertFalse(r["ok"]); self.assertIn("mood", r["reason"])

    def test_reject_non_image(self):
        r = save_meme(mkpng(self.inbox, "a.png", b"plain text"), "urge", memes_dir=self.lib)
        self.assertFalse(r["ok"]); self.assertIn("not a supported image", r["reason"])
        self.assertFalse(os.path.exists(os.path.join(self.lib, "urge")))  # 拒收不落任何文件

    def test_reject_missing_source(self):
        r = save_meme(os.path.join(self.inbox, "nope.png"), "urge", memes_dir=self.lib)
        self.assertFalse(r["ok"]); self.assertIn("not found", r["reason"])

    def test_reject_oversize(self):
        big = PNG + b"\x00" * (5 * 1024 * 1024)
        r = save_meme(mkpng(self.inbox, "big.png", big), "urge", memes_dir=self.lib)
        self.assertFalse(r["ok"]); self.assertIn("too large", r["reason"])


if __name__ == "__main__":
    unittest.main()
