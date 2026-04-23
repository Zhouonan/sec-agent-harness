import sys
import os
import json
from unittest.mock import MagicMock
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.loop import AgentLoop, LoopState, AgentState

def test_fsm_mock_logic():
    # 1. 创建 Agent 实例
    loop = AgentLoop(model="moonshot-v1-8k", api_key="fake-key")
    
    # 2. Mock OpenAI 客户端，使其返回一个 transition_state 的工具调用
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_tool_call = MagicMock()
    
    mock_tool_call.id = "call_123"
    mock_tool_call.function.name = "transition_state"
    mock_tool_call.function.arguments = json.dumps({
        "next_state": "VALIDATOR",
        "summary": "Found SQLi in login.py at line 15"
    })
    
    mock_message.tool_calls = [mock_tool_call]
    mock_message.model_dump.return_value = {"role": "assistant", "tool_calls": []} # 简化处理
    mock_response.choices = [MagicMock(message=mock_message)]
    
    loop.client.chat.completions.create = MagicMock(return_value=mock_response)
    
    # 3. 初始化状态
    state = LoopState(messages=[{"role": "user", "content": "Scan the code."}])
    print(f"--- [START] State: {state.current_state.name} ---")
    
    # 4. 运行一轮 (此时会触发 Mock 的工具调用)
    loop.run_one_turn(state)
    
    # 5. 验证结果
    print(f"\n--- [RESULT] New State: {state.current_state.name} ---")
    print(f"Blackboard: {state.blackboard}")
    
    assert state.current_state == AgentState.VALIDATOR
    assert "INITIAL_ANALYSIS_summary" in state.blackboard
    print("\n[SUCCESS] Mock FSM Logic verified without API calls!")

if __name__ == "__main__":
    test_fsm_mock_logic()
