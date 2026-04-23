# Test Plan: Sec-Agent-Harness Evaluation on VulRepair Dataset

## 1. Objective
Evaluate the effectiveness, robustness, and efficiency of the `Sec-Agent-Harness` in identifying and repairing real-world software vulnerabilities using the `VulRepair` benchmark dataset.

## 2. Dataset Overview
- **Dataset**: `VulRepair` (T5-based Automated Software Vulnerability Repair).
- **Source Files**: `test.csv`, `train.csv`, `val.csv` (located in `agent/VulRepair/data/fine_tune_data/`).
- **Structure**: Each row contains:
    - `cwe_id`: The CWE classification.
    - `source`: Vulnerable C code snippet (with `<S2SV_StartBug>` and `<S2SV_EndBug>` tags).
    - `target`: Ground truth repair patch (with `<S2SV_ModStart>` and `<S2SV_ModEnd>` tags).

## 3. Test Methodology

### 3.1 Sampling Strategy
Due to the large size of the dataset, a representative subset will be used:
- **Top-10 CWEs**: Select 5-10 samples from each of the top 10 most frequent CWEs in `test.csv` (e.g., CWE-119, CWE-125, CWE-20, etc.).
- **Total Samples**: Target 50-100 test cases for the initial benchmark.

### 3.2 Environment Setup
For each test case, a fresh workspace will be initialized:
1.  Create a directory: `challenge/vuln_repair_eval/case_<id>_<cwe_id>/`.
2.  Populate `vulnerable_code.c`:
    -   Strip the `<S2SV_StartBug>`/`<S2SV_EndBug>` tags for the agent's view, or provide them as "hints" if simulating a pre-located bug.
    -   *Decision*: For pure repair evaluation, provide the pre-processed source code.
3.  Include a `README.md` describing the task: "Analyze and fix the vulnerability in `vulnerable_code.c`."

`python3 /Users/nnzz/Documents/agent/sec-agent-harness/scripts/prepare_vulrepair_cases.py`

### 3.3 Execution Pipeline
The evaluation will be automated using a benchmarker script (`scripts/run_vulrepair_benchmark.py` - *to be developed*):
1.  **Iterate** through selected samples.
2.  **Initialize** the FSM-driven `AgentLoop` with the specific case workspace.
3.  **Run** the agent until it reaches `DONE` or `ERROR`.
4.  **Capture** logs, blackboard state, and the final fixed file.

### 3.4 Verification & Metrics
- **Exact Match (EM)**: Compare the agent's fix with the `target` ground truth (after normalization).
- **FSM Trace Analysis**:
    -   Did it correctly transition through all states?ni h
    -   Were there any loops or circuit-breaker triggers?
- **Efficiency**: Number of turns taken to reach `DONE`.
- **Qualitative Review**: For non-EM cases, a manual review to see if the fix is functionally correct even if not identical to the ground truth.

## 4. Expected Outputs
- A comprehensive JSON report detailing success/failure for each case.
- Agent logs for failed cases to identify common failure modes (e.g., stuck in `VALIDATOR`).
- A "Vulnerability Repair Score" for the harness.

## 5. Next Steps
1.  Implement the sampling and workspace preparation script.
2.  Implement the automated benchmark runner.
3.  Execute initial run on 10 samples to calibrate.
4.  Full execution and report generation.
