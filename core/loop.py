import os
import time
import glob
import importlib.util
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Any, Optional
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

from core.config import settings
from core.sandbox import SandboxTool
from core.skill import SkillRegistry
from core.ast_utils import ASTScanner
from core.hook import registry, HookEvent, HookResult

# 配置日志：关闭冗余的网络请求输出，只保留错误
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

class AgentState(Enum):
    INITIAL_ANALYSIS = auto()
    VALIDATOR = auto()
    FIXER = auto()
    REVIEWER = auto()
    DONE = auto()
    ERROR = auto()

@dataclass
class LoopState:
    messages: List[Dict[str, Any]] = field(default_factory=list)
    current_state: AgentState = AgentState.INITIAL_ANALYSIS
    blackboard: Dict[str, Any] = field(default_factory=dict)
    turn_count: int = 0
    state_turn_count: int = 0
    rounds_since_todo_update: int = 0
    max_turns_per_state: int = settings.loop.max_turns_per_state
    total_max_turns: int = settings.loop.total_max_turns
    stop_reason: Optional[str] = None
    session_id: str = field(default_factory=lambda: time.strftime("%Y%m%d_%H%M%S"))
    state_path: List[str] = field(default_factory=list)
    turn_log: List[Dict[str, Any]] = field(default_factory=list)

