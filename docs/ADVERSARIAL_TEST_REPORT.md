# Sec-Agent-Harness: Adversarial Test Report

## 1. Executive Summary
As an adversarial tester, I have executed a series of stress tests against the core FSM and blackboard components. While the circuit breaker mechanism is functional, several architectural fragilities were identified regarding configuration validation, error resilience, and state history.

## 2. Discovered Vulnerabilities & Fragilities

### A. Lack of Configuration Validation
- **Observation**: `core/config.py` loads values from `config.yaml` without sanitization.
- **Impact**: Setting `total_max_turns` to a negative value or zero causes the system to enter an `ERROR` state immediately without processing any input.
- **Adversarial Vector**: Malicious/accidental config modification can DOS the agent.

### B. Brittle Network Resilience
- **Observation**: `AgentLoop.run_one_turn` calls the OpenAI client without exception handling.
- **Impact**: Any network error (Rate Limit 429, Server Error 500, or Timeout) triggers a Python traceback and crashes the process.
- **Adversarial Vector**: Transient network issues are not handled gracefully; the agent cannot self-recover or report a "Network Error" state.

### C. Blackboard Context Loss (Summary Overwriting)
- **Observation**: `transition_handler` overwrites `state.blackboard[f"{old_state_name}_summary"]` on every transition from that state.
- **Impact**: In an oscillation loop (e.g., `FIXER -> VALIDATOR -> FIXER`), the agent loses the context of what it tried in the *previous* `FIXER` turn.
- **Adversarial Vector**: This can lead to the agent repeating the same failed logic because it only sees the most recent summary.

### D. Load-time Binding of Settings
- **Observation**: `LoopState` defaults are bound to `settings` at module load time.
- **Impact**: Difficulty in dynamically reconfiguring the loop limits without restarting the process or monkeypatching the dataclass defaults.

## 3. Verified Attack Vectors (Tests Created)
The following tests were implemented in `tests/test_adversarial_fsm.py`:
1.  `test_infinite_loop_trap`: Confirmed `total_max_turns` eventually stops oscillation.
2.  `test_invalid_transition`: Confirmed `transition_handler` correctly rejects unknown states.
3.  `test_blackboard_payload_injection`: Confirmed the system handles 10KB+ summaries and injection-style characters in summaries.
4.  `test_malicious_config`: Confirmed negative turn limits cause immediate termination.
5.  `test_network_failure_simulation`: Confirmed API exceptions crash the loop.

## 4. Recommendations
1.  **Sanitize Config**: Implement `__post_init__` or validation logic in `Config` to ensure `max_turns` > 0.
2.  **Resilient Loop**: Wrap `client.chat.completions.create` in a try-except block.
3.  **Blackboard History**: Change summary storage to a list (e.g., `state.blackboard[f"{old_state_name}_history"] = []`) to preserve attempt history.
4.  **Dynamic Limits**: Pass limits from `AgentLoop` to `LoopState` explicitly during initialization rather than relying on dataclass defaults.

---
"The system is only as strong as its weakest transition."
