# s08: 动态技能加载与记忆压缩 (Dynamic Skills & Memory Compaction)

本章节将详细说明在 Sec-Agent-Harness 中新引入的三项核心机制：动态 Handler 加载、回归测试技能（Regression Tester）以及黑板压缩策略（Blackboard Compaction Policy）。这些功能进一步提升了 Agent 的扩展性、安全性验证能力以及长文本上下文的管理能力。

## 1. 动态 Handler 加载 (Dynamic Handler Loading)

### 解决了什么问题？
在早期的实现中，所有的工具方法（Handlers）都被硬编码在了 `AgentLoop._register_skill_tools()` 中。这意味着每次新增一个 Skill，开发者不仅要写 `SKILL.md`，还必须修改核心引擎的代码来绑定具体的执行逻辑。这种耦合限制了系统的可插拔性和扩展性。

### 核心设计与实现
现在的架构实现了 **完全的动态加载**：
1. **Skill 目录结构升级**：每个 Skill 目录（如 `skills/file-ops`）下除了声明元数据和 prompt 描述的 `SKILL.md` 之外，还可以包含一个原生的 Python 文件 `handler.py`。
2. **SkillRegistry 解析**：引擎在启动时，`SkillRegistry` 不仅会读取 YAML Frontmatter 提取工具声明，还会通过 `importlib.util` 动态加载 `handler.py` 模块，并将其挂载到解析后的 `skill_data` 中。
3. **AgentLoop 自动绑定**：`_register_skill_tools()` 会自动遍历所有被解析出的 Tools，并尝试去对应 Skill 的 `handler_module` 中寻找同名函数或 `{name}_handler` 命名的函数。
4. **灵活的参数注入**：借助 Python 的 `inspect.signature`，当调用 Handler 时，系统会安全地根据函数签名动态注入 `agent`（当前的 AgentLoop 实例）和 `state`（当前的 LoopState）。这样，不同 Skill 之间的开发是相互隔离的，但又能安全地访问到所需的系统环境。

**优势**：真正的“即插即用”。新增能力只需在 `skills/` 下新建目录并放置两个文件，完全无需修改引擎底层的调度代码。

---

## 2. 回归测试技能 (Regression Testing Skill)

### 解决了什么问题？
在安全漏洞修复 (FIXER 阶段) 之后，我们需要在 REVIEWER 阶段验证修复补丁。但如果修复方案破坏了程序原有的业务逻辑，那么这个补丁也是不合格的。以前系统只能验证漏洞是否被堵住，缺乏标准的回归测试流程。

### 核心设计与实现
新增的 `regression-tester` 技能补齐了这一短板：
1. **沙箱隔离执行**：回归测试完全在 Docker 沙箱中进行（`agent.sandbox.execute`），确保测试过程不会影响宿主机环境，同时也防止恶意测试脚本。
2. **状态机约束**：该技能在 `SKILL.md` 中被严格限制仅在 `REVIEWER` 和 `VALIDATOR` 状态下使用。
3. **自动化结果判别**：通过捕获测试命令的 `exit_code`，Handler 能够自动识别执行状态（0 为 `PASSED`，非 0 为 `FAILED`），并将标准输出（stdout）和标准错误（stderr）一并返回给 LLM。
4. **协作闭环**：LLM Reviewer 可以根据此测试结果决定是否将任务退回给 FIXER，形成完整的自动化质量保证闭环。

---

## 3. 黑板压缩策略 (Blackboard Compaction Policy)

### 解决了什么问题？
Agent 使用基于黑板（Blackboard）的机制来跨状态共享信息。随着任务复杂度的增加、多轮 FSM 跳转以及各种大段 Skill 文本的动态加载，黑板中累积的信息会导致 LLM Context 激增。这不仅会消耗过多的 Token 成本，还会带来注意力稀释和被大模型截断的风险。

### 核心概念说明

#### 什么是“旧状态” (Old States)？
在 FSM 状态机切换时，Agent 会通过 `transition_state` 工具生成一个当前阶段的 **Summary**（摘要）。例如，从 `INITIAL_ANALYSIS` 切换到 `VALIDATOR` 时，Agent 会在黑板上存入一个 `INITIAL_ANALYSIS_summary` 键值对。
- **作用**：让下一个状态（如 VALIDATOR）能够快速理解上一个状态（如 INITIAL_ANALYSIS）发现了什么漏洞、哪些是攻击入口，而无需重新阅读整个历史对话。
- **问题**：当 FSM 经历多次跳转（如 A -> B -> C -> D）时，黑板上会留存 A_summary, B_summary, C_summary... 这些早期的摘要对于当前处于 D 状态的 Agent 来说，其参考价值逐渐降低，但却持续占用着宝贵的上下文空间。这些不再属于“当前状态”的摘要即为 **旧状态**。

