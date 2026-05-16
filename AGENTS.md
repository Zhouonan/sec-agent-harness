# Sec-Agent-Harness: Project Development Guide

To ensure system robustness, maintainability, and seamless collaboration between Agents and human developers, all participants must strictly adhere to these protocols.

## 1. Fast Orientation

Sec-Agent-Harness is a Python security-agent harness built around a finite-state loop, dynamic skills, hooks, sandbox execution, and benchmark evaluation.

Start with these files:
- `main.py`: interactive shell entry point.
- `core/loop.py`: central FSM runtime, tool registration, blackboard compaction, LLM calls, hook dispatch, and turn loop.
- `core/skill.py`: dynamic loader for `skills/*/SKILL.md` manifests and optional `handler.py` tool handlers.
- `core/hook.py`: hook registry and `@hook(...)` decorator used by modules in `hooks/`.
- `core/sandbox.py`: Docker/local command execution boundary.
- `eval/cli.py`, `eval/runner.py`, `eval/orchestrator.py`: benchmark entry points and per-case execution flow.
- `tests/README.md`: test categories and command guidance.

Avoid spending early context on generated or benchmark payload directories unless the task specifically requires them:
- `challenge/runs/`
- `eval_results/`
- `logs/`
- `.pytest_cache/`
- `challenge/secbench_trials/*/mruby/`

## 2. Architecture Map

Runtime flow:
1. `main.py` creates `AgentLoop`.
2. `AgentLoop.__init__` loads config, sandbox, skills, AST scanner, core tools, skill tools, and hooks.
3. `AgentLoop.run()` creates `LoopState`, dispatches `SESSION_START`, then repeatedly calls `run_one_turn()`.
4. `run_one_turn()` builds the system prompt from the current FSM state, skill catalog, plan, and blackboard.
5. LLM tool calls are filtered through `PRE_TOOL_USE` hooks, executed by registered handlers, then enriched by `POST_TOOL_USE` hooks.
6. `transition_state` updates the FSM state, stores a blackboard summary, and compacts message history.
7. Terminal states are `DONE` and `ERROR`; `SESSION_END` hooks run before returning final state.

Main extension surfaces:
- Add or modify agent tools through `skills/<name>/SKILL.md` and `skills/<name>/handler.py`.
- Add guardrails, diagnostics, or recovery behavior through `hooks/*.py`.
- Add benchmark data under `challenge/` and expose it through `eval/datasets.py`.
- Add scoring/reporting behavior through `eval/scorer.py`, `eval/judge.py`, and `eval/reporter.py`.

## 3. Change-To-Test Map

- FSM, blackboard, turn limits, transition behavior: run `PYTHONPATH=. python3 -m pytest tests/test_fsm_loop.py tests/test_fsm_mock.py -v`.
- Hook behavior: run `PYTHONPATH=. python3 -m pytest tests/test_hook_system.py tests/test_adversarial_fsm.py -v`.
- Skill discovery or tool injection: run `PYTHONPATH=. python3 -m pytest tests/test_extensions.py tests/verify_hook_loading.py -v`.
- TODO/autonomy behavior: run `PYTHONPATH=. python3 -m pytest tests/test_todo_*.py -v`.
- Broad local check: run `make test`.
- Benchmark smoke check, if API credentials and sandbox are configured: run `make eval-mini`.

Use `make check` only when an LLM-backed mini benchmark is intended; it runs both unit tests and `eval-mini`.

## 4. The Sync Rule (Critical Habit)
- **Log Everything**: Major logic changes, new features, or bug fixes **MUST** be recorded in `AGENT_ACTIVITY_LOG.md`.
- **Test Before Commit**: Every new feature or edge-case fix must be validated with corresponding test cases.
- **Doc Sync**: When modifying core interfaces or architecture, immediately update the relevant module descriptions in `docs/`.

## 5. FSM & Blackboard Protocol
- **Atomic Transitions**: State changes **MUST** be performed via the `transition_state` tool. Manual modification of `state.current_state` is forbidden.
- **Context Compaction**: Summaries stored on the Blackboard must be concise and high-signal. Do not dump raw logs directly.
- **Circuit Breaker Awareness**: Design all new states with turn limits in mind to ensure the system fails safely into `ERROR` state during anomalies.

## 6. Configuration Management
- **Secret Isolation**: Never hardcode API keys or credentials. Use `.env` (primary) or `config.yaml` (secondary).
- **Default Robustness**: `core/config.py` should always provide sensible defaults to ensure the system can run basic logic tests even when config files are missing.
- **External APIs**: Tests involving real LLM providers must remain optional and have offline/mock alternatives.

## 7. Testing Habits
- **Mock Dependencies**: All tests involving external APIs (e.g., OpenAI/Moonshot) must provide a Mock mechanism for offline verification.
- **Verbose Output**: Test scripts should support high verbosity to clearly visualize FSM paths and blackboard state changes.
- **Boundary Coverage**: Test beyond the "Happy Path." Always cover limits, invalid inputs, and timeouts.

## 8. Collaboration SOP
- **Handover Continuity**: Before ending a long session, update the active handoff or progress document if one exists for the current workstream.
- **Self-Documenting Code**: Use descriptive variable names and clear comments (English/Chinese) for complex logic.
- **Respect Existing Work**: The worktree may contain ongoing user edits. Do not revert unrelated files.

---
"Good code explains how; good documentation explains why."
