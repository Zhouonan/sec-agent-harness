"""
Evaluation CLI — command-line entry point for running benchmarks.

Usage:
    python -m eval.cli list-datasets
    python -m eval.cli list-cases vulrepair
    python -m eval.cli run --dataset vulrepair
    python -m eval.cli run --dataset vulrepair --cases case_02_CWE_125
    python -m eval.cli run --dataset vulrepair --parallel 2
"""

import argparse
import os
import sys

# Ensure project root is on path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from eval.datasets import VulRepairDataset, SecBenchDataset, CustomDataset
from eval.runner import EvalRunner
from eval.orchestrator import RunOrchestrator
from eval.reporter import Reporter


DATASET_REGISTRY = {
    "vulrepair": VulRepairDataset,
    "secbench": SecBenchDataset,
}


def cmd_list_datasets():
    print("Available datasets:")
    for name in DATASET_REGISTRY:
        ds = DATASET_REGISTRY[name]()
        count = len(ds.list_cases())
        print(f"  {name:20s}  ({count} cases)")


def cmd_list_cases(dataset_name: str):
    if dataset_name not in DATASET_REGISTRY:
        print(f"Unknown dataset: {dataset_name}")
        print(f"Available: {list(DATASET_REGISTRY.keys())}")
        return
    ds = DATASET_REGISTRY[dataset_name]()
    cases = ds.list_cases()
    print(f"Cases in {dataset_name} ({len(cases)}):")
    for c in cases:
        print(f"  {c}")


def cmd_run(dataset_name: str, cases: list = None, parallel: int = 1):
    if dataset_name in DATASET_REGISTRY:
        ds = DATASET_REGISTRY[dataset_name]()
    else:
        ds = CustomDataset(root_dir=dataset_name)

    all_cases = ds.list_cases()
    if not all_cases:
        print(f"No cases found in dataset: {dataset_name}")
        return

    if cases:
        target_cases = []
        for c in cases:
            if c in all_cases:
                target_cases.append(c)
            else:
                # Try fuzzy match
                matches = [x for x in all_cases if c in x]
                target_cases.extend(matches)
        target_cases = sorted(set(target_cases))
    else:
        target_cases = all_cases

    if not target_cases:
        print(f"No matching cases found for: {cases}")
        return

    print(f"Selected {len(target_cases)} case(s): {target_cases}")

    runner = EvalRunner()
    orchestrator = RunOrchestrator(parallel=parallel)
    results = orchestrator.run(ds, target_cases, runner=runner)

    reporter = Reporter()
    reporter.generate(results)


def main():
    parser = argparse.ArgumentParser(
        description="Sec-Agent-Harness Evaluation Runner",
        prog="python -m eval.cli",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list-datasets", help="List available datasets")

    list_cases = sub.add_parser("list-cases", help="List cases in a dataset")
    list_cases.add_argument("dataset", help="Dataset name (vulrepair, secbench, or path)")

    run_cmd = sub.add_parser("run", help="Run evaluation")
    run_cmd.add_argument("--dataset", required=True, help="Dataset name or path")
    run_cmd.add_argument("--cases", nargs="*", default=None, help="Specific cases to run")
    run_cmd.add_argument("--parallel", type=int, default=1, help="Number of parallel workers")

    args = parser.parse_args()

    if args.command == "list-datasets":
        cmd_list_datasets()
    elif args.command == "list-cases":
        cmd_list_cases(args.dataset)
    elif args.command == "run":
        cmd_run(args.dataset, args.cases, args.parallel)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
