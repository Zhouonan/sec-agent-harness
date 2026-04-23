import json
import logging
from core.hook import hook, HookResult
# Note: Since we are in process, we can import AgentState if needed, 
# but we can also just modify the current_state attribute if we know the enum.
# To be safe, we'll try to get AgentState from the loop module or just use its logic.

@hook("POST_TOOL_USE", priority=10) # High priority, check this before others
def tactical_backtracking_hook(state, tool_name, args, result):
    """
    自愈策略：管理同一状态下的连续失败。
    如果失败次数超过阈值（如 3 次），强制 Agent 回退到 INITIAL_ANALYSIS 重新对环境进行评估。
    """
    try:
        # 判断工具执行结果是否为失败
        # 兼容 JSON 字符串和字典
        is_failure = False
        if isinstance(result, str):
            try:
                data = json.loads(result)
                is_failure = data.get("status") != "success"
            except:
                # 如果不是 JSON 或者是普通字符串报错，视具体情况而定
                pass
        
        # 初始化或更新失败计数器
        failures = state.blackboard.get("consecutive_failures", 0)
        
        if is_failure:
            failures += 1
            state.blackboard["consecutive_failures"] = failures
            logging.warning(f"[Recovery] Consecutive failures in {state.current_state.name}: {failures}")
            
            # 如果达到阈值，强制回退
            if failures >= 3:
                # 清除失败路径的局部记忆
                state.blackboard["consecutive_failures"] = 0
                state.blackboard["last_backtrack_reason"] = f"Forced reset due to {failures} consecutive failures in {state.current_state.name}."
                
                # 强制变更状态
                # 这里假设 AgentState 在运行时是可访问的
                # 我们通过修改 state.current_state 的值来干预 FSM
                from core.loop import AgentState
                old_state = state.current_state.name
                state.current_state = AgentState.INITIAL_ANALYSIS
                state.state_turn_count = 0 # 重置该状态的轮次统计
                
                msg = f"\n[AUTO-RECOVERY]: Detected {failures} failures. FORCING BACKTRACK from {old_state} to INITIAL_ANALYSIS."
                return HookResult(injected_output=msg)
        else:
            # 执行成功，重置计数器
            if failures > 0:
                state.blackboard["consecutive_failures"] = 0
                
    except Exception as e:
        logging.error(f"Error in tactical_backtracking_hook: {e}")
        
    return None
