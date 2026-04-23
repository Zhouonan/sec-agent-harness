# Sec-Agent-Harness Development Strategy

## Vision
To build a high-performance Agent system specialized for complex logic vulnerability discovery and autonomous repair. It combines the flexible Harness architecture of "Claude Code" with professional security logic (e.g., taint analysis, constraint solving, isolated sandboxing).

## Implementation Phases (Iterative)

### Phase 1: Infrastructure (Core Loop & Skill System)
- **Goal**: Implement core functionalities similar to `s01-s05` in `learn-claude-code`.
- **Components**:
    - **Minimal Loop**: A robust "message-tool-result" closed loop.
    - **Kernel-mode Skill Registry**: A mechanism to load high-performance security tools (e.g., AST parsers, CFG builders) in-process to avoid RPC/serialization overhead.
    - **Basic Context Management**: Initial implementation of message pruning and compaction.

### Phase 2: Security Specialization (Sandbox & Taint Analysis)
- **Goal**: Introduce a defensive execution environment and symbolic reasoning capabilities.
- **Components**:
    - **Defensive Sandbox**: Isolated environment based on Docker or E2B for running generated PoCs or test cases.
    - **Taint-driven Reasoning**: A "Skill" that guides the LLM through structured JSON rules for data flow tracing.

### Phase 3: Multi-Agent & State Machine (Final Goal)
- **Goal**: Orchestrate multiple specialized agents working together.
- **Components**:
    - **FSM Orchestrator**: Automatic transitions between states: "Static Analysis", "Vulnerability Validation", "Fixer", and "Reviewer".
    - **Pointer-based Context Compaction**: Using `Persisted Output Markers` to pass heavy analysis results between Agents without consuming Token space.

## Current Tasks
- [x] Implement `core/loop.py` based on `learn-claude-code/s01`.
- [x] Define `core/skill.py` for kernel-mode skill loading.
- [x] Create prototype templates for "Taint Analysis Skill".
- [x] Implement basic sandbox tool class (`core/sandbox.py`).
- [x] Implement multi-state FSM orchestration logic and backtracking.
- [ ] Implement local execution fallback for Docker dependency.

## Architectural Decision (Logic Chain)

After exploring three technical directions (FSM Orchestration, Neural-Symbolic Engine, Dynamic Feedback Sandbox), we established the **"Unified Sec-Agent Harness"** architecture:

1. **FSM Backbone (Control & Resilience):** Pure LLMs tend to get lost in long-cycle tasks. We use a structured Finite State Machine to enforce deterministic state transitions and circuit breakers.
2. **Neural-Symbolic Nodes (Precision Targeting):** Pure LLMs can hallucinate during initial analysis. We inject "Kernel-mode AST analysis skills" to allow the LLM to output structured JSON rules executed by underlying static engines.
3. **Dynamic Sandbox Nodes (Real-world Feedback):** Static analysis cannot prove exploitability or guarantee that a fix won't break business logic. We execute PoCs and patches in isolated Docker sandboxes to provide closed-loop feedback.

**Logic Chain Summary:** FSM provides the **global control boundary** -> Neural-Symbolic cooperation provides **high-precision static targets** -> Dynamic isolated sandbox provides **closed-loop feedback based on real execution**.