class AgentLoop:
    def __init__(self, workspace_path: str = ".", model: str = None, api_key: str = None, base_url: str = None):
        # 优先级：参数 > settings (环境变量/yaml)
        self.model = model or settings.api.model
        self.api_key = api_key or settings.api.api_key
        self.base_url = base_url or settings.api.base_url
        self.workspace_path = os.path.abspath(workspace_path)
        
        # 初始化会话日志
        self.log_dir = os.path.join(self.workspace_path, "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, f"agent_session_{time.strftime('%Y%m%d_%H%M%S')}.log")

        if not self.model or not self.api_key or not self.base_url:
            raise ValueError(
                "Missing LLM configuration. Please ensure LLM_MODEL, LLM_API_KEY, "
                "and LLM_BASE_URL are set in .env or config.yaml."
            )

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

        
        self.sandbox = SandboxTool(
            workspace_path=self.workspace_path, 
            image=settings.sandbox.image,
            local_fallback=settings.sandbox.local_fallback
        )
        
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.skill_registry = SkillRegistry(skills_dir=os.path.join(project_root, "skills"))
        self.ast_scanner = ASTScanner(root_path=self.workspace_path)

        # Tools and handlers
        self.tools: Dict[AgentState, List[Dict[str, Any]]] = {state: [] for state in AgentState}
        self.tool_handlers: Dict[str, callable] = {}
        self.system_prompts: Dict[AgentState, str] = {
            AgentState.INITIAL_ANALYSIS: (
                "You are a Security Analyst. Your goal is to map the attack surface and find potential vulnerabilities. "
                "1. START by exploring the directory structure using 'list_files'. "
                "2. MANDATORY: Identify the project's test directory structure (e.g., /tests, /challenge/tests) to ensure PoCs and regression tests are placed and executed correctly. "
                "3. Read key files to understand the project logic. "
                "4. Use the available specialized skills (check the skill catalog below) for deep code structure analysis or taint tracking. "
                "5. When you have a clear hypothesis about a vulnerability and a plan to verify it, transition to VALIDATOR state."
            ),
            AgentState.VALIDATOR: (
                "You are a Vulnerability Validator. Your goal is to confirm vulnerabilities found in the analysis phase. "
                "1. Create a Proof of Concept (PoC) script if one doesn't exist. "
                "2. Run the PoC in the sandbox using 'execute_in_sandbox' and analyze the output. "
                "3. If the vulnerability is confirmed, transition to FIXER state."
            ),
            AgentState.FIXER: (
                "You are a Security Fixer. Your goal is to provide a robust patch for the verified vulnerability. "
                "1. Analyze the root cause and generate a fix. "
                "2. Apply the fix using 'write_file'. "
                "3. Transition to REVIEWER state to verify the patch."
            ),
            AgentState.REVIEWER: (
                "You are a Security Reviewer. Your goal is to verify the fix and ensure no regressions. "
                "1. Run the original PoC to ensure it no longer succeeds (vulnerability is patched). "
                "2. Run functional and regression tests to ensure existing features still work. "
                "3. EVALUATE RESULTS: "
                "   - IF ALL TESTS PASS: Transition to 'DONE'. "
                "   - IF ANY TEST FAILS: You MUST analyze the failure and transition back to 'FIXER' to correct the patch. "
                "4. CRITICAL: NEVER transition to 'DONE' if there are active test failures. Your reputation depends on the accuracy of your verification."
            ),
        }
        self._register_core_tools()
        self._register_skill_tools()
        self._load_hooks()

    def _load_hooks(self):
        """Automatically load all Python hook files from the hooks/ directory."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        hooks_dir = os.path.join(project_root, "hooks")
        if not os.path.exists(hooks_dir):
            return

        for hook_file in glob.glob(os.path.join(hooks_dir, "*.py")):
            if os.path.basename(hook_file) == "__init__.py":
                continue
            
            module_name = f"hooks.{os.path.basename(hook_file)[:-3]}"
            try:
                # Use importlib to load the file
                spec = importlib.util.spec_from_file_location(module_name, hook_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self._log_debug(f"[Hook] Loaded module: {module_name}")
            except Exception as e:
                self._log_debug(f"[Hook] Failed to load {hook_file}: {e}")

    def _log_debug(self, message: str, to_console: bool = True):
        """写入日志。根据配置决定是否输出到控制台和文件。"""
        if to_console:
            print(message)
        
        if settings.logging.file_logging_enabled:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")

    def _register_core_tools(self):
        # Standard transition tool
        transition_tool = {
            "type": "function",
            "function": {
                "name": "transition_state",
                "description": "Transition the agent to a new state in the FSM.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "next_state": {
                            "type": "string",
                            "enum": ["INITIAL_ANALYSIS", "VALIDATOR", "FIXER", "REVIEWER", "DONE"]
                        },
                        "summary": {"type": "string", "description": "Summary of findings to be placed on the blackboard."}
                    },
                    "required": ["next_state", "summary"]
                }
            }
        }

        # Skill loading tool
        load_skill_tool = {
            "type": "function",
            "function": {
                "name": "load_skill",
                "description": "Load the full content of a specialized skill.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {"type": "string", "description": "Name of the skill to load."}
                    },
                    "required": ["skill_name"]
                }
            }
        }

        # Sandbox tool
        sandbox_tool = {
            "type": "function",
            "function": {
                "name": "execute_in_sandbox",
                "description": "Execute a shell command in a secure, isolated Docker sandbox.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The shell command to execute."},
                        "timeout": {"type": "integer", "description": "Timeout in seconds.", "default": 60}
                    },
                    "required": ["command"]
                }
            }
        }

        for state in [AgentState.INITIAL_ANALYSIS, AgentState.VALIDATOR, AgentState.FIXER, AgentState.REVIEWER]:
            self.register_tool(state, transition_tool, self.transition_handler)
            self.register_tool(state, load_skill_tool, self.load_skill_handler)

        self.register_tool(AgentState.VALIDATOR, sandbox_tool, self.sandbox_handler)
        self.register_tool(AgentState.REVIEWER, sandbox_tool, self.sandbox_handler)

    def _register_skill_tools(self):
        # Dynamically register tools and handlers discovered from SkillRegistry
        for skill_name, skill_data in self.skill_registry.skills.items():
            handler_module = skill_data.get("handler_module")
            
            for tool_def in skill_data.get("tools", []):
                name = tool_def.get("name") or tool_def.get("function", {}).get("name")
                
                # Convert to standard OpenAI function format if needed
                if "type" not in tool_def:
                    formatted_tool = {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": tool_def.get("description", ""),
                            "parameters": tool_def.get("parameters", {
                                "type": "object",
                                "properties": {},
                                "required": []
                            })
                        }
                    }
                else:
                    formatted_tool = tool_def

                handler = None
                if handler_module:
                    handler = getattr(handler_module, f"{name}_handler", None) or getattr(handler_module, name, None)

                if handler:
                    target_states = [s for s in AgentState if s not in (AgentState.DONE, AgentState.ERROR)]
                    if "states" in tool_def:
                        target_states = [AgentState[s.upper()] for s in tool_def["states"] if hasattr(AgentState, s.upper())]
                        
                    for s in target_states:
                        self.register_tool(s, formatted_tool, handler)

    def _safe_path(self, path: str) -> str:
        # Simple path validation to stay within workspace
        abs_path = os.path.abspath(os.path.join(self.workspace_path, path))
        if not abs_path.startswith(self.workspace_path):
            raise ValueError(f"Access denied: Path {path} is outside the workspace.")
        return abs_path

    def register_tool(self, state: AgentState, definition: Dict[str, Any], handler: callable):
        self.tools[state].append(definition)
        name = definition["function"]["name"]
        self.tool_handlers[name] = handler

    def transition_handler(self, state: LoopState, next_state: str, summary: str):
        try:
            target_state = AgentState[next_state.upper()]
            
            # --- 原硬编码校验已迁移至 hooks/builtin_logic.py ---

            old_state_name = state.current_state.name
            msg = f"\n[FSM] Transitioning from {old_state_name} to {target_state.name}"
            self._log_debug(msg)
            state.current_state = target_state
            state.state_turn_count = 0
            state.blackboard[f"{old_state_name}_summary"] = summary
            state.state_path.append(target_state.name)
            
            # Context Compaction: clear chat history to prevent context window bloat
            if len(state.messages) > 1:
                # Keep the initial user task prompt and the latest assistant message (which contains the tool_calls)
                # to prevent "tool_call_id not found" API errors.
                state.messages = [state.messages[0], state.messages[-1]]

            return f"Successfully transitioned to {target_state.name}."
        except KeyError:
            return f"Error: Invalid state {next_state}."

    def load_skill_handler(self, state: LoopState, skill_name: str):
        content = self.skill_registry.get_skill_content(skill_name)
        if content:
            # Injecting into blackboard so it persists across turns in the prompt
            state.blackboard[f"loaded_skill_{skill_name}"] = content
            return f"Skill '{skill_name}' loaded successfully and added to context."
        return f"Error: Skill '{skill_name}' not found."

    def sandbox_handler(self, state: LoopState, command: str, timeout: int = 60):
        self._log_debug(f"[{state.current_state.name}] Sandbox Exec: {command}")
        result = self.sandbox.execute(command, timeout=timeout)
        
        # 实时打印输出到控制台，让用户可见
        output_block = "\n--- Sandbox Output ---\n"
        output_block += result.get("output", "")
        output_block += "\n----------------------\n"
        self._log_debug(output_block)

        # Track test status on blackboard
        if state.current_state in (AgentState.VALIDATOR, AgentState.REVIEWER):
            state.blackboard["last_test_status"] = result.get("status")
            state.blackboard["last_test_exit_code"] = result.get("exit_code")
            
        # --- 原硬编码诊断建议已迁移至 hooks/builtin_logic.py ---

        return json.dumps(result, indent=2)

    def get_system_prompt(self, state: LoopState) -> str:
        prompt = self.system_prompts.get(state.current_state, "You are a security agent.")
        prompt += f"\n\n{self.skill_registry.get_skill_catalog()}"
        
        if state.blackboard:
            # Plan rendering
            plan = state.blackboard.get("plan", [])
            if plan:
                from core.utils import render_plan
                prompt += f"\n\n### Current Execution Plan\n{render_plan(plan)}"
                
            # Filter blackboard for prompt (can be very large)
            filtered_bb = {k: v for k, v in state.blackboard.items() if k != "plan"}
            if filtered_bb:
                prompt += f"\n\n### Blackboard (State Context)\n{json.dumps(filtered_bb, indent=2)}"
        return prompt

    def call_llm_with_retry(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], max_retries: int = 3):
        for i in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools if tools else None,
                    tool_choice="auto" if tools else None
                )
                return response
            except Exception as e:
                # Handle Rate Limit (429) or other API errors
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    wait_time = (i + 1) * 5
                    self._log_debug(f"Rate limited. Waiting {wait_time}s before retry {i+1}/{max_retries}...")
                    time.sleep(wait_time)
                elif i == max_retries - 1:
                    raise e
                else:
                    self._log_debug(f"API Error: {e}. Retrying {i+1}/{max_retries}...")
                    time.sleep(2)
        return None

    def compact_blackboard(self, state: LoopState, threshold: int = 4000):
        """Automatically summarize or archive old blackboard entries when context length exceeds a threshold."""
        bb_str = json.dumps(state.blackboard)
        if len(bb_str) > threshold:
            self._log_debug(f"[FSM] Blackboard size ({len(bb_str)}) exceeds threshold, compacting...")
            
            # 1. Archive old summaries
            archived = False
            for key in list(state.blackboard.keys()):
                if key.endswith("_summary") and not key.startswith(state.current_state.name):
                    del state.blackboard[key]
                    archived = True
            
            if archived:
                state.blackboard["archived_summaries"] = "Older state summaries have been archived to save context."

            # 2. Truncate loaded skills if still too large
            if len(json.dumps(state.blackboard)) > threshold:
                for key in list(state.blackboard.keys()):
                    if key.startswith("loaded_skill_"):
                        state.blackboard[key] = "<Content compacted. Please reload skill if necessary.>"

    def truncate_content(self, content: str, max_chars: int = 5000) -> str:
        """Truncate content if it exceeds max_chars, keeping head and tail."""
        if len(content) <= max_chars:
            return content
        
        head = content[:1000]
        tail = content[-3500:]
        return f"{head}\n\n[... Truncated {len(content) - 4500} chars for context efficiency ...]\n\n{tail}"

    def run_one_turn(self, state: LoopState) -> bool:
        if state.turn_count >= state.total_max_turns or state.state_turn_count >= state.max_turns_per_state:
            self._log_debug("Max turns reached or Circuit breaker triggered.")
            state.current_state = AgentState.ERROR
            return False

        self.compact_blackboard(state)

        state.rounds_since_todo_update += 1
        system_content = self.get_system_prompt(state)
        messages = [{"role": "system", "content": system_content}] + state.messages

        # 打印调试 Prompt
        debug_prompt = f"\n{'='*20} [TURN {state.turn_count+1}] PROMPT START {'='*20}\n"
        debug_prompt += f"[SYSTEM PROMPT]:\n{system_content}\n"
        debug_prompt += f"[LATEST USER/TOOL MESSAGE]:\n{json.dumps(state.messages[-1] if state.messages else 'N/A', indent=2)}\n"
        debug_prompt += f"{'='*25} PROMPT END {'='*25}\n"
        self._log_debug(debug_prompt, to_console=settings.logging.console_prompt_enabled)

        # Add reminder if needed
        if state.rounds_since_todo_update >= 5:
            messages.append({
                "role": "system", 
                "content": "<reminder>Refresh your plan before continuing. It has been several rounds since you last updated it.</reminder>"
            })

        current_tools = self.tools.get(state.current_state, [])

        response = self.call_llm_with_retry(
            messages=messages,
            tools=current_tools
        )

        if not response:
            return False

        message = response.choices[0].message
        
        if message.content:
            self._log_debug(f"\n🤖 [Agent]: {message.content}\n")
            
        state.messages.append(message.model_dump(exclude_none=True))
        state.turn_count += 1
        state.state_turn_count += 1

        if not message.tool_calls:
            return False

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            handler = self.tool_handlers.get(name)
            
            if handler:
                self._log_debug(f"[{state.current_state.name}] Tool Call: {name} with args {args}")
                tool_start = time.time()

                # --- [Hook] PreToolUse ---
                pre_result = registry.dispatch(HookEvent.PRE_TOOL_USE, state, tool_name=name, args=args)
                if not pre_result.continue_execution:
                    err_msg = pre_result.block_reason or "Blocked by hook."
                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": err_msg
                    })
                    self._log_debug(f"[{state.current_state.name}] Tool Blocked by Hook:\n{err_msg}\n")
                    continue
                
                if pre_result.modified_args:
                    args = pre_result.modified_args

                try:
                    import inspect
                    sig = inspect.signature(handler)
                    kwargs = args.copy()
                    if 'agent' in sig.parameters:
                        kwargs['agent'] = self
                    if 'state' in sig.parameters:
                        kwargs['state'] = state
                    
                    result = handler(**kwargs)
                    
                    # --- [Hook] PostToolUse ---
                    post_result = registry.dispatch(HookEvent.POST_TOOL_USE, state, tool_name=name, args=args, result=result)
                    if post_result.injected_output:
                        if isinstance(result, str):
                            result += post_result.injected_output
                        # 处理可能是 JSON 的字符串
                        elif isinstance(result, str) and (result.startswith("{") or result.startswith("[")):
                            try:
                                data = json.loads(result)
                                if isinstance(data, dict) and "output" in data:
                                    data["output"] += post_result.injected_output
                                    result = json.dumps(data, indent=2)
                            except:
                                result += post_result.injected_output
                    
                    # Truncate large tool output to save context
                    final_content = self.truncate_content(str(result))
                    
                    tool_response = {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": final_content
                    }
                    state.messages.append(tool_response)
                    # 记录工具返回内容
                    if name == "execute_in_sandbox":
                        self._log_debug(f"[{state.current_state.name}] Tool Output ({name}):\n{result}\n")
                    else:
                        res_str = str(result)
                        summary = f"{res_str[:200]}... (Total {len(res_str)} chars)" if len(res_str) > 200 else res_str
                        self._log_debug(f"[{state.current_state.name}] Tool Output Summary ({name}):\n{summary}\n")
                    state.turn_log.append({
                        "turn": state.turn_count,
                        "state": state.current_state.name,
                        "tool": name,
                        "success": True,
                        "duration_ms": round((time.time() - tool_start) * 1000, 1)
                    })
                except Exception as e:
                    err_msg = f"Error executing tool: {str(e)}"
                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": err_msg
                    })
                    self._log_debug(f"[{state.current_state.name}] Tool Execution ERROR:\n{err_msg}\n")
                    state.turn_log.append({
                        "turn": state.turn_count,
                        "state": state.current_state.name,
                        "tool": name,
                        "success": False,
                        "duration_ms": round((time.time() - tool_start) * 1000, 1),
                        "error": str(e)
                    })
            else:
                err_msg = f"Error: Tool {name} not found."
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": err_msg
                })
                self._log_debug(err_msg)
                state.turn_log.append({
                    "turn": state.turn_count,
                    "state": state.current_state.name,
                    "tool": name,
                    "success": False,
                    "duration_ms": 0,
                    "error": f"Tool {name} not found"
                })
        
        return True

    def run(self, initial_query: str):
        state = LoopState(messages=[{"role": "user", "content": initial_query}])
        self._log_debug(f"Starting Agent in state: {state.current_state.name}")
        
        # --- [Hook] SessionStart ---
        registry.dispatch(HookEvent.SESSION_START, state)
        
        while state.current_state not in (AgentState.DONE, AgentState.ERROR):
            active = self.run_one_turn(state)
            
            # If no tools were called and we're not in a terminal state, 
            # give the agent a nudge to continue its work.
            if not active and state.current_state not in (AgentState.DONE, AgentState.ERROR):
                nudger = {
                    "role": "system",
                    "content": "You have not called any tools. Please proceed with your task using the available tools, or transition to the DONE state if you have finished."
                }
                state.messages.append(nudger)
                self._log_debug("[System] Injected nudge to Agent.")
                # Continue the loop to give the agent another chance
                continue
                
            if state.current_state in (AgentState.DONE, AgentState.ERROR):
                break
                
        # --- [Hook] SessionEnd ---
        registry.dispatch(HookEvent.SESSION_END, state)

        self._log_debug(f"Finished. Final State: {state.current_state.name}")
        self._log_debug(f"Full log archived at: {self.log_file}")
        return state
