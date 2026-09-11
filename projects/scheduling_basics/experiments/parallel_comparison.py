"""Greedy、LPT 与并行机 MILP 的同实例比较。"""

import argparse
from math import isclose
from pathlib import Path
import random
import sys
from time import perf_counter

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling.models import Job
from scheduling.bounds import parallel_machine_lower_bound
from scheduling.benchmark import relative_gap
from scheduling.validation import validate_schedule
from scheduling.evaluator import evaluate
from scheduling.heuristics.parallel_machine import greedy_list_scheduling, lpt_list_scheduling


def run_case(title, jobs, num_machines, *, use_milp=True, show_assignments=True, time_limit_ms=5000):
    lower_bound = parallel_machine_lower_bound(jobs, num_machines)
    print(f"\n{title}: n={len(jobs)}, m={num_machines}, LB={lower_bound:g}")
    algorithms = [("Greedy", greedy_list_scheduling), ("LPT", lpt_list_scheduling)]
    if use_milp:
        from scheduling.exact.parallel_machine import solve_parallel_machine_milp
        algorithms.append(("MILP", solve_parallel_machine_milp))

    results = []
    optimum = None
    for name, solve in algorithms:
        start = perf_counter()
        try:
            kwargs = {"time_limit_ms": time_limit_ms} if name == "MILP" else {}
            schedule = solve(jobs, num_machines, **kwargs)
        except RuntimeError as error:
            if name != "MILP":
                raise
            print(f"MILP: {error}; elapsed={perf_counter() - start:.4f}s")
            continue
        runtime = perf_counter() - start
        validate_schedule(schedule, jobs)
        result = evaluate(schedule)
        loads = [0.0] * num_machines
        for item in schedule.assignments:
            loads[item.machine_id] += item.job.processing_time
        if not isclose(max(loads), result["makespan"], abs_tol=1e-7):
            raise RuntimeError("machine loads do not match makespan")
        results.append((name, schedule, result, loads, runtime))
        if name == "MILP":
            optimum = result["makespan"]

    if show_assignments:
        for name, schedule, _, loads, _ in results:
            print(name)
            for machine_id in range(num_machines):
                items = sorted((item for item in schedule.assignments if item.machine_id == machine_id),
                               key=lambda item: item.start_time)
                detail = ", ".join(f"{item.job.job_id}[{item.start_time:g},{item.completion_time:g}]" for item in items)
                print(f"  M{machine_id}: {detail or '(empty)'}; load={loads[machine_id]:g}")
    print("Algorithm  Cmax   Loads                       Utilization  Runtime(s)  Gap to optimum")
    for name, _, result, loads, runtime in results:
        gap = f"{relative_gap(result['makespan'], optimum):.2%}" if optimum is not None else "N/A"
        print(f"{name:9} {result['makespan']:5g} {str(loads):27} "
              f"{result['utilization']:11.2%} {runtime:11.6f}  {gap}")
    if optimum is None:
        print("No MILP optimum available: Gap=N/A; LB remains a lower bound.")


def make_jobs(times):
    return [Job(f"J{i}", p) for i, p in enumerate(times, start=1)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-milp", action="store_true", help="run heuristics without OR-Tools")
    parser.add_argument("--scale", action="store_true", help="also compare 10/3, 30/5 and 100/10 instances")
    parser.add_argument("--time-limit-ms", type=int, default=5000, help="MILP time limit per instance")
    args = parser.parse_args()
    if args.time_limit_ms <= 0:
        parser.error("--time-limit-ms must be positive")
    options = {"use_milp": not args.skip_milp, "time_limit_ms": args.time_limit_ms}
    base = make_jobs([3, 7, 2, 8, 4, 6])
    run_case("1. Base case", base, 2, **options)
    run_case("2. Same jobs, three machines", base, 3, **options)
    run_case("3. LPT is not always optimal", make_jobs([8, 7, 6, 5, 4]), 2, **options)
    run_case("4. Paper exercise", make_jobs([9, 8, 7, 6, 5, 4, 3, 2]), 3, **options)
    run_case("5. Same IDs, reversed input", list(reversed(base)), 2, **options)
    if args.scale:
        rng = random.Random(42)
        jobs = make_jobs([rng.randint(1, 20) for _ in range(100)])
        for size, machines in ((10, 3), (30, 5), (100, 10)):
            run_case("Scale", jobs[:size], machines, show_assignments=False, **options)


if __name__ == "__main__":
    main()
