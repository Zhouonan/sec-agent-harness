from core.hook import hook, HookResult

@hook("POST_TOOL_USE", matcher="execute_in_sandbox")
def system_advice_hook(state, tool_name, args, result):
    """
    捕获沙箱执行失败，并提供诊断建议。
    原逻辑从 core/loop.py 的 sandbox_handler 迁移而来。
    """
    # result 应该是一个包含 status 和 output 的字典或对象
    # 在 loop.py 中，sandbox_handler 返回的是 json.dumps(result)
    # 为了 Hook 方便处理，我们可能需要调整 loop.py 传递给 Hook 的 result 格式
    
    import json
    try:
        data = json.loads(result)
        if data.get("status") != "success":
            diag_msg = "\n\n[SYSTEM ADVICE]: The command failed. Before assuming the code fix is wrong, please check:"
            diag_msg += "\n1. Is the test file path correct? (Use list_files to confirm)"
            diag_msg += "\n2. Is the command name correct for this environment (e.g., python vs python3)?"
            diag_msg += "\n3. Are there any missing dependencies or environment variables?"
            
            # 返回注入内容
            return HookResult(injected_output=diag_msg)
    except:
        pass
    return None

@hook("PRE_TOOL_USE", matcher="transition_state")
def fsm_safety_hook(state, tool_name, args, result):
    """
    封死 FSM 后门，强制执行路径约束。
    原逻辑从 core/loop.py 的 transition_handler 迁移而来。
    """
    next_state_name = args.get("next_state", "").upper()
    current_state_name = state.current_state.name
    
    # 1. 出口路径强制约束：只有 REVIEWER 能转 DONE
    if next_state_name == "DONE" and current_state_name != "REVIEWER":
        return HookResult(
            continue_execution=False,
            block_reason=f"TRANSITION REJECTED: You cannot transition to DONE from {current_state_name}. "
                         "All security fixes MUST be verified in the REVIEWER state first."
        )

    # 2. 质量强校验：跳转 DONE 必须满足测试成功
    if next_state_name == "DONE":
        last_status = state.blackboard.get("last_test_status")
        if last_status not in ("success", "PASSED"):
            return HookResult(
                continue_execution=False,
                block_reason=f"TRANSITION REJECTED: Your last verification attempt did not succeed (Status: {last_status})."
            )
            
    return None
