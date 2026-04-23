import os
import sys
import json
from unittest.mock import MagicMock
import pytest
import logging

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.hook import registry, HookEvent, HookResult, hook
from core.loop import AgentLoop, LoopState, AgentState

# Rename hooks to avoid pytest discovery and fix signature
@hook("SESSION_START", priority=1)
def mock_session_start_hook(state, tool_name=None, args=None, result=None):
    state.blackboard["session_started"] = True
    return HookResult(injected_output="Session started hook fired.")

@hook("PRE_TOOL_USE", matcher="test_tool", priority=5)
def mock_pre_tool_hook(state, tool_name, args, result=None):
    if args and args.get("block"):
        return HookResult(continue_execution=False, block_reason="Blocked for testing.")
    if args and args.get("modify"):
        return HookResult(modified_args={"modified": True})
    return None

@hook("POST_TOOL_USE", matcher="test_tool")
def mock_post_tool_hook(state, tool_name, args, result):
    return HookResult(injected_output="Post-tool injected.")

@hook("POST_TOOL_USE")
def mock_error_hook(state, tool_name, args, result):
    if tool_name == "trigger_error":
        raise Exception("Hook Error Test")
    return None

def test_hook_registration():
    """Verify that hooks are registered correctly."""
    session_hooks = registry._hooks[HookEvent.SESSION_START]
    assert any(h["func"].__name__ == "mock_session_start_hook" for h in session_hooks)
    
    pre_hooks = registry._hooks[HookEvent.PRE_TOOL_USE]
    assert any(h["func"].__name__ == "mock_pre_tool_hook" for h in pre_hooks)
    
    post_hooks = registry._hooks[HookEvent.POST_TOOL_USE]
    assert any(h["func"].__name__ == "mock_post_tool_hook" for h in post_hooks)

def test_session_start_dispatch():
    """Test SESSION_START event dispatch."""
    state = LoopState()
    registry.dispatch(HookEvent.SESSION_START, state)
    assert state.blackboard.get("session_started") is True

def test_pre_tool_block():
    """Test blocking a tool call via PRE_TOOL_USE."""
    state = LoopState()
    args = {"block": True}
    res = registry.dispatch(HookEvent.PRE_TOOL_USE, state, tool_name="test_tool", args=args)
    assert res.continue_execution is False
    assert res.block_reason == "Blocked for testing."

def test_pre_tool_modify():
    """Test modifying tool arguments via PRE_TOOL_USE."""
    state = LoopState()
    args = {"modify": True}
    res = registry.dispatch(HookEvent.PRE_TOOL_USE, state, tool_name="test_tool", args=args)
    assert res.modified_args == {"modified": True}

def test_post_tool_inject():
    """Test injecting output via POST_TOOL_USE."""
    state = LoopState()
    args = {}
    res = registry.dispatch(HookEvent.POST_TOOL_USE, state, tool_name="test_tool", args=args, result="Original")
    assert "Post-tool injected." in res.injected_output

def test_hook_error_handling(caplog):
    """Verify that a hook error doesn't crash the dispatcher."""
    state = LoopState()
    # mock_error_hook will raise if tool_name is "trigger_error"
    res = registry.dispatch(HookEvent.POST_TOOL_USE, state, tool_name="trigger_error", args={}, result="Original")
    assert res.continue_execution is True 
    assert "Error executing hook 'mock_error_hook'" in caplog.text

def test_auto_loading():
    """Test that hooks are automatically loaded by AgentLoop."""
    # We need to set env vars for AgentLoop init
    os.environ["LLM_MODEL"] = "mock-model"
    os.environ["LLM_API_KEY"] = "mock-key"
    os.environ["LLM_BASE_URL"] = "mock-url"
    
    loop = AgentLoop(model="mock", api_key="mock", base_url="mock")
    
    post_hooks = registry._hooks[HookEvent.POST_TOOL_USE]
    assert any(h["func"].__name__ == "system_advice_hook" for h in post_hooks)
    assert any(h["func"].__name__ == "tactical_backtracking_hook" for h in post_hooks)

if __name__ == "__main__":
    pytest.main([__file__])
