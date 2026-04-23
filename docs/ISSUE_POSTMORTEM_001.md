# Post-Mortem: Agent Logic Failure in REVIEWER State

## 1. 现象描述 (Description)
在 `challenge/calculator.py` 的修复测试中，Agent 在 `REVIEWER` 状态执行回归测试后输出：
> “修复后……测试仍然失败……我将重新检查修复方案。”

然而，Agent 紧接着调用的工具却是：
`transition_state(next_state="DONE", summary="...")`

**结果**：系统错误地进入了 `DONE` 终止状态，尽管漏洞并未被成功修复或验证。

## 2. 根因分析 (Root Cause Analysis)

### A. 提示词缺乏“闭环”约束
当前的 `REVIEWER` 系统提示词虽然告诉了 Agent 目标是验证修复，但没有明确规定：
- **成功路径**：测试通过 -> 才能跳转到 `DONE`。
- **失败路径**：测试失败 -> **必须** 跳转回 `FIXER` 重新修复，或者在 `REVIEWER` 中重试。
Agent 倾向于线性完成任务，如果没有明确的“退回”指令，它可能会为了完成流程而强行进入终止态。

### B. 状态机 (FSM) 缺乏逻辑校验
`core/loop.py` 中的 `transition_handler` 只是一个机械的跳转工具，它不具备“审查”跳转合理性的能力。它无法根据当前的测试结果（通常在黑板上）拦截一个不合理的 `DONE` 跳转。

### C. Agent 的“任务完成偏见”
LLM 在长序列对话中存在一种偏见，即认为“对话总会结束”。在连续工作几轮后，它可能会由于 Context 压力或模型惯性，忽略了逻辑上的矛盾，选择了最快的退出路径。

## 3. 修复方向 (Remediation)

### 方案一：强化状态机指令 (Prompt Guardrails)
更新 `REVIEWER` 的系统提示词，加入条件判断逻辑：
- `IF tests fail: You MUST transition back to FIXER.`
- `IF tests pass: You may transition to DONE.`
- `NEVER transition to DONE if the PoC or regression tests are still failing.`

### 方案二：引入“状态回转”机制 (Backtracking)
目前 `transition_state` 的枚举值中没有体现“回退”。我们应该在 `REVIEWER` 的可用工具中明确强调它可以回到 `FIXER`。

### 方案三：校验式状态转换 (Validated Transitions)
修改 `transition_state` 处理器，使其能够访问黑板上的 `test_results`。
如果 Agent 尝试跳转到 `DONE` 但黑板显示最近的测试结果为 `failed`，则处理器返回错误信息，强迫 Agent 纠正行为。

### 方案四：增加 REVIEWER 的判分逻辑
在 `REVIEWER` 状态中增加一个强制步骤：调用 `verify_results` 工具。该工具会解析测试输出，只有输出 `success` 时才解锁 `DONE` 状态的跳转权限。

## 4. 后续建议 (Next Steps)
1. 修改 `core/loop.py` 中的 `REVIEWER` 提示词。
2. 在 `transition_handler` 中增加简单的逻辑检查。
3. 增加一个 `repro_failure` 的引导，让 Agent 在测试失败时先分析原因再跳转。

---

## 5. 验证运行记录 (Verification Run - 2026-04-16)

### 运行摘要 (Run Summary)
在应用了 **方案一 (Prompt Guardrails)**、**方案三 (Validated Transitions)** 和 **本地执行回退** 后的完整运行中，观察到以下行为：
1. **本地回退生效**：由于宿主机 Docker 未启动，系统成功触发 `LOCAL_EXECUTION_FALLBACK`。日志显示 `SandboxTool - INFO - Executing locally`，证明 Agent 获得了执行能力，未因环境阻断而停止。
2. **逻辑守卫拦截成功**：Agent 在 `REVIEWER` 状态下运行测试失败（由于路径错误）后，尝试跳转至 `DONE`。系统通过 `transition_handler` 成功识别并拦截了该跳转，并提示：`TRANSITION REJECTED: ... last test result was 'failed'`。这验证了逻辑守卫功能的可靠性。
3. **最终结果：熔断 (Circuit Breaker)**：由于测试一直无法通过，Agent 在 `FIXER` 和 `REVIEWER` 之间反复循环，最终触发了 `Max turns reached` 熔断，状态被强制转为 `ERROR`。

### 暴露出的新问题 (New Findings)
- **路径偏见固化 (Stubborn Path Bias)**：尽管在提示词中加入了路径发现指令，Agent 仍倾向于执行 `python -m unittest discover -s tests`，而忽略了实际有效的测试路径 `challenge/tests/`。这导致它进入了“修复-运行错误测试-失败-再修复”的死循环。
- **环境命令不一致 (Interpreter Mismatch)**：在本地回退模式下，Agent 使用 `python` 命令报错（未找到），而当前宿主机环境仅支持 `python3`。系统缺乏对本地解释器名称的自动感知或提示。
- **REVIEWER 状态下的违规操作**：观察到 Agent 在 `REVIEWER` 状态下调用了 `write_file`。虽然从功能上被允许，但这模糊了 `FIXER`（负责修复）和 `REVIEWER`（负责审计）的职责边界，容易导致逻辑混乱。

