---
name: habit-enforcer
description: 仅在定时/cron tick（监督 tick）或生成周报/断链日结时使用；处理催促升级、断链审判、档位降级通知。用户即时消息不要用本 skill（走 habit-checkin）。
---

# 习惯监督引擎（tick 流程）

每次 tick 严格按以下顺序：

1. 在仓库根执行 `python3 scripts/tick_check.py --commit --now <当前ISO时间>`，
   得到 `{"now":..., "actions":[...]}`。**不要自行心算时间或轮次——脚本是唯一事实源。**
2. actions 为空 → 本轮结束，不输出任何消息。
3. 对每个 action：
   a. 按 references/personas.md 选当前档位（effective_level）对应 stage 的模板
      （避开 persona_state.recent_templates 最近 5 条；选完追加并裁剪到 5）。
   b. 用 action.slots 填槽（{{name}}/{{habit}}/{{streak}}/{{deadline}}/{{week_rate}}）。
   c. 调 meme-buddy：nudge 用 action.mood；daily_close 用 disappointed；
      weekly_report 用 celebrate（chill）/angry（strict 公审）；level_down 用 cute。
   d. 输出最终消息（文字 + 图），交宿主投递。多 action 时合并为最多 2 条消息，
      按 type 排序：level_down → nudge → daily_close → weekly_report。
4. level_down 动作：脚本已在 commit 时把该习惯降为 chill 并写明理由，你只需
   以当前人设告知用户（例："连续 3 天没理我，先撤为敬，改宽松档了"）。
5. 免打扰与 ≤4 条上限由脚本保证，你不做额外判断，也不要在免打扰时段补发。
