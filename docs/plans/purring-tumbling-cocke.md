# Sec-Agent-Harness 评测体系建设计划

## Context

项目已有 FSM 驱动的安全 Agent 核心和 10 个 VulRepair 测试案例，但评测方式为手工脚本，存在以下问题：
- `exact_match` 指标因 ground truth 被 T5 tokenizer 预处理过而完全失效（10 个 case 全 false）
- 评测脚本零散（`scripts/run_vulrepair_benchmark.py` + `scripts/run_secbench_single_test.py`），无统一框架
- 无系统化指标定义、无趋势追踪、无可扩展的数据集抽象

目标：建立一个**可扩展、多维度、LLM 辅助评分**的评测体系。

## 核心设计决策

1. **新 `eval/` 模块**：作为第一级子系统，不散落在 scripts/ 中
2. **零侵入核心循环**：评测系统是纯后处理器，`AgentLoop.run(prompt)` → `LoopState` → `EvalRunner` 读取 → Judge评分 → 报告
3. **LLM-as-Judge 正确性评分**：用 LLM 对比 agent 修复和 ground truth，做语义等价判断（替代 broken 的 exact_match）
4. **分阶段推进**：Phase 1 先做基础框架 + LLM 评分，跑通后再加报告/趋势等功能
5. **不做 A/B 对比**：第一版只支持单配置评测

## 评测系统与 Hook 模块的关系

```
评测系统（纯后处理器，不碰核心循环）:
  AgentLoop.run(prompt) → LoopState → EvalRunner 读取 → Judge评分 → 报告

Hook 模块（运行时横切干预，继续做该做的事）:
  PRE_TOOL_USE  → 安全校验、参数修改
  POST_TOOL_USE → 诊断建议、熔断回退、上下文快照
```

评测系统不需要通过 Hook 采集数据——Agent 跑完后 LoopState 里已经有了全部信息（turn_count、state_path、blackboard 里的 findings/poc_results/patches、最终 patched code）。评测系统直接读取这些做后处理。

## 需要修改的核心文件（最小侵入）

### `core/hook.py` — 新增 `SESSION_END` 事件

在 `HookEvent` enum 中加 `SESSION_END = auto()`。

**为什么加**：为后续架构提供生命周期插槽——结晶流（blackboard 写入 Tier 1/2）、post-mortem 反思、资源清理等。评测系统不用它，但它是 interview_prep.md 中设计方向的基础设施。

### `core/loop.py` — `LoopState` 加 `turn_log` + `run()` 派发 `SESSION_END`

1. `LoopState` dataclass 新增字段：
```python
state_path: List[str] = field(default_factory=list)       # 记录状态转换路径
turn_log: List[Dict] = field(default_factory=list)         # 每轮工具调用记录
```
- `state_path`：在 `transition_handler` 中追加每次转换目标
- `turn_log`：在 `run_one_turn()` 中每次工具调用后追加 `{turn, state, tool, success, duration_ms}`

2. `run()` 中 while 循环结束后派发：
```python
registry.dispatch(HookEvent.SESSION_END, state)
```

**为什么加 turn_log/metrics**：Agent 跑完后，LoopState 已经包含 turn_count、current_state、blackboard，但没有细粒度的**每轮干了什么**的记录。turn_log 填补这个空白——对调试和评测都有用，属于 LoopState 的自然延伸。评测系统直接从 LoopState 读这些数据。

## Phase 1：评测模块 (`eval/`)

评测系统是完全独立的后处理器，不碰核心循环，不碰 Hook 系统。

```
eval/
  __init__.py
  schema.py            # 数据类定义
  runner.py            # 单 case 评测运行器
  orchestrator.py      # 多 case 编排 + 并行
  judge.py             # LLM-as-Judge 正确性评分
  scorer.py            # 多维度评分汇总
  datasets.py          # 数据集抽象（VulRepair, SEC-bench, Custom）
  reporter.py          # JSON + Markdown 报告生成
  cli.py               # 命令行入口
```

### 数据模型 (`eval/schema.py`)

