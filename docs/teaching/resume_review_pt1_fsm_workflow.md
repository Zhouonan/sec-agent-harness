# 简历复习 · 第一项
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

这种模式**完全依赖模型自己判断**何时进入下一阶段，何时结束。对于复杂的安全漏洞修复任务（需要：分析→验证→修复→回归测试），模型极容易在某个阶段"卡住"或"跳过"关键步骤。

---

## 2. 解决方案：有限状态机（FSM）

### 2.1 FSM 的核心思路

FSM 的关键洞察是：**把"阶段管理"的权力从模型手中收回，交给代码强制执行**。

- 模型只做两件事：在**当前状态**内使用允许的工具；在**确认完成**后调用 `transition_state` 切换阶段
- 代码负责：强制约束每个状态下可用的工具集、校验转移条件（Hook）、熔断保护

### 2.2 状态定义（`core/loop.py`）

```python
class AgentState(Enum):
    INITIAL_ANALYSIS = auto()   # 攻击面分析（探索代码结构、找漏洞假设）
    VALIDATOR        = auto()   # 漏洞 PoC 验证（编写并运行 PoC）
    FIXER            = auto()   # 补丁生成与应用（写 fix、修改源码）
    REVIEWER         = auto()   # 回归测试与最终确认（跑测试、确保无副作用）
    DONE             = auto()   # 成功终态
    ERROR            = auto()   # 熔断终态（超出最大轮次）
```

### 2.3 状态转移图

```
                          ┌──────────────────────────────────┐
                          │      熔断：超过 max_turns         │
                          ▼                                  │
INITIAL_ANALYSIS ──► VALIDATOR ──► FIXER ──► REVIEWER ──► DONE
        ▲                              ▲        │
        │                              │        │  测试失败，重新修复
        │                              └────────┘
        │
        └──── 连续失败 3 次，由 recovery_logic Hook 强制回退
```

### 2.4 FSM 转移的质量门禁（`hooks/builtin_logic.py`）

```python
@hook("PRE_TOOL_USE", matcher="transition_state")
def fsm_safety_hook(state, tool_name, args, result):

    next_state = args.get("next_state", "").upper()

    # 规则1：出口路径强制约束 —— 只有 REVIEWER 能跳 DONE
    if next_state == "DONE" and state.current_state.name != "REVIEWER":
        return HookResult(
            continue_execution=False,
            block_reason="TRANSITION REJECTED: 必须先经过 REVIEWER 验证。"
        )

    # 规则2：质量强校验 —— 必须有成功的测试记录
    if next_state == "DONE":
        last_status = state.blackboard.get("last_test_status")
        if last_status not in ("success", "PASSED"):
            return HookResult(
                continue_execution=False,
                block_reason=f"TRANSITION REJECTED: 上次验证未通过 (Status: {last_status})。"
            )
```

这两条规则从**代码层面**封死了模型"走捷径"的可能——即使模型被幻觉欺骗认为任务完成，Hook 也会强制拦截。

### 2.5 状态局部上下文（`LoopState`）

```python
@dataclass
class LoopState:
    messages:         List[...]   # 对话历史
    current_state:    AgentState  # 当前 FSM 状态
    blackboard:       Dict[...]   # 跨状态共享的黑板数据（摘要、测试结果等）
    turn_count:       int         # 全局轮次计数
    state_turn_count: int         # 当前状态内轮次（用于单状态熔断）
```

`state_turn_count` 在每次状态转移时归零，配合 `max_turns_per_state` 实现**单状态级别的熔断**，防止模型在某一阶段无限循环而不影响其他阶段的配额。

---

## 3. 异常自动重试机制（三层防护）

### 第一层：LLM API 层重试（`call_llm_with_retry`）

```python
def call_llm_with_retry(self, messages, tools, max_retries=3):
    for i in range(max_retries):
        try:
            return self.client.chat.completions.create(...)
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                wait_time = (i + 1) * 5   # 指数退避：5s → 10s → 15s
                time.sleep(wait_time)
            elif i == max_retries - 1:
                raise e                    # 最后一次直接抛出
            else:
                time.sleep(2)             # 其他错误等待 2s 缓冲
```

针对速率限制（429）做**指数退避**，针对网络抖动设置缓冲间隔，超过 `max_retries` 才真正失败。

### 第二层：Nudge 催促机制（防止模型静默）

```python
# core/loop.py run()
if not active and state.current_state not in (AgentState.DONE, AgentState.ERROR):
    state.messages.append({
        "role": "system",
        "content": "You have not called any tools. Please proceed..."
    })
    continue  # 继续循环，给 Agent 再次机会
```

模型有时只输出文字分析而不调用工具（"想了但没做"），Nudge 自动注入系统消息催促其行动，而不是让任务静默退出。

### 第三层：连续失败自动回退（`recovery_logic.py`）

```python
@hook("POST_TOOL_USE", priority=10)  # 最高优先级，最先检查
def tactical_backtracking_hook(state, tool_name, args, result):
    failures = state.blackboard.get("consecutive_failures", 0)

    if is_failure:
        failures += 1
        if failures >= 3:
            # 清除错误路径的局部记忆，重新从全局分析开始
            from core.loop import AgentState
            state.current_state = AgentState.INITIAL_ANALYSIS
            state.state_turn_count = 0
            return HookResult(injected_output="[AUTO-RECOVERY]: Forcing backtrack...")
    else:
        state.blackboard["consecutive_failures"] = 0  # 成功则重置计数器
```

