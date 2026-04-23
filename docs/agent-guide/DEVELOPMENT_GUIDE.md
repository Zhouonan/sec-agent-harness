# Sec-Agent-Harness: Project Development Guide

To ensure system robustness, maintainability, and seamless collaboration between Agents and human developers, all participants must strictly adhere to these protocols.

## 1. The Sync Rule (Critical Habit)
- **Log Everything**: Major logic changes, new features, or bug fixes **MUST** be recorded in `AGENT_ACTIVITY_LOG.md`.
- **Test Before Commit**: Every new feature or edge-case fix must be validated with corresponding test cases.
- **Doc Sync**: When modifying core interfaces or architecture, immediately update the relevant module descriptions in `docs/`.

## 2. FSM & Blackboard Protocol
- **Atomic Transitions**: State changes **MUST** be performed via the `transition_state` tool. Manual modification of `state.current_state` is forbidden.
- **Context Compaction**: Summaries stored on the Blackboard must be concise and high-signal. Do not dump raw logs directly.
- **Circuit Breaker Awareness**: Design all new states with turn limits in mind to ensure the system fails safely into `ERROR` state during anomalies.

## 3. Configuration Management
- **Secret Isolation**: Never hardcode API keys or credentials. Use `.env` (primary) or `config.yaml` (secondary).
- **Default Robustness**: `core/config.py` should always provide sensible defaults to ensure the system can run basic logic tests even when config files are missing.

## 4. Testing Habits
- **Mock Dependencies**: All tests involving external APIs (e.g., OpenAI/Moonshot) must provide a Mock mechanism for offline verification.
- **Verbose Output**: Test scripts should support high verbosity to clearly visualize FSM paths and blackboard state changes.
- **Boundary Coverage**: Test beyond the "Happy Path." Always cover limits, invalid inputs, and timeouts.

## 5. Collaboration SOP
- **Handover Continuity**: Before ending a session, update `HANDOVER.md` with current progress and next steps.
- **Self-Documenting Code**: Use descriptive variable names and clear comments (English/Chinese) for complex logic.

---
"Good code explains how; good documentation explains why."
