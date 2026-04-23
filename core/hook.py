import functools
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

class HookEvent(Enum):
    SESSION_START = auto()
    PRE_TOOL_USE = auto()
    POST_TOOL_USE = auto()

@dataclass
class HookResult:
    """Result of a hook execution."""
    continue_execution: bool = True  # Whether to proceed with the tool call (PreToolUse)
    block_reason: Optional[str] = None # Reason if blocked
    injected_output: str = ""        # Output to append to the tool result (PostToolUse)
    modified_args: Optional[Dict[str, Any]] = None # Optional modified arguments for the tool

class HookRegistry:
    """Singleton registry for managing and dispatching hooks."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HookRegistry, cls).__new__(cls)
            cls._instance._hooks = {event: [] for event in HookEvent}
        return cls._instance

    def register(self, event: HookEvent, func: Callable, matcher: Optional[str] = None, priority: int = 100):
        """Registers a hook function for a specific event."""
        self._hooks[event].append({
            "func": func,
            "matcher": matcher,
            "priority": priority
        })
        # Sort hooks by priority (lower number = higher priority)
        self._hooks[event].sort(key=lambda x: x["priority"])
        logging.info(f"Registered hook '{func.__name__}' for event '{event.name}' (matcher: {matcher})")

    def dispatch(self, event: HookEvent, state: Any, tool_name: Optional[str] = None, 
                 args: Optional[Dict[str, Any]] = None, result: Optional[Any] = None) -> HookResult:
        """Dispatches an event to all registered hooks."""
        final_result = HookResult()
        
        for entry in self._hooks.get(event, []):
            # Check if matcher matches the current tool name
            if entry["matcher"] and tool_name and entry["matcher"] != tool_name:
                continue

            try:
                # Call the hook function
                # Signature: func(state, tool_name, args, result)
                # Note: result is only passed for POST_TOOL_USE
                hook_out = entry["func"](state, tool_name, args, result)
                
                if isinstance(hook_out, HookResult):
                    # Merge HookResult if returned
                    if not hook_out.continue_execution:
                        final_result.continue_execution = False
                        final_result.block_reason = hook_out.block_reason
                    
                    if hook_out.injected_output:
                        final_result.injected_output += "\n" + hook_out.injected_output
                    
                    if hook_out.modified_args:
                        final_result.modified_args = hook_out.modified_args
            except Exception as e:
                logging.error(f"Error executing hook '{entry['func'].__name__}': {e}")
        
        return final_result

# Global Registry Instance
registry = HookRegistry()

def hook(event: str, matcher: Optional[str] = None, priority: int = 100):
    """
    Decorator for registering hooks.
    Example: @hook("POST_TOOL_USE", matcher="execute_in_sandbox")
    """
    def decorator(func: Callable):
        try:
            event_enum = HookEvent[event.upper()]
            registry.register(event_enum, func, matcher, priority)
        except KeyError:
            logging.error(f"Invalid hook event: {event}")
        return func
    return decorator
