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
- **[Agent Development Guide](AGENTS.md)**: Repository map, collaboration rules, and change-to-test guidance for agents and human contributors.
- **[Testing Guide](tests/README.md)**: Unit, adversarial, and integration test categories.
- **[Evaluation System](docs/EVALUATION_SYSTEM.md)**: Benchmark workflow and evaluation notes, when present in the current worktree.
- **[Evaluation System Plan](docs/plans/purring-tumbling-cocke.md)**: Design plan for the extensible evaluation module, LLM-as-Judge scoring, datasets, and reporting.

### 🛠️ Technical Design
- **[Hook System Design](docs/plans/hook-system-design.md)**: Hook architecture and intervention model.
- **[Skill System Upgrade Plan](docs/plans/skill_system_upgrade_plan.md)**: Skill architecture and planned improvements.
- **[General Intervention System](docs/plans/GENERAL_INTERVENTION_SYSTEM.md)**: Broader intervention and control design.
- **[Self-Healing Strategy](docs/design/SELF_HEALING_STRATEGY_2026.md)**: Recovery and self-healing strategy notes.
- **[VulRepair Test Plan](docs/plans/vulrepair_test_plan.md)**: Vulnerability repair benchmark plan.

### 📓 Progress & Teaching Notes
- **[Hook System Implementation](docs/progress/HOOK_SYSTEM_IMPLEMENTATION.md)** and **[Hook System Test Report](docs/progress/HOOK_SYSTEM_TEST_REPORT.md)**: implementation history and validation notes.
- **[Hybrid Taint Analysis](docs/progress/HYBRID_TAINT_ANALYSIS.md)**: static-analysis integration notes.
- **[Teaching Notes](docs/teaching/)**: explanatory writeups on FSM workflow, sandboxing, dynamic skills, prompt construction, and benchmarks.

## 🚦 Getting Started
1. **Configure Environment**: Copy `.env.example` to `.env` and fill in your LLM API credentials.
2. **Start the Harness**:
   ```bash
   python main.py
   ```
3. **Run a Challenge**: Use the `challenge/` directory to test the agent against real-world vulnerability scenarios.

---
"Building a safer world, one autonomous patch at a time."
