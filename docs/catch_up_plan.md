# Sec-Agent-Harness 图驱动架构升级计划

本计划基于 `docs/interview_prep.md` 中的目标架构，以及当前 `core/loop.py`、`core/hook.py`、`core/skill.py`、`core/sandbox.py` 的实现现状。

当前系统已经具备 FSM 状态、Hook、Skill、Sandbox、Eval 等基础能力，但控制流仍主要依赖 LLM 调用 `transition_state` 来主动跳转，`blackboard` 仍是无约束 `Dict`，`AgentLoop` 同时承担图调度、Prompt 构建、工具执行、状态变更、压缩和日志等多重职责。

下一阶段的核心目标不是简单增加更多状态，而是将系统重构为一个**图驱动 Agent Runtime**：

- **任务阶段是节点**：如 `INITIAL_ANALYSIS`、`VALIDATOR`、`FIXER`、`REVIEWER`。
- **阶段流转是边**：边由确定性条件、结构化信号、证据门卡和熔断策略共同决定。
- **LLM 只负责节点内语义推理**：例如发现漏洞、写 PoC、生成 patch、解释测试失败。
- **引擎负责控制流**：模型不直接决定下一节点，只产出结构化信号，下一步由 `EdgeRouter` 决定。

核心原则：**确定性计算交给代码，语义推理交给模型。**

---

## Phase 0：运行时边界收紧 (Runtime Boundary Cleanup)

**目标**：先消除当前实现中最危险的隐式状态写入，为图驱动改造铺路。

1. **统一状态转移入口**
   - **现状**：
     - `transition_handler` 直接修改 `state.current_state`。
     - 部分 Hook 可直接修改 `state.current_state` 实现回退。
   - **行动**：
     - 新增 `TransitionEngine`，所有节点切换都必须通过 `commit_transition(...)`。
     - Hook 不再直接改状态，只能返回 `TransitionRequest`、`RecoveryAdvice` 或 `HookResult`。
     - 在测试中禁止除 `TransitionEngine` 外的运行时代码写入 `state.current_state`。

2. **修正安全边界工具**
   - **现状**：路径检查使用字符串前缀判断，存在边界误判风险。
   - **行动**：
     - `_safe_path` 改用 `os.path.commonpath` 校验 workspace 边界。
     - 将路径校验从 `AgentLoop` 下沉到独立 `WorkspacePolicy` 或 `PathGuard`。

3. **保留兼容层**
   - `transition_state` 暂时保留，但内部改为生成结构化 transition request。
   - 旧测试先不大规模改写，确保重构期间行为可回归。

**验收标准**：
- 代码中运行时状态切换只剩一个提交入口。
- Hook 无法绕过图路由直接跳状态。
- 现有 FSM/Hook 单元测试保持通过。

---

## Phase 1：声明式图运行时 (Graph Runtime MVP)

**目标**：将硬编码 FSM 演进为声明式图，让节点、边、工具权限、证据门卡和熔断策略都可配置、可测试。

1. **定义 `GraphSpec`**
   - 节点字段：
     - `name`
     - `prompt_template`
     - `tools`
     - `max_turns`
     - `context_policy`
     - `is_terminal`
   - 边字段：
     - `from_node`
     - `to_node`
     - `condition`
     - `priority`
     - `evidence_gate`
     - `approval_policy`
     - `fallback`

2. **实现 `EdgeRouter`**
   - 输入：`current_node + LoopState + NodeResult`。
   - 输出：`RouteDecision`，如：
     - `continue_current_node`
     - `transition_to(next_node)`
     - `blocked_by_evidence_gate`
     - `pause_for_approval`
     - `finish`
     - `error`
   - 普通 happy path 示例：
     - `INITIAL_ANALYSIS` 输出 findings 完成信号 -> `VALIDATOR`
     - `VALIDATOR` 确认 PoC -> `FIXER`
     - `FIXER` patch ready -> `REVIEWER`
     - `REVIEWER` tests passed -> `DONE`

3. **弱化 `transition_state` 工具**
   - **目标状态**：模型不再直接说“去哪个状态”。
   - 新增节点内信号工具：
     - `report_finding(...)`
     - `finish_analysis(...)`
     - `confirm_validation(...)`
     - `abort_validation(...)`
     - `submit_patch(...)`
     - `report_review_result(...)`
   - 这些工具只写入 state delta，下一步由 `EdgeRouter` 决定。