### 进一步建议 (Refined Recommendations)
- **引入测试命令自动发现**：在 `INITIAL_ANALYSIS` 阶段，增加一个 `get_test_command` 步骤，让 Agent 明确将“可运行的测试命令”记录在黑板上，后续状态直接引用该命令。
- **强化解释器自检**：在 Agent 启动时，由 `SandboxTool` 自动检测本地可用解释器（`python` vs `python3`），并将其作为“环境变量”告知 Agent。
- **状态机权限硬约束**：在 `core/loop.py` 中，通过 `tools` 列表进一步收紧 `REVIEWER` 的权限，禁止其调用 `write_file` 等修改类工具。
- **黑板压实算法优化**：长循环导致黑板内容迅速膨胀，需要更激进的 `compact_blackboard` 算法来保留关键的失败堆栈信息。

---

## 7. 架构反思：为何 Agent 表现“僵化”？ (Architectural Reflection)

在 2026-04-16 的运行中，观察到 Agent 虽然在 FSM 框架内流转，但表现出一种“机械完成任务”而非“智能解决问题”的倾向。即使环境报错（如 `python` 命令找不到），它仍倾向于直接跳过或强行进入下一状态。

### A. 症结分析 (The "Rigidity" Problem)

1. **线性执行偏见 (Linear Execution Bias)**:
   目前的系统提示词（System Prompts）过于强调“步骤 A -> 步骤 B”，导致模型将其视为流水线而非动态决策过程。模型更关注“我是否执行了这一步”，而非“这一步的结果是否达成了目标”。

2. **缺乏调试意识 (Missing Debugging Intent)**:
   当工具返回错误（如 `command not found`）时，模型未能将其识别为“需要排除的障碍”，而是仅仅将其作为“已完成步骤的输出”。这说明提示词中缺乏对“异常反馈机制”的处理指引。

3. **状态转换的“廉价性” (Low Transition Cost)**:
   在之前的设计中，`transition_state` 是无条件的。模型只要完成了话术上的总结，就可以随意切换状态。这导致它在当前状态目标（如：跑通 PoC）未达成时，就过早地滑向了后续状态。

### B. 根本原因 (Root Causes)

- **提示词类型错误**：目前的提示词是“操作员模式”（Operator Mode），而非“诊断者模式”（Diagnostic Mode）。它只教了怎么做，没教怎么处理“做不成”的情况。
- **环境感知缺失**：Agent 处于“信息黑盒”中，它并不知道宿主机具体是 `python` 还是 `python3`，只能靠先验知识盲猜，失败后又缺乏自愈逻辑。

### C. 演进方向 (Evolutionary Path)

1. **从“步骤指引”转向“目标驱动”**:
   重构各状态的 Prompt，明确定义该状态的 **“退出准则 (Exit Criteria)”**。例如：在 `VALIDATOR` 状态下，必须获得一个明确的、可重现的漏洞触发反馈，否则禁止进入 `FIXER`。

2. **注入环境自检 (Environmental Self-Check)**:
   在 Agent 启动时，自动执行环境探针（解释器版本、当前路径、可用工具），并将结果作为“环境事实”注入提示词，消除 Agent 的先验偏见。

3. **引入内部小循环 (Intra-state Micro-loops)**:
   强化工具反馈的权重。如果最近一次操作报错，强制模型进入“诊断模式”，利用 `list_files` 等工具自愈，而非盲目跳转状态。

4. **硬约束状态权限**:
   严格限制各状态可调用的工具。例如，`REVIEWER` 严禁调用 `write_file`，强制其只能作为审计者存在，从而保证 FSM 逻辑的纯洁性。

---

## 8. 引入 Hook 机制作为“自愈”引擎 (The Hook System Solution)

为了彻底解决 Agent 面对失败反应迟钝的问题，我们计划引入一套 Hook 系统，允许在 Agent 运行的关键节点注入动态校验与辅助逻辑。

### A. 核心 Hook 点设计

1. **`after_tool_call` (后置增强)**:
   - **逻辑**：监控工具输出。若检测到 `stderr` 报错或特定的失败模式（如 `command not found`），Hook 将自动触发诊断逻辑。
   - **自愈**：例如，自动探测正确的解释器路径，并在回复给 Agent 的消息中追加：“系统建议：检测到 `python` 环境异常，请尝试使用 `python3`。”

2. **`before_prompt_generation` (动态上下文注入)**:
   - **逻辑**：在每一轮 LLM 请求前，运行环境探针。
   - **信息**：实时注入当前 `pwd`、`ls -R challenge/` 结果以及可用系统工具列表。
   - **目标**：将 Agent 从“先验偏见”中拉出，使其基于“当前事实”决策。

3. **`on_transition_check` (逻辑闸门)**:
   - **逻辑**：拦截 `transition_state` 调用。
   - **验证**：根据 `AgentState` 强制执行退出检查。例如，若 `VALIDATOR` 尝试跳转到 `FIXER` 但未提供有效的失败堆栈，Hook 将拦截并要求 Agent 继续验证。

### B. 预期收益

- **增强状态内部韧性**：Agent 不再是简单的“一错就走”，而是被迫在 Hook 的指引下进行内部重试和调试。
- **解耦核心循环与环境逻辑**：将繁杂的环境探测（如解释器名称检测）从 `core/loop.py` 主逻辑中移出，保持引擎纯净。
- **更高的任务达成率**：通过 Hook 强化的反馈环，Agent 在进入下一状态前将拥有质量更高、更可信的中间产出。
