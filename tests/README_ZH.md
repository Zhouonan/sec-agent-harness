# Sec-Agent-Harness 测试套件

本目录包含用于验证 FSM 逻辑、沙箱安全性和技能系统的自动化测试和集成 Demo。

## 1. 测试分类

### 1.1 单元与对抗性测试
- **`test_fsm_loop.py`**: 验证核心 FSM 转换、轮数限制和 Blackboard 上下文传递。
- **`test_fsm_mock.py`**: 用于快速验证 FSM 逻辑的轻量级 Mock 测试。
- **`test_adversarial_fsm.py`**: 安全侧重测试，尝试通过恶意工具输出或循环转换破坏 FSM。
- **`test_extensions.py`**: 验证新引入的 AST 扫描器和动态技能注册表工具注入。
- **`test_hook_system.py`**: 验证 Hook 系统的注册、自动加载、PRE/POST 工具事件触发及异常隔离机制。

### 1.2 集成演示 (真实 API)
- **`run_fsm_demo.py`**: 一个完整的端到端集成测试，使用真实 LLM API 执行完整的生命周期（分析 -> 验证 -> 完成）。**需要 API 配置。**

## 2. 运行测试

### 2.1 标准单元测试 (不需要 API Key)
使用 `pytest` 运行所有安全测试：
```bash
export PYTHONPATH=$PYTHONPATH:.
python3 -m pytest tests/test_*.py
```

### 2.2 集成演示 (需要 LLM API)
确保你的 `.env` 文件包含以下配置：
```bash
LLM_MODEL=your-model
LLM_BASE_URL=https://api.your-provider.com/v1
LLM_API_KEY=your-api-key
```
然后运行：
```bash
python3 tests/run_fsm_demo.py
```

## 3. 运行要求
- **Docker**: `execute_in_sandbox` 测试需要 Docker。如果缺少 Docker，测试将执行优雅降级处理。
- **Python 包**: 确保已安装 `openai`、`pytest`、`docker` 和 `pyyaml`。
