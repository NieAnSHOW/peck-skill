# peck-food · 习惯监督 Skills 组合 — 产品需求文档（PRD）

> 版本 v1.0 · 2026-09-20 · 状态：待评审
> 本文档由初步想法（原 prd.md）+ 实地调研 + 两轮设计决策推导而来，作为后续开发与验收的唯一依据。

---

## 1. 产品概述

**一句话**：一组遵循 Agent Skills 开放标准的 skills，寄生在用户已有的常驻 Agent 宿主（Hermes Agent / OpenClaw / WorkBuddy 等）上，通过宿主原生的 IM 通道（微信/飞书/钉钉等）对用户进行**有趣、可调档**的习惯打卡监督——从毒舌连环催到只记账不吭声，配合表情包完成每日互动。

**目标用户**：已经在用（或愿意部署）常驻个人 Agent 的自我管理型用户。

**核心理念**：
1. **寄生而非重建**——skills 不造轮子：不建 IM 网关、不建调度器，全部复用宿主原生能力，skills 只定义"监督行为协议"。
2. **监督是人格化的**——严厉/宽松/自由三档不是简单的开关，是三套完整的人设剧本（语气、催促节奏、断链处理、表情包情绪都不同）。
3. **厌烦即失败**——防骚扰约束（催促上限、熔断降档、免打扰、模板去重）是硬性规格，不是可选项。
4. **离线优先**——表情包本地包打底，在线源只是增强；断网时监督不降级。

**明确不做（v1）**：
- 不做个人微信协议接入（无官方 API，wechaty 类方案有封号风险；微信场景由宿主自行解决，如 WorkBuddy 走企微通道）。
- 不做多人/群监督（状态模型预留 `user.id` 字段，v2 再扩展）。
- 不做 App/网页界面（纯 skills + 状态文件 + IM 交互）。
- 不自建任何常驻服务。

---

## 2. 调研结论（设计依据）

### 2.1 通用性载体：Agent Skills 开放标准