4. **节点级工具权限接入图配置**
   - 当前 `Dict[AgentState, List[Tool]]` 迁移为 `GraphSpec.nodes[*].tools`。
   - Skill frontmatter 中的 `states` 字段逐步兼容为 `nodes` 字段。
   - 默认策略仍是最小权限：
     - 分析节点只读。
     - 验证/审查节点可用 sandbox。
     - 修复节点可写文件。

**验收标准**：
- 主流程可由 `GraphSpec` 声明，而不是散落在 `AgentLoop` 和 Hook 中。
- LLM 不能直接决定目标节点。
- `EdgeRouter` 的条件边可用纯单元测试覆盖。

---

## Phase 2：结构化 State 与 Reducer (Typed State & Reducer)

**目标**：让图中各节点通过结构化增量写入共享状态，避免 `blackboard` key 混乱、覆盖丢失和上下文压缩不安全。

1. **定义结构化 Blackboard Schema**
   - `project_profile`
     - `tech_stack`
     - `entry_points`
     - `high_risk_areas`
     - `file_count`
   - `threat_model`
     - `assets`
     - `trust_boundaries`
     - `attack_surfaces`
     - `high_impact_paths`
   - `findings`
     - `id`
     - `title`
     - `severity`
     - `file_path`
     - `hypothesis`
     - `evidence_chain`
     - `status`
   - `poc_results`
   - `patches`
   - `review_results`
   - `coverage`
   - `retry_context`
   - `observations`

2. **实现 Reducer 合并语义**
   - `findings`：追加 + 按 `id` 去重/更新。
   - `poc_results`：按 `finding_id` 追加版本。
   - `patches`：追加。
   - `project_profile`：字典合并。
   - `coverage`：集合合并并重新计算比例。
   - `current_node`：只能由 `TransitionEngine` 覆盖。

3. **把工具返回改为 `StateDelta`**
   - 工具 handler 不直接写 `state.blackboard[...]`。
   - handler 返回：
     - human readable output
     - structured delta
     - artifacts
   - `StateStore.reduce(...)` 统一应用 delta。

4. **加入状态变更日志**
   - 每次 reducer 应记录：
     - turn
     - node
     - tool
     - delta keys
     - before/after hash
   - 供后续 Checkpoint、Eval 和行为回放使用。

**验收标准**：
- `blackboard` 的核心字段不再由任意字符串 key 随意写入。
- 状态更新可重放、可审计、可测试。
- L1 上下文清洗依赖的“结晶数据”有结构保障。

---

## Phase 3：节点运行器与上下文管理拆分 (NodeRunner & ContextManager)

**目标**：拆薄 `AgentLoop`，让图运行时的各个模块成为深模块。

1. **拆出 `NodeRunner`**
   - 负责单节点 ReAct 循环：
     - 构建当前节点 prompt。
     - 调用 LLM。
     - 执行工具。
     - 产生 `NodeResult`。
   - 不直接决定下一节点。

2. **拆出 `ToolRuntime`**
   - 统一处理：
     - tool call 参数解析。
     - handler 签名注入。
     - PRE/POST Hook。
     - 错误包装。
     - 输出截断。
     - turn_log 记录。

3. **拆出 `ContextManager`**
   - 负责：
     - 当前节点 system prompt。
     - Skill catalog 注入。
     - Blackboard 渲染。
     - L1/L2/L3 压缩策略。
     - 工具类型相关截断。

4. **保留 `AgentLoop` 为 Orchestrator**
   - 目标形态：
     - `node_runner.run(...)`
     - `state_store.reduce(...)`
     - `edge_router.route(...)`
     - `transition_engine.commit(...)`

**验收标准**：
- `AgentLoop` 不再直接处理所有运行时细节。
- Prompt、工具执行、路由、状态归约可分别单测。
- 新增节点不需要修改主循环。

---

## Phase 4：子图与语义短路 (Subgraphs & Semantic Short-Circuit)

**目标**：将复杂阶段封装为子图，既保留主图稳定性，又允许阶段内部有更细粒度控制。

