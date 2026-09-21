# scripts/gen_placeholder_memes.py —— 纯文本 SVG，零依赖，可重跑
import os
MOODS = {"urge": ("催促", "还不打卡？(・`ω´・)"),
         "praise": ("夸奖", "干得漂亮！(๑•̀ㅂ•́)و✧"),
         "disappointed": ("失望", "唉…(´-ι＿-｀)"),
         "angry": ("暴怒", "说好的打卡呢！(╬￣皿￣)=○"),
         "cute": ("卖萌", "求求啦～(｡•ᴗ•｡)♡"),
         "celebrate": ("庆祝", "太强了！(ﾉ≧∀≦)ﾉ")}
BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "assets", "memes")
def main():
    for mood, (zh, kao) in MOODS.items():
        d = os.path.join(BASE, mood); os.makedirs(d, exist_ok=True)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="480">'
               f'<rect width="100%" height="100%" fill="#1e1f24"/>'
               f'<text x="240" y="190" font-size="72" fill="#ffd166" text-anchor="middle" '
               f'font-family="sans-serif">{zh}</text>'
               f'<text x="240" y="300" font-size="40" fill="#fff" text-anchor="middle" '
               f'font-family="sans-serif">{kao}</text></svg>')
        open(os.path.join(d, "01.svg"), "w", encoding="utf-8").write(svg)
    os.makedirs(os.path.join(BASE, "user"), exist_ok=True)
    print("generated:", BASE)
if __name__ == "__main__":
    main()
