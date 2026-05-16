# 知识点复习：YAML Frontmatter (技能元数据管理)

在 `Sec-Agent-Harness` 的技能系统 (`core/skill.py`) 中，我们大量使用了 YAML Frontmatter 技术。这是理解 **s05 (技能加载)** 阶段的关键。

---

## 1. 什么是 YAML Frontmatter？

**Frontmatter**（前置元数据）是放置在 Markdown 文档最顶部的一个特殊块。它由两组三条短横线 `---` 包裹，中间使用 YAML 语法编写键值对。

### 实例展示 (`skills/taint-analysis/SKILL.md`)
```yaml
---
name: taint-analysis
description: 执行数据流与污点分析，识别代码库中的潜在逻辑漏洞。
tools:
  - name: analyze_path
    description: 分析 Source 到 Sink 的具体数据路径。
---
# 技能正文 (Body)
这是给 LLM 看的详细指令内容...
```

---

## 2. 代码实现原理 (以 `core/skill.py` 为例)

项目中的 `SkillRegistry` 类通过以下逻辑解析此结构：

1. **读取文件**：获取整个 Markdown 文件的字符串。
2. **三段式切分**：使用 `content.split("---", 2)`。
    - `parts[0]`：通常为空字符串（因为文件以 `---` 开头）。
    - `parts[1]`：**元数据块 (Frontmatter)**，包含 `name`, `description` 等。
    - `parts[2]`：**正文块 (Body)**，包含详细的 Prompt 指令。
3. **YAML 解析**：使用 `yaml.safe_load(parts[1])` 将文本转换为 Python 字典。

---

## 3. 为什么在 Agent 架构中使用它？(核心价值)

这是针对 **上下文治理 (Context Management)** 的深度优化：

### A. 分层可见性 (Layered Visibility)
- **初始阶段**：Agent 启动时，我们只从 Frontmatter 读取 `name` 和 `description` 注入系统提示词。
- **作用**：Agent 只知道“我能做什么”，而不需要知道“具体怎么做”。这极大地节省了初始会话的 Token 消耗。

### B. 按需加载 (On-Demand Loading)
- **触发机制**：只有当 Agent 决定调用 `load_skill` 时，我们才把 `parts[2]` (正文块) 喂给它。
- **作用**：将沉重的指令推迟到真正需要时加载，保证了 Agent 的“实时响应速度”和“信噪比”。

### C. 结构化工具挂载 (Structured Tool Mounting)
- **核心作用**：通过在 Frontmatter 中定义 `tools` 列表，我们可以让技能文件不仅包含指令，还携带配套的工具定义（符合 OpenAI 函数调用格式）。
- **自动化注入**：`core/skill.py` 会扫描所有技能的 `tools` 字段，并将其自动转换为 API 能够理解的 JSON Schema。
- **原子化绑定**：这实现了“能力定义”与“操作工具”的深度绑定。Agent 只要看到了技能说明，系统就能自动为其配置对应的执行工具。

---

## 4. 进阶：如何设计高质量的工具 Schema？

Schema 不仅仅是代码约束，它更是给 LLM 读的“说明书”。在 `Sec-Agent-Harness` 中，设计良好的 Schema 能显著降低 Agent 的幻觉。

### A. 命名语义化 (Self-Documenting Names)
- **坏例子**：`func1`, `run_analysis` (太笼统)
- **好例子**：`scan_python_file_ast`, `analyze_taint_path_codeql`
- **原则**：动词+名词+技术栈/方法。让 LLM 看到名字就知道它是干什么的。

### B. 描述的“提示词化” (Prompting in Descriptions)
工具描述是 LLM 决定“是否调用”的唯一依据。
- **技巧 1：场景限定**。在描述里加入“Use this when...”。例如：“当你想查找函数定义而非读取全文时，请使用此工具。”
- **技巧 2：参数引导**。例如 `file_path` 的描述可以写成：“项目的相对路径，必须以 ./ 开头。”

### C. 约束的力量 (Constraint Engineering)
- **使用 Enum (枚举)**：如果你知道参数只有几种固定选择，**务必使用 enum**。
  ```yaml
  parameters:
    properties:
      mode:
        type: string
        enum: ["fast", "deep", "symbolic"]
        description: "扫描模式。 fast 适合快速预览，deep 适合漏洞验证。"
  ```
