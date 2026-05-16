# Sec-Agent-Harness: Agent 评测体系实习生对齐与演进计划

这份文档旨在将当前 `Sec-Agent-Harness` 项目的发展方向与 **Code Agent 评测实习生** 的核心岗位职责进行深度对齐。本项目本身就是一个完整的 Agent Harness，通过执行以下计划，不仅能推动项目的迭代，也能完美覆盖实习岗位的核心能力要求。

---

## 1. 设计和构建 Code Agent 评测体系（Harness）
**岗位要求**：包括 benchmark 设计、评测 pipeline 搭建、指标定义与分析。

**本项目演进计划**：
- **Benchmark 设计（集成 SEC-bench）**：
  - 参考 `SEC-bench` 的多代理自动化生成流程，从 OSV 和 CVE 数据库中提取真实的漏洞实例。
  - **SecRepairBench 演进**：不仅包含 `challenge/` 下的合成漏洞，还要通过脚本自动拉取 `SEC-bench` 中的验证实例（如 OpenJPEG, GPAC 的真实 CVE），构建一个包含“合成+真实”两个维度的混合评测集。
- **评测 Pipeline 搭建**：在 `scripts/run_vulrepair_benchmark.py` 的基础上，搭建全自动化的并行评测 Pipeline。同时对接 `SEC-bench` 提供的 Docker 镜像体系，确保 `Sec-Agent-Harness` 的驱动引擎能无缝启动 `SEC-bench` 的评估镜像。
- **指标定义与分析 (Metrics)**：
  - **Pass@k**：生成的补丁在 $k$ 次尝试内通过 Sandbox 所有测试用例的概率。
  - **Turn-to-Fix (TTF)**：成功修复所需的平均交互轮数。
  - **PoC-to-Patch 相关性分析**：参考 `SEC-bench` 的方法论，评估 Agent 生成 PoC 的能力与其最终修复漏洞成功率之间的强关联性。

## 2. 搭建端到端的 Agent 能力评估环境
**岗位要求**：sandbox 隔离、代码执行、多轮交互评测。

**本项目演进计划**：
- **现况总结**：项目已在 `core/sandbox.py` 中实现了基于 Docker 的安全沙箱，支持超时限制和资源隔离。核心引擎 `core/loop.py` 支持多轮交互。
- **改进方案**：
  - **多语言沙箱扩展**：目前主要针对 Python/C，计划引入多镜像环境支持（Java, Go, JS），允许 Agent 动态选择运行环境。
  - **交互环境可视化**：完善日志拦截与输出机制，搭建一个简单的本地 Web Dashboard，用于回放 Agent 与环境的每一轮交互（CLI 输出、代码修改、沙箱返回）。

## 3. 分析 Agent 行为 trace，挖掘 bad pattern，驱动 prompt/策略优化
**岗位要求**：分析 Agent 行为 trace，挖掘 bad pattern，驱动 prompt/策略优化。

**本项目演进计划**：
- **Trace 日志体系**：项目已实现 `logs/agent_session_*.log` 全量记录（包含 System Prompt、LLM 返回、Tool Call、沙箱输出）。
- **Bad Pattern 挖掘专项**：
  - **循环试错 (Looping)**：Agent 在沙箱测试失败后，反复生成相同的错误代码。
  - **工具滥用 (Tool Misuse)**：在不需要深度扫描时反复调用 CodeQL 等重型工具。
  - **幻觉断言 (Hallucinated Success)**：无视错误日志，强行声称漏洞已修复。
- **Prompt 与策略驱动**：根据挖掘出的 Pattern，利用 `core/hook.py` 系统中的 `POST_TOOL_USE` 钩子动态注入 `[SYSTEM ADVICE]`，或对 FSM 各状态的 System Prompt 进行针对性消偏（De-biasing）。

## 4. 探索 Agent 能力的细粒度拆解
**岗位要求**：探索 Agent 能力的细粒度拆解。

**本项目演进计划**：
- **能力维度解耦**：在 `Sec-Agent-Harness` 中，我们将 Agent 的核心能力拆解为以下微维度进行独立测评：
  - **代码感知能力 (Code Perception)**：评估 `ast_scanner` 提取代码结构的准确性。
  - **因果推理能力 (Causal Reasoning)**：在 `INITIAL_ANALYSIS` 阶段，Agent 对漏洞根因分析的准确度。
  - **测试编写能力 (PoC Generation)**：在 `VALIDATOR` 阶段，Agent 根据漏洞点生成复现代码的能力。
  - **代码修复能力 (Patch Generation)**：在 `FIXER` 阶段，生成的补丁是否具备防御深度的能力。
- **基于拆解的评测**：不只看最终修复成功率，而是为上述每个阶段设定独立的检查点（Checkpoints），识别 Agent 究竟在哪一步“掉链子”。

## 5. 调研和复现前沿 Agent 评测框架，提出改进方案
**岗位要求**：调研和复现前沿 Agent 评测框架，提出改进方案。

**本项目演进计划**：
- **前沿框架深度调研**：重点复现 **SEC-bench** (NeurIPS 2024/2025)。
  - **复现任务**：在本地环境搭建 `SEC-bench` 全套流水线，测试其支持的 `smolagents` 或 `SWE-agent` 在安全任务上的基准表现。
  - **改进方案**：对比测试 `Sec-Agent-Harness` 的“FSM 状态机约束”机制与 `SEC-bench` 中原生 Agent 的表现差异，验证状态隔离在解决复杂 C/C++ 内存漏洞时的优势。
- **竞品对标**：同时复现 **SWE-bench**, **HumanEval**, **DevBench** 等框架，总结 `SEC-bench` 在安全垂直领域（如 PoC 验证）的独特竞争力并提取可借鉴的评估算子。

## 6. 参与 Code Agent 产品的 dogfood 测试和真实场景评估
**岗位要求**：参与 Code Agent 产品的 dogfood 测试和真实场景评估。

**本项目演进计划**：
- **Dogfooding (吃狗粮)**：将 `Sec-Agent-Harness` 部署到日常开发流中。让项目自身的 Bug 或新增特性（如重构 `hook.py`）交由 Agent 自己来 review 和修复。
- **真实场景评估**：导入一些真实的开源项目 CVE，观察 Agent 是否能在包含数万行代码的真实工程中，定位到隐藏的漏洞，而非仅仅在 `challenge/` 下的 Demo 代码里生效。

---
**结语**：
`Sec-Agent-Harness` 不仅仅是一个安全 Agent，它在架构设计上天然就是一个**完备的代码 Agent 评测 Harness**。沿着上述计划推进，将全方位覆盖评测体系搭建、Trace 分析、沙箱工程以及前沿探索，是展示相关工程与研究能力的绝佳载体。
