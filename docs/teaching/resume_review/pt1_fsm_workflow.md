# 复习文档 · 第一项
# 基于状态机编排的确定性工作流

> **简历原文**：针对 Agent 容易"逻辑跑偏"和陷入工具死循环的问题，利用状态机强制规范修复链路，确保模型严格按照"分析-验证-修复"的 SOP 执行，配合异常自动重试机制，从底层架构层面解决了长链路任务的不确定性。

---

## 1. 问题背景：为什么 LLM Agent 需要 FSM？

### LLM 的两个核心缺陷

| 缺陷 | 具体表现 | 后果 |
|---|---|---|
| **逻辑跑偏** | 模型在多轮对话后忘记原始目标，开始做无关的事（如重复探索已经看过的文件） | 任务永远无法终结 |
| **工具死循环** | 模型反复调用同一工具（如 `execute_in_sandbox`）而不分析结果，或陷入"尝试→失败→再尝试"的无限循环 | Token 耗尽、资源浪费、任务失败 |

### 朴素 ReAct 循环的局限

传统 ReAct（Reason + Act）模式是一个无结构的 `while True` 循环：

```
while not done:
    思考 → 行动 → 观察 → 思考 → ...
```

这种模式完全依赖模型自己判断何时进入下一阶段，何时结束。对于复杂的安全漏洞修复任务（需要：分析→验证→修复→回归测试），模型极容易在某个阶段"卡住"或"跳过"关键步骤。

---

## 2. 解决方案：有限状态机（FSM）

### 2.1 FSM 的核心思路

FSM 的关键洞察是：**把"阶段管理"的权力从模型手中收回，交给代码强制执行**。

模型只做两件事：
1. 在**当前状态**内使用允许的工具完成该阶段任务
2. 在**确认完成**后调用 `transition_state` 工具主动切换阶段

代码负责：
- 强制约束每个状态下可用的工具集
- 校验转移条件（通过 Hook 系统）
- 熔断保护（防止单状态死循环）

### 2.2 状态定义

```python
# core/loop.py
class AgentState(Enum):
    INITIAL_ANALYSIS = auto()   # 攻击面分析
    VALIDATOR        = auto()   # 漏洞 PoC 验证
    FIXER            = auto()   # 补丁生成与应用
    REVIEWER         = auto()   # 回归测试与最终确认
    DONE             = auto()   # 成功终态
    ERROR            = auto()   # 熔断终态
```

### 2.3 状态转移图

```
                    ┌─────────────────────────────────┐
                    │         熔断：超过最大轮次        │
                    ▼                                 │
INITIAL_ANALYSIS ──►  VALIDATOR ──► FIXER ──► REVIEWER ──► DONE
        ▲                              ▲        │
        │                              │        │ 测试失败，需要重新修复
        │                              └────────┘
        │
        └──── 连续失败 3 次，由 recovery_logic Hook 强制回退
```

**关键设计约束（`hooks/builtin_logic.py`）**：

```python
# 规则1：只有 REVIEWER 才能跳转到 DONE
if next_state_name == "DONE" and current_state_name != "REVIEWER":
    return HookResult(
        continue_execution=False,
        block_reason="TRANSITION REJECTED: 必须经过 REVIEWER 验证才能完成。"
    )

# 规则2：跳转 DONE 前必须有成功的测试记录
if next_state_name == "DONE":
    last_status = state.blackboard.get("last_test_status")
    if last_status not in ("success", "PASSED"):
        return HookResult(continue_execution=False, ...)
```

这两条规则从**代码层面**封死了模型"走捷径"的可能——即使模型被幻觉欺骗认为任务完成，Hook 也会强制拦截。

### 2.4 状态局部上下文（LoopState）

```python
@dataclass
class LoopState:
    messages:         List[...]   # 对话历史
    current_state:    AgentState  # 当前 FSM 状态
    blackboard:       Dict[...]   # 跨状态共享的黑板数据（摘要、测试结果等）
    turn_count:       int         # 全局轮次
    state_turn_count: int         # 当前状态内轮次（用于熔断）
```

`state_turn_count` 在每次状态转移时归零，配合 `max_turns_per_state` 实现**单状态级别的熔断**，防止模型在某一阶段无限循环。