#### 为什么技能正文 (Skill Body) 会进入黑板？
在 `load_skill` 工具被调用时，技能的完整正文会被注入到黑板中（键名如 `loaded_skill_ast-scanner`）。
- **持久化上下文**：因为 `AgentLoop` 在每一轮（Turn）都会重新构建 System Prompt，并将整个黑板内容序列化后放入 Prompt 中。将技能正文存入黑板，是为了确保这份知识在当前阶段的 **后续多轮对话中持续可见**，而不需要 Agent 每轮都去重新调用 `load_skill`。
- **按需注入**：这符合“平时只显示目录，需要时才展开正文”的 S05 设计理念。

### 核心设计与实现
我们在 `AgentLoop.run_one_turn()` 中引入了自动触发的 `compact_blackboard()` 方法，按照优先级进行分层压缩：

1. **动态阈值监控**：每次调用 LLM 前，系统会将当前 Blackboard 转换为 JSON 字符串并检测其长度。如果超过设定阈值（默认为 4000 字符），将触发压缩。
2. **分层压缩逻辑**：
   - **第一层：归档旧状态摘要**：遍历黑板，寻找所有以 `_summary` 结尾且不属于当前所处 `state` 的键。将它们从黑板中删除，并添加一条 `archived_summaries` 提示，告知 LLM 旧信息已被清理。
   - **第二层：截断重型知识包**：如果清理完旧摘要后黑板依然超载，系统会遍历所有 `loaded_skill_` 开头的键，将其值替换为 `<Content compacted. Please reload skill if necessary.>`。
3. **自我恢复机制**：这种“硬截断”虽然会让 Agent 暂时失去这份技能正文，但由于 Prompt 中依然存在技能目录，Agent 在意识到知识缺失时，可以通过再次调用 `load_skill` 来重新获取最新的、完整的内容。

### 进阶思考与 FAQ

#### Q1：如果旧状态摘要被压缩了，模型还能找回那些详细信息吗？
**当前状态**：目前系统主要依靠 **原始对话历史 (Message History)** 作为底座。
- 虽然 `compact_blackboard` 会为了节省 Prompt 空间而从结构化的“黑板”中移除旧摘要，但这些信息依然存在于之前的对话轮次中。
- **回溯能力**：模型如果发现摘要丢失且确实需要细节，它会通过搜索之前的 `role: tool` 响应来获取信息。
- **未来演进**：可以考虑增加一个 `fetch_archived_summary` 工具，允许模型主动请求将特定的历史摘要重新提取回黑板，实现更精准的“记忆检索”。

#### Q2：技能正文进入黑板后，如果下一个状态用不到，会被自动筛掉吗？
**当前机制**：目前采取的是 **“按需加载，压力触发”** 的延迟清理策略，而不是基于状态的强制清理。
- **逻辑隔离**：即使 `INITIAL_ANALYSIS` 阶段加载的技能正文还残留在黑板中，但在进入 `VALIDATOR` 阶段后，`AgentLoop` 只会向模型暴露当前状态允许调用的 **工具列表 (Tools)**。这意味着模型即便能看到旧技能的说明，也无法调用它。
- **为什么不立即清理？**：某些技能（如 `file-ops`）是全阶段通用的。如果在状态切换时强制清理所有技能，会导致模型在每个新阶段都要重复调用 `load_skill`，造成不必要的 Turn 浪费。
- **压缩时机**：只有当黑板内容真正威胁到上下文窗口安全（触发阈值）时，系统才会不分青红皂白地截断所有非必要的技能正文，由模型决定是否需要重新加载。

---

## 4. 会话内规划系统 (Session Planning / Todo)

### 解决了什么问题？
在执行复杂的安全分析任务时（例如跨多个文件的污点追踪或复杂的漏洞利用编写），Agent 很容易“走一步忘一步”或者在多轮对话后偏离最初的目标。

### 核心设计与实现 (参考 S03 TodoWrite)
我们引入了显式的 **会话内规划 (In-session Planning)** 机制：
1. **结构化计划 (Structured Plan)**：通过 `update_plan` 工具，Agent 可以维护一个包含 `content`（任务内容）、`status`（状态：pending, in_progress, completed）和 `activeForm`（进行时描述）的列表。
2. **焦点约束 (Focus Constraint)**：Handler 强制要求同一时间只能有一个任务处于 `in_progress` 状态，迫使 LLM 保持焦点。
3. **显式提示 (Explicit Prompting)**：计划被从通用的黑板（Blackboard）中提取出来，在 System Prompt 中以可读的格式（如 `[>] 正在执行...`）独立展示。
4. **活度监控 (Liveness Monitoring)**：`AgentLoop` 会记录 `rounds_since_todo_update`。如果 Agent 连续 5 轮没有更新其计划，系统会自动注入一个 `<reminder>`，提醒 Agent 刷新其计划。

**优势**：将“正在做什么”从模型的隐含思维转变为显式的外部状态，显著减少了长任务中的“思维漂移”现象。