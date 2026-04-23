import os
import sys
import json
import time
import shutil
from datetime import datetime

# Add project root to path
project_root = "/Users/nnzz/Documents/agent/sec-agent-harness"
sys.path.insert(0, project_root)

from core.loop import AgentLoop, AgentState

CHALLENGE_ROOT = os.path.join(project_root, "challenge/vuln_repair_eval")
RUNS_ROOT = os.path.join(project_root, "challenge/runs")
DOCS_DIR = os.path.join(project_root, "docs/test_results/json")

def run_benchmark(target_case=None):
    # Ensure the output directories exist
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(RUNS_ROOT, exist_ok=True)
    
    if not os.path.exists(CHALLENGE_ROOT):
        print(f"Error: Challenge directory not found at {CHALLENGE_ROOT}")
        return

    all_cases = sorted([d for d in os.listdir(CHALLENGE_ROOT) if d.startswith("case_")])
    
    # 动态生成报告文件名
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"vulrepair_report_{timestamp_str}.json"
    current_report_file = os.path.join(DOCS_DIR, report_filename)
    latest_report_file = os.path.join(DOCS_DIR, "vulrepair_benchmark_report_latest.json")

    if target_case:
        if target_case in all_cases:
            cases = [target_case]
        else:
            matches = [c for c in all_cases if target_case in c]
            if len(matches) == 1:
                cases = matches
            else:
                print(f"Error: Case '{target_case}' not found or ambiguous in {CHALLENGE_ROOT}")
                return
    else:
        cases = all_cases

    print(f"Starting benchmark on {len(cases)} case(s)...")

    results = {
        "timestamp": datetime.now().isoformat(),
        "total_cases": len(cases),
        "cases": []
    }

    for case_name in cases:
        # --- FORK LOGIC START ---
        # 1. 定义原始路径和运行副本路径
        original_case_path = os.path.join(CHALLENGE_ROOT, case_name)
        run_case_path = os.path.join(RUNS_ROOT, f"run_{timestamp_str}_{case_name}")
        
        print(f"\n[{case_name}] Forking case to: {run_case_path}")
        
        # 2. 物理复制整个目录，实现环境隔离
        try:
            if os.path.exists(run_case_path):
                shutil.rmtree(run_case_path)
            shutil.copytree(original_case_path, run_case_path)
        except Exception as e:
            print(f"Error forking case {case_name}: {e}")
            continue
        # --- FORK LOGIC END ---

        print(f"[{case_name}] Starting evaluation in isolated workspace...")
        
        prompt = (
            "Analyze and fix the vulnerability in 'vulnerable_code.c'.\n"
            "IMPORTANT GUIDELINES for this C snippet:\n"
            "1. This is a function snippet, not a full program. To compile it, you MUST create a wrapper (e.g., 'poc.c') with a 'main()' function.\n"
            "2. If you encounter missing types (e.g., structs, typedefs), define minimal MOCK versions in your wrapper to satisfy the compiler.\n"
            "3. Use 'execute_in_sandbox' to run your compilation and PoC tests.\n"
            "Follow the standard FSM procedure: Analyze -> Validate -> Fix -> Review."
        )
        
        try:
            # Initialize loop targeting the FORKED workspace
            loop = AgentLoop(workspace_path=run_case_path)
            
            start_time = time.time()
            final_state_obj = loop.run(prompt)
            duration = time.time() - start_time
            
            # Check results from the FORKED workspace
            final_code_path = os.path.join(run_case_path, "vulnerable_code.c")
            with open(final_code_path, 'r') as f:
                final_code = f.read()
                
            solution_path = os.path.join(run_case_path, "solution.txt")
            with open(solution_path, 'r') as f:
                solution_content = f.read()
            
            ground_truth = solution_content.split("--- Ground Truth Fix ---")[-1].strip()
            is_exact_match = final_code.strip() == ground_truth.strip()
            
            case_result = {
                "case_name": case_name,
                "run_directory": run_case_path,
                "final_state": final_state_obj.current_state.name,
                "duration_seconds": round(duration, 2),
                "turn_count": final_state_obj.turn_count,
                "exact_match": is_exact_match,
                "blackboard_summary": {k: v for k, v in final_state_obj.blackboard.items() if k.endswith("_summary")},
                "log_file": loop.log_file
            }
            
            results["cases"].append(case_result)
            print(f"[{case_name}] Finished. State: {case_result['final_state']}, Match: {is_exact_match}")

        except Exception as e:
            print(f"[{case_name}] CRASHED: {e}")
            results["cases"].append({
                "case_name": case_name,
                "error": str(e),
                "status": "CRASHED"
            })

    # Save reports
    with open(current_report_file, 'w') as f:
        json.dump(results, f, indent=4)
    with open(latest_report_file, 'w') as f:
        json.dump(results, f, indent=4)
    
    print(f"\nBenchmark complete.")
    print(f"📄 Full report saved: {current_report_file}")
    print(f"🔗 Latest report updated: {latest_report_file}")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    run_benchmark(target)
