# Skill System Upgrade Plan: 从 L2 到 L4 的架构演进

**日期**: 2026-04-25  
**目标**: 重构 `core/loop.py` 中的 Skill 加载与生命周期管理机制，解决上下文全局污染问题，并为系统引入 L4 级别的自我演化能力。

---

## 1. 当前架构分析 (Current State)

在分析了 `core/loop.py` 的现有实现后，目前架构已达到 **L2 (模块化加载)** 级别：
*   **优势**：实现了渐进式披露（Progressive Disclosure）的基础——System Prompt 中仅注入 Catalog，通过 `load_skill` 动态加载具体内容；通过 `compact_blackboard` 实现了基本的上下文长度保护。
*   **痛点**：
    1.  **缺乏真正的三层解耦**：`load_skill` 将整个 Skill 的 `content` 一次性塞入 Blackboard，如果附带大量规则文档，容易造成上下文突发爆炸。
    2.  **生命周期全局污染**：挂载在 Blackboard 上的 `loaded_skill_*` 不会随 FSM 状态转移而卸载，导致早期状态（如 `INITIAL_ANALYSIS`）加载的规范在后续状态（如 `FIXER`）中无效占用 Token。
    3.  **缺乏硬性门卡 (Checklist)**：状态流转全靠大模型自觉，缺乏针对 Skill 规范执行情况的强制断言（Assert）。
    4.  **无自我演化机制**：Agent 在修复漏洞过程中的踩坑经验无法固化。

---

## 2. 演进计划 (Improvement Plan)

### Phase 1: 真正实现三层架构与作用域隔离 (Target: L3)

**目标**：彻底解决上下文污染，实现极致的按需加载。

*   **Action 1: 改造 `load_skill_handler`**
    *   取消加载全量内容的逻辑。
    *   修改为：仅读取 `SKILL.md` 的 YAML Frontmatter 和核心路由表（META 层）。
    *   在 System Prompt 中提供标准的文件读取工具 (`read_file`)，让 Agent 根据 META 层的指示，自行去读取 `references/` 下的具体文档。
*   **Action 2: 实现基于 FSM 的技能生命周期**
    *   在 `loop.py` 的 `transition_handler` 中追加卸载逻辑。
    *   当状态从 A 转移到 B 时，主动清空 Blackboard 中不再相关的 `loaded_skill_*` 键值对，保持显存极致干净。
    ```python
    # Draft Implementation in transition_handler:
    for key in list(state.blackboard.keys()):
        if key.startswith("loaded_skill_"):
            del state.blackboard[key]
    ```

### Phase 2: 引入断言门卡与强制自检 (Target: L3+)

**目标**：防止大模型跳过关键步骤，将 Prompt 的软约束升级为 Hook 的硬约束。

*   **Action 3: 扩展现有的 Hook 状态转移拦截**
    *   **现状查验**：目前在 `hooks/builtin_logic.py` 中，我们已经实现了强大的 `fsm_safety_hook`，它能拦截非法的出口转移（必须在 REVIEWER 状态）并强制要求测试通过（`last_test_status == success`）。
    *   **下一步增强**：在现有的 `fsm_safety_hook` 中追加对 **Skill Checklist** 的检查。当系统挂载了特定的 Skill 时，Hook 不仅要查沙箱测试状态，还要检查 Blackboard 中是否已标记了对应 Skill 的自检清单（如 `has_completed_security_checklist == True`）。
    *   如果不满足，抛出拦截信息：“Transition blocked. Test passed, but you must complete the security checklist defined in the loaded skill before marking as DONE.”

### Phase 3: 打造记忆与自我演化机制 (Target: L4)

**目标**：参考目前业界领先的自进化框架（如 **Voyager** 与 **Hermes Agent**），让 Agent 具备长时记忆，将运行时的试错经验“结晶”为永久的可执行代码或硬规范。

*   **Action 4: 基于向量检索的技能库 (参考 Voyager 架构)**
    *   **现状**：目前所有技能都是人类静态编写的。
    *   **演进**：引入类似 Voyager 的 **Skill Library（技能库）** 机制。提供一个 `crystallize_skill` 原生工具。当 Agent 发现某个漏洞的修复逻辑具有强复用性时（例如特定的 AST 过滤规则），Agent 自动生成一段独立的 Python 模块代码（Procedural Memory）并附带自然语言描述 (Docstring)。后台将其转化为向量存入本地数据库（如 SQLite）。下次遇到类似任务时，系统基于语义相似度直接挂载并调用该代码技能，从而避免每次都让 LLM 从零开始生成代码。
*   **Action 5: 从失败到成功的经验闭环 (参考 Hermes 的反思机制)**
    *   **详细流程说明**：
        1. **执行追踪 (Execution Trace)**：修改 `REVIEWER` 到 `FIXER` 的退回逻辑。当 Agent 测试报错时，完整保存每轮的动作与报错输出。
        2. **评估与提取 (LLM-as-a-Judge)**：如果在多次试错后最终成功转入 `DONE`，后台启动类似 Hermes 的反馈闭环，把这段完整的“失败 -> 调整 -> 成功”的执行轨迹喂给一个独立的反思 Agent。
        3. **自动优化规范 (Prompt Evolution)**：反思 Agent 提炼出导致早期失败的逻辑盲点，然后调用 `record_postmortem` 工具，直接修改该漏洞对应 Skill 文件夹下的 `references/checklist.md`，追加一条新的核对规则。
*   **Action 6: L4 演化的潜在风险与防御机制 (Risks & Mitigations)**
    *   **知识退化 (Catastrophic Forgetting)**：自进化最大的风险。大模型极有可能将某次“针对特定环境的变通绕过（Workaround）”当作“普适真理”结晶化并写进规则，从而导致未来正常环境的漏洞修复全部失败。
    *   **Context 污染与行为死锁**：若 Agent 无节制地往 Checklist 追加规则，不仅会导致加载该技能时 Token 爆炸，更可能出现新旧规则互相矛盾（例如规则 A 要求强校验，规则 B 要求放宽容错），导致 Agent 直接卡死。
    *   **工业级防御方案 (PR隔离 + 自动化回归测试)**：
        *   **人工审批屏障 (Human-in-the-loop)**：严禁 Agent 拥有直接写回主分支仓库的权限。它产生的所有代码（结晶技能）和规范（Markdown），只能触发 Git 的 Pull Request (PR)。人类专家就像 Review 同事的代码一样，去 Review 智能体的演化提案。
        *   **基准测试回归 (Evals Benchmark)**：建立一套安全漏洞靶场的自动化测试集。每次合并了智能体的新经验 PR 后，自动跑一遍测试集，如果引入了新规则导致原有可以修好的漏洞现在修不好了，直接触发回滚 (Revert)。

---

## 3. 下一步行动项 (Next Steps)

1.  [ ] **Refactor**: 修改 `core/skill.py` (SkillRegistry)，使其能够区分获取 META 内容和获取全量内容。
2.  [ ] **Update**: 在 `core/loop.py` 的 `transition_handler` 增加卸载缓存逻辑。
3.  [ ] **Feature**: 编写一个新的 Hook 文件 `hooks/assert_checklist.py` 拦截非法流转。
4.  [ ] **Feature**: 添加 `record_postmortem` 工具。
