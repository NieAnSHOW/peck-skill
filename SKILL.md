---
name: peck-skill
description: 习惯打卡监督员（单技能自包含版）。两种场景必须触发：① 用户消息涉及习惯打卡、查询进度、请假、补卡、新建/修改习惯、切换监督档位（严厉/宽松/自由）——如"打卡/今天跑了/睡了✅/我这周怎么样/补昨天的/监督我早睡/改成严厉"；② 定时监督 tick（cron 唤醒）——催促升级、周报、断链日结、档位降级通知。自带表情包配图能力。
---

# peck-skill · 习惯监督

一个自包含技能：`scripts/`（确定性判定引擎）+ `references/`（人设剧本与协议）+ `assets/`（本地表情包）。复制本文件夹到任意宿主 skills 目录即完成安装。

## 状态

`~/.peck-skill/habits.json`（环境变量 `PECK_SKILL_STATE` 可覆盖；schema 见 `references/state-schema.md`）。文件不存在时脚本会自动初始化。一切时间以状态内 `user.timezone` 为准。

## 路由（先判断当前处于哪个流）

- **即时流**（用户在 IM 里说话）→ 读 `references/checkin.md`，按五类意图表处理。
- **定时流**（监督 tick / 周报 / 日结）→ 读 `references/enforcer.md`，严格按其 6 步执行。
- **配图**（两个流都需要时）→ 读 `references/meme.md`。

## 硬约束（任何流程不得违反）

1. **不要自行心算时间、轮次、streak、免打扰——一律执行 `scripts/` 下的脚本，脚本是唯一事实源。**
2. 免打扰（默认 22:30–07:00）不主动发消息；单习惯单日提醒/催促 ≤ 4 条；幂等以 `nudge_state` 为准。
3. 改动状态后执行 `python3 scripts/validate_state.py` 自检，非法结构必须修复后再继续。

## scripts/

| 命令 | 作用 |
|---|---|
| `python3 scripts/tick_check.py [--now ISO] [--commit]` | tick 判定引擎：输出本轮动作 JSON；`--commit` 落库 |
| `python3 scripts/validate_state.py` | schema 校验（OK 退出 0） |
| `python3 scripts/gen_placeholder_memes.py` | 重新生成占位表情 SVG（可重复执行） |

状态库函数（`load/save/validate/apply_checkin/plan_tick/commit_tick` 等）在 `scripts/state.py`，签名见 `references/state-schema.md`。
