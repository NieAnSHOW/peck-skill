# Repository Guidelines

## Project Overview

`peck-skill` is a **self-contained Agent Skill** that turns a host agent (Hermes, later OpenClaw/WorkBuddy) into a habit-checkin supervisor: two tunable tiers (strict 「教导主任, four-round escalation」 / chill 「损友, weekly goal + makeup coupons」), meme images, kaomoji fallback when images are unavailable.

Hard product boundary (README.md:5, prd.md:20-24): no app, no gateway, no long-running service, no personal-WeChat protocol, no multi-user. The deliverable is `SKILL.md` + `references/` (LLM behavior protocol) + `scripts/` (deterministic judge, stdlib only) + `assets/` (memes). **The repo root IS the skill root**; distribution is `cp -r` into the host's skills directory — there is no build, install, or packaging layer.

Host contract H1–H4 (README.md:7-12): Agent Skills support, scheduled prompt+skills wake-up (cron), IM text+image send, shell (Python 3.9+, zero third-party deps).

M1 shipped: strict/chill full behavior, local meme pack + kaomoji degrade, Hermes wiring. Keyword web meme search shipped 2026-09-21 (`references/meme.md` step 4 + `scripts/save_meme.py`). M2 (not implemented, do not build unasked): `free` tier, daily report, achievements, dedicated online meme API providers (Giphy/ALAPI), `host-openclaw.md` / `host-workbuddy.md`.

## Architecture & Data Flow

Three layers with one hard seam — **the LLM never computes time, rounds, streaks, caps, or quiet hours**; `scripts/` is the single source of truth (`SKILL.md:22`, `references/enforcer.md:7`).

```
host agent (cron wake-up + IM send + shell)
  └─ SKILL.md            entry: YAML frontmatter description (auto-trigger) + 3-way router
       ├─ references/checkin.md    instant flow (IM intents)
       ├─ references/enforcer.md   scheduled flow (6-step tick)
       └─ references/meme.md       image selection for both (user lib → builtin → web search → kaomoji)
  └─ scripts/state.py     deterministic engine (schema, IO, streak, ticks)  ← pure logic
       ├─ scripts/tick_check.py     CLI: plan (and optionally commit) one tick
       ├─ scripts/validate_state.py CLI: schema self-check
       └─ scripts/save_meme.py      CLI + importable core: file downloaded meme into ~/.peck-skill/memes/
  └─ assets/memes/<mood>/ local pack, 6 fixed moods + user/ override
state: ~/.peck-skill/habits.json  (PECK_SKILL_STATE overrides; OUTSIDE the skill dir)
memes: ~/.peck-skill/memes/       web-fetched user meme library (same dir as state)
```

**Scheduled tick flow** (`references/enforcer.md:5-21`, code path `scripts/tick_check.py:16-31`):
1. Host cron wakes the agent with the canonical prompt (`docs/host-hermes.md:21`, spec PRD §5.2).
2. `python3 scripts/tick_check.py --commit --now <ISO+offset>` → `ensure_state` → `load` → `plan_tick` (pure) → `commit_tick` (mutating) → `save` (atomic) → prints one line `{"now":…,"actions":[…]}`.
3. Empty `actions` → say nothing at all.
4. Per action: pick template from `references/personas.md` (avoid `persona_state.recent_templates` last 5) → fill `action.slots` → pick image by `action.mood` via `references/meme.md` → merge multiple actions into ≤2 messages ordered `level_down → nudge → weekly_report`.
5. `daily_close` is silent bookkeeping: no message, no mood, never rendered (the streak was already zeroed during `--commit`).

**Instant check-in flow** (`references/checkin.md:10-17`, 8 intent rows): resolve intent → `find_habit` → `apply_checkin(state, habit_id, day, note, proof, now)` → `save()` → `validate()` self-check → persona reply. Every write is: mutate in-memory dict → `save()` (temp + `os.replace`) → `validate`; a non-empty error list means the write failed and must be rolled back (`references/state-schema.md:64-66`, `SKILL.md:24`). Same-day duplicate, future date, makeup without a freeze ticket, and unknown habit are rejected via a returned `{"ok": False, "reason": …}` dict, not exceptions.

