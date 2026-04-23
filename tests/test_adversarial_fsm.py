import sys
import os
import json
from unittest.mock import MagicMock
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.loop import AgentLoop, LoopState, AgentState
from core.config import settings

def mock_transition_response(next_state, summary):
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_tool_call = MagicMock()
    
    mock_tool_call.id = "call_123"
    mock_tool_call.function.name = "transition_state"
    mock_tool_call.function.arguments = json.dumps({
        "next_state": next_state,
        "summary": summary
    })
    
    mock_message.tool_calls = [mock_tool_call]
    mock_message.model_dump.return_value = {
        "role": "assistant", 
        "tool_calls": [{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "transition_state",
                "arguments": json.dumps({"next_state": next_state, "summary": summary})
            }
        }]
    }
    mock_response.choices = [MagicMock(message=mock_message)]
    return mock_response

def test_infinite_loop_trap():
    """
    Test that the circuit breaker (total_max_turns) is triggered when 
    the agent oscillates between two states indefinitely.
    """
    print("\n[TEST] Starting test_infinite_loop_trap...")
    
    loop = AgentLoop(model="mock-model", api_key="mock-key")
    
    # We want to alternate between VALIDATOR and FIXER
    def side_effect(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            return mock_transition_response("VALIDATOR", "Found something")
        elif call_count % 2 == 0:
            return mock_transition_response("FIXER", f"Fixing attempt {call_count}")
        else:
            return mock_transition_response("VALIDATOR", f"Validating attempt {call_count}")

    call_count = 0
    loop.client.chat.completions.create = MagicMock(side_effect=side_effect)
    
    # Run the loop. It will use default settings (40 total turns)
    final_state = loop.run("Start oscillation.")
    
    print(f"Final State: {final_state.current_state.name}")
    print(f"Total Turns: {final_state.turn_count}")
    
    assert final_state.current_state == AgentState.ERROR
    # Default total_max_turns is 40
    assert final_state.turn_count == 40
    print("[SUCCESS] Infinite loop trap caught by global turn limit.")

def test_invalid_transition():
    """
    Test how the system handles invalid state transitions.
    """
    print("\n[TEST] Starting test_invalid_transition...")
    loop = AgentLoop(model="mock-model", api_key="mock-key")
    
    # Mock an invalid state transition
    def side_effect(messages, **kwargs):
        return mock_transition_response("SUPER_USER", "Attempting privilege escalation")

    loop.client.chat.completions.create = MagicMock(side_effect=side_effect)
    
    # We'll run one turn manually to check the handler output
    state = LoopState(messages=[{"role": "user", "content": "Try invalid state."}])
    loop.run_one_turn(state)
    
    # Check last message content (it should be the error from tool)
    last_msg = state.messages[-1]
    print(f"Tool response: {last_msg['content']}")
    
    assert "Error: Invalid state SUPER_USER" in last_msg['content']
    assert state.current_state == AgentState.INITIAL_ANALYSIS
    print("[SUCCESS] Invalid transition handled correctly.")

def test_blackboard_payload_injection():
    """
    Test blackboard robustness against large payloads and special characters.
    """
    print("\n[TEST] Starting test_blackboard_payload_injection...")
    loop = AgentLoop(model="mock-model", api_key="mock-key")
    
    large_payload = "A" * 10000 # 10KB string
    special_chars = "}{'; injection attempt -- \n\r\t\""
    
    def side_effect(messages, **kwargs):
        return mock_transition_response("VALIDATOR", large_payload + special_chars)

    loop.client.chat.completions.create = MagicMock(side_effect=side_effect)
    
    state = LoopState(messages=[{"role": "user", "content": "Inject payload."}])
    loop.run_one_turn(state)
    
    # Verify blackboard content
    summary_key = "INITIAL_ANALYSIS_summary"
    assert summary_key in state.blackboard
    assert state.blackboard[summary_key] == large_payload + special_chars
    
    # Verify system prompt generation with large payload
    system_prompt = loop.get_system_prompt(state)
    assert large_payload in system_prompt
    assert "### Blackboard" in system_prompt
    
    # Ensure it's valid JSON in the prompt
    # The prompt contains text then JSON
    json_part = system_prompt.split("### Blackboard (State Context)\n")[1]
    parsed_blackboard = json.loads(json_part)
    assert parsed_blackboard[summary_key] == large_payload + special_chars
    
    print("[SUCCESS] Blackboard handled large payload and special characters.")

def test_malicious_config():
    """
    Test how the system behaves with malicious or edge-case configurations.
    """
    print("\n[TEST] Starting test_malicious_config...")
    
    # Manually inject bad values into settings
    original_total = settings.loop.total_max_turns
    settings.loop.total_max_turns = -1
    
    try:
        loop = AgentLoop(model="mock-model", api_key="mock-key")
        state = LoopState(messages=[{"role": "user", "content": "Start."}], total_max_turns=settings.loop.total_max_turns)
        
        # Should immediately fail or handle gracefully
        active = loop.run_one_turn(state)
        print(f"Active: {active}, State: {state.current_state.name}")
        
        assert not active
        assert state.current_state == AgentState.ERROR
        print("[SUCCESS] Negative turn limit handled (stopped immediately).")
    finally:
        settings.loop.total_max_turns = original_total

def test_network_failure_simulation():
    """
    Test how the system handles API errors (500, 429, timeouts).
    """
    print("\n[TEST] Starting test_network_failure_simulation...")
    loop = AgentLoop(model="mock-model", api_key="mock-key")
    
    # Simulate an API error
    loop.client.chat.completions.create = MagicMock(side_effect=Exception("API Error: Rate Limit Exceeded (429)"))
    
    state = LoopState(messages=[{"role": "user", "content": "Hello."}])
    
    try:
        loop.run_one_turn(state)
    except Exception as e:
        print(f"Caught expected exception: {e}")
        assert "429" in str(e)
        print("[SUCCESS] Network failure propagated (though not gracefully handled in core/loop.py).")

if __name__ == "__main__":
    test_infinite_loop_trap()
    test_invalid_transition()
    test_blackboard_payload_injection()
    test_malicious_config()
    test_network_failure_simulation()
