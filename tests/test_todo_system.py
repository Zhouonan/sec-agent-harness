import sys
import os
import json
from unittest.mock import MagicMock
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.loop import AgentLoop, LoopState, AgentState
from skills.file_ops.handler import update_plan_handler
from core.utils import render_plan

def test_todo_update_logic():
    print("\n[TEST] Starting test_todo_update_logic...")
    loop = AgentLoop(workspace_path=".", model="mock-model", api_key="mock-key", base_url="mock-url")
    state = LoopState()
    
    # 1. Test basic update
    plan_items = [
        {"content": "Analyze attack surface", "status": "completed"},
        {"content": "Verify vulnerability", "status": "in_progress", "activeForm": "Running PoC"},
        {"content": "Fix bug", "status": "pending"}
    ]
    
    result = update_plan_handler(loop, state, items=plan_items)
    print(f"Update Result:\n{result}")
    
    assert state.blackboard["plan"] == plan_items
    assert state.rounds_since_todo_update == 0
    assert "[x] Analyze attack surface" in result
    assert "[>] Verify vulnerability (Running PoC)" in result
    assert "[ ] Fix bug" in result
    print("[SUCCESS] Basic plan update verified.")

def test_todo_focus_constraint():
    print("\n[TEST] Starting test_todo_focus_constraint...")
    loop = AgentLoop(workspace_path=".", model="mock-model", api_key="mock-key", base_url="mock-url")
    state = LoopState()
    
    # 2. Test focus constraint (only one in_progress)
    invalid_plan = [
        {"content": "Task 1", "status": "in_progress"},
        {"content": "Task 2", "status": "in_progress"}
    ]
    
    result = update_plan_handler(loop, state, items=invalid_plan)
    print(f"Invalid Update Result: {result}")
    
    assert "Error" in result
    assert "Only one item can be 'in_progress'" in result
    assert "plan" not in state.blackboard
    print("[SUCCESS] Focus constraint verified.")

def test_todo_reminder_trigger():
    print("\n[TEST] Starting test_todo_reminder_trigger...")
    # Mocking client to avoid real API calls
    loop = AgentLoop(workspace_path=".", model="mock-model", api_key="mock-key", base_url="mock-url")
    loop.client.chat.completions.create = MagicMock()
    
    state = LoopState()
    state.rounds_since_todo_update = 4
    
    # After one turn, it should be 5
    # We mock the response to just return a message without tool calls
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.tool_calls = None
    mock_message.content = "Thinking..."
    mock_message.model_dump.return_value = {"role": "assistant", "content": "Thinking..."}
    mock_response.choices = [MagicMock(message=mock_message)]
    loop.client.chat.completions.create.return_value = mock_response
    
    loop.run_one_turn(state)
    
    assert state.rounds_since_todo_update == 5
    
    # Check if reminder is in messages for the NEXT turn
    # Actually, the reminder is injected into 'messages' passed to LLM, not saved in state.messages
    # Let's verify get_system_prompt doesn't have it, but run_one_turn adds it.
    
    # We can verify by inspecting the call to completions.create
    last_call_args = loop.client.chat.completions.create.call_args
    sent_messages = last_call_args.kwargs['messages']
    
    # The last turn was 4->5. Wait, run_one_turn increments it BEFORE calling LLM?
    # Let's check loop.py:
    # state.rounds_since_todo_update += 1
    # if state.rounds_since_todo_update >= 5: ... inject reminder
    
    reminder_found = any("<reminder>" in m['content'] for m in sent_messages if m['role'] == 'system')
    assert reminder_found
    print("[SUCCESS] Reminder injection at round 5 verified.")

if __name__ == "__main__":
    test_todo_update_logic()
    test_todo_focus_constraint()
    test_todo_reminder_trigger()
