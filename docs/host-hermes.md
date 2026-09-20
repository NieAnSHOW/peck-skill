# Hermes 接线指南（peck-food M1）

> 目标：在一台自托管 Hermes Agent 上，10 分钟内把 peck-food 的监督 tick 跑起来（PRD §5.3、§8 场景 1–5）。
> 本仓库不做任何网络服务，全部行为由三个 skills + 一个状态文件 + 三个纯标准库脚本组成。

## 0. 前置：宿主能力假设 H1–H4（PRD §2.2）

| 假设 | 需要什么 | 不满足时 |
|---|---|---|
| H1 | 支持 Agent Skills（SKILL.md 体系） | 无法接入，本仓库不提供其它加载方式 |
| H2 | 定时任务能按计划以「prompt + skills」唤醒 agent | 降级：把 tick 交给纯脚本（§4），零 LLM |
| H3 | 能向用户 IM 发文本与图片 | 发图不通 → meme-buddy 自动降级为 kaomoji 文字表情，文字行为完整 |
| H4 | 有文件系统且能绑定工作目录 | 无法接入（状态文件与脚本都在仓库里） |

Hermes 满足全部四项：`/cron` 支持 `--skill` 与 `--workdir`，结果自动投递回 IM 渠道。

## 1. 安装

**两个位置都要放东西**（这是最容易踩的坑）：

1. **skills** → Hermes 的 skills 目录（默认 `~/.hermes/skills/`；若你的实例另有配置，以实例为准）。目录名必须原样保留 `habit-checkin` / `habit-enforcer` / `meme-buddy`，description 是自动触发的依据。
2. **仓库** → 服务器上任意路径（下例用 `/srv/peck-food`）。`state/habits.json`（唯一状态）与 `scripts/*.py` 都在仓库里，cron 通过 `--workdir` 指向它；enforcer 的 SKILL.md 里所有命令都要求「在仓库根执行」。

```bash
# ① 仓库落位（git clone 或直接拷贝整个目录都可以）
git clone <你的仓库地址> /srv/peck-food
cd /srv/peck-food && python3 scripts/validate_state.py        # 应打印 OK

# ② skills 落位
mkdir -p ~/.hermes/skills
cp -r /srv/peck-food/skills/habit-checkin \
      /srv/peck-food/skills/habit-enforcer \
      /srv/peck-food/skills/meme-buddy ~/.hermes/skills/

# ③ 自检：三个 SKILL.md 都在，且 frontmatter 只有 name/description
ls ~/.hermes/skills/*/SKILL.md
```

依赖只有 Python 3.9+ 标准库（`json/datetime/argparse/zoneinfo/unittest`），不需要 pip、不需要联网。

## 2. 建 cron（每 30 分钟，PRD §5.2 标准 tick prompt）

```bash
/cron add "every 30m" "执行习惯监督 tick：cd 到 peck-food 仓库根（/srv/peck-food），运行 python3 scripts/tick_check.py --commit，然后按 skills/habit-enforcer 的协议处理输出；actions 为空则保持沉默。若 actions 里出现 daily_close，那是静默记账——不发任何消息、不配图。" --skill habit-enforcer --skill meme-buddy --workdir /srv/peck-food
```

要点：

- **脚本是唯一事实源**：轮次、幂等、免打扰、≤4 条上限、熔断全部由 `tick_check.py` 判定，LLM 只负责选模板、填槽、配图与投递。不要让它自己心算时间。
- **cron 只是 30 分钟粒度的唤醒器**（H2 不足时可放宽到 1h，`_due_rounds` 会就近补发）。
- **`daily_close` 静默**：当日 due 未打卡且已过 23:30 时，脚本会产出 `daily_close` 用于断链归档（同时把 strict 的 `stats.current_streak` 归零），但它不对应任何 IM 消息——收到它不要渲染、不要配图。
- 标准 tick prompt 的等价原文见 PRD §5.2；`skills/habit-enforcer/SKILL.md` 的 1–6 步协议优先级高于本文件的转述。

**渠道绑定**：Hermes 的 `/cron` 结果自动投递回来源会话/IM 渠道（Gateway 支持 20+ 平台）。首次配置建议把频率临时改成 `every 5m`，确认消息真的进到了你与 bot 的私聊，再改回 `every 30m`。

## 3. 即时流（用户发消息的那条路）

用户消息由宿主唤醒 agent → 触发 `habit-checkin`（"打卡/睡了吗/我这周怎么样/补昨天/改成严厉"等），它按 `skills/habit-checkin/SKILL.md` 的五类意图协议记账、改状态、按档位人设回复。tick 与即时流通过**同一个** `state/habits.json` 协作（原子写；冲突窗口极小，写失败放弃本轮）。

