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

### C. 结构化工具挂载
- 通过在 Frontmatter 中定义 `tools` 列表，我们可以让技能文件不仅包含指令，还携带配套的工具定义（JSON Schema），实现了**能力与工具的原子化绑定**。

---

## 4. 复习思考题

- **问题**：如果我想给 Agent 增加一个新的“修复漏洞”技能，我应该在 Frontmatter 里写什么？
- **回答**：至少需要 `name` (如 `vulnerability-fixer`) 和 `description` (简述其功能)，这样 Agent 才能在目录中看到它并决定是否加载。
