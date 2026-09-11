"""dispatching rules and initial solutions."""

import argparse
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from math import isclose
from data.instances import example_jobs, homework_jobs
from evaluation.evaluate import evaluate
from models.job import Job
from scheduling.dispatching import RULES, dispatch
from scheduling.schedule import build_schedule
from scheduling.validation import validate_schedule


def compare_rules(title: str, jobs: list[Job]) -> dict[str, dict]:
    print(f"\n=== {title} ===")
    print("Job     p    r    d")
    for job in jobs:
        print(f"{job.job_id:5} {job.processing_time:4g} {job.release_time:4g} {str(job.due_date):>4}")
    results = {}
    for name in RULES:
        sequence = dispatch(jobs, name)
        schedule = build_schedule(sequence)
        validate_schedule(schedule, jobs)
        results[name] = evaluate(schedule)
        print(f"\n{name.upper()}: " + " -> ".join(job.job_id for job in sequence))
        print("  " + ", ".join(f"{item.job.job_id}[{item.start_time:g},{item.completion_time:g}]"
                                 for item in schedule.assignments))
    columns = ("makespan", "average_completion_time", "total_tardiness", "max_lateness")
    print("\nRule     Makespan  Avg Completion  Total Tardiness  Max Lateness")
    for name, metrics in results.items():
        print(f"{name.upper():6} {metrics['makespan']:10g} {metrics['average_completion_time']:15.2f} "
              f"{metrics['total_tardiness']:16g} {metrics['max_lateness']:13g}")
    winners = {}
    for metric in columns:
        best = min(values[metric] for values in results.values())
        winners[metric] = {name for name, values in results.items() if isclose(values[metric], best)}
        print(f"Best {metric}: " + ", ".join(name.upper() for name in RULES if name in winners[metric]))
    common = set.intersection(*winners.values())
    print("Best on all four metrics: " + (", ".join(name.upper() for name in RULES if name in common) or "None"))
    if all(job.release_time == 0 for job in jobs):
        print("All releases are zero and there is no idle time: Makespan = sum(p).")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="seed for the ten-job instance")
    args = parser.parse_args()
    compare_rules("Five-job example", example_jobs())
    compare_rules(f"Ten-job homework, seed={args.seed}", homework_jobs(args.seed))


if __name__ == "__main__":
    main()