## 4. 无 agent 模式降级（零 LLM，省钱挂机）

不想为每 30 分钟一次 tick 付 LLM 调用时，把 tick 交给 Hermes 的无 agent（script payload）通道：**不经模型，直接执行命令、原样投递输出**。

- 要执行的命令原文：`cd /srv/peck-food && python3 scripts/tick_check.py --commit`
- 投递的是脚本的 JSON：`{"now": "...", "actions": [{"type": "nudge", "stage": "first", "mood": "urge", "slots": {...}}]}`
- 代价：没有人设润色与表情包（actions 里只有 stage/mood/slots，需要自己拼固定文案）；`daily_close` 依旧是静默记账，别把它投递出去。
- 具体开关名/字段名以你的 Hermes 版本文档为准（本仓库未实测该通道的 CLI 原文）。

## 5. 10 分钟验收清单（PRD §8 场景 1–5 手工版）

前置：`cd /srv/peck-food`，所有命令都在仓库根执行。

| # | 做什么 | 期望 |
|---|---|---|
| 1 | 让 agent 建习惯："监督我早睡，严厉模式，21-23 点打卡"（或直接编辑 `state/habits.json`） | 条目字段齐全（默认：每天、窗口 07:00–22:00、继承全局档、无凭证、周目标 5），`python3 scripts/validate_state.py` → `OK` |
| 2 | 观察窗口开启提醒：`python3 scripts/tick_check.py --now "2026-09-21T07:00:00+08:00"` | 有 `"stage": "remind"`（窗口 07:00–22:00 时 07:00 正是第一个 tick） |
| 3 | 观察催促升级链：同一命令换 `--now` 到 `08:00` / `10:00` / `21:30` | 依次 `first` / `warn` / `final`；同一时刻连跑两次，第二次 actions 为空（幂等） |
| 4 | 打卡反馈：给 agent 发"睡了 ✅" | 按档位风格回复 + 表情包，streak +1；带图则 `proof:true` |
| 5 | 断链与熔断：`--now` 到 `23:50` 看 `daily_close`；把某习惯 `nudge_state.no_response_days` 设成 3 再看 08:00 | 前者**不发消息**（静默记账，且 `stats.current_streak` 归零）；后者产出 `level_down` 并把该习惯降为 chill |
| 6 | 补卡券：chill 档"补昨天的跑步" | `freeze_left` 扣 1、周计数 +1；券尽拒绝并解释 |
| 7 | 免打扰：`--now "2026-09-21T23:00:00+08:00"` 与 `06:30` | 都没有任何 nudge/weekly_report（22:30–24:00 与 00:00–07:00 两段）；strict 撞免打扰的轮次提前到 22:00，chill 作废 |
| 8 | 表情包降级：临时把 `skills/meme-buddy/assets/memes/` 改名 | 消息照发，图变成 kaomoji 文字表情（图是增强不是依赖） |
| 9 | schema 校验：故意删掉 `state/habits.json` 里一个顶层键 | `python3 scripts/validate_state.py` 退出码 1 并列出错误，修回后回到 `OK` |

**快速观察催促的调试技巧**（不想等到窗口起 + 1h）：

- 首选：不改状态，直接用 `--now` 注入时刻反复试（上表第 2/3 行）。
- 要在真实 cron 里马上看到催促：把该习惯的 `schedule.window` 起点临时改到「当前时刻 − 1h」（例：现在 14:10 → `["13:00","22:00"]`），下一个 tick 就会拿到 `first`（已过点的 `remind` 被合并）。
  **验完务必还原窗口**，并跑一次 `python3 scripts/validate_state.py` 确认没改坏；`--commit` 写的 `nudge_state` 会被幂等位占住，想重看请顺手删掉 `nudge_state.per_habit_day` 里的当日键。

## 6. 排错

| 症状 | 原因 | 处理 |
|---|---|---|
| tick 完全没有输出 | 没到点/已打卡/免打扰/当日 ≤4 条已用满 | 这是设计行为；用 `--now` 换时刻验证，或看 `tick_log` 最近一条 |
| 一直收不到消息 | cron 投递没绑到渠道，或 agent 拿不到 workdir | 临时改 `every 5m` 观察投递；确认 `--workdir` 指向仓库根 |
| 报 `No module named 'zoneinfo'` | Python < 3.9 | 升级 Python（或不用 `user.timezone` 的 IANA 名不可行，M1 不支持降级） |
| 图片发不出 | H3 能力差异 | 走 kaomoji 降级，文字行为不受影响 |
| 状态文件疑似写坏 | 并发写 | 从 `state/habits.json` 备份恢复；`validate_state.py` 会拦住非法结构 |