```python
@dataclass
class EvalCaseResult:
    case_name: str
    dataset: str
    run_id: str
    timestamp: str
    model: str
    final_state: str           # DONE / ERROR
    duration_seconds: float
    total_turns: int
    turns_per_state: Dict[str, int]
    state_path: List[str]      # ["INITIAL_ANALYSIS","VALIDATOR","FIXER","REVIEWER","DONE"]
    
    # 评分维度
    correctness_score: float       # LLM Judge 评分 0-1
    correctness_reasoning: str     # Judge 的判断理由
    process_score: float           # FSM 流程完整性 0-1
    efficiency_score: float        # 效率评分 0-1
    composite_score: float         # 加权综合评分
    
    # 制品
    patched_code: str
    error_info: Optional[str]
    log_file: str
    turn_log: List[Dict]           # 从 LoopState.turn_log 读取
```

### LLM-as-Judge 评分 (`eval/judge.py`)

核心思路：单次 LLM 调用做「安全模式检测」+「语义等价判断」+「与标准答案对比」。

**Judge Prompt 设计：**
```
你是一个安全代码审查专家。请对比以下两段代码：

【漏洞代码】
{vulnerable_code}

【Agent 的修复】
{patched_code}

【标准答案（Ground Truth）】
{ground_truth}

【漏洞类型】
CWE: {cwe_id}

请从以下维度评分（0-100分）：

1. **漏洞根因消除** (40分)：Agent 的修复是否消除了漏洞代码中的根因？
2. **修复等价性** (30分)：Agent 的修复思路是否与标准答案等价（不要求完全相同，但安全效果应一致）？
3. **代码质量** (20分)：修复代码是否清晰、最小化、不引入不必要修改？
4. **安全性不退化** (10分)：修复是否未引入新的安全问题？

请以 JSON 格式输出：
{"total_score": 85, "dimensions": {...}, "reasoning": "..."}
```

**设计要点：**
- 使用独立的 LLM 调用（不带工具、纯评分），避免「自己评自己」的 bias
- 对 CWE 类型做针对性评分提示（如 CWE-119/125 重点关注边界检查）

### 数据集抽象 (`eval/datasets.py`)

```python
@dataclass
class EvalCase:
    """单个评测案例"""
    name: str
    source_dir: str
    vulnerable_code: str
    ground_truth: str            # solution.txt 内容
    cwe_id: str
    cve_id: str
    metadata: Dict[str, Any]

class DatasetProvider:
    """数据集提供者基类"""
    def list_cases(self) -> List[str]: ...
    def load_case(self, name: str) -> EvalCase: ...
    def build_prompt(self, case: EvalCase) -> str: ...

class VulRepairDataset(DatasetProvider):
    """读取 challenge/vuln_repair_eval/ 下的 case_* 目录"""
    
class SecBenchDataset(DatasetProvider):
    """读取 challenge/secbench_trials/ 下的 case"""
    
class CustomDataset(DatasetProvider):
    """读取用户自定义目录"""
```

### 评测运行器 (`eval/runner.py`)

```
EvalRunner.run_single(case: EvalCase) -> EvalCaseResult:
  1. fork case 到 challenge/runs/run_{ts}_{case_name}/
  2. 创建 AgentLoop(workspace_path=forked_dir)
  3. 执行 loop.run(prompt) → 得到 LoopState
  4. 从 LoopState 读取 patched_code、turn_log、state_path 等
  5. 调用 Judge 评分
  6. 计算 process_score + efficiency_score
  7. 返回 EvalCaseResult
```

### 多 case 编排 (`eval/orchestrator.py`)

```
RunOrchestrator.run(dataset, cases, config) -> List[EvalCaseResult]:
  - ThreadPoolExecutor 并行（每个 case 有独立 fork 目录 + Docker 容器，线程安全）
  - per-case 超时控制
  - 单个 case 崩溃不中断整体评测
```

### 评分汇总 (`eval/scorer.py`)

三个维度，可配置权重（默认：correctness 0.50, process 0.25, efficiency 0.25）：

