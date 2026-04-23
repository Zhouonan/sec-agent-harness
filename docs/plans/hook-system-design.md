# Sec-Agent-Harness: Hook 系统架构与开发设计文档

## 1. 模块功能介绍 (Module Introduction)
根据 `s08-hook-system.md` 的核心思想与 `SELF_HEALING_STRATEGY_2026.md` 的演进需求，Hook 模块旨在为当前的 Agent FSM 主循环引入**非侵入式的扩展机制**。

当 Agent 在复杂任务中（如验证漏洞、打补丁）调用工具时，如果将所有安全扫描、日志记录、错误诊断的逻辑都硬编码在 `core/loop.py` 中，会导致代码极度臃肿。Hook 模块允许外部代码在固定生命周期节点（Lifecycle Events）介入并观察/影响当前工具的执行。

### 核心生命周期事件 (Lifecycle Events)
1. **`SessionStart`**: 在会话初始化时触发（适合环境探针、依赖版本拉取、读取历史记忆规则）。
2. **`PreToolUse`**: 在调用具体工具之前触发。可以：
   - **阻断 (Block)**：如果工具参数存在风险或不合规，拒绝执行并返回错误建议给 Agent。
   - **注入 (Inject)**：在工具执行前注入额外的分析提示。
3. **`PostToolUse`**: 工具调用之后触发。是实现**“诊断子循环”**的核心：
   - 捕获复杂错误（如测试失败、环境异常），并自动追加现场快照（当前目录、系统路径）。
   - 将“带参回溯”所需的失败尝试记录写入 `Blackboard`。

---

## 2. 多个技术选型与优劣分析 (Technical Options Analysis)

为了满足既有系统的复杂性和扩展需求，我们设计了三种可能的技术路线。

### 选型 A：Shell-based Subprocess Hooks (基于子进程的原生 s08 方案)
通过项目根目录的 `.hooks.json` 配置，Hook 以外部 Shell 命令或脚本形式独立运行。通过环境变量（如 `HOOK_EVENT`, `HOOK_TOOL_NAME`）传递上下文，通过退出码（0/1/2）和标准错误输出与主 Agent 通信。

- **优势 (Pros)**：
  - **语言无关与高隔离性**：不同团队可以用 Bash、Go 或 JS 编写 Hook，完全不会污染主干代码。
  - **防御性极佳**：恶意的或崩溃的 Hook 不会导致整个 AgentLoop 崩溃。
- **劣势 (Cons)**：
  - **进程创建开销大**：每次高频的工具调用都要 Fork 子进程，造成性能损耗。
  - **状态隔离**：无法直接读取或修改 Python 进程内的 `LoopState.blackboard`，导致实现复杂的基于记忆的自愈策略（如维护连续失败次数 `failed_attempts`）非常困难。

### 选型 B：Native Python Callback Hooks (进程内回调方案)
在 `core/` 下引入 `hook_registry.py`，允许在 Python 代码中通过装饰器 `@hook('PostToolUse', matcher='execute_in_sandbox')` 注册函数。Hook 在 `loop.py` 的相同进程内执行，接收 `LoopState` 对象和工具参数。

- **技术细节 (Technical Details)**：
  - **装饰器实现原理 (@hook)**：
    - **加载期注册 (Registration)**：装饰器本质上是一个“注册器工厂”。在 Python 解释器加载模块（Import）阶段，装饰器会立即执行，将目标函数及其触发条件（Event, Matcher）记录到全局单例 `HookRegistry` 的映射表中。
    - **发布-订阅模式 (Pub-Sub)**：`@hook` 并不修改原函数逻辑，而是将其标记为特定事件的“订阅者”。
    - **对象引用直传**：Dispatcher 在触发时，直接将 `state` (LoopState) 和 `result` (ToolResult) 的**内存引用**传递给 Hook。这使得 Hook 具有“外科医生”般的干预能力——它可以直接在内存中修改 Blackboard 计数、追加消息，甚至强行变更 FSM 的 `current_state`。
  - **HookRegistry 实现**：采用单例模式维护一个 `events -> list[dict(func, matcher, priority)]` 的映射表。
  - **上下文共享**：Hook 函数直接接收 `state: LoopState` 对象。这意味着 Hook 可以直接修改 `state.blackboard`（如增加失败计数器）或直接向 `state.messages` 注入诊断消息。
  - **异常捕获闸门**：Dispatcher 使用强健的 `try...except` 包裹每个 Hook 的执行，防止单个 Hook 崩溃导致主循环退出。
  - **同步阻塞调用**：由于主循环目前是同步的，Hook 亦采用同步阻塞方式，确保在工具执行前逻辑已生效。
- **优势 (Pros)**：
  - **零 IPC 性能损耗**：进程内调用，开销极小。
  - **全局上下文透传**：可以直接读写 `LoopState`、`Blackboard` 和 `messages`，这对于落实《复杂错误自愈方案》中的“状态回溯”、“记忆提炼”至关重要。
