import json

def run_regression_tests_handler(agent, state, test_command: str):
    print(f"[{state.current_state.name}] Running regression tests: {test_command}")
    result = agent.sandbox.execute(test_command)
    
    # 实时打印输出到控制台，让用户可见
    print("\n--- Regression Test Output ---")
    print(result.get("output", ""))
    print("------------------------------\n")

    # Track test status on blackboard for transition validation
    state.blackboard["last_test_status"] = result.get("status")
    state.blackboard["last_test_exit_code"] = result.get("exit_code")

    if result.get("exit_code") == 0:
        status = "PASSED"
    else:
        status = "FAILED"
        
        # 注入诊断建议，纠正路径偏见
        diag_msg = "\n\n[SYSTEM ADVICE]: Tests failed. Check if you are using the CORRECT test path."
        diag_msg += "\nExample: If the code is in challenge/, tests might be in challenge/tests/."
        result["output"] += diag_msg
        
    return json.dumps({
        "status": status,
        "output": result.get("output", ""),
        "exit_code": result.get("exit_code")
    }, indent=2)