**Fail-closed gating** (all enforced in `plan_tick`, `scripts/state.py:276-333`): quiet hours block `nudge`/`level_down`/`weekly_report`; per-habit per-day nudge cap 4; already-checked-in days emit nothing; already-sent stages are suppressed via `nudge_state`. `daily_close` is deliberately exempt from quiet hours and is the only mood-less action.

## Key Directories

| Path | Contents / purpose |
|---|---|
| `SKILL.md` | Skill entry point: frontmatter (exactly `name` + `description`), flow router, 3 hard constraints, scripts table. Keep folder name `peck-skill` (the description is the auto-trigger contract). |
| `references/` | LLM behavior protocol — `checkin.md` (intents), `enforcer.md` (6-step tick), `meme.md` (image/degrade), `personas.md` (template pool), `escalation.md` (operator restatement of PRD §4.2), `state-schema.md`. Prose here is a runtime contract, not documentation. |
| `scripts/` | Stdlib-only Python. `state.py` (406 lines, the whole engine) plus thin CLIs `tick_check.py`, `validate_state.py`, `gen_placeholder_memes.py`, and `save_meme.py` (importable `save_meme()` core + argparse `main()`). |
| `assets/memes/` | `_index.json` (flat array `{file,mood,caption,tags}`) + 6 fixed mood dirs (`urge praise disappointed angry cute celebrate`), one placeholder SVG each + `user/` drop-in dir. |
| `tests/` | 4 stdlib `unittest` modules (34 tests) against `scripts/state.py` and `scripts/save_meme.py`. |
| `docs/` | `host-hermes.md` (wiring + 10-minute acceptance checklist), `state-schema.md` (schema copy + manual checklist), `superpowers/plans/…m1.md` (historical plan — see hazards). |
| `prd.md` | PRD v1.2, self-declared authority, but contains stale M1/M2 and `no_response_days` statements — code + tests + README win on conflict. |

## Development Commands

No build, no install, no dev server. Everything is `python3` + stdlib.

```bash
# Full test suite (27 tests, ~0.01s) — run from repo root
python3 -m unittest discover tests -v
env -u PECK_SKILL_STATE python3 -m unittest discover tests -v   # hermetic: ambient env var breaks one test
python3 -m unittest tests.test_tick -v                          # single module

# State schema self-check: prints OK / exit 0, else error list / exit 1
python3 scripts/validate_state.py
python3 scripts/validate_state.py /tmp/peck/habits.json

# Tick engine: dry run (prints actions, writes nothing) then commit
python3 scripts/tick_check.py --now "2026-09-21T07:00:00+08:00"
python3 scripts/tick_check.py --commit

# Regenerate placeholder memes (idempotent; overwrites assets/memes/<mood>/01.svg)
python3 scripts/gen_placeholder_memes.py

# Sandbox a scratch state file instead of the real ~/.peck-skill/habits.json
PECK_SKILL_STATE=/tmp/peck/habits.json python3 scripts/tick_check.py --now "2026-09-21T07:00:00+08:00"
```

`--now` **must** carry a timezone offset (naive value → `sys.exit` with the message at `scripts/tick_check.py:22`); omit it to use the wall clock. `tick_check.py --state` auto-creates a missing file, while `validate_state.py <missing path>` raises a raw `FileNotFoundError` — different behavior for the same mistake.

Install / host wiring (verified text in README.md:14-21, `docs/host-hermes.md:5-30`):

```bash
cp -r <peck-skill 目录> ~/.hermes/skills/peck-skill
ls ~/.hermes/skills/peck-skill/SKILL.md
/cron add "every 30m" "执行习惯监督 tick：运行 python3 ~/.hermes/skills/peck-skill/scripts/tick_check.py --commit，然后按 peck-skill 技能 references/enforcer.md 的协议处理输出；actions 为空则保持沉默。若 actions 里出现 daily_close，那是静默记账——不发任何消息、不配图。" --skill peck-skill
```

## Code Conventions & Common Patterns

**Environment discipline.** `scripts/*.py` uses stdlib only (`json os tempfile datetime zoneinfo argparse sys`) — never add a dependency; the constraint exists because the host environment cannot assume `pip` (`docs/superpowers/plans/2026-09-20-peck-food-m1.md:15`). No `pyproject.toml`/`requirements.txt`/lockfile/CI is intentional; adding one would imply pip-installability that does not exist.

