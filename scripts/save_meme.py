"""网络表情包入库（PRD §6 增强，references/meme.md 第 3 步的落盘端）。

核心函数 save_meme() 可导入直调（tests 直用，不靠 subprocess）；
main() 只做 argparse → 调用。仅标准库。
"""
import argparse, hashlib, json, os, shutil, sys, tempfile

MOODS = ["urge", "praise", "disappointed", "angry", "cute", "celebrate"]
MAX_BYTES = 5 * 1024 * 1024  # 超过 5MB 拒收：IM 发大图无意义

# ---- 魔数嗅探（扩展名不可信） ----

_MAGIC = [
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
]


def sniff_image(path):
    """返回 png/jpg/gif/webp 之一；不认识返回 None。"""
    with open(path, "rb") as f:
        head = f.read(12)
    for magic, ext in _MAGIC:
        if head.startswith(magic):
            return ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


# ---- 落盘目录（跟状态文件同目录，随 PECK_SKILL_STATE 沙箱隔离） ----

def default_memes_dir():
    from state import default_state_path
    return os.path.join(os.path.dirname(os.path.abspath(default_state_path())), "memes")


def _index_path(memes_dir):
    return os.path.join(memes_dir, "_index.json")


def _write_json_atomic(path, obj):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# ---- 入库核心 ----

def save_meme(src_path, mood, caption="", tags=None, memes_dir=None):
    """把一张已下载的图收编进用户表情包库。

    返回 {"ok": True, "file": "<mood>/<hash8>.<ext>", "dedup": bool}，
    非法输入返回 {"ok": False, "reason": ...}（与 apply_checkin 同风格，不抛异常）。
    """
    if mood not in MOODS:
        return {"ok": False, "reason": "unknown mood: %s" % mood}
    if not os.path.isfile(src_path):
        return {"ok": False, "reason": "source file not found"}
    if os.path.getsize(src_path) > MAX_BYTES:
        return {"ok": False, "reason": "image too large (>5MB)"}
    ext = sniff_image(src_path)
    if ext is None:
        return {"ok": False, "reason": "not a supported image (png/jpg/gif/webp)"}

    memes_dir = memes_dir or default_memes_dir()
    with open(src_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    rel = os.path.join(mood, "%s.%s" % (digest[:8], ext))
    dest = os.path.join(memes_dir, rel)
    dedup = os.path.exists(dest)
    if not dedup:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(src_path, dest)  # 临时文件可能跨盘，move 兜底 copy+delete

    idx_path = _index_path(memes_dir)
    index = []
    if os.path.exists(idx_path):
        with open(idx_path, encoding="utf-8") as f:
            index = json.load(f)
    if any(e.get("file") == rel for e in index):
        return {"ok": True, "file": rel, "dedup": True}
    index.append({"file": rel, "mood": mood, "caption": caption,
                  "tags": [t.strip() for t in (tags or []) if t.strip()]})
    _write_json_atomic(idx_path, index)
    return {"ok": True, "file": rel, "dedup": dedup}


def main():
    ap = argparse.ArgumentParser(description="网络表情包入库：魔数校验 → 去重落盘 → 更新 _index.json")
    ap.add_argument("--mood", required=True, help="固定枚举之一：%s" % "/".join(MOODS))
    ap.add_argument("--file", required=True, help="已下载到本地的临时图片路径（收编后会被移动走）")
    ap.add_argument("--caption", default="", help="图上的话或用途说明")
    ap.add_argument("--tags", default="", help="逗号分隔关键词，如 催促,加班")
    ap.add_argument("--dir", help="表情包库目录（缺省随状态目录 ~/.peck-skill/memes/）")
    args = ap.parse_args()

    r = save_meme(args.file, args.mood, args.caption,
                  [t for t in args.tags.split(",") if t.strip()], args.dir)
    print(json.dumps(r, ensure_ascii=False))
    if not r["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
