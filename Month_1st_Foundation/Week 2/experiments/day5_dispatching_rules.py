"""Day 5: compare dispatching rules, release-aware scheduling and MILP."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from time import perf_counter

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling.evaluator import evaluate
from scheduling.benchmark import relative_gap
from scheduling.validation import validate_schedule
from scheduling.heuristics import edd, fcfs, lpt, spt, wspt
from scheduling.models import Job, Schedule

RULES = {"FCFS": fcfs, "SPT": spt, "LPT": lpt, "EDD": edd, "WSPT": wspt}


@dataclass
class ExperimentResult:
    schedule: Schedule
    metrics: dict[str, float | int]
    runtime: float


def run_algorithm(jobs, solve, **kwargs) -> ExperimentResult:
    start = perf_counter()
    schedule = solve(jobs, **kwargs)
    runtime = perf_counter() - start
    validate_schedule(schedule, jobs)
    return ExperimentResult(schedule, evaluate(schedule), runtime)


def print_result(name: str, result: ExperimentResult) -> None:
    sequence = " -> ".join(item.job.job_id for item in result.schedule.assignments)
    values = result.metrics
    print(f"{name:6} {sequence:28} "
          f"Cmax={values['makespan']:g} SumC={values['total_completion_time']:g} "
          f"SumwC={values['weighted_completion_time']:g} "
          f"SumT={values['total_tardiness']:g} SumwT={values['weighted_tardiness']:g} "
          f"Tardy={values['num_tardy_jobs']} Idle={values['idle_time']:g} "
          f"Runtime={result.runtime:.6f}s")


def run_rules(title: str, jobs: list[Job], *, dynamic: bool) -> dict[str, ExperimentResult]:
    print(f"\n{title} ({'dynamic' if dynamic else 'static'})")
    results = {}
    for name, rule in RULES.items():
        results[name] = run_algorithm(jobs, rule, dynamic=dynamic)
        print_result(name, results[name])
    return results


def compare_with_milp(title: str, jobs: list[Job], heuristic: ExperimentResult) -> None:
    # Only the benchmark needs OR-Tools; rule-only experiments use the standard library.
    from scheduling.exact.single_machine import solve_single_machine_total_completion

    optimal = run_algorithm(jobs, solve_single_machine_total_completion)
    gap = relative_gap(heuristic.metrics["total_completion_time"],
                       optimal.metrics["total_completion_time"])
    print(f"\n{title}: min total completion time")
    print_result("SPT", heuristic)
    print_result("MILP", optimal)
    print(f"MILP status=OPTIMAL, relative gap={gap:.2%}")


def simultaneous_jobs() -> list[Job]:
    return [
        Job("J1", 3, due_date=10, weight=2),
        Job("J2", 6, due_date=15, weight=1),
        Job("J3", 2, due_date=6, weight=5),
        Job("J4", 7, due_date=20, weight=3),
        Job("J5", 4, due_date=9, weight=4),
    ]


def staggered_jobs() -> list[Job]:
    return [
        Job("J1", 3, release_time=0, due_date=10, weight=2),
        Job("J2", 1, release_time=10, due_date=11, weight=1),
        Job("J3", 2, release_time=0, due_date=6, weight=5),
        Job("J4", 4, release_time=4, due_date=12, weight=4),
        Job("J5", 3, release_time=1, due_date=9, weight=2),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-milp", action="store_true", help="run without OR-Tools")
    args = parser.parse_args()

    jobs = simultaneous_jobs()
    baseline = run_rules("1. All jobs released at zero", jobs, dynamic=False)
    released_jobs = staggered_jobs()
    run_rules("2. Fixed order with release times", released_jobs, dynamic=False)
    run_rules("3. Choose among released jobs", released_jobs, dynamic=True)

    if not args.skip_milp:
        compare_with_milp("4. SPT matches MILP for simultaneous releases", jobs, baseline["SPT"])
        idle_jobs = [Job("Long", 10), Job("Short", 1, release_time=1)]
        dynamic_spt = run_algorithm(idle_jobs, spt, dynamic=True)
        compare_with_milp("5. Dynamic SPT can lose to deliberate waiting", idle_jobs, dynamic_spt)


if __name__ == "__main__":
    main()
