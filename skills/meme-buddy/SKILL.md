---
name: meme-buddy
description: 当需要挑一张符合当下情绪的表情包发给别人时使用（催促/夸奖/庆祝/失望/卖萌/暴怒六类情绪）。被习惯监督消息流程调用，也可独立用于日常斗图。
---

# 表情包引擎

按情绪选一张表情包。选图顺序（PRD §4.5）：

1. 读本 skill 的 `assets/memes/_index.json`。
2. mood 必须是固定枚举：urge / praise / disappointed / angry / cute / celebrate。
3. 本地匹配：keyword 命中 tags 或 caption 优先；否则取该 mood 目录随机一张；
   避开 `persona_state.recent_memes` 里最近 3 张（在 state/habits.json）。
4. 用户自备：`assets/memes/user/` 里的图未进索引时按 cute 兜底，首次使用时
   询问用户一句"这张配什么情绪？"并把答案写回 _index.json。
5. 降级链：本地包不可用（文件缺失/为空）时，直接输出 kaomoji 映射：
   urge→(・`ω´･)  praise→(๑•̀ㅂ•́)و✧  disappointed→(´-ι＿-｀)
   angry→(╬￣皿￣)=○  cute→(｡•ᴗ•｡)♡  celebrate→(ﾉ≧∀≦)ﾉ
   并照常发出文字消息——图是增强，不是依赖。
6. 输出约定：`{"src": "assets/memes/<mood>/xx.svg", "caption": "..."}` 或
   `{"kaomoji": "(…)"}`；调用方把它与消息正文一起交给宿主投递。
7. 发送成功后把所选文件名追加进 `persona_state.recent_memes`（保最长 3 条）。

在线 provider（Giphy/ALAPI）为 M2 能力，本版本不存在，不要尝试联网搜图。