- **劣势 (Cons)**：
  - **耦合度与脆弱性**：只能用 Python 编写；虽然有异常保护，但错误的 Hook 可能篡改核心状态导致逻辑混乱。

### 选型 C：Hybrid Plugin-driven Hooks (混合插件架构)
由 `config.yaml` 或 `.hooks.yaml` 驱动，支持插件包（Plugin Bundle）的概念。一个插件可以包含 `__init__.py`（注册 Python 回调）和 `scripts/`（存放外部脚本）。

- **技术细节 (Technical Details)**：
  - **多模式驱动器 (Polyglot Dispatcher)**：
    - **Python 模式**：使用 `importlib` 动态加载配置的模块，寻找指定的入口类/函数。
    - **Shell 模式**：模仿 Claude Code，使用 `subprocess.run` 执行脚本，并通过环境变量注入关键上下文（如 `SEC_AGENT_CWD`, `SEC_AGENT_STATE_JSON`）。
  - **统一结果协议 (Unified Result Protocol)**：定义 `HookResult` 类，包含 `status` (continue/block/inject), `output` (诊断文本), 和 `modified_payload` (允许修改工具参数)。
  - **加载器优先级**：允许配置 Hook 的执行顺序（Priority），例如安全拦截 Hook 始终在日志记录 Hook 之前执行。
- **优势 (Pros)**：
  - **完美兼顾**：用 Python 处理高性能/强状态依赖的内部诊断，用 Shell 处理跨团队的安全卡点（如执行外部 Lint 检查）。
  - **生态友好**：方便安全研究员使用自己擅长的工具链（如用 Go 写的高性能扫描器）作为 Hook。
- **劣势 (Cons)**：
  - **实现复杂度最高**：需要同时维护两种协议（对象级传递 vs 环境变量+退出码解析）。

---

## 3. 行业标杆参考 (Industry Benchmarks)

在设计本项目 Hook 系统时，我们调研并参考了以下主流 Agent 的实现方案：

| 智能体 | 核心 Hook 机制 | 通信协议 | 核心特点 |
| :--- | :--- | :--- | :--- |
| **Claude Code** | Shell/Subprocess | JSON via Stdin + Exit Codes | **拦截器模式**：通过退出码 (0/1/2) 决定是允许、失败还是强制拦截。支持 12+ 生命周期点。 |
| **OpenHands** | Event-Sourced Hooks | Python Class / Docker Exec | **溯源驱动**：基于事件流触发，强调在 Docker 沙箱内执行工具后的自动补救（如自动运行 Pylint）。 |
| **OpenClaw** | Plugin Callbacks | Native Python Objects | **高集成度**：提供 28+ 细粒度 Hook 点，插件可深度干预推理大脑（Brain）的逻辑。 |

**对本项目的启发**：
- **拦截能力**：应学习 Claude Code 的退出码机制，为 `PreToolUse` 提供强力的拦截语义。
- **状态访问**：应学习 OpenClaw 的对象直传，确保自愈逻辑能读写 Blackboard。
- **自动化补救**：应学习 OpenHands 的思路，在 `PostToolUse` 中自动注入环境探针信息。

## 4. 场景化流程对比：自动化代码检查 (Auto-Linting)

为了直观展示不同选型的差异，我们以 **“在 Agent 修改代码后自动运行 Linter 并回传建议”** 为例，详细拆解各方案的执行链。

### 场景描述：
Agent 在 `FIXER` 状态调用 `write_file` 修复了一个 Bug。Hook 需要在文件写入后自动运行 `pylint`，如果发现语法错误或风格问题，将警告信息追加到工具输出中，引导 Agent 自行修正。

---

### 选型 A：Shell-based Subprocess (外部脚本驱动)
1.  **准备**：根目录存在 `.hooks.json`，配置了 `PostToolUse` 事件运行 `.hooks/lint.sh`。
2.  **触发**：`loop.py` 完成 `write_file` 执行。
3.  **环境准备**：`loop.py` 设置环境变量：
    - `HOOK_TOOL_NAME=write_file`
    - `HOOK_TOOL_INPUT={"path": "app.py", "content": "..."}`
    - `HOOK_TOOL_OUTPUT="Successfully wrote file app.py"`
4.  **子进程执行**：`loop.py` 调用 `bash .hooks/lint.sh`。
5.  **脚本逻辑**：`lint.sh` 读取环境变量，提取路径 `app.py`，运行 `pylint app.py`。
6.  **结果回传**：`lint.sh` 将 `pylint` 的报错输出到 `stderr`，并以 **Exit Code 2 (Inject)** 退出。
7.  **主循环处理**：`loop.py` 捕获到退出码 2，读取 `stderr` 中的 Lint 警告，将其拼接到 Agent 看到的工具返回信息末尾。

