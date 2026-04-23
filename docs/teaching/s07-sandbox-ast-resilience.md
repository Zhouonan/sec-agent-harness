# s07: 隔离、分析与韧性 (Sandbox, AST & Resilience)

`s00 > s01 > s02 > s03 > s04 > s05 > s06 > [ s07 ]`

> *安全 Agent 不仅要能思考，还要能在“泥潭”中稳健运行。*

## 这一章要解决什么问题

在前面的章节中，你的 Agent 已经具备了 FSM 状态机和基础的技能加载能力。但在真实的漏洞挖掘场景中，你会面临三个核心挑战：

1.  **安全性 (Security)**：运行漏洞 PoC 或测试代码时，如何防止它破坏宿主机？
2.  **侦察效率 (Reconnaissance Efficiency)**：对于大型项目，如果每一轮都让模型读几千行代码，上下文很快就会爆炸。如何快速提取代码结构？
3.  **运行韧性 (Resilience)**：LLM API 可能会因为速率限制 (429) 或网络波动而失败。如何保证长任务不因一次网络抖动而崩盘？

这一章我们将通过 **Docker 隔离沙箱**、**AST 静态分析** 和 **指数退避重试** 来解决这些问题。

---

## 1. 隔离执行：Docker 沙箱 (`core/sandbox.py`)

在安全领域，执行不受信任的代码是必经之路。

### 最小设计原则
-   **资源限制**：通过 `mem_limit` 和 `cpu_quota` 防止恶意代码耗尽系统资源。
-   **网络隔离**：`network_disabled=True` 防止 PoC 向外回连（如反弹 Shell）。
-   **权限最小化**：使用非 root 用户 (`1000:1000`) 运行容器。
-   **懒初始化 (Lazy Init)**：如果宿主机没装 Docker，系统应记录警告而非直接崩溃，这保证了在受限环境（如 CI）下的可用性。

### 教学要点
> **为什么不用简单的 `subprocess.run`?**
> 因为 `subprocess` 共享文件系统、网络和进程空间。一个简单的 `rm -rf /` 就能让你的 Agent 系统彻底报废。

---

## 2. 结构化侦察：AST 静态分析 (`core/ast_utils.py`)

与其让模型盲目地 `read_file`，不如给它一个“战术地图”。

### 核心机制
利用 Python 原生的 `ast` 模块，我们可以在不执行代码的情况下提取：
-   **类 (Classes)**：及其包含的方法。
-   **函数 (Functions)**：及其参数。
-   **导入 (Imports)**：了解模块依赖关系。

### 为什么这很重要？
1.  **节省 Token**：一个 2000 行的文件，AST 摘要可能只有 50 行。
2.  **符号定位**：快速找到某个变量或函数是在哪个文件定义的。

---

## 3. 动态技能与工具注入 (`core/skill.py`)

在 `s05` 中，我们实现了技能加载。现在我们将它升级为 **动态工具注入**。

### 流程图
```text
SKILL.md (YAML Frontmatter)
  |
  +-- 定义 tools 列表 (OpenAI 格式)
  |
SkillRegistry.discover_skills()
  |
AgentLoop._register_skill_tools()
  |
LLM 获得新工具 (如 scan_python_file)
```

**设计哲学**：
> **解耦**。AgentLoop 不应该知道 `ast-scanner` 的存在。它只负责从注册中心发现工具并分发给对应的 Handler。

---

## 4. 运行韧性：API 重试机制

由于安全任务通常是长耗时的（涉及多轮 FSM 转换），任何一轮 LLM 调用失败都会导致整个流程中断。

我们在 `AgentLoop.call_llm_with_retry` 中实现了：
-   **速率限制处理**：捕获 429 错误并等待。
-   **指数退避 (Exponential Backoff)**：随着重试次数增加，等待时间变长。
-   **防御性执行**：即使工具执行崩溃，也会将错误返回给模型，允许它尝试修复。

---

## 实践练习
1.  查看 `skills/ast-scanner/SKILL.md`，了解如何定义动态工具。
2.  尝试在没有启动 Docker 守护进程的情况下运行 `tests/test_fsm_loop.py`，观察系统如何降级处理。
3.  在 `AgentLoop` 中添加更多的技能工具映射，观察 Agent 如何在 `INITIAL_ANALYSIS` 状态下自动获得新能力。
