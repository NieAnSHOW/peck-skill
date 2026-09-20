# peck-food 🐦

一句话：一组遵循 Agent Skills 开放标准的 skills，寄生在你已有的常驻 Agent 宿主（Hermes / OpenClaw / WorkBuddy …）上，通过宿主原生的 IM 通道，对你的习惯打卡做**有趣、可调档**的监督——从毒舌连环催（strict）到只记账不吭声，配合本地表情包完成每日互动。

不做 App、不做网关、不建服务：`skills/` 定义行为协议，`state/habits.json` 是唯一状态，`scripts/` 是纯标准库的判定引擎。

## 能力假设 H1–H4

| 假设 | 内容 | 不满足时 |
|---|---|---|
| H1 | 宿主支持 Agent Skills（SKILL.md + references） | 无法接入 |
| H2 | 宿主定时任务能按计划以「prompt + skills」唤醒 agent（30min 粒度最佳） | 降级为纯脚本 tick（零 LLM）：只发固定文案，无配图 |
| H3 | 宿主能向用户 IM 发文本与图片 | 发图不通 → meme-buddy 自动降级为 kaomoji 文字表情，文字行为完整 |
| H4 | 宿主有文件系统、能绑定工作目录 | 无法接入（状态与脚本都在仓库里） |

宿主只需三种已有动词：**发文本**、**发图**、**按计划唤醒**。任何满足 H1–H4 的 Agent 产品都能用；不满足者（如云端无文件系统的 Coze/Dify）不在 v1 范围。

## 快速开始（3 步）

1. **放仓库**：把本仓库放到宿主能访问的路径，例如 `/srv/peck-food`。
   ```bash
   git clone <你的仓库地址> /srv/peck-food && cd /srv/peck-food
   python3 scripts/validate_state.py          # → OK
   ```
2. **装 skills**：把三个 skill 目录拷进宿主的 skills 目录（Hermes 默认 `~/.hermes/skills/`）。
   ```bash
   cp -r skills/habit-checkin skills/habit-enforcer skills/meme-buddy ~/.hermes/skills/
   ```
3. **建 cron**：每 30 分钟跑一次监督 tick，详见 [docs/host-hermes.md](docs/host-hermes.md)。
   ```bash
   /cron add "every 30m" "执行习惯监督 tick：cd 到 peck-food 仓库根，运行 python3 scripts/tick_check.py --commit，然后按 skills/habit-enforcer 的协议处理输出；actions 为空则保持沉默。若 actions 里出现 daily_close，那是静默记账——不发任何消息、不配图。" --skill habit-enforcer --skill meme-buddy --workdir /srv/peck-food
   ```

## scripts/ 三个命令

| 命令 | 作用 |
|---|---|
| `python3 scripts/tick_check.py [--now "<ISO>"] [--commit]` | **唯一事实源**：算出本轮该发什么（`{"now":..., "actions":[...]}`）。`--now` 注入时间便于复现；`--commit` 才写回 `nudge_state`/`tick_log` 并落库 |
| `python3 scripts/validate_state.py [path]` | 校验 `state/habits.json`：合法打印 `OK` 退出 0，非法列出错误清单退出 1 |
| `scripts/state.py`（库，非 CLI） | 业务逻辑本体：`load/save/validate/empty_state/effective_level/find_habit/is_due/apply_checkin/recompute_streak/plan_tick/commit_tick`，供 habit-checkin 通过 `python3 -c` 或小脚本调用 |

（另有 `scripts/gen_placeholder_memes.py`：重新生成 `skills/meme-buddy/assets/memes/` 下的占位 SVG，可重复执行。）

依赖：Python 3.9+ 标准库，零第三方包。

## 文档

- [docs/host-hermes.md](docs/host-hermes.md) —— Hermes 接线（安装 / cron 原文 / 渠道绑定 / 无 agent 降级 / 10 分钟验收清单）
- [docs/state-schema.md](docs/state-schema.md) —— 状态文件 schema + 人工检查清单
- [prd.md](prd.md) —— 产品需求（权威定义）；[计划](docs/superpowers/plans/2026-09-20-peck-food-m1.md) —— M1 实施计划与验收

## 表情包版权声明

内置表情包（`skills/meme-buddy/assets/memes/<mood>/`）**全部是自绘占位 SVG**（纯文本生成，code 即素材），不涉第三方版权，可自由替换/删除。

- 想要真图：把你的图丢进 `skills/meme-buddy/assets/memes/user/`，丢图即生效（首次使用时补一句情绪标签即可进 `_index.json`）。
- 替换内置素材请遵守 **自绘或 CC0** 原则；用户自备目录的图片版权由用户自担。
- 本仓库不含任何在线表情包 API 的 key，也**不会**在 M1 联网搜图。

## M1 范围

M1 = habit-checkin 全量 + habit-enforcer 严厉/宽松两档核心行为（提醒、催促、断链、周报）+ meme-buddy 本地包 + Hermes 接线指南，验收 PRD §8 场景 1–5；**M2** 再做自由档、日报/公审周报、成就、在线 provider 与 OpenClaw/WorkBuddy 接线。
