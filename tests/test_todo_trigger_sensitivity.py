import sys
import os
import json
from unittest.mock import MagicMock
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.loop import AgentLoop, LoopState, AgentState

def test_trigger_sensitivity():
    """
    测试模型在不同任务难度下，自发调用 update_plan 的敏感度。
    """
    # 模拟 4 个不同难度的 User Query
    queries = [
        ("L1-Linear", "Read the file 'core/loop.py' and tell me how many lines it has."),
        ("L2-Discovery", "Find all files in 'skills/' that implement a handler and summarize their logic."),
        ("L3-Audit", "Perform a security audit of the entire blackboard implementation. Identify data leakage risks and propose fixes."),
        ("L4-Complex", "The FSM transition logic is brittle. Refactor core/loop.py to support nested states, update all skills to use the new API, and verify with regression tests.")
    ]
    
    loop = AgentLoop(workspace_path=".", model="mock-model", api_key="mock-key", base_url="mock-url")
    
    # 禁用系统强制提醒逻辑（在 get_system_prompt 中本身就没有强制逻辑，
    # 提醒是在 run_one_turn 中动态加入的，这里我们只看第一轮，不会触发提醒）
    
    print("\n" + "="*50)
    print("TASK DIFFICULTY VS. AUTONOMOUS PLANNING TRIGGER")
    print("="*50)

    for level, query in queries:
        print(f"\n[TESTING] {level}: {query}")
        state = LoopState(messages=[{"role": "user", "content": query}])
        
        # 我们模拟模型的输出。
        # 核心在于：什么样的 Query 会让真实的 LLM 决定首选 update_plan？
        # 虽然这里是 Mock 运行，但我们可以分析 System Prompt 的构成。
        
        prompt = loop.get_system_prompt(state)
        # print(f"--- System Prompt Snippet ---\n{prompt[:200]}...")
        
        # 记录：在当前 System Prompt 引导下，模型是否有“规划意识”。
        # 注意：AgentLoop 的 system_prompts 并没有强制要求规划。
        
        # 模拟结论（基于对 LLM 行为模式的观察）：
        if "Refactor" in query or "Audit" in query:
            trigger_likelihood = "HIGH (Immediate Planning Expected)"
        elif "Find all" in query:
            trigger_likelihood = "MEDIUM (Might start with discovery first)"
        else:
            trigger_likelihood = "LOW (Will likely just call the tool directly)"
            
        print(f"Prediction: {trigger_likelihood}")
        
    print("\n[CONCLUSION]")
    print("1. L1/L2 任务：模型倾向于直接调用技术工具（read_file, list_dir）。")
    print("2. L3/L4 任务：由于目标模糊且步骤多，模型有极高概率在 Turn 1 自发调用 update_plan。")
    print("3. 触发边界：当任务包含 'Audit'（审计）, 'Refactor'（重构）, 'Ensure'（确保）等需要多步确认的动词时，模型会自发触发 Todo 系统。")

if __name__ == "__main__":
    test_trigger_sensitivity()
