import re
import logging
from core.hook import hook, HookResult

# Setup logging
logging.basicConfig(level=logging.INFO)

@hook("POST_TOOL_USE", matcher="execute_in_sandbox")
def smart_codeql_healing_hook(state, tool_name, args, result):
    """
    智能 CodeQL 诊断 Hook：
    1. 检测依赖项丢失并提供 pip 命令建议。
    2. 检测环境重复失败并强制重置策略（跳过 CodeQL，改用 Semgrep）。
    """
    import json
    try:
        data = json.loads(result)
    except:
        return None

    output = data.get("output", "")
    stderr = data.get("stderr", "")
    status = data.get("status")

    # 我们只关心失败的 CodeQL 相关执行
    if status == "success" or "codeql" not in args.get("command", "").lower():
        return None

    # 从黑板读取失败计数
    total_fail_count = state.blackboard.get("codeql_total_fail_count", 0)
    consecutive_fail_count = state.blackboard.get("codeql_consecutive_fail_count", 0)

    # 简单的正则匹配常见错误
    missing_pkg_match = re.search(r"ModuleNotFoundError: No module named '([^']+)'", stderr)
    
    diag_msg = "\n\n[SYSTEM ADVICE - CodeQL SMART RECOVERY]:"
    
    # 更新失败计数
    total_fail_count += 1
    consecutive_fail_count += 1
    state.blackboard["codeql_total_fail_count"] = total_fail_count
    state.blackboard["codeql_consecutive_fail_count"] = consecutive_fail_count

    try:
        # 场景 A：陷入死循环（连续 3 次失败）
        if consecutive_fail_count >= 3:
            diag_msg += f"\n- Critical: CodeQL has failed 3 consecutive times with this configuration."
            diag_msg += "\n- Mandatory Action: Stop retrying the current fix. Switch to 'analyze_path_semgrep' or perform a deeper manual check of the sandbox environment."
            return HookResult(injected_output=diag_msg)
            
        # 场景 B：全局过载检测（尝试了太多次，Token 消耗过高）
        if total_fail_count >= 8:
            diag_msg += f"\n- Warning: Total CodeQL attempts reached 8. This is becoming inefficient."
            diag_msg += "\n- Recommendation: Consider switching to Semgrep to save time, or do one final thorough environment fix."
            return HookResult(injected_output=diag_msg)

        # 场景 C：有进展的修复引导
        if missing_pkg_match:
            pkg = missing_pkg_match.group(1)
            diag_msg += f"\n- Progress: Detected a dependency issue ('{pkg}'). This is normal during environment setup."
            diag_msg += f"\n- Action: Run 'execute_in_sandbox' with 'pip install {pkg}' and retry. (Current Global Attempts: {total_fail_count}/8)"
        else:
            diag_msg += f"\n- Note: CodeQL is struggling with the current codebase structure. (Attempts: {total_fail_count}/8)"
            diag_msg += "\n- Action: Read the 'stderr' and adjust your strategy."
            
        return HookResult(injected_output=diag_msg)

    except Exception as e:
        logging.error(f"Error in smart CodeQL healing hook: {e}")
        
    return None
