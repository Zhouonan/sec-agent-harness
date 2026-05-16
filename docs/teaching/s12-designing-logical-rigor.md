# 知识点复习：强制逻辑严密性 (Designing Logical Rigor)

在 `Sec-Agent-Harness` 中，“逻辑严密”不是通过在 Prompt 里写“请你逻辑严密一点”实现的，而是通过**防御性架构设计 (Defensive Architectural Design)** 强制约束的结果。

本节将深入探讨系统中已有的硬核逻辑约束机制，并规划未来的演进方向。

---

## 1. 为什么需要“强制”逻辑严密？

安全任务（如漏洞分析与修复）是一个高熵过程。LLM 在长路径任务中极易产生：
- **越权幻觉**：还没验证漏洞就尝试修复。
- **跳步幻觉**：直接跳过测试流程进入 `DONE` 状态。
- **先验偏见**：忽视沙箱的实际报错，反复执行同一个错误命令。

**核心哲学**：将逻辑约束从“建议层 (Prompt)”下沉到“协议层 (Protocol)”和“物理层 (Code)”。

---

## 2. 现有的逻辑约束机制 (Deep Dive)

### A. 信息饥饿策略 (Information Scarcity Strategy)
**实现位置**：`core/skill.py` & `core/loop.py`
- **原理**：系统在初始化阶段故意隐藏技能的详细 SOP（正文块 Body）。
- **逻辑点**：Agent 只能看到工具名和描述。如果它需要复杂的逻辑指导，必须显式调用 `load_skill`。
- **意义**：这迫使 Agent 的每一动作都必须伴随一个明确的“求知决策”。在日志中，`load_skill` 的出现标志着 Agent 逻辑链条的完整性。

### B. 基于 FSM 的状态权限隔离 (State-Based Isolation)
**实现位置**：`core/loop.py` -> `self.tools`
- **原理**：工具被“挂载”到特定的 `AgentState` 上。
- **逻辑点**：
    - 在 `INITIAL_ANALYSIS` 状态，`write_file` 工具不可见。
    - 在 `FIXER` 状态，`execute_in_sandbox` (运行测试) 是核心工具。
- **意义**：这在代码层面封死了“先修复、后验证”的可能性。Agent 必须通过 `transition_state` 完成合法的状态流转，才能解锁下一阶段的工具权限。

### C. 钩子驱动的逻辑门控 (Hook-Driven Logic Gates)
**实现位置**：`core/hook.py` -> `POST_TOOL_USE` 钩子
- **原理**：在工具执行后，通过 Python 逻辑对结果进行硬性评估。
- **逻辑点**：在 `REVIEWER` 状态下，系统会检查沙箱返回的 Exit Code。如果 Exit Code 为非零（测试失败），钩子会自动拦截 Agent 试图跳转到 `DONE` 的 `transition_state` 请求。
- **意义**：这建立了“物理指标决定逻辑路径”的机制。Agent 的“主观意愿”必须服从沙箱执行的“客观结果”。

### D. 诊断建议注入 (Diagnostic Injection)
**实现位置**：`hooks/builtin_logic.py`
- **原理**：当工具返回错误时，系统自动在结果中附加 `[SYSTEM ADVICE]`。
- **逻辑点**：建议通常是“你是否假设了错误的路径？”或“请先用 ls 确认文件是否存在”。
- **意义**：这强制 Agent 在下一轮对话中必须处理该诊断信息，防止其陷入死循环。

---

## 3. 未来演进规划 (Roadmap)

为了进一步提升系统的自主性与鲁棒性，我们将引入以下进阶设计：

### 阶段 1：逻辑一致性审计 (Reasoning-Action Alignment)
- **目标**：防止 Agent “说一套做一套”。
- **设计**：在 `PRE_TOOL_USE` 钩子中，利用轻量级模型对 Agent 的 `thought`（思维过程）与即将调用的 `tool_call`（实际动作）进行语义对齐检查。
- **场景**：如果 Agent 说“我要读取 README”，但调用的却是 `write_file`，系统将直接打断并报错。

### 阶段 2：对抗式自我纠错 (Adversarial Shadow Agent)
- **目标**：引入“批评者”角色。
- **设计**：在关键决策点（如从 `VALIDATOR` 转到 `FIXER`），启动一个隐形的影子 Agent（Shadow Agent），专门负责寻找当前结论的漏洞。
- **场景**：影子 Agent 会质疑：“你的 PoC 真的触发了溢出吗？还是只是程序崩溃了？”。只有通过对抗质询，决策才会被正式接受。

### 阶段 3：概率性路径回溯 (Probabilistic Backtracking)
- **目标**：智能处理“死胡同”。
- **设计**：引入“置信度分数”。当 Agent 连续 3 轮无法推进任务且置信度过低时，系统强制其回退到 `INITIAL_ANALYSIS` 状态并清理黑板（Blackboard）中的旧假设。
- **场景**：防止 Agent 在错误的漏洞利用路径上耗尽所有 Token。

### 阶段 4：SOP 形式化验证 (Formal Verification of SOPs)
- **目标**：确保技能文档的逻辑零错误。
- **设计**：将 `SKILL.md` 的正文转换为形式化逻辑描述（如 TLA+ 或类似的逻辑表示），并在加载前由验证引擎检查其步骤是否存在冲突或死循环。

---

## 4. 复习思考题

- **问题**：在 `Sec-Agent-Harness` 中，为什么 `write_file` 不能在 `INITIAL_ANALYSIS` 状态下被调用？
- **回答**：因为在 `core/loop.py` 的 `_register_core_tools` 和 `_register_skill_tools` 方法中，`write_file` 工具并未被挂载（Mount）到 `INITIAL_ANALYSIS` 状态对应的工具池中。这是一种架构级的状态权限隔离，强制 Agent 遵循先分析、后验证、再修复的逻辑严密流程。
