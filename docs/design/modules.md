# Sec-Agent-Harness: Module Documentation

This document provides a detailed technical breakdown of the core modules in the Sec-Agent-Harness project.

---

## 1. Core Engine (`core/loop.py`)

The `core/loop.py` module is the "brain" of the agent. It implements a **Finite State Machine (FSM)** to manage complex security workflows.

### 1.1 AgentState (Enum)
Defines the lifecycle of a vulnerability mining and repair task:
- `INITIAL_ANALYSIS`: Codebase mapping and taint source/sink identification.
- `VALIDATOR`: Empirical verification of vulnerabilities via PoC generation and execution.
- `FIXER`: Patch generation for confirmed vulnerabilities.
- `REVIEWER`: Sandbox-based patch verification and regression testing.
- `DONE` / `ERROR`: Terminal states.

### 1.2 LoopState (Dataclass)
Maintains the runtime state of the agent:
- `messages`: Conversation history.
- `current_state`: The active `AgentState`.
- `blackboard`: A shared dictionary for **Context Compaction**. Instead of passing raw logs, agents store light-weight summaries (pointers/data) here.
- `state_turn_count`: Track turns per state to trigger **Circuit Breakers** (preventing infinite tool loops).

### 1.3 AgentLoop (Class)
The orchestrator that runs the turn-based loop:
- `transition_state` tool: Injected into every state, allowing the LLM to trigger state changes and update the blackboard.
- `run_one_turn`: Fetches the state-specific system prompt and tools, calls the LLM, and dispatches tool execution.

---

## 2. Skill System (`core/skill.py`)

The `core/skill.py` module manages specialized knowledge and high-performance tools ("Kernel-mode Skills").

### 2.1 SkillRegistry (Class)
- **Discovery**: Scans the `skills/` directory for `SKILL.md` files.
- **Two-Layer Loading**: 
    - *Layer 1*: Injects metadata (name/description) into the system prompt to let the agent know what skills are available.
    - *Layer 2*: Provides a `load_skill` tool to fetch the full instruction set only when needed, keeping the context window lean.
- **Kernel-mode Concept**: High-performance analyzers (like AST parsers) are designed to be loaded as in-process skills to eliminate RPC/serialization latency.

---

## 3. Data Flow & Interaction

1. **Query**: User provides a target codebase or task.
2. **Analysis**: `AgentLoop` starts in `INITIAL_ANALYSIS`. It uses the `SkillRegistry` to find security skills.
3. **Blackboard**: Analysis results are saved to the `blackboard`.
4. **Transition**: Agent calls `transition_state` to move to `VALIDATOR`.
5. **Sandbox**: (Planned) `VALIDATOR` uses sandbox tools to confirm the findings.