---

## 3. 异常自动重试机制

### 3.1 LLM API 层重试（call_llm_with_retry）

```python
def call_llm_with_retry(self, messages, tools, max_retries=3):
    for i in range(max_retries):
        try:
            response = self.client.chat.completions.create(...)
            return response
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                wait_time = (i + 1) * 5   # 指数退避：5s, 10s, 15s
                time.sleep(wait_time)
            elif i == max_retries - 1:
                raise e                    # 最后一次直接抛出
            else:
                time.sleep(2)             # 其他错误等待 2s
```

**设计要点**：
- 针对限速（429）做指数退避，避免立即重试加剧速率问题
- 非限速错误（网络抖动等）也有 2s 缓冲
- 超过 `max_retries` 才真正失败，避免偶发网络错误导致任务中断

### 3.2 自动 Nudge 机制（防止模型静默）

```python
# core/loop.py run()
if not active and state.current_state not in (AgentState.DONE, AgentState.ERROR):
    nudger = {
        "role": "system",
        "content": "You have not called any tools. Please proceed with your task..."
    }
    state.messages.append(nudger)
    continue   # 继续循环，给 Agent 再次机会
```

**为什么一定要模型调用工具？**
因为 LLM 本质上是文本生成器，只有通过**工具调用（Tool Calling/Function Calling）**才能对外部环境产生实际影响（如执行命令、读写文件、状态流转）。如果模型"想了但没做"（只输出了分析文本但没有发起工具调用），FSM 的状态就不会推进，系统就会停滞。Nudge 机制自动注入系统消息催促其行动，而不是让循环因为缺乏实质性动作而直接退出。

### 3.3 连续失败自动回退（recovery_logic.py Hook）

```python
@hook("POST_TOOL_USE", priority=10)
def tactical_backtracking_hook(state, tool_name, args, result):
    failures = state.blackboard.get("consecutive_failures", 0)

    if is_failure:
        failures += 1
        if failures >= 3:
            # 清除局部记忆，强制回到初始分析阶段重新评估
            state.current_state = AgentState.INITIAL_ANALYSIS
            state.state_turn_count = 0
            return HookResult(injected_output="[AUTO-RECOVERY]: Forcing backtrack...")
    else:
        state.blackboard["consecutive_failures"] = 0
```

连续 3 次工具失败触发**战术回退**：状态机强制跳回 `INITIAL_ANALYSIS`，让模型重新审视环境，而不是在错误的假设下无限重试。

**为什么一定是跳回 INITIAL_ANALYSIS？是不是要视情况而定？**
> [!NOTE]
> 在目前的极简实现中，跳回 `INITIAL_ANALYSIS` 是一种**Fail-Safe（失效安全）兜底策略**，因为一切修复失败的根源通常在于最初的环境感知和漏洞定位出了偏差。
> 但在更高级的工程实践中，回退应该是**视情况而定（Context-Aware Backtracking）**的：
> - 如果在 `REVIEWER` 测试失败，应该回退到 `FIXER` 重新打补丁。
> - 如果在 `FIXER` 找不到修改点，应该回退到 `VALIDATOR` 确认 PoC 是否准确。
> 面试时可以指出：当前的全局重置过于粗暴，下一步的优化方向是实现**基于当前状态的阶梯式回退（Cascading Fallback）**。

---

## 4. Hook 系统：FSM 的"神经反射弧"

Hook 系统把 FSM 的约束逻辑从主循环中解耦出来，以插件形式注入：

```
工具调用前  ──► PRE_TOOL_USE Hook  ──► [可拦截/修改参数]
工具执行
工具调用后  ──► POST_TOOL_USE Hook ──► [可注入反馈/触发状态变更]
```

| Hook 文件 | 事件 | 职责 |
|---|---|---|
| `builtin_logic.py` | `PRE_TOOL_USE` (transition_state) | FSM 转移质量门禁 |
| `builtin_logic.py` | `POST_TOOL_USE` (execute_in_sandbox) | 沙箱失败诊断注入 |
| `recovery_logic.py` | `POST_TOOL_USE` (全部) | 连续失败自动回退 |

