# Todo 系统与规划机制提升建议文档

## 1. 概述
当前的 Todo 系统通过 `update_plan` 工具实现了基础的状态管理和焦点约束。然而，面对极其复杂的安全分析任务（如跨多文件的漏洞链路分析），现有的扁平化计划结构和手动更新模式仍有提升空间。

## 2. 短期改进方案 (Low-Hanging Fruit)

### 2.1 计划持久化 (Persistence)
- **现状**：计划目前仅存在于内存中的 Blackboard，一旦程序崩溃，进度将完全丢失。
- **改进**：每次 `update_plan` 成功后，自动将计划快照同步到本地文件（如 `.sec-agent/plan.json`）。在 `AgentLoop` 启动时，增加“恢复模式”以从该文件重新加载进度。

### 2.2 FSM 状态自动联动 (State Alignment)
- **现状**：Agent 必须手动调用 `update_plan` 来标记任务完成，这有时会导致 Blackboard 状态与 FSM 实际状态脱节。
- **改进**：当 `transition_handler` 触发状态转换时，系统可以尝试自动识别并更新对应的计划项。例如，从 `INITIAL_ANALYSIS` 进入 `VALIDATOR` 时，自动将“分析攻击面”标记为 `completed`。

### 2.3 语义一致性检查
- **现状**：Agent 可能会在 `update_plan` 中写一套，但实际操作另一套。
- **改进**：在 Prompt 中加入约束，对比 `activeForm` 描述的行为与 Agent 过去 3 轮执行的工具调用。如果发现严重偏离（如计划说在修复，实际在扫描），系统主动注入一个 `Planning Mismatch` 的警告信息。

## 3. 中期增强方案 (Structural Changes)

### 3.1 层次化子任务 (Hierarchical Tasks)
- **现状**：计划是扁平的列表。
- **改进**：引入父子任务结构。例如，主任务为“修复 SQL 注入”，子任务包含“定位 Sink 点”、“生成补丁”、“运行回归测试”。这有助于 Agent 处理需要 20 轮以上的复杂任务。

### 3.2 依赖关系追踪
- **现状**：任务之间没有逻辑关联。
- **改进**：允许定义任务依赖（Depends-on）。只有当前序任务标记为 `completed` 时，后续任务才允许进入 `in_progress` 状态。

### 3.3 动态重要性排序
- **改进**：为每个 Todo 项增加 `priority` 属性。当全局 `turn_count` 接近 `total_max_turns` 时，提示 Agent 优先处理高优先级任务，并考虑裁剪低优先级任务。

## 4. 长期愿景 (AI-Driven Autonomy)

### 4.1 预演式规划 (Proactive Planning)
- **改进**：在 `INITIAL_ANALYSIS` 阶段，要求 Agent 先生成一个完整的“任务路线图”。系统根据该路线图的复杂度，动态调整 `total_max_turns` 配额。

### 4.2 计划失败后的自我重构 (Self-Healing Plan)
- **改进**：当 `VALIDATOR` 状态下的 PoC 运行失败（验证失败）时，系统可以强制触发一个 `PLAN_REVISION` 会话，要求 Agent 解释为何计划失败，并更新后续所有步骤，而不是简单地死循环。

## 5. 总结
通过引入**持久化**、**层级化**和**状态联动**，Todo 系统将从一个简单的“记事本”进化为真正的“任务导航仪”，大幅提升 Agent 在处理非线性安全任务时的鲁棒性和成功率。
