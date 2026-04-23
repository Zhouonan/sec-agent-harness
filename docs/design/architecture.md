# Sec-Agent-Harness: 模块级详细架构图 (Granular Module Architecture)

本文档将系统拆解为三个核心子系统：**FSM 运行引擎**、**自动化侦察与执行 (Sandbox/AST)** 和 **动态技能生命周期管理**。

---

## 1. FSM 运行引擎详解 (`core/loop.py`)

本模块负责 Agent 的决策与执行循环，并集成了 API 韧性机制。

### 1.1 `run_one_turn` 执行流程 (Flowchart)

```mermaid
graph TD
    A[开始 Turn] --> B{检查限制}
    B -- Turn/State 超过限制 --> C[状态切换为 ERROR]
    B -- 正常 --> D[生成 System Prompt]
    D -- 注入 Blackboard/Skill Catalog --> E["调用 LLM (带指数退避重试)"]
    E -- 429/网络错误 --> E
    E -- 文本回复 (无工具调用) --> F2{触发 Nudge?}
    F2 -- 是 --> G2[注入 System Reminder]
    F2 -- 否 --> N
    E -- 成功 --> F[解析 Assistant 响应]
    F -- 包含 Tool Use --> H[分发工具执行]
    H -- transition_state --> I[更新 Blackboard 并切换 AgentState]
    H -- load_skill --> K[将技能正文注入 Blackboard]
    H -- execute_in_sandbox --> L[Docker 隔离执行]
    H -- list_files --> M2[文件系统目录发现]
    H -- ast_scan --> M[静态提取代码结构]
    F -- 包含文本 --> G[存入 Messages]
    G --> N[结束 Turn]
    I --> N
    K --> N
    L --> N
    M --> N
    M2 --> N
    G2 --> N
    C --> N
```

---

## 2. 自动化侦察与安全执行

### 2.1 Docker 隔离沙箱 (`core/sandbox.py`)
- **设计目标**：确保 PoC 验证和回归测试在受限、不可恢复的环境中运行。
- **核心特性**：
    - **资源控制**：限制 CPU 份额和内存上限。
    - **网络截断**：默认禁用网络，防止数据外泄或反弹 Shell。
    - **权限隔离**：强制以非 root 用户 (`1000:1000`) 身份运行。
    - **容错初始化**：如果 Docker 未就绪，系统会降级并记录警告，而非终止运行。

### 2.2 AST 静态分析器 (`core/ast_utils.py`)
- **设计目标**：在不读取全量文件内容的情况下，快速映射项目结构。
- **能力**：
    - 提取类定义及其方法。
    - 提取顶层函数及参数列表。
    - 分析模块导入依赖。

---

## 3. 动态技能与工具注入 (`core/skill.py`)

本模块不仅负责知识加载，还负责 **工具定义的动态发现**。

### 3.1 技能与工具生命周期 (Lifecycle)

```mermaid
sequenceDiagram
    participant Agent as AgentLoop
    participant Registry as SkillRegistry
    participant FS as Filesystem (skills/)
    
    Registry->>FS: 1. 扫描 SKILL.md
    Registry->>Registry: 2. 解析 YAML Frontmatter (meta & tools)
    
    Agent->>Registry: 3. get_all_tools()
    Registry-->>Agent: 4. 返回所有技能中定义的 OpenAI 工具格式
    
    Agent->>Agent: 5. 在 _register_skill_tools 中映射 Handler
    
    Note over Agent, Registry: 运行时
    Agent->>Registry: 6. load_skill(name)
    Registry-->>Agent: 7. 返回 Markdown Body 并注入 Blackboard
```

---

## 4. 跨模块交互总结 (Interaction Map)

```mermaid
graph LR
    subgraph "Core Engine (core/loop.py)"
        AL[AgentLoop]
        LS[LoopState]
    end
    
    subgraph "Capabilities (core/)"
        SB[SandboxTool]
        AST[ASTScanner]
    end
    
    subgraph "Knowledge Layer (core/skill.py)"
        SR[SkillRegistry]
    end
    
    AL -- 管理状态 --> LS
    AL -- 执行命令 --> SB
    AL -- 结构分析 --> AST
    AL -- 发现并加载 --> SR
    SR -- 提供工具定义/正文 --> AL
```

---
*上次更新: 2026-04-15*
---