- **correctness_score**: 来自 LLM Judge（0-100 归一化到 0-1）
- **process_score**: FSM 是否走过完整 4 个状态？是否达到 DONE？Blackboard 是否有各阶段总结？
- **efficiency_score**: turns 和 time 对预算的归一化利用率

### 报告生成 (`eval/reporter.py`)

- **JSON 报告**: `eval_results/{run_id}/results.json` — 完整结构化数据
- **Markdown 报告**: `eval_results/{run_id}/report.md` — 摘要表 + 逐 case 详情 + 失败模式分析

### CLI (`eval/cli.py`)

```bash
# 运行全部 VulRepair 评测
python -m eval.cli run --dataset vulrepair

# 运行单个 case
python -m eval.cli run --dataset vulrepair --cases case_02_CWE_125

# 指定并行数
python -m eval.cli run --dataset vulrepair --parallel 2

# 列出可用数据集
python -m eval.cli list-datasets

# 列出某个数据集的测试用例
python -m eval.cli list-cases vulrepair
```

### 更新 Makefile

```makefile
eval-mini:
    PYTHONPATH=. python -m eval.cli run --dataset vulrepair --cases case_02_CWE_125

eval-vulrepair-full:
    PYTHONPATH=. python -m eval.cli run --dataset vulrepair --parallel 2
```

## 数据流总览

```
AgentLoop.run(prompt)
  │
  ▼
LoopState (完整状态产出)
  ├── blackboard → findings, poc_results, patches, 各阶段summary
  ├── current_state → DONE / ERROR
  ├── turn_count, state_turn_count
  ├── state_path → 状态转换路径
  └── turn_log → 每轮工具调用记录
  │
  ▼
EvalRunner（后处理器）
  ├── 读取 patched_code → judge.py (LLM评分)
  ├── 读取 state_path + blackboard → scorer (process + efficiency)
  └── 汇总 → EvalCaseResult
  │
  ▼
Reporter
  ├── JSON → eval_results/{run_id}/results.json
  └── Markdown → eval_results/{run_id}/report.md
```

## Phase 2：报告增强 + 趋势追踪（后续）

- `eval/reporting/trend_tracker.py` — 跨运行的趋势对比
- Markdown 报告增强：失败模式聚类、CWE 类型维度的统计

## Phase 3：高级功能（后续）

- 自定义 test harness 支持（dataset 级别的 `test.sh` / `test_harness.c`）
- 评测结果可视化
- Agent 行为回放（基于 turn_log）

## 需要创建的文件

| 文件 | 职责 |
|------|------|
| `eval/__init__.py` | 包入口，导出公共 API |
| `eval/schema.py` | EvalCaseResult 等数据类 |
| `eval/runner.py` | 单 case 评测执行 |
| `eval/orchestrator.py` | 多 case 编排 + 并行 |
| `eval/judge.py` | LLM-as-Judge 正确性评分 |
| `eval/scorer.py` | 多维度评分汇总 |
| `eval/datasets.py` | 数据集抽象层 |
| `eval/reporter.py` | JSON + Markdown 报告 |
| `eval/cli.py` | 命令行入口 |

## 需要修改的文件

| 文件 | 改动 | 改动量 |
|------|------|--------|
| `core/hook.py` | 新增 `SESSION_END = auto()` | 1 行 |
| `core/loop.py` | `LoopState` 新增 `state_path` + `turn_log`；`run_one_turn()` 中记录；`run()` 中派发 `SESSION_END` | ~15 行 |

## 验证方法

1. **向后兼容**：`pytest tests/test_*.py -v` 确保现有单元测试全部通过
2. **单 case 评测**：`python -m eval.cli run --dataset vulrepair --cases case_02_CWE_125` 走通完整流程
3. **全量评测**：`python -m eval.cli run --dataset vulrepair --parallel 2` 对 10 个 case 完整跑一轮
4. **报告检查**：查看 `eval_results/` 下的 JSON 和 Markdown 报告是否完整、可读
