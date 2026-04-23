import json
import os
from core.hook import hook, HookResult

@hook("POST_TOOL_USE", matcher="execute_in_sandbox", priority=50)
def context_snapshot_hook(state, tool_name, args, result):
    """
    当沙箱执行失败时，自动捕获环境快照（目录结构、当前路径）。
    帮助 Agent 诊断路径错误或环境配置问题。
    """
    try:
        # 解析结果，判断是否失败
        if isinstance(result, str):
            data = json.loads(result)
        else:
            data = result
            
        if data.get("status") != "success":
            # 这里的 agent 实例可以通过某些方式获取，或者直接使用 sandbox 工具
            # 为了保持 Hook 纯粹，我们利用 blackboard 里的信息或建议 Agent 运行探测工具
            # 更好的做法是：Hook 自动追加当前环境的探测信息
            
            # 由于 Hook 运行在宿主机，但命令跑在沙箱，
            # 最准确的快照应该是再次运行一个简单的探测命令。
            # 但为了性能，我们先从 Hook 层注入“强制探测”的指令建议，
            # 或者利用 blackboard 记录的信息。
            
            snapshot = "\n[CONTEXT SNAPSHOT - AUTO DIAGNOSIS]:"
            snapshot += f"\n- Working Directory: {os.getcwd()}"
            
            # 尝试获取当前目录的简易列表（宿主机视角，通常与沙箱挂载一致）
            try:
                files = os.listdir(".")
                snapshot += f"\n- Files in CWD: {files[:10]}{'...' if len(files) > 10 else ''}"
            except:
                pass
                
            snapshot += "\n- Hint: If the error is 'File Not Found', check if the path is relative to the workspace root."
            
            return HookResult(injected_output=snapshot)
    except:
        pass
    return None