**Hook 注册方式（装饰器）**：
```python
@hook("PRE_TOOL_USE", matcher="transition_state", priority=10)
def fsm_safety_hook(state, tool_name, args, result):
    ...
```

`matcher` 精确匹配工具名，`priority` 控制多个 Hook 的执行顺序（数字越小越优先）。

---

## 5. 整体执行流

```
main.py
  └─► AgentLoop.run(initial_query)
        └─► while state ∉ {DONE, ERROR}:
              └─► run_one_turn(state)
                    ├─► compact_blackboard()          # 上下文压缩
                    ├─► get_system_prompt()            # 注入角色+黑板
                    ├─► call_llm_with_retry()          # LLM 推理
                    └─► for each tool_call:
                          ├─► registry.dispatch(PRE_TOOL_USE)   # Hook 拦截
                          ├─► handler(**args)                    # 实际执行
                          └─► registry.dispatch(POST_TOOL_USE)  # Hook 反馈
```

---

## 6. 高频面试问答

### Q1：你为什么用 FSM 而不是让模型自己管理流程？

> 本质上是**可靠性 vs 灵活性的权衡**。纯 ReAct 模式下，流程完全依赖模型的推理能力，但 LLM 在长对话中存在注意力偏移，可能忘记目标或跳过关键步骤。FSM 把"我现在在哪个阶段""完成这个阶段需要满足什么条件"硬编码到代码逻辑里，用状态机的**确定性**补偿模型的**不确定性**。代价是灵活性降低，但对于安全修复这种需要严格 SOP 的任务，确定性优先。

### Q2：如何防止模型绕过 FSM 直接跳转 DONE？

> 通过 Hook 系统的 `PRE_TOOL_USE` 拦截。模型想跳转 DONE 必须调用 `transition_state` 工具，而这个工具在执行前会触发 `fsm_safety_hook`。Hook 会检查两个条件：① 当前状态必须是 REVIEWER；② `blackboard["last_test_status"]` 必须为 `success`。两个条件任一不满足，转移请求直接被拒绝，错误信息会反馈给模型。这是**代码层面的强制约束**，不依赖模型遵守 Prompt 里的规定。

### Q3：熔断机制是怎么工作的？假如任务确实很棘手，需要更多次数怎么办？

> **基础回答**：有两层熔断。**全局熔断**（`total_max_turns`）限制任务总轮次，超出强制 ERROR；**单状态熔断**（`max_turns_per_state`）限制单阶段最大尝试次数，转移时归零。
> **追问（棘手任务感知）**：对于确实棘手的任务，硬编码的阈值太死板。改进方案是引入**配额动态协商机制（Dynamic Quota Allocation）**：允许 Agent 在耗尽配额前调用一个特定的系统工具（如 `request_quota_extension`），并必须在参数中给出"为什么需要更多次数"以及"接下来的新思路"。Hook 会基于 LLM-as-a-Judge 对其理由进行评估，如果理由充分且思路没有陷入循环，则动态增加 `state_turn_count` 的上限。

### Q4：异常重试和熔断会不会冲突？除了网络问题还有什么异常？

> **基础回答**：不会冲突。重试针对的是 API 层面的临时故障，熔断针对的是任务逻辑层面的持续失败，两者互补。
> **追问（其他异常类型）**：除了 429 限速和网络断连，`call_llm_with_retry` 还需要处理：
> 1. **Context Length Exceeded（上下文超限）**：工具输出过大导致 Token 爆表，需要捕获该异常并触发黑板的深度压缩。
> 2. **JSON 解析错误**：模型输出的工具调用 JSON 格式破损，需要捕获并提示模型修复语法。
> 3. **内容安全拦截（Content Filter Blocks）**：安全审查 API（特别是生成 PoC 攻击代码时）经常报 400 违规，需要通过系统提示词绕过或重试。

### Q5：这个 FSM 设计有什么缺陷或改进空间？（详解概率性状态转移）

