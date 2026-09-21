# Hermes Agent 接线指南（单技能版）

宿主能力假设 H1–H4 见 `README.md`。Hermes 满足全部四项：`/cron` 支持 `--skill`，结果自动投递回 IM 渠道；shell 工具可执行 Python。

## 安装

1. **技能** → Hermes 的 skills 目录（默认 `~/.hermes/skills/`；若你的实例另有配置，以实例为准）：

```bash
cp -r <peck-skill 目录> ~/.hermes/skills/peck-skill
ls ~/.hermes/skills/peck-skill/SKILL.md   # 确认入口存在
```

目录名建议保持 `peck-skill`（SKILL.md 的 name 与 description 是自动触发的依据）。

2. **状态** → 无需任何操作：首次运行自动初始化 `~/.peck-skill/habits.json`（想放别处就设 `PECK_SKILL_STATE` 环境变量并写进 Hermes 的 `.env`）。

## 建定时监督（cron）

```
/cron add "every 30m" "执行习惯监督 tick：运行 python3 ~/.hermes/skills/peck-skill/scripts/tick_check.py --commit，然后按 peck-skill 技能 references/enforcer.md 的协议处理输出；actions 为空则保持沉默。若 actions 里出现 daily_close，那是静默记账——不发任何消息、不配图。" --skill peck-skill
```

- 不再需要 `--workdir`：状态在 `~/.peck-skill/`，脚本路径在 prompt 里写死绝对路径。
- 用户即时消息（"打卡/我这周怎么样/改成严厉"）由 SKILL.md 的 description 自动触发，走 `references/checkin.md`。
- 渠道绑定：cron 结果默认投递回创建会话；想投到别的渠道，按 Hermes 文档配置目标。

## 零 LLM 降级（省钱挂机）

把上面的 cron 换成 Hermes 的无 agent 模式（script payload）：直跑 `tick_check.py --commit`，stdout 的 JSON 原样投递。判定、幂等、免打扰全部由脚本保证，只是消息变成裸 JSON 而非人设文案。适合长期挂着省 token。

## 10 分钟验收清单

前置：所有命令在任意目录可跑（脚本用绝对路径）。

| # | 操作 | 期望 |
|---|---|---|
| 1 | 让 agent 建习惯："监督我早睡，严厉模式，21-23 点打卡"（或直接编辑 `~/.peck-skill/habits.json`） | 条目字段齐全（默认：每天、窗口 07:00–22:00、继承全局档、无凭证、周目标 5），`python3 ~/.hermes/skills/peck-skill/scripts/validate_state.py` → `OK` |
| 2 | 严厉档窗口开启后的第一个 tick | 收到 remind（教导主任语气 + urge 图） |
| 3 | 持续不打卡，等 +1h / +3h / 结束前 30min | first → warn（disappointed）→ final（angry），语气逐轮升级；同日同轮不重复 |
| 4 | 回"睡了 ✅" | ≤2 句人设反馈 + streak +1；带图消息记 proof=true |
| 5 | 漏打卡一整天 | 23:30 后无任何消息（daily_close 静默记账），streak 归零，周日 21:00 公审周报点名 |
| 6 | 连续 3 天不理催促 | 自动降档 chill 并收到"先撤为敬"通知 |
| 7 | chill 档说"补昨天的跑步" | freeze_left 扣 1、本周计数 +1；券尽（<1）则拒绝并解释 |
| 8 | 表情包降级：临时把 `assets/memes/` 改名 | 消息照发，图变成 kaomoji 文字表情（图是增强不是依赖） |
| 9 | schema 校验：故意删掉状态文件里一个顶层键 | `validate_state.py` 退出码 1 并列出错误，修回后回到 `OK` |

调试技巧：把窗口起点临时改成"当前时间 −1h"，下一个 tick 就能看到 first 轮催促，验完改回。

## 排错

| 症状 | 排查 |
|---|---|
| 一直收不到消息 | cron 投递没绑到渠道 | 临时改 `every 5m` 观察投递；确认 cron job 状态 |
| tick 报状态找不到 | `PECK_SKILL_STATE` 设了但目录不存在 | 脚本会自动建目录；检查 Hermes `.env` 是否注入了该变量 |
| 状态文件疑似写坏 | 并发写 | 从 `~/.peck-skill/habits.json` 备份恢复；`validate_state.py` 会拦住非法结构 |

## 迁移（自三技能版）

旧版状态在仓库 `state/habits.json` 的用户：`mkdir -p ~/.peck-skill && mv state/habits.json ~/.peck-skill/habits.json` 即可，schema 不变。

标准 tick prompt 的等价原文见 PRD §5.2；`references/enforcer.md` 的 1–6 步协议优先级高于本文件的转述。
