# Sec-Agent-Harness: 模块技术说明文档 (中文版)

本文档详细解析了 Sec-Agent-Harness 项目核心模块的技术实现与设计思路。

---

## 1. 核心引擎 (`core/loop.py`)

`core/loop.py` 是 Agent 的“大脑”，通过 **有限状态机 (FSM)** 架构来管理复杂的安全审计工作流。

### 1.1 AgentState (状态枚举)
定义了漏洞挖掘与修复的完整生命周期：
- `INITIAL_ANALYSIS` (初始分析)：映射攻击面，识别污点源 (Source) 与汇聚点 (Sink)。**强化点**：强制优先执行目录扫描以建立路径感知。
- `VALIDATOR` (漏洞验证)：通过生成并执行 PoC 来证实漏洞。
- `FIXER` (漏洞修复)：针对已证实的漏洞生成高质量补丁。
- `REVIEWER` (修复审计)：在沙箱中验证补丁并运行回归测试。**强化点**：引入严格的逻辑门，测试失败必须回转至 `FIXER`，禁止在未通过时跳转 `DONE`。
- `DONE` / `ERROR`：终止状态。

### 1.2 LoopState (运行状态对象)
维护 Agent 的运行时数据：
- `messages`：对话历史记录。
- `current_state`：当前所处的 `AgentState`。
- `blackboard` (黑板)：用于 **上下文压实 (Context Compaction)**。不同状态间不再传递冗长的日志，而是将轻量级摘要（指针或关键数据）存储于此。
- `state_turn_count`：统计当前状态下的轮次，用于触发 **熔断机制 (Circuit Breaker)**，防止工具调用死循环。
- **活跃度监控**：新增轮数监控，若 Agent 长时间不调用工具将触发系统提示词 Nudge。

...

## 2. 技能系统 (`core/skill.py`)

...

### 2.2 核心技能包示例
- **file_ops**：提供 `read_file`, `write_file`, `list_files` (新增) 以及 `update_plan` 工具，支持 Agent 的基础文件交互与会话规划。
- **ast_scanner**：提供 `scan_python_file` 和 `find_definition` 处理器，实现高性能的进程内 AST 分析。

### 1.3 AgentLoop (编排器类)
执行基于轮次的循环：
- `transition_state` 工具：注入到每个状态中，允许 LLM 自主触发状态跳转并更新黑板数据。
- `run_one_turn`：根据当前状态获取专属的系统提示词和工具集，调用 LLM 并分发执行工具。

---

## 2. 技能系统 (`core/skill.py`)

`core/skill.py` 负责管理专业知识库和高性能工具（即“内核态 Skill”）。

### 2.1 SkillRegistry (技能注册中心)
- **自动发现**：扫描 `skills/` 目录下的 `SKILL.md` 文件。
- **双层加载机制**：
    - *第一层*：将技能元数据（名称/描述）注入系统提示词，让 Agent 知晓可用能力。
    - *第二层*：提供 `load_skill` 工具，仅在需要时加载完整的指令集，保持上下文窗口的精简。
- **内核态概念**：高性能分析器（如 AST 解析器）被设计为进程内加载的技能，以消除 RPC 或序列化带来的延迟。

---

## 3. 数据流与交互逻辑

1. **查询 (Query)**：用户输入目标代码库或任务。
2. **分析 (Analysis)**：`AgentLoop` 从 `INITIAL_ANALYSIS` 状态启动，利用 `SkillRegistry` 检索安全技能。
3. **黑板 (Blackboard)**：分析结果被写入 `blackboard`。
4. **跳转 (Transition)**：Agent 调用 `transition_state` 跳转至 `VALIDATOR`。
5. **验证 (Validation)**：(规划中) `VALIDATOR` 状态利用沙箱工具验证漏洞真实性。