1. **优先实现 `VALIDATOR` ReAct 子图**
   - 内部流程：
     - `WRITE_POC`
     - `RUN_SANDBOX`
     - `DIAGNOSE_FAILURE`
     - `RETRY_OR_CONFIRM`
   - 输出：
     - `validation_confirmed`
     - `validation_failed`
     - `abort_validation`

2. **实现 `INITIAL_ANALYSIS` 多阶段子图**
   - 内部流程：
     - `PLANNING`
     - `DEEP_ANALYSIS`
     - `CRITIQUE`
   - `PLANNING` 产出项目画像和审计计划。
   - `DEEP_ANALYSIS` 产出 findings 和 coverage。
   - `CRITIQUE` 过滤低置信度 finding。

3. **实现语义短路信号**
   - 示例：
     - VALIDATOR 发现漏洞不可利用 -> `abort_validation(reason, classification=false_positive)`。
     - ANALYSIS 发现无有效攻击面 -> `finish_analysis(no_findings=True)`。
   - LLM 只提交语义信号。
   - `EdgeRouter` 根据信号和当前 state 决定跳过、回退或继续。

4. **避免图爆炸**
   - 主图保持粗粒度。
   - 子图表达局部复杂性。
   - 子图内部状态默认不暴露给主图，只输出结构化结果。

**验收标准**：
- 至少一个阶段由子图运行。
- 子图可独立配置工具、prompt、轮次和上下文策略。
- 语义短路不绕过 `EdgeRouter`。

---

## Phase 5：自主证据门卡、Checkpoint 与可回放审计轨迹

**目标**：优先提升 Agent 的自主审计能力，让关键状态转移由证据质量驱动；同时保留未来接入人工审批的接口，并实现暂停、恢复和事后回放能力。

1. **证据门卡作为主流程策略**
   - `INITIAL_ANALYSIS -> VALIDATOR`：
     - finding 必须包含文件位置、攻击假设、证据链、置信度。
     - Critique 后仍保留的 finding 才能进入验证。
   - `REVIEWER -> DONE`：
     - 必须有已确认 PoC 或明确验证证据。
     - 必须有 patch rationale。
     - 必须有回归测试结果。
     - 必须通过 anti-cheat 检查。
   - 全局熔断：
     - 引擎优先生成阶段性报告。
     - 根据已有 findings、验证结果和剩余预算决定继续、回退或结束。

2. **预留 ApprovalPolicy 接口**
   - 当前默认实现：`AutoApprovalPolicy`。
   - 行为：
     - 证据门卡通过 -> 自动继续。
     - 证据不足 -> 阻断或回退，而不是等待人工。
   - 未来可替换为：
     - `HumanApprovalPolicy`
     - `RiskBasedApprovalPolicy`
     - `ComplianceApprovalPolicy`
   - `GraphSpec` 中保留 `approval_policy` 字段，但默认 `mode=auto`。

3. **Checkpoint 生命周期**
   - 状态切换前。
   - L2 Blackboard Eviction 前。
   - approval pause 前。
   - 全局熔断前。
   - 有副作用工具执行前后。

4. **状态恢复与幂等性**
   - Checkpoint 记录：
     - current node
     - graph version
     - messages
     - blackboard
     - artifacts
     - side effects
   - 恢复后避免重复执行已完成的写文件、patch、git 等副作用操作。

5. **行为回放**
   - 基于 `state_path`、`turn_log`、`state_delta_log`、checkpoints 重建执行轨迹。
   - 支持回答：
     - 某个 finding 是何时产生的？
     - 为什么从 VALIDATOR 回退到 INITIAL_ANALYSIS？
     - 哪次工具输出影响了 patch 决策？

**验收标准**：
- 关键边由证据门卡自动判定，不依赖人工确认。
- approval policy 有接口和默认自动实现。
- approval pause 作为扩展能力保留，但不阻塞当前自主审计主线。
- 崩溃后可从最近 checkpoint 继续。
- 能生成基本执行轨迹报告。

---

## Phase 6：Skill、项目知识与自进化 (Knowledge Evolution)

**目标**：在稳定图运行时之上，让 Agent 从一次性扫描器进化为项目级安全专家。

1. **Skill 三层加载完善**
   - META：`SKILL.md` frontmatter + workflow。
   - REFERENCES：深度文档、checklist、case studies。
   - ASSETS：危险函数、source/sink、sanitizer JSON。

