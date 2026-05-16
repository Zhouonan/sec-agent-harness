# 针对应聘智能体工程师：Sec-Agent-Harness 代码级实现解析

**目标**：从代码实现层面（而非纯理论或文档）向面试官讲述项目开发经历，体现对 Agent 底层机制（Prompt 控制、上下文调度、拦截器）的深度控制力。

## 1. 一句话简要介绍（Elevator Pitch）

> **Sec-Agent-Harness 是一个通过代码层级的高强度约束，来解决大语言模型在长周期任务中容易失控和产生幻觉的智能体框架。**
> 在底层代码的实现上，我通过严格的 `Enum` 构建了 FSM 状态流转引擎，利用代码逻辑层面的动态阈值实现了 Blackboard（黑板）的上下文自动压缩，并通过一套事件驱动的 Hook 系统（拦截器）在代码层面对非法的工具调用进行“硬拦截”，从而实现了一个高工程完成度的漏洞自动修复 Agent。

---

## 2. 核心代码实现拆解（面试重点）

可以重点讲解以下 4 个代码模块的实现机制（对应实际代码树）：

### 2.1 FSM 骨架与提示词动态路由 (`core/loop.py`)
* **实现逻辑**：系统没有采用基于 ReAct 的普通 while 循环，而是定义了严格的 `AgentState` Enum（包含 `INITIAL_ANALYSIS`, `VALIDATOR`, `FIXER`, `REVIEWER`, `DONE`）。
* **技术亮点**：在核心的 `AgentLoop` 类中，`get_system_prompt()` 函数会根据 `state.current_state` 动态组装不同的系统提示词。比如当处于 `REVIEWER` 状态时，System Prompt 会从代码层面强制追加“你必须再次运行 PoC 测试”的严格指令。大模型只能通过我暴露给它的 `transition_state` 工具进行状态切换，实现了“业务逻辑流”和“大模型控制流”的解耦。

### 2.2 渐进式技能加载与 Blackboard 上下文压缩 (`core/skill.py` & `core/loop.py`)
* **实现逻辑**：为了防止 Prompt 内容爆炸（Token 上限），`SkillRegistry` 类在初始化时会解析各技能文件夹下 `SKILL.md` 的 YAML Frontmatter（元数据）。每轮对话中，Agent 的 Prompt 里只注入一个极简的 `catalog` 列表。
* **技术亮点**：当且仅当 Agent 主动调用 `load_skill` 工具时，技能的具体规范才会作为字典键值对挂载到 `LoopState` 的 `blackboard` 字典中。同时，我实现了一个 `compact_blackboard` 方法：每当 JSON 格式的上下文长度超过预设阈值（如 4000 字符），引擎会自动截断并归档旧的 `_summary`。这是借鉴了操作系统的“按需分页与内存回收”思想，实现了极致的 Context 治理。

### 2.3 基于 Hook 的防御性拦截机制 (`hooks/builtin_logic.py`)
* **实现逻辑**：单纯依赖 Prompt 来约束大模型极不可靠，因此我实现了一套事件驱动的 Hook 系统（包括 `PRE_TOOL_USE` 和 `POST_TOOL_USE` 生命周期钩子）。
* **技术亮点**：我编写了一个 `fsm_safety_hook` 函数来专门拦截大模型对 `transition_state` 工具的调用。如果在转入 `DONE` 状态时，代码从 Blackboard 取出的 `last_test_status` 不是 `success`（代表沙箱测试未通过），或者当前状态根本不是 `REVIEWER`，该 Hook 会直接返回 `continue_execution=False`，并将具体的 `block_reason` 喂给大模型打回重做。这种代码级别的“硬门卡”彻底杜绝了“大模型自我宣告修复成功”的幻觉。

### 2.4 工具调用的工程健壮性设计 (`core/loop.py`)
* **实现逻辑**：在调用 LLM 时，`call_llm_with_retry` 实现了带指数退避（Exponential Backoff）的重试机制来处理 API 限流问题 (HTTP 429)。
* **技术亮点**：针对沙箱执行命令后可能返回的超长日志，我的框架利用 `truncate_content` 截断中间冗余部分，仅保留头尾（即保留报错根因），既省 Token 又保证了调试信息的完整；而对于连续 5 轮都不更新计划或不调用工具的闲聊（Drifting）行为，系统会自动注入 `nudger` (Nudge) 提示词，通过代码强制引导它回归主线任务。

---

> 💡 **总结建议：**
> 面试时，不要光讲概念，一定要提到你在 `loop.py`、`skill.py` 里面的具体数据结构（比如 Enum、字典挂载、Hook 阻断机制）。这会体现出你不是在用外部现成的框架搭积木，而是真正具备底层 Agent Engine 的造轮子能力。


