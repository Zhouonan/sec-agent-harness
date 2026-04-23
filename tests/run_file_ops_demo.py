import os
import sys

# Add project root to PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from core.loop import AgentLoop, AgentState

def main():
    print("Initializing AgentLoop with real API key for File-Ops test...")
    try:
        loop = AgentLoop(workspace_path=project_root)
    except ValueError as e:
        print(f"Initialization Error: {e}")
        return

    # Initial query for the agent
    prompt = (
        "This is a skill integration test. Please do exactly the following in order:\n"
        "1. In the INITIAL_ANALYSIS state, add a TODO saying 'Verify file writing works'.\n"
        "2. Use 'read_file' to read the contents of 'environment.yml'.\n"
        "3. Transition to the VALIDATOR state.\n"
        "4. In the VALIDATOR state, use 'write_file' to create a file named 'test_skill_output.txt' "
        "with the content 'Skill integration success!'.\n"
        "5. Transition to the DONE state."
    )

    print("\n" + "="*50)
    print(f"User Query: {prompt}")
    print("="*50 + "\n")

    # Run the loop
    final_state = loop.run(prompt)
    
    print("\n" + "="*50)
    print(f"Execution completed. Final State: {final_state.current_state.name}")
    print("="*50 + "\n")

    # Print the last few messages to show the interaction
    print("Recent Message History:")
    for msg in final_state.messages[-8:]:
        role = msg.get("role", "unknown")
        name = msg.get("name", "")
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])
        
        if tool_calls:
            for tc in tool_calls:
                print(f"[{role.upper()}] Tool Call -> {tc.get('function', {}).get('name')}({tc.get('function', {}).get('arguments')})")
        else:
            # truncate output if it's too long
            print(f"[{role.upper()}] {name if name else ''}: {content[:150]}..." if len(content) > 150 else f"[{role.upper()}] {name if name else ''}: {content}")

    # Verify if the file was created
    test_file_path = os.path.join(project_root, "test_skill_output.txt")
    if os.path.exists(test_file_path):
        print(f"\n[VERIFICATION] test_skill_output.txt was created successfully!")
        with open(test_file_path, "r") as f:
            print(f"Content: {f.read()}")
        # Clean up
        os.remove(test_file_path)
    else:
        print(f"\n[VERIFICATION FAILED] test_skill_output.txt was NOT created.")

if __name__ == "__main__":
    main()
