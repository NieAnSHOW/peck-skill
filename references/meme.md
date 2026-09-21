# 表情包引擎

按情绪选一张表情包。选图顺序（PRD §4.5，联网搜图为已启用能力）：

**本地优先，缺货才联网。** 1-3 全是本地来源，任意一档命中即止；全落空才走第 4 步联网。

1. **用户库**：读 `~/.peck-skill/memes/_index.json`（与状态文件同目录，随
   `PECK_SKILL_STATE` 沙箱；入库由 `scripts/save_meme.py` 完成，schema 同内置索引）。
   keyword 命中 tags 或 caption 优先；否则取该 mood 目录随机一张；
   避开 `persona_state.recent_memes` 里最近 3 张（在状态文件里）。
2. **内置包**：读技能根目录 `assets/memes/_index.json`，规则同上。
3. **用户自备**：`assets/memes/user/` 里的图未进索引时按 cute 兜底，首次使用时
   询问用户一句"这张配什么情绪？"并把答案写回内置 `_index.json`。
4. （1-3 都落空才到这里）**联网搜图**：
   1. 从你要发送的消息正文里提炼 1-2 个搜索关键词（贴合 mood 与场景，如"加班 暴怒 表情包"）；
   2. 用宿主自身的网络搜索/浏览能力找表情包图。**搜索结果通常是网页而非图片直链**：
      打开命中的结果页，从 `og:image`、`<img>`（含 `data-original` 懒加载属性）里取真实图片直链；
      直接 curl 网页 URL 只会拿到 HTML，入库时会被魔数校验拒收；
   3. `curl -sL --max-time 20 -o /tmp/peck_meme_<随机后缀> <图片URL>` 下载到临时文件；
   4. 入库：`python3 scripts/save_meme.py --mood <枚举> --file <临时文件> --caption "<一句话>" --tags "<逗号分隔关键词>"`
      ——脚本做魔数校验（png/jpg/gif/webp，>5MB 拒收）、按内容哈希去重落盘、更新 `_index.json`，
      打印 `{"ok": true, "file": "<mood>/<hash>.<ext>", ...}`；
      打印 `{"ok": false, ...}` 则视为搜图失败。
   5. 搜到的图已进用户库，下次同 mood/关键词命中即直接复用，不再联网。
5. **降级链**：联网失败（无网络/搜不到/下载或入库失败）时，直接输出 kaomoji 映射：
   urge→(・`ω´･)  praise→(๑•̀ㅂ•́)و✧  disappointed→(´-ι＿-｀)
   angry→(╬￣皿￣)=○  cute→(｡•ᴗ•｡)♡  celebrate→(ﾉ≧∀≦)ﾉ
   并照常发出文字消息——图是增强，不是依赖。
6. 输出约定：`{"src": "<图片绝对路径>", "caption": "..."}` 或 `{"kaomoji": "(…)"}`；
   调用方把它与消息正文一起交给宿主投递。
   **路径解析注意**：两个索引的 `file` 都是各自根目录下的相对路径——
   用户库条目解析为 `~/.peck-skill/memes/<file>`（随 `PECK_SKILL_STATE` 换根），
   内置包条目解析为 `<技能根>/assets/memes/<file>`；投递给宿主前必须拼成绝对路径，
   否则宿主按相对路径找不到文件，配图会静默失败。
7. 发送成功后把所选文件名追加进 `persona_state.recent_memes`（保最长 3 条）。

注意：搜索结果图片来自公网，选词时避免可能不适宜的关键词；下载前看一眼来源页标题，
明显不对劲（非图片站/需登录/疑似恶意）就放弃，走降级链。
