"""Day 4：同一批任务的 Makespan、总延期与加权延期对比。"""

from pathlib import Path
import sys
from time import perf_counter

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling.models import Job
from scheduling.evaluator import evaluate
from scheduling.exact.single_machine import (
    solve_single_machine_makespan,
    solve_single_machine_total_tardiness,
    solve_single_machine_weighted_tardiness,
)


def main():
    jobs = [
        Job("J1", 4, due_date=6, weight=1),
        Job("J2", 2, due_date=8, weight=5),
        Job("J3", 5, due_date=10, weight=2),
        Job("J4", 1, due_date=5, weight=8),
        Job("J5", 3, due_date=12, weight=1),
    ]
    results = []
    for label, solve in (
        ("Makespan", solve_single_machine_makespan),
        ("Total tardiness", solve_single_machine_total_tardiness),
        ("Weighted tardiness", solve_single_machine_weighted_tardiness),
    ):
        start = perf_counter()
        schedule = solve(jobs)
        runtime = perf_counter() - start
        result = evaluate(schedule)

        results.append((label, result, runtime))
        print(f"\n{label} (OPTIMAL)")
        print(" -> ".join(item.job.job_id for item in schedule.assignments))
        print("Job  Start  End  Due  Lateness  Tardiness  Weight  wT")
        for item in schedule.assignments:
            print(f"{item.job.job_id:3} {item.start_time:6g} {item.completion_time:4g} "
                  f"{item.job.due_date:4g} {item.lateness:9g} {item.tardiness:10g} "
                  f"{item.job.weight:7g} {item.job.weight * item.tardiness:3g}")
    print("\nGoal                  Cmax  SumT  Sum(wT)  MaxT  TardyJobs  Runtime(s)")
    for label, result, runtime in results:
        print(f"{label:21} {result['makespan']:4g} {result['total_tardiness']:5g} "
              f"{result['weighted_tardiness']:8g} {result['max_tardiness']:5g} "
              f"{result['num_tardy_jobs']:10d} {runtime:11.4f}")


if __name__ == "__main__":
    main()
