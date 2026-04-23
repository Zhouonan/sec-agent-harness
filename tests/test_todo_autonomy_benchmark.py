import sys
import os
import json
from unittest.mock import MagicMock
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.loop import AgentLoop, LoopState, AgentState

def run_complexity_benchmark(level, name, silent_rounds):
    """
    模拟不同复杂度的任务。
    silent_rounds: Agent 在这期间只进行技术操作（如 read_file），不更新 plan。
    """
    print(f"\n[BENCHMARK] Level {level}: {name}")
    loop = AgentLoop(workspace_path=".", model="mock-model", api_key="mock-key", base_url="mock-url")
    state = LoopState()
    
    # 模拟任务开始时的初始计划
    state.blackboard["plan"] = [{"content": name, "status": "in_progress"}]
    
    reminder_triggered = False
    for i in range(1, 10):
        # 模拟 Agent 的行为
        # 在 silent_rounds 期间，Agent 不调用 update_plan，只进行普通操作
        # 超过 silent_rounds 后，Agent 尝试调用 update_plan
        
        mock_msg = MagicMock()
        mock_msg.content = f"Step {i} execution"
        
        if i > silent_rounds:
            # Agent 终于想起来要更新计划了
            mock_msg.tool_calls = [MagicMock(id=f"c{i}", function=MagicMock(name="update_plan", arguments=json.dumps({"items": []})))]
        else:
            # Agent 沉溺于技术细节，只调用了普通工具（如 read_file）
            mock_msg.tool_calls = [MagicMock(id=f"c{i}", function=MagicMock(name="read_file", arguments=json.dumps({"path": "test.txt"})))]
        
        mock_msg.model_dump.return_value = {"role": "assistant", "content": mock_msg.content}
        loop.client.chat.completions.create = MagicMock(return_value=MagicMock(choices=[MagicMock(message=mock_msg)]))
        
        active = loop.run_one_turn(state)
        
        # 检查本轮是否注入了提醒
        sent_msgs = loop.client.chat.completions.create.call_args.kwargs['messages']
        has_reminder = any("<reminder>" in m['content'] for m in sent_msgs if m['role'] == 'system')
        
        if has_reminder:
            print(f"!!! Round {i}: System Reminder TRIGGERED!")
            reminder_triggered = True
            break
        else:
            print(f"    Round {i}: Agent focusing... (rounds_since_todo_update: {state.rounds_since_todo_update})")
            
        if i > silent_rounds:
            print(f"--- Round {i}: Agent autonomously updated plan. Success!")
            break

    return reminder_triggered, i

if __name__ == "__main__":
    results = []
    # L1: 2轮内解决，不应触发提醒
    results.append(run_complexity_benchmark(1, "Simple Sequence", 2))
    # L2: 4轮内解决，不应触发提醒
    results.append(run_complexity_benchmark(2, "Multi-step Dependency", 4))
    # L3: 5轮内未更新，刚好触发提醒边界
    results.append(run_complexity_benchmark(3, "Cross-component Trace", 5))
    # L4: 7轮沉溺，必然触发提醒
    results.append(run_complexity_benchmark(4, "Dynamic Debugging", 7))
    
    print("\n" + "="*30)
    print("BENCHMARK FINAL REPORT")
    print("="*30)
    for i, (triggered, rounds) in enumerate(results):
        status = "RELIANT (Needed Reminder)" if triggered else "AUTONOMOUS"
        print(f"Level {i+1}: {status} at Round {rounds}")
