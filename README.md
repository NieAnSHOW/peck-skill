# peck-skill · 习惯监督技能

一个**自包含**的 Agent Skill：通过宿主 Agent（Hermes / OpenClaw / WorkBuddy 等支持 SKILL.md 标准 + 定时任务 + IM 通道的产品）对你做**有趣、可调档**的习惯打卡监督——严厉（教导主任·四轮催促）/ 宽松（损友·周目标+补卡券），配表情包，断网降级为 kaomoji。

不做 App、不做网关、不建服务：`SKILL.md` + `references/`（行为协议）+ `scripts/`（纯标准库判定引擎）+ `assets/`（表情包）。

## 宿主要求（H1–H4）

1. 支持 Agent Skills（SKILL.md 文件夹标准）
2. 定时任务可按计划以 prompt + skills 唤醒 agent（cron/automations）
3. 可向用户 IM 发文本与图片
4. 可执行 shell（跑 `scripts/*.py`，需 Python 3.9+，零第三方依赖）

## 安装（复制即分发）

```bash
# 整个仓库就是一个技能文件夹：拷进宿主 skills 目录即完成
cp -r <peck-skill 目录> ~/.hermes/skills/peck-skill     # Hermes 示例
# 或 git clone
git clone <repo> ~/.hermes/skills/peck-skill
```

状态文件在**技能目录之外**：`~/.peck-skill/habits.json`（`PECK_SKILL_STATE` 环境变量可覆盖），首次运行自动初始化——技能目录可被宿主随意升级/覆盖，打卡数据不受影响。

接线（cron 定时监督）见 `docs/host-hermes.md`，10 分钟验收清单也在里面。

## scripts/

| 命令 | 作用 |
|---|---|
| `python3 scripts/tick_check.py [--now ISO] [--commit] [--state PATH]` | tick 判定引擎：输出本轮动作 JSON；`--commit` 落库 |
| `python3 scripts/validate_state.py [path]` | schema 校验：合法打印 `OK` 退出 0，非法列错误退出 1 |
| `python3 scripts/gen_placeholder_memes.py` | 重新生成占位表情 SVG（可重复执行） |

## 表情包版权

内置表情包（`assets/memes/<mood>/`）**全部是自绘占位 SVG**（纯文本生成，code 即素材），不涉第三方版权，可自由替换/删除。

- 想要真图：把你的图丢进 `assets/memes/user/`，丢图即生效（首次使用时补一句情绪标签即可进 `_index.json`）。

## 范围

- **M1（当前）**：严厉/宽松两档全行为（四轮催促/免打扰/熔断降档/补卡券/周报）、本地表情包 + kaomoji 降级、Hermes 接线。
- **M2 预告**：自由档、每日日报、成就系统、在线表情包源（Giphy/ALAPI）、OpenClaw/WorkBuddy 接线。
