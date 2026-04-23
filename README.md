# Sec-Agent-Harness 🛡️

A high-performance, FSM-driven Agent Harness for automated security vulnerability analysis and remediation.

## 🚀 Overview
Sec-Agent-Harness is designed to solve the challenges of LLMs getting "lost" in long-cycle security tasks. By combining a strict **Finite State Machine (FSM)** with **Neural-Symbolic reasoning** and **Defensive Sandboxing**, it provides a reliable pipeline for discovering, validating, and fixing code vulnerabilities.

## 🏗️ Core Architecture
- **FSM Backbone**: Manages state transitions between `INITIAL_ANALYSIS`, `VALIDATOR`, `FIXER`, and `REVIEWER`.
- **Hybrid Runtime**: Kernel-mode skills (e.g., AST scanning) for low-latency analysis.
- **Context Compaction**: A Blackboard-based system to keep the LLM's context window clean and focused.
- **Secure Sandbox**: Docker-based isolation for safe execution of PoCs and regression tests.

## 📂 Documentation Map
All project documentation is organized within the `docs/` directory:

### 📖 For Users & Contributors
- **[Development Guide](docs/agent-guide/DEVELOPMENT_GUIDE.md)**: Guidelines for contributing and maintaining system robustness.

### 🛠️ Technical Design
- **[Project Overview](docs/design/PROJECT_OVERVIEW.md)**: High-level goals and implementation status. ([中文版](docs/design/PROJECT_OVERVIEW_ZH.md))
- **[Development Strategy](docs/design/STRATEGY.md)**: Vision and phased implementation plan. ([中文版](docs/design/STRATEGY_ZH.md))
- **[Detailed Architecture](docs/design/architecture.md)**: Mermaid diagrams of internal loops and module interactions.
- **[Module Documentation](docs/design/modules.md)**: Technical breakdown of core and skill systems. ([中文版](docs/design/modules_zh.md))

## 🚦 Getting Started
1. **Configure Environment**: Copy `.env.example` to `.env` and fill in your LLM API credentials.
2. **Start the Harness**:
   ```bash
   python main.py
   ```
3. **Run a Challenge**: Use the `challenge/` directory to test the agent against real-world vulnerability scenarios.

---
"Building a safer world, one autonomous patch at a time."
