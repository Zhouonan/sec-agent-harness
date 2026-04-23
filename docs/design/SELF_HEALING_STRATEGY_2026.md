# 高级 Agent 复杂错误自愈与持续进化方案 (2026 版)

## 1. 核心哲学：从“机械重试”转向“认知诊断”
在处理复杂错误（如逻辑矛盾、架构不匹配、依赖链崩溃）时，简单的正则匹配（如 `python -> python3`）是无能为力的。核心方案必须建立在 **“元认知（Metacognition）”** 之上——即 Agent 必须能够意识到“我的假设错了”，并主动开启诊断循环。

---

## 2. 三阶段自愈架构设计 (The Triple-Loop Architecture)

### 第一阶段：诊断钩子 (Diagnostic Hooks - `after_tool_call`)
**目标：提供比原始报错更丰富的“第一现场”信息。**
当复杂工具调用失败时，系统不应只返回 `stderr`，而应通过 Hook 自动执行以下操作：
- **现场快照 (Context Snapshot)**：自动追加当前目录结构、环境变量摘要、相关文件的最近修改记录。
- **引导式询问 (Guided Feedback)**：在错误信息后附加系统提示：“检测到逻辑冲突。请在下一次行动前，先执行 `Root Cause Analysis (RCA)`，解释为何之前的假设导致了此失败。”

### 第二阶段：回溯与重构 (Tactical Backtracking - `on_failure_loop`)
**目标：防止 Agent 在错误的路径上反复横跳（熔断死循环）。**
- **路径重评 (Path Re-evaluation)**：如果同一状态（如 `FIXER`）连续失败 3 次，系统 Hook 将强制清空该状态的局部记忆，并将 Agent 退回到 `INITIAL_ANALYSIS`。
- **带参回溯**：回溯时，将失败的尝试记录在 **Blackboard** 的 `failed_attempts` 字典中。强制 Agent 在新一轮分析中首句回答：“根据之前的失败记录（ID: XXX），我发现原来的路径 A 不可行，原因是 B，我现在将尝试路径 C。”

### 第三阶段：经验提炼 (Procedural Evolution - `Post-Mortem`)
**目标：实现“错不再犯”的长效记忆。**
- **自愈日志 (`MEMORY.md`)**：任务结束后（无论成功失败），触发一个隐藏的“提炼任务”。由一个轻量级模型回顾全过程，总结出：“在这个项目中，运行测试必须先执行脚本 X，否则会报 Y 错。”
- **规则注入**：将提炼出的规则存入项目根目录的 `.gemini/rules.md`。每次会话开始时，这些规则将作为 **High-Priority Context** 被注入到 System Prompt。

---

## 3. 处理复杂错误的四大高级策略

### 策略一：诊断子智能体 (Diagnostic Sub-agents)
当主循环（Main Loop）在修复一个复杂 Bug 连续失败时，主 Agent 可以调用 `spawn_inspector` 工具。
- **原理**：创建一个拥有**全新 Context 窗口**的子 Agent，只给它报错信息和相关代码，让它从第三方视角进行 Code Review。
- **收益**：打破主 Agent 的“思维惯性（Mental Tunneling）”。

### 策略二：反思性验证 (Reflective Verification)
在执行任何 `write_file` 之前，强制 Agent 调用 `predict_impact`（模拟执行）。
- **要求**：Agent 必须列出：“这次修改预期会通过测试 A，但可能会影响模块 B，我将通过运行测试 C 来验证我的担忧。”

### 策略三：多维环境感知 (Multi-dimensional Sensing)
复杂错误往往源于对环境的误判。
- **实施**：集成 `system_probe` 工具。当 Agent 感到困惑时，它可以查询系统的进程状态、端口占用、依赖库版本，甚至模拟一个迷你的测试环境来验证猜想。

### 策略四：分层记忆检索 (Tiered Memory Retrieval)
- **片段记忆 (Episodic)**：利用向量数据库存储过去所有的错误堆栈。
- **逻辑**：当当前错误与库中某个历史错误相似度 > 85% 时，Hook 自动弹出提示：“你在 3 天前的任务中也遇到过类似的报错，当时的解决方法是修改配置项 Z。”

---

## 4. 在 `sec-agent-harness` 中的落地路线图

### 短期 (1-2 天)：自愈基础
1.  **升级 `core/loop.py`**：在 `transition_handler` 中加入 `failure_counter`。
2.  **强化 Prompt**：加入 `Diagnostic Rules` 章节，明确告诉模型在遇到报错时必须先调用 `list_files` 或 `read_file` 重新评估，禁止直接重试。

### 中期 (3-5 天)：Hook 系统与自检
1.  **实现 `after_tool_call` Hook**：专门捕获复杂报错（如 `ImportError`, `LogicMismatch`）。
2.  **环境探针**：自动在报错后追加 `which python3`, `pwd`, `pip list` 等关键背景信息。

### 长期 (1 周+)：记忆持久化
1.  **实现 `MEMORY.md` 自动化更新**：任务结束时自动触发总结任务。
2.  **规则加载器**：将会话间的“教训”转化为下一轮的“指令”。

---

## 5. 参考资料与业界案例 (2026 最新)
1.  **Claude Code "nO" Loop**: 内部使用了 `verify-think-fix` 深度循环，强调在失败后重新 Perceive（感知）环境。
2.  **Mem0 (The Memory Layer for AI Agents)**: 提供了跨会话的片段记忆管理，实现了“错不再犯”的存储层。
3.  **Mengram Framework (2025)**: 提出了“程序化指令进化（Instruction Evolution）”，通过历史错误自动调整系统 Prompt。
4.  **Anthropic Research**: "Building Effective Agents" - 强调了在复杂任务中使用子 Agent 进行“结果审计”的重要性。
