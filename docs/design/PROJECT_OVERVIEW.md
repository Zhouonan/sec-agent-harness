# Sec-Agent-Harness: Technical Design & Implementation Report

## 1. 概述 (Overview)
本项旨在构建一个面向复杂逻辑漏洞挖掘与自动修复的高性能 Agent 框架。参考 `learn-claude-code` 的分层设计，我们正在实现一个具备“混合运行时”和“内核态 Skill”能力的定制化 Harness。

The goal is to build a high-completion agent harness optimized for security research, emphasizing low-latency data processing (AST/CFG) and safe code execution (Sandboxing).

---

## 2. 设计哲学 (Design Philosophy)

### 2.1 Hybrid Runtime (混合运行时)
- **Kernel-mode Skills**: For heavy computation tasks (e.g., parsing 50MB ASTs), logic is executed in-process. This avoids the 1s+ serialization overhead of JSON-RPC/MCP and preserves object references.
- **Protocol-based Extension**: For non-critical external integrations (Slack, Jira), we utilize the **Model Context Protocol (MCP)** to maintain ecosystem compatibility.

### 2.2 Defensive Sandboxing (防御性沙箱)
- All generated PoCs, tests, and build commands are executed within an isolated environment (Docker/E2B) with strict resource quotas (CPU/Memory) to prevent side effects on the host.

### 2.3 Context Compaction (上下文压实)
- Instead of passing raw logs between Agent turns, we use **Persisted Output Markers** (Pointers). The LLM receives a lightweight summary and fetches the full content only when necessary.

---

## 3. 架构组件 (Architecture Components)

### 3.1 Core Harness (`core/`)
- **`loop.py` (The Engine)**: Implements the fundamental `Request -> Response -> Tool Use -> Result` cycle. It maintains history and ensures role-alternation integrity.
- **`skill.py` (The Registry)**: A two-layer loading mechanism.
    - *Layer 1*: Injects a summary of capabilities into the System Prompt.
    - *Layer 2*: Loads detailed instructions and specialized tools on-demand to keep the context window "lean".

### 3.2 Security Skills (`skills/`)
- **Taint Analysis**: Guided reasoning for mapping Sources to Sinks.
- **Vulnerability Validator**: (Planned) Symbolic execution and constraint solving to filter false positives.

---

## 4. 当前实现进度 (Current Progress)

| Component | Status | Description |
| :--- | :--- | :--- |
| **Agent Loop** | ✅ Completed | Robust class-based implementation in `core/loop.py` with API retry and "nudge" logic. |
| **Skill Registry** | ✅ Completed | On-demand loading logic implemented in `core/skill.py` with dynamic tool injection. |
| **Strategy Mapping**| ✅ Completed | Evolution path defined in `STRATEGY.md`. |
| **Taint Skill Stub**| 🚧 In Progress| Template created in `skills/taint_analysis/`. |
| **Sandbox Runtime** | ✅ Completed | Robust Docker-based secure isolation in `core/sandbox.py`. |
| **Multi-Agent FSM** | ✅ Completed | Orchestration logic for analysis-repair pipeline (INITIAL_ANALYSIS to REVIEWER) implemented. |

---

## 5. 后续计划 (Next Steps)

1. **Bootstrap the Sandbox**: Implement a `SandboxTool` that wraps shell commands inside a restricted container.
2. **Deep-Dive Static Analysis Skill**: Integrate a fast parser (e.g., tree-sitter) as a "Kernel-mode Skill" to provide the LLM with direct AST access.
3. **FSM Orchestration**: Define the state transitions between the *Static Analyst Agent* and the *Validator Agent*.

---
*Created on: 2026-04-14*
