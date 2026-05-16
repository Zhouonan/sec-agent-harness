# Sec-Agent-Harness 特性对齐与开发计划 (Feature Alignment Plan)

## 1. 概述
本计划旨在弥补 `docs/interview_prep.md` 中描述的高阶架构特性与当前代码实现之间的差距。通过补全这些特性，确保项目在面试演示和实际运行中具备极高的技术竞争力。

## 2. 特性差距矩阵 (Gap Analysis)

| 面试技术锚点 | 优先级 | 当前实现 | 目标实现 |
| :--- | :--- | :--- | :--- |
| **Reducer 状态合并** | P0 | 简单赋值/追加 | 实现统一的 `reduce(state, update)` 逻辑，支持 `operator.add` 等合并语义。 |
| **基于结果的自动路由** | P0 | LLM 自主调用工具跳转 | 在 `loop.py` 中增加观察者逻辑，根据 Sandbox 结果、Test 结果自动触发 `transition`。 |
| **Checkpoint 持久化** | P1 | 无 | 每次 `run_one_turn` 结束后，自动将状态快照保存至 JSON，支持 `resume`。 |
| **HITL 断点审批** | P1 | 无 | 在 `FIXER` 执行敏感操作（如 `write_file`）前，暂停并等待 CLI 输入确认。 |
| **子图嵌套 (ReAct)** | P2 | 线性主循环 | 在 `VALIDATOR` 节点内封装一个微型循环，专门用于 PoC 迭代。 |
| **Skill 反思进化** | P3 | 静态加载 | 任务结束后增加 `REVIEW_STATE`，分析成功路径并自动更新 `SKILL.md` 的 Checklist。 |

## 3. 开发阶段规划

### 阶段一：硬核对齐 (Hardcore Alignment) - 预计 1-2 天
- **[ ] 重构 State 管理**：引入 `reducer.py`，规范 `blackboard` 的增量合并。
- **[ ] 路由自动化**：修改 `AgentLoop`，在 `handle_tool_call` 之后判断是否满足自动跳转条件（如 PoC 运行成功 -> 自动转 FIXER）。
- **[ ] 工具隔离强化**：在 `registry` 中更严格地限制不同 State 可见的工具集。

### 阶段二：架构演进 (Architectural Evolution) - 预计 2-3 天
- **[ ] 实现 Checkpoint**：增加 `core/persistence.py`，支持会话级别的断点续传。
- **[ ] 静态断点集成**：在 Hook 体系中加入 `HumanInterrupt` 异常拦截，实现人工审批流。
- **[ ] 上下文三级压缩**：细化 `compact_blackboard` 逻辑，增加对旧摘要的“结晶化”总结。

### 阶段三：自进化增强 (Self-Evolution) - 预计 3-5 天
- **[ ] 引入反思 Agent**：在主流程最后加入一个独立节点，利用长上下文总结经验。
- **[ ] Skill 自动结晶**：实现将常用的 shell 命令组合自动封装为新 Skill 工具的逻辑。

## 4. 维护说明
- 每次完成一个特性的开发后，需同步更新 `docs/design/modules.md` 和 `AGENT_ACTIVITY_LOG.md`。
- 重点关注 FSM 状态转换的确定性测试。
