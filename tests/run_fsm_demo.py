import os
import sys

# Add project root to PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from core.loop import AgentLoop, AgentState

def main():
    # Retrieve the API key from the local file
    # Note: For better security, keep these in your .env file
    loop = AgentLoop(
        workspace_path=project_root
    )

    # Initial query for the agent
    prompt = (
        "We are performing a basic system check. "
        "Please transition to the VALIDATOR state, "
        "execute a simple 'uname -a' command in the sandbox, "
        "and then transition to the DONE state."
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
    for msg in final_state.messages[-5:]:
        role = msg.get("role", "unknown")
        name = msg.get("name", "")
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])
        
        if tool_calls:
            for tc in tool_calls:
                print(f"[{role.upper()}] Tool Call -> {tc.get('function', {}).get('name')}({tc.get('function', {}).get('arguments')})")
        else:
            print(f"[{role.upper()}] {name if name else ''}: {content[:150]}..." if len(content) > 150 else f"[{role.upper()}] {name if name else ''}: {content}")

if __name__ == "__main__":
    main()
