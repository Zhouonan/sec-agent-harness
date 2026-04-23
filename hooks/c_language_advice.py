import re
import json
from core.hook import hook, HookResult

@hook("POST_TOOL_USE", matcher="execute_in_sandbox")
def c_compiler_advice_hook(state, tool_name, args, result):
    """
    针对 C 语言编译错误的自动化诊断 Hook。
    不修改 AgentLoop 内部逻辑，而是通过外部反馈回路纠偏。
    """
    try:
        data = json.loads(result)
        if data.get("status") == "success":
            return None
            
        stderr = data.get("stderr", "")
        diag_msg = "\n\n[SYSTEM ADVICE - C COMPILATION HELP]:"
        
        # 1. 检测 main() 函数缺失
        if "undefined reference to `main'" in stderr or "main function is required" in stderr.lower():
            diag_msg += "\n- This is a C snippet. You MUST create a wrapper C file with a 'main()' function to call the target function for testing."
            return HookResult(injected_output=diag_msg)
            
        # 2. 检测结构体缺失
        if "error: unknown type name" in stderr or "error: dereferencing pointer to incomplete type" in stderr:
            diag_msg += "\n- It seems you are missing struct or typedef definitions. Since this is an isolated snippet, "
            diag_msg += "you should define MOCK versions of these types (e.g., 'typedef void* TypeName;') in your wrapper file."
            return HookResult(injected_output=diag_msg)
            
        # 3. 常见的链接库报错（如 libm）
        if "undefined reference to `pow'" in stderr or "undefined reference to `sqrt'" in stderr:
            diag_msg += "\n- Math functions detected. Add '-lm' to your gcc command."
            return HookResult(injected_output=diag_msg)
            
    except:
        pass
        
    return None
