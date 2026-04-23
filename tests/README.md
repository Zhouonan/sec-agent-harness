# Sec-Agent-Harness Testing Suite

This directory contains automated tests and integration demos to verify the FSM logic, sandbox security, and skill system.

## 1. Test Categories

### 1.1 Unit & Adversarial Tests
- **`test_fsm_loop.py`**: Verifies core FSM transitions, turn limits, and blackboard context passing.
- **`test_fsm_mock.py`**: Lightweight mock tests for rapid FSM logic verification.
- **`test_adversarial_fsm.py`**: Security-focused tests that attempt to break the FSM using malicious tool outputs or circular transitions.
- **`test_extensions.py`**: Verifies the new AST Scanner and dynamic Skill Registry tool injection.

### 1.2 Integration Demos (Real API)
- **`run_fsm_demo.py`**: A complete end-to-end integration test that uses a real LLM API to perform a full lifecycle (Analysis -> Validation -> Done). **Requires API configuration.**

## 2. Running Tests

### 2.1 Standard Unit Tests (No API Key Required)
Run all safe tests using `pytest`:
```bash
export PYTHONPATH=$PYTHONPATH:.
python3 -m pytest tests/test_*.py
```

### 2.2 Integration Demo (Requires LLM API)
Ensure your `.env` file contains the following:
```bash
LLM_MODEL=your-model
LLM_BASE_URL=https://api.your-provider.com/v1
LLM_API_KEY=your-api-key
```
Then run:
```bash
python3 tests/run_fsm_demo.py
```

## 3. Requirements
- **Docker**: Required for `execute_in_sandbox` tests. If Docker is missing, tests will perform a graceful fallback.
- **Python Packages**: Ensure `openai`, `pytest`, `docker`, and `pyyaml` are installed.