- **设置 Required (必填项)**：通过 `required` 列表强制 LLM 必须提供某些关键参数，防止缺失信息导致的调用失败。

### D. 保持参数扁平化
LLM 处理嵌套对象的嵌套层级越深，逻辑出错概率越大。
- **建议**：尽量将参数设计为简单的 `string`, `integer` 或 `boolean`。如果必须传递复杂对象，请在描述中给出明确的 JSON 示例。

---

## 5. 函数级流程详解：从定义到执行

为了彻底理解 YAML Frontmatter 的作用，我们以 `taint_analysis/SKILL.md` 的真实 YAML 头部为例，跟踪这些定义是如何一步步变成 Agent 可用的工具的：

```yaml
---
name: taint-analysis
description: Perform data-flow and taint analysis. Contains guidelines for tools 'analyze_path_codeql' and 'analyze_path_semgrep'.
tools:
  - name: analyze_path_codeql
    description: Performs deep, whole-program semantic analysis using GitHub CodeQL...
    parameters:
      type: object
      properties:
        source: {type: string, description: "The starting point of the taint..."}
        sink: {type: string, description: "The sensitive function..."}
      required: ["source", "sink"]
  - name: analyze_path_semgrep
    description: Performs agile, pattern-based taint analysis using Semgrep...
    parameters: ...
---
```

### 第一阶段：注册与发现 (Discovery & Handler Loading)
**位置**：`core/skill.py` -> `SkillRegistry.discover_skills()`
1. 系统启动，`SkillRegistry` 扫描 `skills/` 目录，找到 `taint_analysis/SKILL.md`。
2. **元数据解析**：提取 `---` 之间的 YAML 内容。系统提取最外层的 `name` 和 `description`，生成**全局技能目录 (Catalog)** 的一条记录：
   `- taint-analysis: Perform data-flow and taint analysis. Contains guidelines for tools 'analyze_path_codeql' and 'analyze_path_semgrep'.`

> [!TIP]
> **最佳实践**：如上所示，Skill 的外层 `description` **必须明确提及它包含的底层工具名**。这样当大模型在 `tools` 列表里看到 `analyze_path_codeql` 时，结合 Catalog 的描述，它才能建立起“哦，这两个工具的使用说明书在 taint-analysis 这个技能里”的关联认知，从而主动去 `load_skill`。
3. **提取底层工具清单**：解析 `tools` 数组，发现该技能包含了两个底层扫描器：`analyze_path_codeql` 和 `analyze_path_semgrep`。
4. **Handler 预加载**：系统尝试加载同目录下的 `handler.py`。如果存在，它会被动态加载并暂存在 `skill_data["handler_module"]` 中。
   - *注意：此时只是把 Python 模块加载进内存，工具函数名与 Python 代码的映射还没建立。*

### 第二阶段：工具转换与状态挂载 (Conversion & State Mounting)
**位置**：`core/loop.py` -> `AgentLoop._register_skill_tools()`
1. **标准转换**：系统遍历刚才解析出的 `tools` 数组，将每一个 YAML 工具定义严格转换为 OpenAI 兼容的 **JSON Schema**。
   以 `analyze_path_codeql` 为例，转换后如下：
   ```json
   {
     "type": "function",
     "function": {
       "name": "analyze_path_codeql",
       "description": "Performs deep, whole-program semantic analysis using GitHub CodeQL...",
       "parameters": {
         "type": "object",
         "properties": {
           "source": { "type": "string", "description": "The starting point of the taint..." },
           "sink": { "type": "string", "description": "The sensitive function..." }
         },
         "required": ["source", "sink"]
       }
     }
   }
   ```
2. **挂载操作 (Mounting)**：
   在 `AgentLoop` 中，工具是按 FSM 状态隔离的（如 `{INITIAL_ANALYSIS: [], VALIDATOR: []}`）。系统将上述两个生成的 JSON Schema 添加到对应状态的可用工具列表中。这实现了**基于状态的权限隔离**。
3. **Handler 映射建立**：
   系统从第一阶段缓存的 `handler_module` 中，通过反射寻找名为 `analyze_path_codeql` 和 `analyze_path_semgrep` 的真实 Python 函数，并将它们存入 `self.tool_handlers` 字典。至此，"工具名 -> 真实可执行代码" 的通道打通。

