# 设计方案：通用认知干预与决策模块 (Decision Center)

## 1. 行业标杆参考 (Industry Benchmarks)

在设计本模块前，我们深度分析了 2025/2026 年最先进的智能体架构：

| 智能体 | 决策机制 | 关键技术点 | 启发 |
| :--- | :--- | :--- | :--- |
| **Claude Code** | 确定性拦截 (Middleware) | 退出码 (0/1/2) + JSON 上下文管道。 | 决策结果必须是确定性的，且能够直接影响主循环的执行路径。 |
| **OpenClaw** | 中心化网关 (Gateway) | 所有工具调用必须经过 Gateway 审计，支持多渠道 (Slack/WA) 异步人工确认。 | 干预模块应独立于业务逻辑（Skill），作为一个控制平面的“安全网”。 |
| **Hermes** | 学习循环 (Learning Loop) | 性能 Delta 计算 (期望路径 vs 实际路径)。如果偏离 > 15%，触发元认知自评。 | 应引入“期望路径”的概念，通过检测偏差自动触发干预，而不仅仅是出错时。 |

---

## 2. 模块架构设计 (Architectural Design)

本模块 (`core/decision_center.py`) 定位为 **Agent 的“前额叶皮层”**，负责在执行工具（特别是高危或高成本工具）时进行最后的决策把关。

### 2.1 核心组件
1.  **策略控制器 (Policy Controller)**：根据配置加载 `IDENTITY.md` 或 `config.yaml` 中的权限与干预规则。
2.  **现状提炼器 (Status Synthesizer)**：当触发阈值时，自动收集 Blackboard 历史、错误指纹、Token 消耗量，调用 LLM 生成一份人类可读的“战术申请”。
3.  **多模态网关 (Interaction Gateway)**：支持 `ask_user` (CLI) 和未来可能的 Webhook/Slack 回调。
4.  **元认知评估器 (Metacognitive Evaluator)**：计算任务进展的“健康度”。若检测到“逻辑原地打转”或“性能偏差”，主动发起干预请求。

---

## 3. 实现方案 (Implementation Details)

### 3.1 决策分级 (Decision Levels)
通过环境变量或配置定义三种干预强度：
*   **`AUTONOMOUS`**：系统根据预设脚本自动处理（如：错误 3 次后自动降级到 Semgrep）。
*   **`ADVISORY`**：Agent 在命令行打印建议及理由，静默 10 秒无响应则执行。
*   **`INTERACTIVE`**：系统暂停，展示“现状提炼报告”，等待用户显式指令（Approve/Deny/Modify）。

### 3.2 典型流程：CodeQL 降级决策
1.  **触发**：Hook 系统检测到 CodeQL 连续失败指纹。
2.  **介入**：`DecisionCenter` 挂起进程。
3.  **提炼**：LLM 生成报告：
    > “我目前已尝试 4 次修复依赖，当前的报错是 `pkg-config` 编译失败。我预测继续尝试的成功率仅为 20%，且单轮成本已达 $0.5。建议切换至 Semgrep。”
4.  **询问**：调用 `ask_user` 展示上述报告。
5.  **回馈**：用户输入 `Retry one more time with apt-get install`，`DecisionCenter` 将此指令注入 Blackboard，重置计数器，命令 Agent 执行特定操作。

---

## 4. 与现有系统的集成

### 4.1 Hook 集成点
修改 `core/hook.py`，增加对 `HookResult.requires_intervention` 标记的处理。

```python
# loop.py 集成逻辑预览
post_result = registry.dispatch("POST_TOOL_USE", ...)
if post_result.requires_intervention:
    report = decision_center.synthesize_status(state)
    user_instruction = agent.ask_user(report)
    state.blackboard['human_instruction'] = user_instruction
    # 根据用户反馈调整状态或重新执行
```

---

## 5. 开发阶段规划 (Development Phases)

### Phase 1: 基础网关与规则引擎 (1-2 天)
*   实现 `core/decision_center.py` 基础框架。
*   支持从 `config.yaml` 读取 `INTERVENTION_RULES`。

### Phase 2: 现状提炼模板 (2-3 天)
*   设计专门的 Prompt 模板，用于将 Blackboard 和 Log 提炼为“病历报告”。
*   实现 `synthesize_status` 方法。

### Phase 3: 性能 Delta 监测 (3-5 天)
*   引入 Hermes 的“期望路径”理念，监测 Agent 的任务达成进度。
*   实现“逻辑死循环”检测算法（基于错误指纹的熵增检测）。

---

## 6. 下一步行动
1.  创建 `docs/plans/GENERAL_INTERVENTION_SYSTEM.md` 正式文档。
2.  开始 Phase 1 代码开发。
