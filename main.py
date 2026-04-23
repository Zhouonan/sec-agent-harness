import os
import sys
import readline # Enables arrow key navigation and history in input()

# Add project root to PYTHONPATH
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from core.loop import AgentLoop

def main():
    print("=" * 60)
    print("🛡️  Sec-Agent-Harness Interactive Shell 🛡️")
    print("=" * 60)
    
    try:
        loop = AgentLoop(workspace_path=project_root)
        print("[System] AgentLoop initialized successfully based on .env config.")
    except ValueError as e:
        print(f"\n[Error] Initialization Failed: {e}")
        print("Please ensure your .env file is correctly set up.")
        sys.exit(1)

    print("\nType your task/prompt for the security agent.")
    print("Type 'exit' or 'quit' to close the session.\n")

    while True:
        try:
            user_input = input("Agent Prompt > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ['exit', 'quit']:
                print("Exiting Sec-Agent-Harness...")
                break

            print("\n" + "-" * 50)
            print(f"Executing Task: {user_input}")
            print("-" * 50 + "\n")
            
            # 运行 Agent 循环
            final_state = loop.run(user_input)

            print("\n" + "=" * 50)
            print(f"Task Completed! Final Agent State: {final_state.current_state.name}")
            print("=" * 50 + "\n")

        except KeyboardInterrupt:
            print("\nOperation cancelled by user. Type 'exit' to quit.")
        except Exception as e:
            print(f"\n[Unexpected Error] {e}")

if __name__ == "__main__":
    main()