[agentskills.io](https://agentskills.io) 定义的开放标准——**一个文件夹 + SKILL.md（YAML frontmatter: name/description + Markdown 正文）+ 可选的 references/ 脚本与资源**——已被 30+ Agent 产品采纳：Claude Code、ChatGPT/Codex、Cursor、GitHub Copilot、VS Code、Gemini CLI、Goose、OpenCode、Amp、OpenClaw、Hermes Agent、WorkBuddy 等。

**结论**：skills 按此标准编写即获得最大兼容性。description 字段是自动触发加载的依据，必须写成精确的"何时用我"。

### 2.2 目标宿主能力契约（三家实测文档核实）

三家宿主对 skills 组合所需的能力**全部原生具备**，且模型高度一致：

| 能力 | Hermes Agent (Nous Research) | OpenClaw | WorkBuddy (腾讯) |
|---|---|---|---|
| Skills 加载 | ✅ SKILL.md 体系 | ✅ openclaw/agent-skills 生态 | ✅ Skills 市场/配置 |
| 定时任务 | ✅ `/cron add "every 2h" "prompt" --skill xxx --workdir <dir>`，**cron 可附带 skills 运行**，结果自动投递回 IM 渠道；另有零 LLM 的无 agent 模式 | ✅ Automations：`openclaw automations create <schedule> --message "<prompt>"`，输出可投递聊天渠道；支持 script payload（零 LLM） | ✅ 计划任务 |
| IM 渠道 | ✅ Gateway 接 20+ 消息平台（微信/钉钉/飞书/Telegram/WhatsApp…） | ✅ Agent Channels（WhatsApp/Telegram 等） | ✅ 微信/飞书/钉钉接入 |
| 文件系统 | ✅ 自托管，支持 workdir 绑定 | ✅ 自托管 | ✅ 桌面应用 |
| 发图能力 | ✅ send_message/媒体投递 | ✅ 媒体投递 | ✅ 多模态（图片发送细节待接线时验证，有降级方案，见 §4.5） |

**由此确定寄生架构**：skills 依赖宿主四项假设（H1 SKILL.md 支持 / H2 定时任务可按计划以 prompt+skills 唤醒 agent / H3 可向用户 IM 发文本与图片 / H4 有文件系统），只编排宿主已有的三类工具动词——**发文本**（send_text/等效）、**发图**（send_media/等效）、**按计划唤醒**（schedule/cron/等效）——不自建任何 IM 网关、webhook 或消息协议适配器；微信/飞书/钉钉/Telegram 等协议细节完全由宿主处理。任何满足 H1–H4 的 Agent 产品均可接入；不满足者（如云端无文件系统的 Coze/Dify）不在 v1 范围。

### 2.3 表情包源现状（2026-09 实测）

| 源 | 状态 | 结论 |
|---|---|---|
| Tenor API | ❌ **已停止服务**（官方公告） | 不可用 |
| 斗图啦 doutula.com API | ❌ 多轮实测超时（对照：同环境 baidu/Giphy 可达，已排除本机断网；2019 年老 API，图床为新浪外链早已失效） | 不可用 |
| fabiaoqing.com | ⚠️ 无官方 API（站内无接口文档），搜索路径实测不通，仅可爬页面 | 脆弱，不纳入 |
| Giphy API | ✅ API 端点实测可达（返回 403 = 公共演示 key 失效，服务在线）；官方免费 key 约 100 次/时 | 可选 provider（偏国际风 GIF） |
| ALAPI 斗图接口 | ✅ 官方文档在线，可用但需注册 token，有免费额度 | 可选 provider（中文梗图） |
| 字节跳动 cv-api 表情包搜索 | ✅ 官方文档在线，按量付费 | 可选 provider（v2 备选） |

**结论**：免费表情包 API 生命周期极不可靠（头部服务 Tenor 官方停服、斗图啦实测不可达），在线源只做可插拔 provider 并明示"随时可死"。因此**内置本地表情包是唯一稳定底座**——这不是权宜，是架构决策：断网断源时监督互动不降级。

### 2.4 习惯方法论（档位设计的理论依据）

- **连续打卡链（Don't Break the Chain）**：动机强，但断链归零带来强烈挫败感，是弃用的主因之一（业界数据：42% 用户第一周弃疗；形成习惯平均需 66 天）。
- **反向修正潮流**（guilt-free / CheckHabit / Loop Habit）：周目标 4/7、断链保护券（streak freeze）、错过一天不清零——保留动机、消除焦虑。
- **提醒疲劳**：催促频率与流失率正相关——宽松/自由档存在的理由，也是防骚扰硬约束的理论依据。

**映射**：严厉档 = streak 完整主义（适合冲刺期用户，明知代价而选择压力）；宽松档 = 周目标 + 补卡券（默认推荐档）；自由档 = 纯记录（防彻底弃用）。

### 2.5 竞品空白

2026-06 GitHub 热门盘点与各 skills 集合中，**未发现"习惯监督"方向的 Agent Skill**（高星 skills 集中在编码/审查/文档/媒体工作流）。差异化空间明确。

---

## 3. 系统架构

### 3.1 总体形态：寄生架构

```
宿主 Agent（Hermes / OpenClaw / WorkBuddy ……，用户自有）
│  原生能力：IM 渠道（微信/飞书/钉钉/…）· 定时任务 · 发消息/图片 · 文件系统
│
├── 定时流（每 30 分钟 tick，宿主 cron 附带 skills 运行）
│     └─ [habit-enforcer] 读 state/habits.json → 按档位协议判定该做什么
│           → 需要发催促/夸奖/报告时：[meme-buddy] 按情绪选图
│           → 组装消息 → 宿主投递到用户 IM
│
└── 即时流（用户在 IM 里发消息，宿主唤醒 agent）
      └─ [habit-checkin] 意图识别（打卡/查询/请假/补卡/改配置/换档）
            → 更新 state/habits.json → 按当前档位风格反馈（+ 表情包）
```

三个 skill 之间**只通过状态文件和文件系统协作**，不引入任何进程间机制——保持对最笨宿主的兼容。

### 3.2 Skills 清单与职责边界

```
peck-food/
├── skills/
│   ├── habit-enforcer/            # 监督引擎（定时流的全部行为协议）
│   │   ├── SKILL.md               # 档位判定逻辑、tick 流程、消息组装规则
│   │   └── references/
│   │       ├── personas.md        # 三档人设剧本 + 催促模板池（各 8-12 条）
│   │       ├── escalation.md      # 催促升级与熔断规则
│   │       └── achievements.md    # 成就触发规则表
│   ├── habit-checkin/             # 打卡入口（即时流的全部行为协议）
│   │   ├── SKILL.md               # 意图识别、打卡记账规则、凭证、请假/补卡
│   │   └── references/
│   │       └── state-schema.md    # 状态文件完整 schema 与读写约定
│   └── meme-buddy/                # 表情包引擎（通用，被前两者调用，也可独立使用）
│       ├── SKILL.md               # 情绪→选图协议、降级链
│       ├── assets/memes/          # 内置表情包（见 §4.5）
│       │   ├── _index.json        # 全量索引：mood/关键词/caption
│       │   ├── urge/  praise/  disappointed/  angry/  cute/  celebrate/
│       │   └── user/              # 用户自备目录（丢图即生效）
│       └── providers/
│           ├── giphy.md           # 在线源接入说明（关键词映射+API+校验）
│           └── alapi.md
├── state/habits.json              # 唯一状态文件（schema 见 §3.3）
├── docs/
│   ├── host-hermes.md             # 宿主接线指南 × 3（tick prompt 模板原文）
│   ├── host-openclaw.md
│   ├── host-workbuddy.md
│   └── state-schema.md            # schema 单独文档（供人工检查）
└── README.md                      # 安装、快速开始、能力假设 H1-H4 声明
```

**触发路由**（靠 description 字段，写清"何时用我"）：
- `habit-enforcer`："仅在定时/cron tick 或生成周期报告时使用；处理催促、断链审判、成就颁发"
- `habit-checkin`："当用户消息涉及习惯打卡、查询进度、请假、补卡、修改习惯配置、切换监督档位时使用"
- `meme-buddy`："当需要挑一张符合情绪的表情包发给别人时使用（催促/夸奖/庆祝/失望/卖萌/暴怒）"

### 3.3 状态文件 schema（habits.json v1）

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
      "days": [1,2,3,4,5,6,0],        // 周几需打卡（1=周一）
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
      "h_running@2026-09-20": {"count": 1, "stage": "first"}
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

schema 细则（约束、默认值、校验清单）在 `docs/state-schema.md` 展开；本表为权威定义。

### 3.4 三条核心数据流

**定时流（tick，每 30 分钟）**：
1. 宿主 cron 以标准 tick prompt（§5.2 模板）唤醒 agent，附带 habit-enforcer（+ 按需 meme-buddy）。
2. enforcer 读状态 → 对每个习惯判定：窗口内未打卡？到催促节点了吗？今天断链了吗？到报告时刻了吗？
3. 判定要发消息 → 调 meme-buddy 协议选图 → 按 persona 模板组装 → 输出消息（宿主自动投递 IM）。
4. 更新 nudge_state / tick_log / persona_state，原子写回。

**即时流（用户消息）**：
1. 宿主收到用户 IM 消息唤醒 agent，触发 habit-checkin。
2. 意图识别 → 执行（记账/查询/请假/补卡/改配置/换档）→ 更新状态 → 按当前档位人设风格回复（+ 表情包）。

**配置流**：所有配置变更（建习惯/改档位/改窗口）都通过即时流的自然语言完成（"监督我早睡，严厉模式，打卡窗口 21 点到 23 点"），checkin 负责落库。不做配置文件/命令行。

---

## 4. 功能规格

### 4.1 习惯定义与管理

- **习惯字段**：名称、emoji（可选）、打卡日（周几）、打卡窗口（起止时间）、监督档位（可空=继承全局）、是否需凭证、周目标次数。
- **建习惯**：自然语言，agent 引导补齐缺省项（默认：每天、窗口 07:00–22:00、继承全局档、无凭证、周目标 5）。给出确认摘要后写入。
- **预设模板**：饮食 / 运动 / 睡眠 / 喝水 四类开箱模板（含推荐窗口与周目标），用户可一句话实例化（"帮我建一个运动打卡"→ 反问具体项目）。
- **改/停**：自然语言修改任意字段；暂停（请假）支持日期区间与理由；删除需二次确认。
- **迟到打卡**：窗口结束后、当日 24:00 前打卡记 `late:true`——计次且 streak 照常延续，但严厉档日报视为"破窗"点名批评；宽松/自由档仅如实记录。
- **补卡**：仅宽松档可用补卡券追认**昨日**（`freeze_left` 扣 1，记 `proof:false, note:"补卡"`）；每月 1 号重置为 2。严厉/自由档无补卡（严厉是选择，自由无需补）。

### 4.2 监督档位系统（核心规格）

档位 = 全局默认 + 每习惯可覆盖。有效档位 = `habit.level ?? global_level`。

| 维度 | 🔴 严厉 strict | 🟡 宽松 chill（默认） | 🟢 自由 free |
|---|---|---|---|
| 人设 | "教导主任"：毒舌、记小本本、开审判 | "损友"：调侃、捧场、不记仇 | "账房先生"：只记账、话少、问才答 |
| 提醒时机 | 窗口开启即提醒 | 窗口中点提醒 1 次 | 零提醒 |
| 催促轮次 | 3 轮：T+1h（提醒）→ T+3h（警告）→ 窗口结束前 30min（最后通牒） | 窗口结束前 1h 仅 1 次 | 无 |
| 催促语气升级 | 温和→毒舌点名→表情包轰炸+明日审判预告 | 始终温和幽默，绝不连发 | — |
| 断链判定 | 当日 24:00 未打卡即断链，streak 归零 | 周目标制：本周完成 < weekly_goal 才算失败，单日错过不断链 | 不判定 |
| 断链处理 | 次日日报公开处刑（毒舌但好笑）+ 记入"前科" | 周报里温和提示差距 | 仅统计 |
| 夸奖反馈 | 简短："哼，算你过关"+ celebrate 图 | 热烈吹捧 + praise/cute 图 | 一句"已记录" |
| 报告 | 每日 21:30 日报（审判体）+ 周日 21:00 公审周报 | 周六 10:00 温和周报（正向统计为主） | 周日 20:00 静默周报（纯数据） |
| 表情包情绪权重 | angry/disappointed 为主，urge 点缀 | cute/urge 为主，praise 常见 | 几乎不用（周报 1 张 celebrate/月） |

**防骚扰硬约束（覆盖所有档位，不可被人设覆盖）**：
1. 单习惯单日**提醒/催促类**主动消息 ≤ 4 条（恰好覆盖严厉档"提醒 1 + 催促 3"；报告与成就消息独立计数，不受此限）。
2. **熔断**：连续 3 天用户对某习惯零打卡回应 → 自动降一档（strict→chill→free）并明告知理由（"连续 3 天没理我，先撤为敬"）；用户可手动调回。
3. 免打扰时段（默认 22:30–07:00，可配置）优先级最高：期间不主动发任何消息。催促时刻若落入免打扰：严厉档提前至免打扰开始前最后一个 tick 发出，宽松/自由档作废。晚间习惯（如 21:00–23:00 窗口）的"窗口结束前"轮次由此自然落在 22:30 前或作废，属预期行为。
4. tick 幂等：同一习惯同日同轮次（stage）只发一次，以 `nudge_state` 为准；tick 重复执行不产生重复消息。

### 4.3 打卡交互（habit-checkin）

**支持的意图**（一条消息可复合）：
- 打卡："跑步 5 公里 ✅"、"今天喝水达标了"（含日期推断：默认今天；"昨天"需宽松档+补卡券）
- 带凭证打卡：用户消息附图 → 该习惯记 `proof:true`（图留在 IM 侧，状态文件只记布尔）
- 索要凭证：`require_proof` 的习惯收到纯文字打卡 → 温和索要（"图呢？"）×1 次，用户坚持则记 `proof:false` 照常入账（凭证是软约束）
- 查询："我这周怎么样" / "跑步连续几天了" → 按档位风格答
- 请假："下周出差，跑步请个假" → pauses 落库
- 补卡："补昨天的跑步" → 宽松档+有券才受理
- 配置：建习惯/改窗口/换档位/改免打扰/改称呼
- 闲聊兜底：与习惯无关时不抢话（描述里声明边界，让宿主其他能力处理）

**回复风格**：由有效档位人设决定（§4.2 表）；打卡成功的反馈消息 ≤ 2 句 + 表情包（自由档仅 1 句无图）。

### 4.4 催促/反馈消息系统（habit-enforcer）

- **模板池**：每档 persona 8–12 条消息模板，含结构变体（先图后文 / 先文后图 / 纯文字 / 纯图 + 一句话）。模板是"骨架 + 填槽"（称呼、习惯名、streak 数字、剩余时间），允许 agent 在骨架内自由发挥，不允许偏离人设。
- **短期去重**：`persona_state.recent_templates`（最近 5 条）内的模板不再选用；全部用遍后清空重来。
- **催促升级**（严厉档三轮的 stage 机）：`first → warn → final`，每个 stage 对应独立模板子池与表情包情绪（urge → disappointed → angry）。
- **时间计算**：所有"窗口相对时间"由 tick 内基于 `user.timezone` 计算，cron 本身只是 30 分钟粒度的唤醒器。

### 4.5 表情包引擎（meme-buddy）

**情绪目录（6 类，固定枚举）**：`urge`(催促) `praise`(夸奖) `disappointed`(失望) `angry`(暴怒) `cute`(卖萌) `celebrate`(庆祝)

**本地包规格**：
- `assets/memes/<mood>/` 每类 ≥ 5 张，JPG/PNG/GIF，单张 ≤ 2MB（主流 IM 附件上限内，宿主转发零转码）
- `_index.json`：`{"file": "urge/03.jpg", "caption": "我看好你哦", "tags": ["催促","盯"]}`
- 内置包**只收录自绘或 CC0 素材**（版权干净）；README 声明
- `assets/memes/user/`：用户自备目录，丢图即生效（首次 tick 时由 agent 引导打标进 `_index.json`；未打标的图按目录名兜底归为 cute）

**选图协议（调用方视角）**：
1. 输入：`mood`（必填）+ `keyword`（可选，如习惯名/情绪词）
2. 顺序：本地包匹配（keyword 命中 tags/caption 优先，否则 mood 目录随机，避开 `recent_memes`）→ 若启用在线 provider：按 providers/*.md 的关键词映射换词搜索，取 URL → 校验可访问（HEAD 请求）
3. **降级链**：在线失败 → 本地；本地空 → kaomoji 文字表情（如 `(╬￣皿￣)=○` (￣︶￣)）按情绪映射表输出——保证断网断源时互动永不失败
4. 输出：图片文件路径或 URL + caption；由调用方（enforcer/checkin）随消息一起交给宿主投递

**在线 provider 契约**（每个 provider 一个 md，含：关键词映射表 zh→en/平台词、API 调用示例、返回校验规则、最后验证日期、失效摘除条件）。v1 附 giphy.md、alapi.md 两份，均默认**关闭**，用户显式配置 key 才启用。

### 4.6 报告系统

- **日报（仅严厉档，每日 21:30）**：当日各习惯完成情况逐条点评，未完成者"公开处刑"（毒舌体），完成者一笔带过；结尾附明日预告。
- **周报（三档各异，时刻见 §4.2）**：完成率、streak 榜、最佳/最差习惯、下周目标建议；严厉=公审体，宽松=损友总结体，自由=纯数据表格体。周报是自由档唯一的主动输出。
- 报告生成也走 tick（到达报告时刻的 tick 内执行），复用模板池与表情包（celebrate/cute）。

### 4.7 成就系统（v1 最小集）

成就 = 触发规则 + 称号 + celebrate 表情包，规则表在 `references/achievements.md`：

| 成就 | 触发 |
|---|---|
| 初来乍到 | 首次打卡 |
| 三日之约 / 卷王一周 / 月度传说 | streak 达 3 / 7 / 30 |
| 王者归来 | 断链 ≥7 天后恢复打卡 |
| 周末战士 | 周目标 100% 达成 |

成就消息独立于当日消息计数之外不受 ≤4 条限制，但每习惯每日最多颁发 1 个（防刷屏）。

---

## 5. 宿主接入规格

### 5.1 能力假设与降级

- **H1–H4**（§2.2）：README 显式声明；不满足 H3 发图能力的宿主 → meme-buddy 降级链自动落到 kaomoji（§4.5）。
- **H2 不足**（宿主定时器粒度 > 30min）：允许 1h tick，enforcer 按实际 tick 时刻就近补发（幂等由 stage 保证）。

### 5.2 标准 tick prompt（三宿主通用原文，固化在 PRD）

```text
执行习惯监督 tick：读取 state/habits.json（相对本仓库根目录）。
对每个习惯：以 user.timezone 的当前时间为准，判定是否处于打卡窗口、
是否命中催促轮次/报告时刻/断链日结，按 habit-enforcer 的档位行为协议
决定本轮动作。需发消息时按 meme-buddy 协议配图。严格遵守防骚扰硬约束
与幂等规则（nudge_state / tick_log）。无动作则只更新 tick_log 并安静退出。
最后原子写回状态文件。
```

### 5.3 三宿主接线（docs/host-*.md 的规格）

- **Hermes**：`/cron add "every 30m" "<标准 tick prompt>" --skill habit-enforcer --skill meme-buddy --workdir /path/to/peck-food`；文档含：安装 skills 路径、渠道绑定、无 agent 模式降级说明。
- **OpenClaw**：skills 置于其 skills 目录；`openclaw automations create "*/30 * * * *" --name peck-food-tick --message "<标准 tick prompt>" --session main`；文档含 delivery 到聊天渠道配置。
- **WorkBuddy**：Skills 配置导入 + 计划任务绑定 tick prompt；图片发送能力接线时实测，不通则走 kaomoji 降级。
- 每份指南含 10 分钟验收清单（建习惯→等待 tick→收到催促→打卡→收到反馈）。

---

## 6. 非功能需求

1. **隐私**：状态只存本地 JSON（明文，不含凭证原图）；不引入任何第三方上报；在线表情包 provider 启用时仅搜索关键词出网。
2. **成本**：30min tick × 轻量 LLM 调用；提供**纯脚本 tick 降级模式**（Hermes 无 agent 模式 / OpenClaw script payload：脚本判定+固定模板直发，零 LLM）——文档给出切换方法，适合长期挂着省钱的用户。
3. **可靠性**：状态原子写；tick 幂等；records 只留 90 天（启动时清理）；tick 异常不写坏状态（先读后写、失败放弃本轮）。
4. **兼容性底线**：即使 meme-buddy 整体不可用，enforcer/checkin 的文字行为必须完整（图片是增强不是依赖）。
5. **时区**：全部以 `user.timezone` 计算；跨时区出差场景 v1 不处理（用户可自行改字段）。

## 7. 里程碑

| 阶段 | 范围 | 验收标志 |
|---|---|---|
| M1 最小闭环 | habit-checkin 全量 + habit-enforcer（严厉/宽松两档核心行为：提醒、催促、断链、周报）+ meme-buddy 本地包 + host-hermes.md | 在 Hermes 实例上完成 §8 场景 1–5 |
| M2 完全体 | 自由档、日报/公审、成就、催促熔断、补卡券、在线 provider（giphy/alapi）、host-openclaw.md、host-workbuddy.md、纯脚本 tick 降级 | §8 全场景 + 双宿主接线验收 |
| M3 打磨 | 模板池扩充（每档 12+）、彩蛋（节日/周末特别行为）、WorkBuddy 发图实测补齐、多人预留字段文档化 | 用户实测两周无厌烦反馈 |

## 8. 验收标准（行为测试清单）

1. **建习惯**："监督我早睡，严厉模式，21-23 点打卡" → 状态文件出现正确条目，缺省项被引导确认。
2. **催促链**（严厉）：模拟至窗口结束前 30 分钟的最后一个 tick 仍未打卡 → 收到 final 轮催促（angry 表情包 + 审判预告）；同日重复 tick 不重复发（幂等）。
3. **打卡反馈**：用户发"睡了 ✅" → 按档位风格回复 + streak +1；带图打卡记 proof:true。
4. **断链**：严厉档漏打卡一天 → 次日 21:30 日报点名，streak 归零；连续 3 天无回应 → 自动降档为 chill 并告知。
5. **补卡券**：chill 档 "补昨天的跑步" → freeze_left 扣减、本周计数 +1；券尽则拒绝并解释。
6. **免打扰**：23:00 tick 无任何主动消息；严厉档催促提前到 22:30 前发出，chill 作废。
7. **表情包降级**：断网/删空本地包 → 消息仍发出，图为 kaomoji。
8. **schema 校验**：对 habits.json 跑 schema 校验脚本，非法字段/缺字段被拒绝。
9. **报告**：chill 档周六 10:00 收到温和周报（完成率/streak 榜）；free 档周日仅静默周报、其余零打扰。

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| 在线表情包源再死一家 | 本地包为主、provider 可插拔可摘除、降级链兜底 |
| 宿主发图能力差异（尤其 WorkBuddy 未实测） | kaomoji 降级保证文字完整性；M3 实测补齐 |
| LLM tick 成本 | 纯脚本 tick 降级模式；30min 粒度可调稀 |
| 模板同质化引发厌烦 | 模板池 + 结构变体 + 短期去重 + 熔断降档 |
| 状态文件并发写（tick 与用户消息同时刻） | 原子写 + "先读后写、失败放弃本轮"约定；30min 粒度下冲突窗口极小 |
| 表情包版权 | 内置包仅自绘/CC0；用户自备目录自担 |

## 10. v2 展望（不承诺）

多人/群监督（一个 bot 监督一群人打卡排行榜）、习惯数据可视化周报图、自定义人设（用户调教专属监督人格）、Coze/Dify 云端平台移植层、健康数据源接入（Apple Health/手环自动打卡）。

---

## 附：原始需求追溯

原 prd.md 的四点要求 → 本文档落点：
1. "强制提醒习惯打卡（饮食/运动/睡眠/其他）" → §4.1 习惯模板 + §4.2 档位 + §4.4 催促系统
2. "通用性，兼容各类 Agent 产品" → §2.1 开放标准 + §2.2 宿主契约 + §5 接入规格
3. "监督程度分档（严厉/宽松/自由）" → §4.2 三档行为协议表
4. "趣味互动：表情包网站搜图表达监督情绪" → §4.5 meme-buddy（本地包 + 可插拔在线源 + 降级链）+ §4.7 成就
