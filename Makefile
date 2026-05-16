.PHONY: test eval-mini eval-vulrepair-full eval-secbench check clean ls-datasets ls-cases

# ==========================================
# Sec-Agent-Harness 增量开发测评体系
# ==========================================

# 1. 单元与集成测试 (L1: Unit Tests) - 每次代码修改（如改 FSM、Hook、状态合并）后必跑，耗时数秒
test:
	@echo "==> Running L1 Unit Tests..."
	PYTHONPATH=. python3 -m pytest tests/test_*.py -v

# 2. 迷你测评 (L2: Mini Benchmark) - 每次功能重构后验证 LLM 决策流与沙箱交互，耗时约 2-3 分钟
eval-mini:
	@echo "==> Running L2 Mini Benchmark (case_02_CWE_125)..."
	PYTHONPATH=. python3 -m eval.cli run --dataset vulrepair --cases case_02_CWE_125

# 3. 全量与真实环境测评 (L3: Full Benchmark & SEC-bench) - 阶段性大改动或发版前验证整体成功率与真实环境应对能力
eval-vulrepair-full:
	@echo "==> Running L3 Full VulRepair Benchmark..."
	PYTHONPATH=. python3 -m eval.cli run --dataset vulrepair --parallel 2

eval-secbench:
	@echo "==> Running L3 SEC-bench Trial..."
	PYTHONPATH=. python3 -m eval.cli run --dataset secbench

# Dataset inspection
ls-datasets:
	PYTHONPATH=. python3 -m eval.cli list-datasets

ls-cases:
	PYTHONPATH=. python3 -m eval.cli list-cases vulrepair

# 一键日常检查：L1 (单元测试) + L2 (迷你测评)
check: test eval-mini
	@echo "✅ L1 & L2 Checks Passed! No regressions detected in core workflow. Safe to proceed."

# 清理测试产生的临时缓存与跑测记录
clean:
	rm -rf challenge/runs/*
	rm -rf eval_results/*
	rm -rf .pytest_cache
	find . -name "__pycache__" -type d -exec rm -rf {} +