连续 3 次工具失败触发**战术回退**：强制跳回 `INITIAL_ANALYSIS`，让模型重新审视环境假设，而不是在错误的方向上无限重试。

---

## 4. Hook 系统：FSM 的"插件式约束层"

Hook 系统将 FSM 的约束逻辑从主循环解耦，以插件形式注入：

```
工具调用前  ──► PRE_TOOL_USE Hook  ──► [可拦截 / 修改参数]
              ↓ 通过
工具实际执行
              ↓
工具调用后  ──► POST_TOOL_USE Hook ──► [可注入反馈 / 触发状态变更]
```

| 文件 | 事件 | 职责 |
|---|---|---|
| `builtin_logic.py` | `PRE_TOOL_USE` (transition_state) | FSM 出口质量门禁 |
| `builtin_logic.py` | `POST_TOOL_USE` (execute_in_sandbox) | 沙箱失败诊断注入 |
| `recovery_logic.py` | `POST_TOOL_USE` (全部工具) | 连续失败自动回退 |

**Hook 装饰器注册方式**：
```python
@hook("PRE_TOOL_USE", matcher="transition_state", priority=10)
def fsm_safety_hook(state, tool_name, args, result):
    ...
```

`matcher` 精确匹配工具名（不匹配的工具不触发此 Hook），`priority` 控制多个 Hook 的执行顺序（数字越小越优先）。

---

## 5. 整体执行流（代码调用链）

```
main.py
  └─► AgentLoop.run(initial_query)
        └─► while state ∉ {DONE, ERROR}:
              └─► run_one_turn(state)
                    ├─► compact_blackboard()             # 上下文压缩（防溢出）
                    ├─► get_system_prompt()               # 注入角色定义 + 黑板数据
                    ├─► call_llm_with_retry()             # LLM 推理（带重试）
                    └─► for each tool_call:
                          ├─► registry.dispatch(PRE_TOOL_USE)    # Hook 前置拦截
                          ├─► handler(**args)                     # 实际工具执行
                          └─► registry.dispatch(POST_TOOL_USE)   # Hook 后置注入
```

---

## 6. 高频面试问答

### Q1：你为什么用 FSM 而不是让模型自己管理流程？

> 本质是**可靠性 vs 灵活性的权衡**。纯 ReAct 模式完全依赖模型推理能力，但 LLM 在长对话中存在注意力偏移，可能忘记目标或跳过关键步骤。FSM 把"我现在在哪个阶段""完成这个阶段需要满足什么条件"**硬编码到代码逻辑**里，用状态机的确定性补偿模型的不确定性。代价是灵活性降低，但对于安全修复这种需要严格 SOP 的任务，确定性优先。

### Q2：如何防止模型绕过 FSM 直接跳转 DONE？

> 通过 Hook 系统的 `PRE_TOOL_USE` 拦截。模型想跳转 DONE 必须调用 `transition_state` 工具，执行前触发 `fsm_safety_hook`。Hook 检查两个条件：① 当前状态必须是 REVIEWER；② `blackboard["last_test_status"]` 必须为 `success`。任一不满足，转移请求直接被拒绝，错误信息反馈给模型。这是**代码层面的强制约束**，不依赖模型遵守 Prompt 里的规定。

### Q3：熔断机制是怎么工作的？两层有什么区别？

> 有两层熔断：**全局熔断**（`total_max_turns`）限制任务总轮次，超出强制进入 `ERROR`；**单状态熔断**（`max_turns_per_state`）限制模型在单个状态内的最大尝试次数，每次状态转移时 `state_turn_count` 归零。区别在于：全局熔断保护资源，单状态熔断防止某一阶段死循环而不影响其他阶段的配额，两者是逻辑上的父子关系。

### Q4：异常重试和熔断会不会冲突？

> 不冲突，两者作用在不同层面。重试（`call_llm_with_retry`）针对**网络/API 层面的临时故障**，重试成功后轮次仍然计入计数器。熔断针对**任务层面的持续失败**，即使 API 调用成功但 Agent 行动反复失败也会触发。前者处理基础设施抖动，后者处理逻辑僵局，互补关系。

### Q5：这个 FSM 设计有什么缺陷或改进空间？

> 真实测试中发现一个典型问题（mruby CVE-2022-0240 案例）：Hook 把"沙箱环境未启动（`initialization_error`）"和"测试运行但失败（`failed`）"当成同一情况处理，导致 Docker 不可用时系统陷入无法破解的死锁（Docker 不可用→Hook 拦截→再次尝试沙箱→再次失败→循环）。改进方向：**在 FSM 中增加环境感知层**，对环境异常走降级路径（`local_fallback`），与业务失败分开处理。这一缺陷教会了我，FSM 的转移条件设计必须区分"业务失败"和"环境故障"，两种错误的处理策略本质上不同。

---

## 7. 关键词速查

| 术语 | 你的实现 |
|---|---|
| FSM / 有限状态机 | `AgentState` enum + `LoopState.current_state` |
| 确定性工作流 | 转移由 Hook 校验，不依赖模型自由决策 |
| 工具死循环防护 | `max_turns_per_state` 熔断 + `recovery_logic.py` 回退 |
| SOP 强制执行 | 系统 Prompt 角色定义 + Hook 门禁双重保障 |
| 异常重试 | `call_llm_with_retry` 指数退避 + Nudge 催促机制 |
| 自动回退 | 连续失败 3 次→强制 `INITIAL_ANALYSIS` |
| 插件式约束 | Hook 系统装饰器注册，`PRE/POST_TOOL_USE` 双向钩子 |
