# 定时流 · 监督引擎（tick 流程）

每次 tick 严格按以下顺序：

1. 执行 `python3 scripts/tick_check.py --commit --now <当前ISO时间>`（在技能根目录下；
   状态文件默认 `~/.peck-skill/habits.json`，`PECK_SKILL_STATE` 可覆盖），
   得到 `{"now":..., "actions":[...]}`。**不要自行心算时间或轮次——脚本是唯一事实源。**
2. actions 为空 → 本轮结束，不输出任何消息。
3. 对每个 action：
   a. 按 `references/personas.md` 选当前档位（effective_level）对应 stage 的模板
      （避开 persona_state.recent_templates 最近 5 条；选完追加并裁剪到 5）。
   b. 用 action.slots 填槽（{{name}}/{{habit}}/{{streak}}/{{deadline}}/{{week_rate}}）。
   c. 按 `references/meme.md` 协议配图：nudge 用 action.mood；weekly_report 用
      celebrate（chill）/angry（strict 公审）；level_down 用 cute。
   d. 输出最终消息（文字 + 图），交宿主投递。多 action 时合并为最多 2 条消息，
      按 type 排序：level_down → nudge → weekly_report。
4. `daily_close`：**不发消息、不配图**——断链已由脚本记录归档（commit 时已把 streak 归零），
   处刑在周日公审周报（M2 起为次日日报）。它没有 `mood` 字段，你不得为它渲染任何消息。
5. level_down 动作：脚本已在 commit 时把该习惯降为 chill 并写明理由，你只需
   以当前人设告知用户（例："连续 3 天没理我，先撤为敬，改宽松档了"）。
6. 免打扰与 ≤4 条上限由脚本保证，你不做额外判断，也不要在免打扰时段补发。