2. **项目级 Skill Overlay**
   - 路径：
     - `.sec-agent/skill_overrides/<skill_name>/safe_functions.json`
     - `.sec-agent/skill_overrides/<skill_name>/project_sinks.json`
     - `.sec-agent/skill_overrides/<skill_name>/project_guards.json`
   - 加载顺序：
     - 通用 Skill。
     - 项目 overlay。
     - 当前 session observations。

3. **结晶流**
   - `observations`、reviewer 误报修正、PoC 成功路径、未来 approval feedback，在 session 结束后进入反思阶段。
   - 反思阶段只生成知识变更建议，不直接改主分支。

4. **知识退化防御**
   - 每次自进化生成 PR。
   - PR 必须附带回归测试用例。
   - Skill CI 检查：
     - precision 不下降。
     - recall 不下降。
     - 既有用例不回归。

5. **Code-Graph-Indexed Activation**
   - 将项目知识挂载到 AST/call graph 节点。
   - 分析某条调用链时，只激活路径相关知识。
   - 避免把整个项目 overlay 注入上下文。

**验收标准**：
- 项目 overlay 可被加载并影响分析工具。
- 自进化只以 PR 形式提出，不直接污染知识库。
- Skill 变更有回归基准保护。

---

## Phase 7：评测体系升级 (Graph-Aware Evaluation)

**目标**：让每次架构改动都能被量化评估，避免图驱动重构后只凭主观感觉判断效果。

1. **扩展 process_score**
   - 不只检查是否访问四个旧状态。
   - 改为检查：
     - 是否符合 GraphSpec 合法路径。
     - 是否使用必要节点。
     - 是否出现非法回退。
     - 是否正确处理证据门卡、approval policy 和熔断。

2. **增加 route_score**
   - 判断边选择是否合理：
     - 测试失败不能进入 DONE。
     - PoC 未确认不能进入 FIXER。
     - REVIEWER 失败应回到 FIXER 或 VALIDATOR。

3. **增加 evidence_score**
   - finding 是否包含：
     - source/sink 或攻击入口。
     - 文件路径与代码片段。
     - evidence_chain。
     - PoC 或验证结果。

4. **引入 anti-cheat review**
   - 防止 Agent 通过删除功能、吞异常、绕过测试来“修复”漏洞。
   - Reviewer 必须检查：
     - 漏洞根因是否被消除。
     - 正常业务路径是否保留。
     - patch 是否最小。
     - 是否新增安全风险。

5. **趋势追踪**
   - 对比图重构前后：
     - correctness。
     - process。
     - efficiency。
     - route validity。
     - false positive/false negative。

**验收标准**：
- 图驱动重构后的评测不再只依赖旧 `state_path`。
- 回归报告能指出是修复质量问题、路由问题、证据链问题还是效率问题。

---

## 推荐执行顺序

1. **Phase 0：运行时边界收紧**
2. **Phase 1：Graph Runtime MVP**
3. **Phase 2：Typed State & Reducer**
4. **Phase 3：拆分 NodeRunner / ToolRuntime / ContextManager**
5. **Phase 4：先落地 VALIDATOR 子图，再落地 INITIAL_ANALYSIS 子图**
6. **Phase 5：自主证据门卡 + Checkpoint + ApprovalPolicy 预留接口**
7. **Phase 7：Graph-aware Eval**
8. **Phase 6：Skill 自进化与项目知识层**

注意：Phase 6 的想象空间最大，但它必须建立在稳定的图运行时、结构化状态和回归评测之上。否则让 Agent 在运行时不稳定的情况下修改自己的知识库，会放大错误并造成知识退化。

---

## 当前最小可行里程碑

下一轮开发建议先完成一个小闭环：

1. 新增 `GraphSpec`、`EdgeRouter`、`TransitionEngine`。
2. 用 GraphSpec 表达现有四阶段主流程。
3. 保持旧工具与旧测试兼容。
4. 将 `transition_state` 内部改为 route request，不再直接改 `state.current_state`。
5. 为 EdgeRouter 补单元测试：
   - analysis done -> validator
   - validation confirmed -> fixer
   - patch ready -> reviewer
   - review passed -> done
   - review failed -> fixer
   - max turns -> configured fallback or approval policy

完成这个里程碑后，再继续推进 typed blackboard 和子图，不要一口气把所有愿景同时实现。
