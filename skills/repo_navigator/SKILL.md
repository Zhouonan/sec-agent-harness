---
name: repo-navigator
description: Navigate the Sec-Agent-Harness repository efficiently before making architectural, FSM, hook, skill, sandbox, or evaluation changes.
tools: []
---
# Repo Navigator Skill

Use this skill when you need to understand or modify Sec-Agent-Harness itself. Its purpose is to reduce aimless file reading and keep attention on the right subsystem.

## First Pass

1. Read `AGENTS.md` for the current repo map and collaboration rules.
2. Read `README.md` only for high-level positioning and current documentation links.
3. Use `list_files` on the smallest relevant directory instead of scanning the whole repository.
4. Avoid generated or bulky benchmark payloads unless the task explicitly targets them:
   - `challenge/runs/`
   - `eval_results/`
   - `logs/`
   - `.pytest_cache/`
   - `challenge/secbench_trials/*/mruby/`

## Subsystem Routing

- FSM behavior, state transitions, blackboard, turn limits, prompt construction, or tool dispatch: start with `core/loop.py`.
- Skill loading, YAML frontmatter, dynamic tool registration, or handler discovery: start with `core/skill.py`, then inspect `skills/<name>/SKILL.md` and `skills/<name>/handler.py`.
- Hook registration, pre/post tool policy, diagnostics, recovery, or transition guardrails: start with `core/hook.py`, then inspect the matching file under `hooks/`.
- Sandbox execution, Docker behavior, local fallback, command timeout, or path isolation: start with `core/sandbox.py`.
- Config defaults, `.env`, `config.yaml`, or provider setup: start with `core/config.py`.
- Evaluation runs, datasets, scoring, reporting, or parallel benchmark execution: start with `eval/cli.py`, `eval/datasets.py`, `eval/runner.py`, and `eval/orchestrator.py`.
- Unit/adversarial behavior expectations: start with `tests/README.md`, then the most specific `tests/test_*.py` file.

## Test Selection

- After FSM or blackboard changes: run `PYTHONPATH=. python3 -m pytest tests/test_fsm_loop.py tests/test_fsm_mock.py -v`.
- After hook changes: run `PYTHONPATH=. python3 -m pytest tests/test_hook_system.py tests/test_adversarial_fsm.py -v`.
- After skill changes: run `PYTHONPATH=. python3 -m pytest tests/test_extensions.py tests/verify_hook_loading.py -v`.
- After TODO/autonomy changes: run `PYTHONPATH=. python3 -m pytest tests/test_todo_*.py -v`.
- For a broad offline check: run `make test`.
- For an LLM-backed benchmark smoke test, only when credentials and sandbox are configured: run `make eval-mini`.

## Modification Rules

- Preserve FSM transitions through the `transition_state` tool path; do not introduce direct state mutation patterns in agent-facing logic.
- Keep blackboard entries concise. Store summaries and structured status, not raw logs.
- Prefer hooks for policy, diagnostics, and recovery behavior that should wrap existing tools.
- Prefer skills for new agent-facing capabilities with a clear instruction/tool boundary.
- Keep external API tests mockable and offline-safe.
- Update `AGENT_ACTIVITY_LOG.md` for major behavior changes.
