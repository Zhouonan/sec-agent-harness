import pytest

from eval.reporter import _compute_summary
from eval.schema import EvalCaseResult


def _result(case_name, dataset, final_state, correctness, duration=100.0, turns=10):
    return EvalCaseResult(
        case_name=case_name,
        dataset=dataset,
        run_id="test_run",
        timestamp="2026-05-16T00:00:00",
        model="test-model",
        final_state=final_state,
        duration_seconds=duration,
        total_turns=turns,
        correctness_score=correctness,
        process_score=0.5,
        efficiency_score=0.7,
        composite_score=0.6,
    )


def test_compute_summary_reports_success_rate_by_dataset():
    results = [
        _result("vuln_case_1", "VulRepairDataset", "DONE", 0.9, duration=120, turns=8),
        _result("vuln_case_2", "VulRepairDataset", "DONE", 0.7, duration=180, turns=12),
        _result("sec_case_1", "SecBenchDataset", "ERROR", 0.0, duration=900, turns=30),
    ]

    summary = _compute_summary(results)

    assert summary["success_count"] == 1
    assert summary["success_rate"] == pytest.approx(1 / 3, abs=0.0001)
    assert summary["by_dataset"]["VulRepairDataset"]["total"] == 2
    assert summary["by_dataset"]["VulRepairDataset"]["success_count"] == 1
    assert summary["by_dataset"]["VulRepairDataset"]["success_rate"] == 0.5
    assert summary["by_dataset"]["SecBenchDataset"]["total"] == 1
    assert summary["by_dataset"]["SecBenchDataset"]["success_count"] == 0
    assert summary["by_dataset"]["SecBenchDataset"]["success_rate"] == 0.0
