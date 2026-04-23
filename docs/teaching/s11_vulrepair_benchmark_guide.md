# Sec-Agent-Harness: VulRepair 漏洞修复基准测试指南

本指南旨在说明如何利用 `VulRepair` 数据集对安全智能体（Agent）的漏洞分析与修复能力进行系统性评估。

---

## 1. 测试流程概览

自动化测试流程分为三个主要阶段：**准备 (Preparation)** -> **执行 (Execution)** -> **评判 (Evaluation)**。

### 1.1 准备阶段：数据采样与工作区初始化
使用 `scripts/prepare_vulrepair_cases.py` 脚本从 `VulRepair` 测试集中提取最具代表性的 CWE 类型。
*   **动作**：脚本会为每个测试用例创建一个独立的沙箱工作区（位于 `challenge/vuln_repair_eval/`）。
*   **输出**：
    *   `vulnerable_code.c`：经过清洗的原始漏洞代码（去除了 Bug 标记）。
    *   `solution.txt`：包含 CWE ID、CVE 编号以及标准答案补丁。
    *   `README.md`：供 Agent 阅读的任务说明。

### 1.2 执行阶段：FSM 驱动的自动化修复
使用 `scripts/run_vulrepair_benchmark.py` 脚本启动 FSM 循环。
*   **单例校准**：建议先对单个用例进行测试，以验证 Agent 的推理路径是否正确。
    ```bash
    python3 scripts/run_vulrepair_benchmark.py case_01_CWE_119
    ```
*   **全量测试**：运行所有已准备好的测试用例。
    ```bash
    python3 scripts/run_vulrepair_benchmark.py
    ```

### 1.3 评判阶段：多维度结果分析
测试结束后，系统会在 `docs/` 下生成 `vulrepair_benchmark_report.json` 汇总报告。

---

## 2. 如何查看测试结果

### 2.1 汇总报告 (`vulrepair_benchmark_report.json`)
报告记录了每个用例的关键元数据：
*   **`final_state`**：如果是 `DONE`，表示 Agent 自认为修复完成；如果是 `ERROR` 或停在其他状态，表示任务失败。
*   **`turn_count`**：完成修复所需的总轮次数，反映了效率。
*   **`exact_match`**：Agent 修复的代码是否与 `solution.txt` 中的标准答案完全一致。
*   **`blackboard_summary`**：最重要的部分，记录了 Agent 在每个状态下的“思考过程”和“发现总结”。

### 2.2 详细日志
每个用例的工作区内都有一个 `logs/` 文件夹，包含该次任务的完整 Prompt 记录和工具调用详情。如果 Agent 报错或进入死循环，这里是排查问题的首选。

---

## 3. 评判标准与原则

在安全 Agent 的评估中，我们采用“逻辑优先，字符匹配次之”的原则。

### 3.1 核心评判指标
1.  **FSM 完整性 (FSM Integrity)**：Agent 是否按照 `Analyze -> Validate -> Fix -> Review` 的顺序流转？是否跳过了必要的 Review 步骤？
2.  **逻辑正确性 (Logical Correctness)**：虽然 `exact_match` 可能是 `false`（例如 Agent 增加了一行注释或变量名不一致），但如果它修复了缓冲区溢出的边界条件（如将 `==` 改为 `<=`），则应视为 **有效修复**。
3.  **自愈能力 (Self-Healing)**：当编译失败或沙箱报错时，Agent 是否能根据 `[SYSTEM ADVICE]` 自动调整修复策略并最终成功。

### 3.2 常见失败模式
*   **幻觉循环**：Agent 在 `VALIDATOR` 阶段无法编写出正确的测试脚本，导致不断重试直到触发 Circuit Breaker（熔断）。
*   **过度修复**：Agent 修改了不相关的代码逻辑，导致功能性回归（Review 阶段应能发现此类问题）。
*   **FSM 越权**：试图绕过 `REVIEWER` 直接跳转到 `DONE`（目前已被 Hook 系统封死）。

---

## 4. 环境维护

*   **编译器**：测试 C 语言用例时，请确保 `config.yaml` 中的 `sandbox.image` 设置为 `gcc:11` 或更高版本。
*   **清理**：如果需要重新生成测试用例，可以直接删除 `challenge/vuln_repair_eval/` 目录并重新运行准备脚本。

---
*编撰人：Gemini CLI*
*日期：2026-04-20*