### 选型 B：Native Python Callback (进程内对象驱动)
1.  **准备**：在 `core/hooks/lint_plugin.py` 中定义了一个 Python 函数，并用 `@hook('PostToolUse', matcher='write_file')` 装饰。
2.  **触发**：`loop.py` 完成 `write_file` 执行。
3.  **内部分发**：`hook_manager` 直接在当前进程调用该函数，传入 `(state, tool_name, args, result)` 对象。
4.  **插件逻辑**：函数内部使用 `subprocess` 或 Python API 运行 `pylint`。
5.  **状态交互（关键差异）**：
    - 函数直接修改 `result.output += "\n[Linter Warning]: ..."`。
    - **进阶自愈**：函数检测到严重语法错误，直接修改 `state.blackboard['consecutive_lint_failures'] += 1`。如果次数 > 3，函数甚至可以直接修改 `state.current_state = AgentState.INITIAL_ANALYSIS` 强制 Agent 重新分析（无需通过 LLM 决定）。
6.  **返回**：函数执行完毕，`loop.py` 无缝继续下一轮。

### 选型 C：Hybrid Plugin (混合模式驱动)
1.  **配置**：`config.yaml` 声明了两个 Hook：一个是 `type: python` 的内部诊断插件，一个是 `type: shell` 的团队合规脚本。
2.  **第一步（Python Hook）**：执行流程同选型 B，完成 Blackboard 的计数更新和深度状态检查。
3.  **第二步（Shell Hook）**：执行流程同选型 A，调用公司统一的安全合规脚本。
4.  **聚合输出**：`hook_manager` 汇总 Python 插件的修改结果和 Shell 脚本的 `stderr` 注入，最终将一份完整、多维的反馈包提供给 Agent。

---

## 5. 与现有系统的适配度分析 (Compatibility & Integration)


当前 `sec-agent-harness` 在 `core/loop.py` 中存在大量**硬编码的诊断逻辑**（例如在 `sandbox_handler` 失败时硬编码追加 `[SYSTEM ADVICE]`）。

**推荐选型结论：【选型 C (以选型 B 为核心起步)】**
考虑到《高级 Agent 复杂错误自愈与持续进化方案 (2026 版)》对 **Blackboard 状态读写**（如连续失败计数、历史记忆召回）有极高依赖，纯 Shell 方案（A）难以胜任。
1. **最佳路径**：首期实现**选型 B (Python 原生 Hook)**，以最快速度将现有硬编码解耦，并在 `run_one_turn` 函数调用前后插入 Hook 派发点。
2. **渐进式升级**：在基础稳固后，向选型 C 演进，暴露外部 `shell` 调用接口，满足 `s08-hook-system.md` 的纯粹外部扩展需求。

### 核心切入点：
在 `loop.py` 的 `run_one_turn` 方法中重构工具调用逻辑：
```python
# 1. 触发 PreToolUse
pre_result = hook_manager.run_hooks("PreToolUse", state, name, args)
if pre_result.blocked:
    return pre_result.error_message # 直接写入 messages

# 2. 原始工具执行
result = handler(**kwargs)

# 3. 触发 PostToolUse (在这里实现自愈诊断)
post_result = hook_manager.run_hooks("PostToolUse", state, name, args, result)
result.output += post_result.injected_diagnostics
```

---

## 4. 开发阶段规划 (Development Phase Planning)

### Phase 1: 核心框架基建 (1-2 天)
- **目标**：实现 Hook 管理器与 `LoopState` 的集成。
- **任务**：
  1. 创建 `core/hook.py`，定义 `HookEvent`, `HookResult` 和 `HookRegistry`。
  2. 修改 `core/loop.py`，在工具执行前后插入 Hook 分发点。
  3. 配置加载：在 `config.yaml` 中支持声明 Hook 模块的路径。

### Phase 2: 逻辑解耦与迁移 (2-3 天)
- **目标**：消除现有的硬编码逻辑，验证 Hook 系统的有效性。
- **任务**：
  1. 将 `sandbox_handler` 中的硬编码 `[SYSTEM ADVICE]` 剥离，迁移为 `SystemAdviceHook` (监听 `PostToolUse` 事件)。
  2. 将 `transition_handler` 中的“禁止跳级到 DONE”逻辑迁移至 `PreToolUse` 的拦截策略中。

### Phase 3: 高级自愈与环境探针落地 (3-5 天)
- **目标**：实现 `SELF_HEALING_STRATEGY_2026.md` 的核心诉求。
- **任务**：
  1. 编写 **Context Snapshot Hook**：在执行报错时，自动获取当前目录结构和 `which python` 追加至错误输出。
  2. 编写 **Tactical Backtracking Hook**：在黑板 (`Blackboard`) 记录 `failed_attempts`，连续失败 3 次强制重置状态。

### Phase 4: 测试与对抗 (1-2 天)
- **目标**：遵循 `TESTER_AGENT_GUIDE.md` 进行破坏性测试。
- **任务**：
  1. 模拟崩溃的 Hook，验证 `hook_registry` 的容错机制是否会导致 `AgentLoop` 主循环崩溃。
  2. 验证 Hook 大量注入数据是否会被 Blackboard 的 Compact 逻辑正确压实。
  3. 更新 `AGENT_ACTIVITY_LOG.md` 和文档映射。