> 首要缺陷是没有区分"环境故障"（如 Docker 挂了）和"业务失败"（如测试没过），导致死锁。
> 第二个改进空间是引入**概率性状态转移（Probabilistic State Transition）**。目前 FSM 的门禁是绝对的 0 或 1（如：测试必须 100% pass）。但在现实的复杂 C/C++ 仓库中，修好了一个漏洞往往会引发几个边缘用例的不稳定（Flaky Tests）。如果卡死在 100% pass，Agent 永远无法进入 DONE。
> **实现思路**：引入一个评分系统（Scoring System）。转移不再由死板的 if-else 决定，而是由一个验证者模型（LLM-as-a-Judge）对当前状态打分。例如：核心 PoC 已经防御成功（权重 80%），但有两个不相关的 UI 测试失败（权重 20%）。综合得分 0.8，超过允许退出的阈值，Hook 允许其"带瑕疵退出"，从而避免在修补无关痛痒的副作用上耗尽 Token。

### Q6：你在简历里写状态转移由 Hook 校验，为什么不直接写在主循环（loop.py）的逻辑里？

> **核心回答**：为了遵循**开放封闭原则（OCP）**和**解耦**。
> 如果写在 `loop.py` 里，主循环代码会充斥着各种 `if current_state == X and target == Y` 的硬编码。未来每次修改转移规则、新增状态，都要去改动核心引擎代码，极易引发回归 Bug。
> 使用 Hook 机制后，FSM 引擎（`loop.py`）只负责"状态流转的机械动作"，而"要不要流转"的**业务策略**被抽离到了 `hooks/builtin_logic.py` 中。这使得约束逻辑变成了可插拔的插件，我可以为不同的评测任务（如 C 语言漏洞修复 vs Python Web 修复）挂载完全不同的 Hook 约束，而核心引擎一行代码都不用改。

### Q7：市面上已经有 LangGraph、AutoGen 这样的框架，你为什么要自己写状态机编排？除了 ReAct 和 FSM，你还了解哪些 Agent 范式？

> **为什么不用 LangGraph**：
> LangGraph 确实是构建状态机 Agent 的优秀标准库。但我选择自研 Harness 的原因在于**对底层控制力的极致追求**。在安全漏洞修复这个特定领域，我需要极高频地干预工具调用的前后文（通过 Hook 注入安全检查和降级策略）、需要精确控制内存中代码图结构的零拷贝传递、还需要处理极端的沙箱隔离和进程级熔断。现有的通用框架在这些深度定制点上往往显得过于笨重，自研轻量级引擎能最大化降低序列化开销，并保证每一行代码的安全性。但在普通业务场景下，我绝对认同拥抱 LangGraph 这样的开源生态。
> 
> **其他主流 Agent 模式（范式）**：
> 1. **Plan-and-Solve（计划与执行）**：把大任务先拆解成明确的步骤列表（Plan），然后逐个执行（Solve）。比 ReAct 的走一步看一步更有大局观，适合长线任务。
> 2. **Reflexion（自我反思）**：在 ReAct 基础上增加专门的反思节点。执行失败后，不立即重试，而是生成一段"为什么失败"的反思日志存入短期记忆，指导下一次行动。
> 3. **Multi-Agent Debate / Collaboration（多智能体协作）**：比如一个 Agent 专职写代码（Coder），一个专职找 Bug（Reviewer），两者互相博弈。这也是我的系统架构中划分为 `FIXER` 和 `REVIEWER` 状态的底层逻辑。
> 4. **DSPy（编程化 Prompt 优化）**：不手写 Prompt，而是把 Agent 的推理步骤模块化，用机器学习的方式自动优化各个步骤的 Prompt。

---

## 7. 关键词速查

| 术语 | 你的实现 |
|---|---|
| FSM / 有限状态机 | `AgentState` enum + `LoopState.current_state` |
| 确定性工作流 | 状态转移由 Hook 校验，不依赖模型自由决策 |
| 工具死循环防护 | `max_turns_per_state` 熔断 + 连续失败回退 |
| SOP 强制执行 | 系统 Prompt 角色定义 + Hook 门禁双重保障 |
| 异常重试 | `call_llm_with_retry` 指数退避 + Nudge 机制 |
| 自动回退 | `recovery_logic.py` 连续失败→强制 `INITIAL_ANALYSIS` |