**Python style in `scripts/`.** No type annotations, no dataclasses, no walrus, no `match`, no `logging`, no `raise`/`assert` in scripts. `snake_case`, private helpers `_`-prefixed, one-line `def`s and guards, Chinese comments that cite PRD sections, module section banners `# ---- … ----`. `argparse` only in `tick_check.py` (`validate_state.py` uses bare `sys.argv[1]`). Error handling: returned rejection dicts inside the domain (`_reject`, `state.py:130`), `sys.exit(msg)` for CLI misuse; nearly everything else propagates. I/O always `encoding="utf-8"`, JSON written `ensure_ascii=False, indent=2`.

**Pure vs mutating split (load-bearing).** `plan_tick` is pure and reads the idempotency maps with `.get`; `commit_tick` mutates and uses `setdefault`. Swapping those breaks dry-run purity — dry runs intentionally skip `reset_monthly_freeze`, `no_response_days` increments, and `records` pruning (all live only in `commit_tick`). `apply_checkin` never writes; the caller must `save`.

**Constants and enum ordering.** All tunables live as module constants at `scripts/state.py:179-186` (none are config): `STAGES_STRICT = ["remind","first","warn","final"]`, `STAGES_CHILL = ["remind","lastcall"]`, `DAILY_NUDGE_CAP = 4`, `TICK_GRID_MIN = 30`, `DAY_CLOSE_TIME = time(23,30)`, `HISTORY_DAYS = 90`, `TICK_LOG_KEEP = 50`, `GLOBAL_KEY_ID = "global"`. Order in the stage lists encodes priority; `commit_tick` marks sent stages by `index()`, `_due_rounds` uses index order to skip lower-priority backlog. Reordering either list in isolation silently changes which nudges are suppressed.

**Idempotency & time.** Idempotency keys are `nudge_state.per_habit_day["<habit_id>@<YYYY-MM-DD>"] = {"count": int, "stages": [str]}` plus the pseudo-habit `global@<date>` for reports; non-nudge action types are recorded as stage names in the same list. `count` increments only for `nudge`. Every datetime is derived from `state["user"]["timezone"]` via `ZoneInfo`; naive datetimes are never persisted (offset-bearing ISO strings only).

**Prose conventions (`references/*.md`) — strings are keys, not text.**
- Route only through the existing three files; `escalation.md` and `personas.md` are currently reachable only from `prd.md:107` and `references/enforcer.md:10`.
- Stage names (`remind first warn final lastcall`), the six mood values (`urge praise disappointed angry cute celebrate`), slot variables (`{{name}} {{habit}} {{streak}} {{deadline}} {{week_rate}}`), and file paths are frozen (`escalation.md:95`: 不得改名、不得新增). Renaming any of them silently desyncs prose from `scripts/state.py`.
- A template's identity = the first 12 characters after `- ` (`references/personas.md:6-8`), persisted into live user state as `persona_state.recent_templates`. Rewording the **head** of a template line (including the `[首日]` tag) invalidates stored ids.
- `references/checkin.md` and `references/enforcer.md` are the protocol of record; `docs/host-hermes.md:62` itself says the reference files outrank its summary.

