# 状态文件 schema（~/.peck-skill/habits.json v1）

> 权威定义：PRD §3.3。实现：`scripts/state.py`（仅 Python 标准库）。
> 所有时间计算基于 `user.timezone`（IANA 名），用 `datetime.now(ZoneInfo(tz))`。

## 1. 完整 schema（PRD §3.3 原文）

单一 JSON 文件，原子写（先写临时文件再 rename），所有时间计算基于 `user.timezone`。

```jsonc
{
  "version": 1,
  "user": {
    "id": "default",                  // v2 多人预留，v1 恒为 default
    "name": "老板",                    // 称呼，人设剧本用它喊人
    "timezone": "Asia/Shanghai",
    "quiet_hours": ["22:30", "07:00"] // 免打扰窗口，tick 期间不发主动消息
  },
  "global_level": "chill",            // strict | chill | free，全局默认档
  "habits": [{
    "id": "h_running",
    "name": "跑步",
    "emoji": "🏃",
    "schedule": {
      "days": [1,2,3,4,5,6,0],        // 周几需打卡（1=周一，0=周日）
      "window": ["06:00", "22:00"]    // 当日打卡窗口，窗口外打卡=迟到
    },
    "level": null,                     // null=继承 global_level；可独立设档
    "require_proof": false,            // 是否需要凭证（附图）
    "weekly_goal": 3,                  // 宽松档的周目标（次/周）
    "stats": {
      "current_streak": 4, "best_streak": 12,
      "total": 30, "week_count": 2     // 本周已完成次数
    },
    "records": [                       // 按日期追加，只保留最近 90 天
      {"date": "2026-09-19", "proof": true, "note": "5km", "late": false}
    ],
    "pauses": [                        // 请假（窗口内的日子不计入断链）
      {"from": "2026-09-01", "to": "2026-09-05", "reason": "出差"}
    ],
    "freeze_left": 2                   // 补卡券余额（每月重置为 2，仅宽松档消耗）
  }],
  "nudge_state": {                     // 催促记账：防重复催促、熔断判定
    "per_habit_day": {                 // "h_running@2026-09-20": 本日已催次数/轮次
      "h_running@2026-09-20": {"count": 1, "stages": ["remind"]}
    },
    "no_response_days": 0              // 连续无打卡回应天数，≥3 触发熔断降档
  },
  "persona_state": {                   // 防重复趣味约束
    "recent_templates": ["tpl-id…"],   // 最近 5 条用过的消息模板，选新模板时避开
    "recent_memes": ["urge/03.jpg"]    // 最近 3 张发过的图，选图时避开
  },
  "achievements": ["first-checkin"],
  "tick_log": [                        // 最近 50 条 tick 摘要（幂等依据）
    {"ts": "2026-09-20T09:00+08:00", "actions": ["nudge h_running stage=first"]}
  ]
}
```

> 实现注记：`empty_state()` 产出的 `no_response_days` 是**按习惯的映射** `{}`（键为 `habit_id`，`plan_tick` 读 `no_response_days[habit_id] >= 3` 触发熔断）；`per_habit_day` 键统一为 `<habit_id>@<YYYY-MM-DD>`。

## 2. 三条操作约定

1. **原子写**：永远 `save(path, state)` 落库（内部 temp + `os.replace`），绝不直接 `open(path,"w")` 覆写。
2. **改后 validate**：任何写入前先改内存 dict，写入后跑 `validate(state)` 自检；非空错误清单视为落库失败并回退。
3. **records 保留 90 天**：`records` 按日期追加，只保留最近 90 天，由 tick 侧清理；`pauses` 不清理。

## 3. 调用契约（scripts/state.py，Task 2 Interfaces）

调用方式：宿主用 shell 执行 `python3 -c "..."` 或写小脚本 import 本模块（`scripts/` 需在 `sys.path`）。

```python
effective_level(state, habit) -> str
# habit["level"] or state["global_level"]；返回值 ∈ {"strict","chill","free"}

find_habit(state, name) -> dict | None
# 按 habit["id"] 精确匹配，或按 habit["name"] 模糊匹配；找不到返回 None

is_due(habit, day: date) -> bool
# schedule["days"] 含该周几（(day.weekday()+1)%7，周一=1 … 周日=0）且 day 不在任何 pause 的 [from, to] 闭区间

apply_checkin(state, habit_id, day: date, note: str, proof: bool, now: datetime) -> dict
# 直接改 state（调用方负责 save）
# 返回 {"ok": bool, "reason": str|None, "streak": int, "late": bool, "makeup": bool}
#   - 同日重复        -> {"ok": False, "reason": "already checked in", ...}
#   - 目标日 == 今天   -> late = now 时间 > 窗口结束；记账 {date, proof, note, late}；streak/total/week_count 同步 +1
#   - 目标日 == 昨天   -> 仅 effective_level == "chill" 且 freeze_left > 0 受理，makeup=True，freeze_left -= 1
#   - 其他日期        -> {"ok": False, "reason": "out of range", ...}

reset_monthly_freeze(state, today: date) -> None
# 仅每月 1 号（today.day == 1）把每个 habit 的 freeze_left 重置为 2，其余日期直接返回（当日幂等）
```

配套读接口：`load(path) -> dict`、`validate(state) -> list[str]`（空列表=合法）、`save(path, state) -> None`（原子写）、`empty_state(name, tz) -> dict`。
