import sys
import os
import json
from unittest.mock import MagicMock
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.loop import AgentLoop, LoopState, AgentState
from skills.file_ops.handler import update_plan_handler

def setup_mock_loop():
    loop = AgentLoop(workspace_path=".", model="mock-model", api_key="mock-key", base_url="mock-url")
    loop.client.chat.completions.create = MagicMock()
    return loop

def test_liveness_persistence():
    """场景 A: 验证提醒在计划更新前会一直存在"""
    print("\n[SCENARIO A] Testing Liveness Reminder Persistence...")
    loop = setup_mock_loop()
    state = LoopState()
    state.rounds_since_todo_update = 4
    
    # 第一次运行：触发提醒
    mock_msg = MagicMock()
    mock_msg.content = "Action 1"
    mock_msg.tool_calls = None
    mock_msg.model_dump.return_value = {"role": "assistant", "content": "Action 1"}
    loop.client.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=mock_msg)])
    
    loop.run_one_turn(state)
    sent_msgs_1 = loop.client.chat.completions.create.call_args.kwargs['messages']
    assert any("<reminder>" in m['content'] for m in sent_msgs_1)
    
    # 第二次运行：依然没有更新计划，提醒应继续存在
    loop.run_one_turn(state)
    sent_msgs_2 = loop.client.chat.completions.create.call_args.kwargs['messages']
    assert any("<reminder>" in m['content'] for m in sent_msgs_2)
    assert state.rounds_since_todo_update == 6
    
    # 第三次运行：更新计划，提醒应消失
    update_plan_handler(loop, state, items=[{"content": "New Plan", "status": "in_progress"}])
    loop.run_one_turn(state)
    sent_msgs_3 = loop.client.chat.completions.create.call_args.kwargs['messages']
    assert not any("<reminder>" in m['content'] for m in sent_msgs_3)
    assert state.rounds_since_todo_update == 1
    print("[SUCCESS] Liveness reminder lifecycle verified.")

def test_large_plan_impact():
    """场景 B: 超大规模计划下的 Prompt 渲染"""
    print("\n[SCENARIO B] Testing Large Plan Prompt Impact...")
    loop = setup_mock_loop()
    state = LoopState()
    
    large_plan = [{"content": f"Task {i}", "status": "pending"} for i in range(30)]
    large_plan[0]["status"] = "in_progress"
    
    update_plan_handler(loop, state, items=large_plan)
    prompt = loop.get_system_prompt(state)
    
    # 验证是否全部渲染
    assert "Task 0" in prompt
    assert "Task 29" in prompt
    assert "[>] Task 0" in prompt
    assert "[ ] Task 29" in prompt
    print(f"[SUCCESS] Large plan (30 items) rendered correctly. Prompt size: {len(prompt)} chars.")

def test_state_plan_drift():
    """场景 C: 状态转换后的计划滞后"""
    print("\n[SCENARIO C] Testing State-Plan Drift...")
    loop = setup_mock_loop()
    state = LoopState()
    state.current_state = AgentState.VALIDATOR
    
    # 计划仍停留在 INITIAL_ANALYSIS 阶段
    stale_plan = [{"content": "Analyze code", "status": "in_progress"}]
    update_plan_handler(loop, state, items=stale_plan)
    
    prompt = loop.get_system_prompt(state)
    # 虽然系统不强制报错，但我们在报告中记录这种“漂移”作为潜在风险
    # VALIDATOR 对应的 prompt 包含 "Vulnerability Validator"
    assert "Vulnerability Validator" in prompt
    assert "Analyze code" in prompt
    print("[SUCCESS] State-Plan drift detected in prompt (Visual check).")

def test_complex_focus_denial():
    """场景 D: 复杂的焦点占用尝试"""
    print("\n[SCENARIO D] Testing Complex Focus Denial...")
    loop = setup_mock_loop()
    state = LoopState()
    
    # 尝试在一次更新中放入多个 in_progress，或者在已存在 in_progress 时更新为另一个
    initial_plan = [{"content": "Task 1", "status": "in_progress"}]
    update_plan_handler(loop, state, items=initial_plan)
    
    # 试图直接切换到 Task 2 也是 in_progress
    new_plan = [
        {"content": "Task 1", "status": "in_progress"},
        {"content": "Task 2", "status": "in_progress"}
    ]
    result = update_plan_handler(loop, state, items=new_plan)
    assert "Error" in result
    print("[SUCCESS] Multi-focus update rejected.")

if __name__ == "__main__":
    test_liveness_persistence()
    test_large_plan_impact()
    test_state_plan_drift()
    test_complex_focus_denial()
