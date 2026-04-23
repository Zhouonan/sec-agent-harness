# Sec-Agent-Harness: Technical Handover (Agent-to-Agent)

## 1. Core Component Status
- **FSM Loop (`core/loop.py`)**: 
    - **UPGRADED**: Loop logic now includes a "Nudge" mechanism to prevent premature exit.
    - **HARDENED**: `transition_handler` now enforces strict exit rules. Only `REVIEWER` can transition to `DONE`. Direct jumps from `FIXER` or `VALIDATOR` to `DONE` are blocked.
    - **VALIDATED**: Logic gates now prevent forward transitions if the last tool call failed, forcing the agent to resolve errors locally.
- **Observability & Debugging**:
    - **NEW**: Full prompt tracing. Every turn's System Prompt and tool input are printed to the console and archived in `logs/`.
    - **NEW**: Live Sandbox Streaming. Raw command outputs (stdout/stderr) are now visible in the console during execution.
    - **NEW**: Session Logging. Every run creates a timestamped log in the `logs/` directory for post-mortem analysis.
- **Hook System (`core/hook.py`)**:
    - **NEW**: Implemented a comprehensive, event-driven Hook system. Supports `SESSION_START`, `PRE_TOOL_USE`, and `POST_TOOL_USE`.
    - **MODULAR**: Hardcoded FSM safety checks and sandbox failure diagnostics have been decoupled into `hooks/builtin_logic.py`.
    - **DYNAMIC**: The system automatically loads all `.py` files from the `hooks/` directory at startup.
- **Taint Analysis Skill (`skills/taint_analysis`)**:
    - **UPGRADED**: Evolved from mock to a **Hybrid Engine**.
    - **PRIMARY**: CodeQL for deep, semantic whole-program data-flow analysis.
    - **FALLBACK**: Semgrep for agile, pattern-based taint tracking (supports dynamic rule generation).
- **Self-Healing Mechanics (via Hooks)**:
    - **Context Snapshot**: `hooks/diagnostic_tools.py` automatically injects environment snapshots (PWD, LS) upon sandbox failures.
    - **Tactical Recovery**: `hooks/recovery_logic.py` breaks failure loops by forcing a transition to `INITIAL_ANALYSIS` after 3 consecutive errors.
- **Sandbox Environment (`core/sandbox.py`)**:
    - **UPGRADED**: Implemented `LOCAL_EXECUTION_FALLBACK`.
    - **SMART ADVICE**: Diagnostics for failed commands are now injected via the `system_advice_hook`.

## 2. Architectural Guardrails
- **Exit Criteria**: Transitioning to `DONE` requires a `success` status on the blackboard (enforced by `fsm_safety_hook`).
- **Path Integrity**: Hooks now block illegal state jumps (e.g., `FIXER -> DONE`) without going through `REVIEWER`.
- **Loop Resistance**: Automatic state resets (Backtracking) prevent Agents from staying stuck in a failing state indefinitely.

## 3. Immediate Technical Backlog
- **Hybrid Hook Support**: Extend `HookRegistry` to support external Shell/Go scripts as hooks (Option C).
- **Procedural Evolution (Phase 4)**: Implement a `Post-Mortem` mechanism to generate project-specific rules (`rules.md`) after each session.
- **Sub-agent Spawning**: Implement a `spawn_inspector` tool for deep diagnostic analysis of complex errors.

## 4. Advice for the Incoming Agent
> "The system is now much more 'vocal'. You can see exactly what the LLM is thinking and what the sandbox is returning. If the agent gets stuck in a loop, check the `logs/` to see if it's ignoring the `[SYSTEM ADVICE]`. The FSM backdoors are closed—don't try to jump to `DONE` without a passing test from the `REVIEWER` state."
