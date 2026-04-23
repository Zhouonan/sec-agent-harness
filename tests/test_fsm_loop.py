import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import json

# Ensure we can import from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.loop import AgentLoop, LoopState, AgentState
from core.config import settings

class TestFSMLoop(unittest.TestCase):
    def setUp(self):
        print(f"\n{'='*60}\n[SETUP] Initializing Test Case: {self._testMethodName}\n{'='*60}")

    def test_logic_transition(self):
        """测试 FSM 内部转换逻辑是否正确更新黑板"""
        loop = AgentLoop()
        state = LoopState()
        
        print(f"[*] Initial State: {state.current_state.name}")
        summary = "Potential vulnerability found: SQL injection in auth.py"
        
        print(f"[*] Calling transition_handler to VALIDATOR...")
        result = loop.transition_handler(state, next_state="VALIDATOR", summary=summary)
        
        print(f"[+] Result: {result}")
        print(f"[+] Blackboard: {json.dumps(state.blackboard, indent=2)}")
        
        self.assertEqual(state.current_state, AgentState.VALIDATOR)
        self.assertIn("INITIAL_ANALYSIS_summary", state.blackboard)
        self.assertEqual(state.blackboard["INITIAL_ANALYSIS_summary"], summary)

    def test_system_prompt_generation(self):
        """测试生成的 System Prompt 是否包含了黑板内容"""
        loop = AgentLoop()
        state = LoopState()
        test_summary = "Sensitive data leak found in /logs"
        state.blackboard["INITIAL_ANALYSIS_summary"] = test_summary
        
        print(f"[*] Current State: {state.current_state.name}")
        print(f"[*] Blackboard state: {list(state.blackboard.keys())}")
        
        prompt = loop.get_system_prompt(state)
        print(f"[*] Generated Prompt Fragment (tail):\n{'-'*40}\n{prompt[-150:]}\n{'-'*40}")
        
        self.assertIn("INITIAL_ANALYSIS_summary", prompt)
        self.assertIn(test_summary, prompt)

    @patch('openai.resources.chat.completions.Completions.create')
    def test_mock_loop_turn(self, mock_create):
        """模拟一次完整的工具调用循环"""
        print("[*] Setting up Mock LLM response with tool_call: transition_state")
        
        # 1. 设置 Mock 返回值
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_tool_call = MagicMock()
        
        mock_tool_call.id = "call_abc_123"
        mock_tool_call.function.name = "transition_state"
        mock_tool_call.function.arguments = json.dumps({
            "next_state": "VALIDATOR",
            "summary": "Confirmed injection point via mock"
        })
        
        mock_message.tool_calls = [mock_tool_call]
        mock_message.content = None
        mock_message.model_dump.return_value = {
            "role": "assistant", 
            "tool_calls": [{
                "id": "call_abc_123",
                "type": "function",
                "function": {
                    "name": "transition_state",
                    "arguments": mock_tool_call.function.arguments
                }
            }]
        }
        
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_create.return_value = mock_response

        # 2. 执行一轮循环
        loop = AgentLoop()
        state = LoopState(messages=[{"role": "user", "content": "Analyze the login flow"}])
        
        print(f"[*] Running one turn in {state.current_state.name}...")
        active = loop.run_one_turn(state)
        
        # 3. 验证结果
        print(f"[+] Turn completed. Active: {active}")
        print(f"[+] New State: {state.current_state.name}")
        print(f"[+] Blackboard: {json.dumps(state.blackboard, indent=2)}")
        
        self.assertTrue(active)
        self.assertEqual(state.current_state, AgentState.VALIDATOR)
        self.assertEqual(state.blackboard["INITIAL_ANALYSIS_summary"], "Confirmed injection point via mock")

    def test_state_turn_limit_circuit_breaker(self):
        """测试单一状态步数达到上限时的熔断机制"""
        loop = AgentLoop()
        # 模拟已经运行了 10 步 (上限也是 10)
        state = LoopState(
            current_state=AgentState.INITIAL_ANALYSIS,
            state_turn_count=settings.loop.max_turns_per_state
        )
        
        print(f"[*] Current State: {state.current_state.name}")
        print(f"[*] State Turn Count: {state.state_turn_count} (Limit: {state.max_turns_per_state})")
        
        active = loop.run_one_turn(state)
        
        print(f"[!] Circuit Breaker Triggered. Active: {active}")
        print(f"[!] Final State: {state.current_state.name}")
        
        self.assertFalse(active)
        self.assertEqual(state.current_state, AgentState.ERROR)

    def test_total_turn_limit_circuit_breaker(self):
        """测试全局步数达到上限时的熔断机制"""
        loop = AgentLoop()
        # 模拟全局运行了 40 步 (上限也是 40)
        state = LoopState(
            current_state=AgentState.INITIAL_ANALYSIS,
            turn_count=settings.loop.total_max_turns
        )
        
        print(f"[*] Total Turn Count: {state.turn_count} (Limit: {state.total_max_turns})")
        
        active = loop.run_one_turn(state)
        
        print(f"[!] Global Circuit Breaker Triggered. Active: {active}")
        print(f"[!] Final State: {state.current_state.name}")
        
        self.assertFalse(active)
        self.assertEqual(state.current_state, AgentState.ERROR)

def run_live_demo():
    if not settings.api.api_key or settings.api.api_key == "sk-placeholder":
        print("\n[SKIP] Live demo skipped: No real API Key configured.")
        return

    print(f"\n{'#'*60}\n# RUNNING LIVE FSM DEMO\n{'#'*60}")
    loop = AgentLoop()
    query = "请分析这段代码是否有风险：`eval(user_input)`。如果你发现了风险，请通过 transition_state 跳转到 VALIDATOR 状态并总结你的发现。"
    state = loop.run(query)
    
    print(f"\n[DEMO DONE]")
    print(f"Final State: {state.current_state.name}")
    print(f"Blackboard: {json.dumps(state.blackboard, indent=2)}")

if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    # run_live_demo()
