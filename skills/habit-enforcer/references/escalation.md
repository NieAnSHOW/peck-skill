# 催促升级规则（操作员视角）

本文件是 PRD §4.2「防骚扰硬约束」的操作员重述。所有时刻由 `scripts/tick_check.py` 基于
`user.timezone` 计算，cron 只是 30 分钟粒度的唤醒器；你（LLM）**不做时间运算、不做轮次判断、
不做上限判断**，只按脚本给的 `stage` 选模板。

## 1. stage 状态机

`date` = 该习惯当日 due 日；`W = schedule.window`（本地时区）；`w_start` / `w_end` 为窗口起止。

### strict（严厉档）——「提醒 1 + 催促 3」共四轮

| 轮次 stage | 名义时刻 | mood | 语气 |
|---|---|---|---|
| `remind` | 窗口开启后第一个 tick（≥ `w_start`） | `urge` | 温和提醒 |
| `first` | `w_start` + 1h | `urge` | 毒舌点名 |
| `warn` | `w_start` + 3h | `disappointed` | 警告 |
| `final` | `w_end` − 30min | `angry` | 最后通牒 |

- 四轮各占一个独立 `stage` 值，**幂等键是 stage**：同 habit 同日同 stage 只发一次。
- 四轮恰好用满当日上限 4 条，因此第 5 轮不存在；上限用满后脚本不再产出任何 `nudge`。

### chill（宽松档）——两轮，绝不连发

| 轮次 stage | 名义时刻 | mood | 语气 |
|---|---|---|---|
| `remind` | 窗口中点（`w_start` 与 `w_end` 中点）后的第一个 tick | `cute` | 调侃式提醒 |
| `lastcall` | `w_end` − 1h（若落入免打扰则作废，见 §3） | `cute` | 最后一次问 |

- 中点之前**不产出任何消息**；落入免打扰的轮次一律作废、不补发。
- 单日错过不断链（周目标制，见 §6）。

### 报告类 stage（不受 4 条上限约束，独立计数）

| 动作 | 时刻 | mood | 说明 |
|---|---|---|---|
| `daily_close` | 当日 due 且 23:30 后仍无 record（免打扰豁免） | **无 mood 字段** | 仅 strict：**静默记账**——不发消息、不配图；`--commit` 时脚本把 `stats.current_streak` 归零（PRD §4.2「当日 24:00 未打卡即断链」） |
| `weekly_report` | chill 周六 10:00–10:29 的第一个 tick；strict 周日 21:00 | chill→`celebrate`；strict→`angry`（公审） | 完成率 / streak 榜 / 最佳最差习惯 / 下周建议 |
| `level_down` | 熔断触发时当轮 tick | `cute` | 见 §5 |

已打卡的习惯当日不产出任何 `nudge`；`daily_close` 也只对「当日 due 且无 record」产生，且它只写状态、不产生消息。

## 2. 每日 ≤ 4 条（脚本保证）

- 计数落在 `nudge_state.per_habit_day["<habit_id>@<YYYY-MM-DD>"] = {"count": N, "stages": [...]}`。
- 只有**提醒/催促类**（`type == "nudge"`）计入 `count`；`daily_close` / `weekly_report` / `level_down` 独立计数，不受此限。
- 当日 `count ≥ 4` → 脚本跳过全部后续 `nudge`。你不需要、也不得自行补发。

## 3. 免打扰 22:30–07:00（最高优先级，可被 `user.quiet_hours` 覆盖）

- 免打扰是跨零点区间：`22:30 <= t` 或 `t < 07:00` 均视为免打扰。
- 期间**不主动发任何消息**：脚本在免打扰时段跳过一切 `nudge` / `weekly_report` / `level_down` 产出。
- **`daily_close` 是唯一豁免项**——它不对应任何 IM 消息（静默记账、断链归档），因此允许在免打扰内产出；你不得为它渲染消息。
- 名义时刻落入免打扰（≥22:30）的处理：
  - **strict**：提前至 22:30 前最后一个可发 tick 发出；同一 tick 积压多个 stage 时**合并为最高优先级一条**，优先级 `final > warn > first > remind`（合并的那一条只消耗一个 stage 幂等位，被合并掉的 stage 不补发）。
  - **chill**：直接**作废**，不提前、不补发。
- 晚间窗口（如 21:00–23:00）的「窗口结束前」轮次自然落在 22:30 前或作废，属预期行为；你**不得在免打扰时段补发**任何消息。

## 4. 幂等（tick 重复执行不产生重复消息）

- 事实源是 `nudge_state.per_habit_day`：`stages` 是已发 stage 的集合，已发过的 stage 当轮直接跳过。
- cron 30 分钟粒度可能在同一名义时刻触发多次 tick；重复 tick 只会得到空 `actions`。
- 你只消费脚本输出的 actions，**不得**因为「上次没发出去」而重发。

## 5. 熔断（M1 即生效）

- 计数：`nudge_state.no_response_days[habit_id]`——当日有 record 归 0，否则 +1。
- 某习惯 `no_response_days ≥ 3` 且有效档位为 strict → 产出 `level_down` 动作；`--commit` 时脚本已把该习惯写为 `level == "chill"`，并在 slot 里给出理由。
- 你的职责：以当前人设告知用户（例：「连续 3 天没理我，先撤为敬，改宽松档了」），不再追问、不改回档位。用户手动调回由 habit-checkin 处理。
- 档位阶梯 `strict → chill → free`；M1 只在 strict→chill 上触发（free 档为 M2，不在 M1 实现范围）。

## 6. chill 周目标制判定

- 达标口径：**`stats.week_count ≥ weekly_goal` 即本周达标**（周一为界）。单日错过不算失败、不断链。
- chill 档不产出断链日结；周日 23:30 的统计仅作为 `weekly_report` 前置数据。
- 周报按完成率呈现（`{{week_rate}}` 填槽），语气为损友式正向总结，不公开处刑。

## 7. mood 枚举（六值，不可增删）

`urge` / `praise` / `disappointed` / `angry` / `cute` / `celebrate`

映射关系：nudge 用脚本给出的 `action.mood`；`weekly_report` → chill `celebrate` / strict `angry`；`level_down` → `cute`；打卡成功（habit-checkin 侧）→ `praise`；**`daily_close` 无 mood（不渲染消息、不配图）**。

## 8. 模板变量契约

`{{name}}`（称呼）、`{{habit}}`（习惯名）、`{{streak}}`（当前连续天数）、`{{deadline}}`（窗口结束时刻）、`{{week_rate}}`（本周完成率）。填槽值一律取自 `action.slots`，字段名与变量名一一对应，缺失时回退到习惯默认值，不得改写变量名。`daily_close` 的 slots 仅作归档，不用于渲染。

## 9. 操作员红线（快速自查）

1. 先跑脚本，后选模板——不心算时间、不猜轮次。
2. `actions` 为空则一个字符都不输出。
3. 免打扰时段一条主动消息都不发；`daily_close` 是静默记账，不是消息，不得为它发任何东西。
4. 同一 stage 一天只发一次；不因投递失败重发。
5. 超过 4 条的上限由脚本兜底，你不加判断也不绕过。
6. 模板变量与 stage 名不得改名、不得新增。
