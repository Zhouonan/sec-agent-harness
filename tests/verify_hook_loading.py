import os
import sys
# Ensure we can import from core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.loop import AgentLoop
from core.hook import registry, HookEvent

def test_hook_loading():
    print("Initializing AgentLoop...")
    try:
        # We need a workspace path
        workspace = os.path.abspath(".")
        # Minimal init to trigger _load_hooks
        # Note: it will fail if .env is missing or invalid, so we mock those if needed
        # But let's see what happens. 
        os.environ["LLM_MODEL"] = "mock"
        os.environ["LLM_API_KEY"] = "mock"
        os.environ["LLM_BASE_URL"] = "http://localhost/v1"
        
        loop = AgentLoop(workspace_path=workspace)
        
        print("\nRegistered Hooks:")
        for event in HookEvent:
            hooks = registry._hooks.get(event, [])
            print(f"  {event.name}: {len(hooks)} hooks")
            for h in hooks:
                print(f"    - {h['func'].__name__} (matcher: {h['matcher']})")
                
    except Exception as e:
        print(f"Initialization failed (expected if API/env missing): {e}")

if __name__ == "__main__":
    test_hook_loading()