### 第三阶段：决策与提示 (Prompting)
**位置**：`core/loop.py` -> `AgentLoop.run_one_turn()`
1. 新的回合开始，调用 `get_system_prompt()`。
2. **组装提示词**：系统将第一阶段生成的 **Catalog（目录）** 塞进 System Prompt；并将第二阶段生成的 **JSON Schema 数组（即底层工具）** 作为大模型的 `tools` 参数传入。
3. 这时模型能看到两样东西：一个是知道有个叫 `taint-analysis` 的高级技能，另一个是能直接调用 `analyze_path_codeql` 这种底层接口。

### 第四阶段：模型决策 (Decision)
**位置**：LLM 响应阶段
模型在阅读完上下文后，面临决策分岔：
*   **分支 A（需要查阅文档）**：模型认为需要做污点分析，但光看 CodeQL 的参数描述，不知道 `source` 和 `sink` 具体该怎么填才能查出特定的漏洞。它决定先看长篇说明书，于是返回一个基础工具调用：`load_skill(skill_name="taint-analysis")`。
*   **分支 B（直接执行扫描）**：模型之前已经加载过文档，或者自己判断能力足够，直接返回底层工具调用：`analyze_path_codeql(source="request.form", sink="os.system")`。

### 第五阶段：分发与按需加载 (Dispatch & On-Demand Loading)
**位置**：`core/loop.py` -> `AgentLoop.run_one_turn()` (Tool Handling 循环)

系统收到大模型的 `tool_calls`，进入分发执行逻辑：

1. **如果是分支 A (`load_skill`) —— 【核心：正文块 Body 的按需加载】**：
   - **提取正文**：触发内置的 `load_skill_handler`。该函数从 `taint_analysis/SKILL.md` 中提取第二条 `---` 之后的全部 **Markdown 正文 (Body)**。
   - **注入黑板**：将庞大的正文内容存入 `state.blackboard["loaded_skill_taint-analysis"]`。
   - **延迟生效**：本回合结束。在**下一轮对话**的第三阶段时，黑板里的正文会被全量注入系统提示词。模型因此学到了该技能的最佳实践，从而在下一轮能够精准触发分支 B。
   - **价值**：真正实现了“指令的延迟加载”，既节省了初期的 Token 消耗，又保障了复杂任务的指导精度。

2. **如果是分支 B (`analyze_path_codeql`)**：
   - **钩子拦截**：触发系统的 `PRE_TOOL_USE` 钩子，进行安全检查或参数校验。
   - **真机执行**：在 `self.tool_handlers` 字典中找到并执行真实的 Python 函数。
   - **结果回传**：将代码扫描器的真实输出作为 `role: tool` 的消息塞回历史记录，供模型继续推理。

---

## 6. 复习思考题

- **问题 1**：如果我想给 Agent 增加一个新的“修复漏洞”技能，我应该在 Frontmatter 里写什么？
- **回答**：至少需要 `name` (如 `vulnerability-fixer`) 和 `description` (简述其功能，并列出包含的底层工具名)。同时必须包含 `tools` 列表，定义具体的 `write_file` 等相关工具规范，否则 Agent 将处于“空谈”状态。

- **问题 2（高阶架构题）**：如果大模型觉得自信，没有调用 `load_skill` 提取 Body，那它怎么知道 `CodeQL` 和 `Semgrep` 谁优先谁备用呢？如果把它写在最外层的 Catalog 描述里，会导致系统提示词过长，怎么办？
- **回答**：这是一个极其敏锐的边界场景！应对方案是：**利用 Tool Schema 的 `description` 字段作为路由拦截**。
  仔细看我们前面配置的 YAML，在底层工具的描述里已经写了防呆提示：
  - `analyze_path_codeql` 的描述：`... Preferred for accurate vulnerability verification. Try it first ...`
  - `analyze_path_semgrep` 的描述：`... Fallback if CodeQL is unavailable.`
  由于底层工具的 Schema 是常驻模型上下文的，所以即使模型不读 Body，当它扫视工具列表准备“盲调”时，也会一眼看到这个优先级限制。
  **设计法则**：**路由级、红线级**的规则写在 Tool Schema Description 里；**长篇幅、示例、排错 SOP** 写在 Skill Body 里。