**Editing hazards.**
1. **Spec duplication.** The state schema JSON exists three times (`prd.md:130-178`, `references/state-schema.md:10-58`, `docs/state-schema.md:11-59`), and the tick/intent/meme protocols are restated in the historical plan. Edit every copy in the same change.
2. **`references/state-schema.md` is stale relative to `docs/state-schema.md`** (which self-describes as its copy): the reference lacks the `plan_tick`/`commit_tick` action contract, and its JSONC still shows scalar `"no_response_days": 0` while the code and both docs' own notes require a `habit_id → int` map. Implemented truth: `scripts/state.py:17,341,378-380`; the docs' 15-item checklist is far stricter than `validate()` (which checks ~4 items and never checks `version`), and `tick_check.py` never calls `validate()` at all.
3. **`daily_close`'s quiet-hours exemption is intentional** (`scripts/state.py:312-318` omits `not quiet`). "Fixing" it re-introduces late-night messages.
4. **Breaker semantics ride on `tick_log`.** `no_response_days` advances only on the day's first *committed* tick, detected by `str(entry["ts"])[:10]` matching today (`state.py:343-344`). Changing the `ts` format or log retention changes downgrade behavior.
5. **`commit_tick` assumes schema-valid habits** (indexes `a["slots"]`, `h["stats"]["current_streak"]`). A hand-edited state that passes the weak `validate()` can still traceback.
6. **Test-file trap:** `tests/test_state.py:32-33` has `if __name__ == "__main__": unittest.main()` **mid-file**, so `python3 tests/test_state.py` runs 5 of 8 tests and exits 0. Never document direct-script invocation; if you touch the file, move that block to EOF (or delete it — `-m unittest` does not need it).
7. **Test env trap:** `PECK_SKILL_STATE` is only popped in `tearDown`, so an ambient value fails `test_default_is_home_dotfile` (runs first). Use `env -u PECK_SKILL_STATE`, or add a `setUp` pop.
8. **Keep `tests/__init__.py`** (empty; it is what makes `tests.test_x` and `discover tests` resolve) and never add a repo-local `state/` directory — state belongs outside the skill dir so the folder stays host-replaceable.
9. **Fixture/schema lockstep:** adding a key to `REQUIRED_TOP/USER/HABIT` (`scripts/state.py:5-10`) requires updating `empty_state` **and** both `mkstate()` helpers (`tests/test_tick.py:9-17`, `tests/test_checkin.py:9-17`).
10. **Do not "correct" these stale artifacts to match each other:** `prd.md` §7 lists 熔断/补卡券 as M2 (they are shipped, per README.md:43 and the tests) and a 21:30 daily report as M1 (M1's day-end is 23:30 silent `daily_close`); `prd.md:278` references a nonexistent `references/achievements.md`; `docs/superpowers/plans/2026-09-20-peck-food-m1.md` is a completed plan for a superseded three-skill layout (`peck-food`, `skills/*`, repo-root `state/habits.json`) — history, not spec. PRD section numbering (`§3.3 §4.2 §4.5 §5.2 §7 §8`) is cited by other files; never renumber, bump the version line at `prd.md:3` instead.
11. `gen_placeholder_memes.py` overwrites `assets/memes/<mood>/01.svg` unconditionally but never touches `user/` — round-tripping it destroys hand-edited placeholders.

## Important Files

| File | Why it matters |
|---|---|
| `scripts/state.py` | The engine and the only place deterministic behavior lives: schema + `validate` (21), atomic `load`/`save` (39/42), `find_habit` (71), `is_due` (86), `recompute_streak` (105), `apply_checkin` (133), `reset_monthly_freeze` (168), constants (179-186), quiet-hours math (188-214), round tables (216-255), `plan_tick` (276), `commit_tick` (335), `default_state_path`/`ensure_state` (392/400). No `__main__`. |
| `scripts/tick_check.py` | Tick CLI + JSON stdout contract (`{"now","actions"}`); the only script the cron prompt calls. |
| `scripts/validate_state.py` | Post-mutation self-check required by `SKILL.md:24`. |
| `SKILL.md` | Frontmatter `description` is the auto-trigger surface for both flows; router at lines 14-18. |
| `references/enforcer.md`, `references/checkin.md`, `references/meme.md` | The three routed protocols. Everything else in `references/` hangs off them. |
| `docs/state-schema.md` | Superset of `references/state-schema.md`: adds the tick action contract and the manual checklist. |
| `docs/host-hermes.md` | Wiring + the 9-step manual acceptance checklist (lines 32-48) that automated tests do not cover. |
| `tests/test_tick.py`, `tests/test_checkin.py`, `tests/test_state.py` | Executable spec of the tier ladder, idempotency, quiet hours, breaker, makeup, streak. |
| `assets/memes/_index.json` | Meme lookup index; flat `{file,mood,caption,tags}` array over the 6 fixed mood dirs. |
| `prd.md` | Authority for product intent (H1-H4, hard constraints, acceptance scenarios) — but treat its M1/M2 tables and schema JSON as stale where they conflict with code/README. |

## Runtime/Tooling Preferences

- **Runtime:** Python **3.9+** — the real floor is `zoneinfo` (`scripts/state.py:3`, `scripts/tick_check.py:3`, tests). Verified locally on 3.11. `ZoneInfo("Asia/Shanghai")` requires tzdata on the host.
- **Dependencies:** none. Zero third-party runtime and test deps; no package manager, lockfile, build backend, Makefile, or CI workflow anywhere in the repo. Do not add one.
- **State location is load-bearing** and must be changed in lockstep across `scripts/state.py:392-397`, `SKILL.md:12`, `README.md:23`, `references/checkin.md:3`, `references/enforcer.md:6`, `docs/host-hermes.md:16`, `prd.md:128`, and `tests/test_state.py:40-48`: `~/.peck-skill/habits.json` with `PECK_SKILL_STATE` override. Legacy names (`PECK_FOOD_STATE`, `~/.peck-food/`) must not reappear outside the historical plan.
- **Commits:** Conventional Commits with Chinese subjects, prefix + `——`-separated detail (e.g. `fix: 窄窗口 warn 名义时刻防倒序…`); types seen: `feat fix docs refactor test chore`. Default branch `main`.
- **Skill packaging constraint:** `SKILL.md` frontmatter must stay exactly `name` + `description`; the folder name `peck-skill` must be preserved (docs/host-hermes.md:14).
- **Images are an enhancement, never a dependency** (PRD §6): the kaomoji fallback must keep working with `assets/memes/` renamed away. Keyword web meme search IS enabled (meme.md step 4, via `save_meme.py`); dedicated API providers (Giphy/ALAPI) remain M2. The web-search tier must degrade silently to kaomoji on any failure — never traceback into the reply flow.

## Testing & QA

**Framework:** stdlib `unittest`. 27 tests — `test_state.py` 8, `test_tick.py` 12, `test_checkin.py` 7 — all green in ~0.01s. No pytest config, no `conftest.py`, no CI; pytest is undeclared and must not be presented as the runner.

```bash
python3 -m unittest discover tests -v                          # full suite, from repo root
env -u PECK_SKILL_STATE python3 -m unittest discover tests -v  # preferred (hermetic)
python3 -m unittest tests.test_tick -v                         # per module
```

**Hermetic policy:** no network, no mocks, no subprocess, no fixture files. Every test imports `scripts/state.py` through a per-file `sys.path.insert(0, …/scripts)` hack (duplicated in all three files, plus the same idiom in the two CLIs). Time is **injected**, never frozen: `plan_tick`/`commit_tick`/`apply_checkin` take an explicit `now`, and tests build literal tz-aware datetimes (`tests/test_tick.py:8,19`). Disk-touching tests use `tempfile.TemporaryDirectory()`; the real `~/.peck-skill/habits.json` is never read or written.

**Corpora:** none — fixtures are inline. Add a case by adding a `test_*` method to the existing class and mutating the output of the file-local `mkstate()` (`tests/test_tick.py:9-17` strict ladder fixture; `tests/test_checkin.py:9-17` permissive 7-day fixture), then override e.g. `st["habits"][0]["schedule"]["window"] = ["21:00","23:00"]`. New cases go next to the behavior they extend; `test_*_snake_case` names state behavior, and Chinese inline comments cite the PRD clause that motivates the case.

**Load-bearing test constants:** `2026-09-21` must stay a Monday and `2026-09-26` a Saturday; window ends and tick times are chosen relative to `DAY_CLOSE_TIME = 23:30` and quiet hours `22:30–07:00`, so moving a tick time silently changes what `test_daily_cap_four` / the `daily_close` tests prove. Some error strings are contract: `"already checked in"` is asserted verbatim (`tests/test_checkin.py:40` ← `scripts/state.py:144`).

**Known coverage gaps** (do not claim these are tested): the three CLIs, `reset_monthly_freeze` (never imported by tests), `validate`'s user/window/level branches, `commit_tick` housekeeping (tick_log trim, 90-day prune, breaker counter write-back), the strict/Sunday weekly-report branch, `free`-level short-circuit, `is_due`'s weekday filter, `require_proof` semantics, and `_in_quiet`'s non-crossing configuration.

**Beyond the suite:** `docs/host-hermes.md:32-48` holds the 9-step manual acceptance checklist (create habit → remind/first/warn/final chain → check-in → silent day-end → breaker downgrade → makeup coupon → meme degrade with `assets/memes/` renamed → schema validation exit code). Run it for any change that touches the tick ladder, persona output, or the meme protocol; unit tests cannot cover rendered messages.
