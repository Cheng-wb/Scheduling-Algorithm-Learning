"""Day 2：并行机 MILP 的三个基础题目与可选规模实验。"""

import argparse
from math import ceil
from pathlib import Path
import random
import sys
from time import perf_counter

# 支持 IDE 直接运行，也支持在 Week 2 下使用 python -m。
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling.models import Job
from scheduling.exact.parallel_machine import solve_parallel_machine_milp
from scheduling.evaluator import evaluate


def run_case(processing_times, num_machines, *, show_schedule=True):
    jobs = [Job(f"J{i}", p) for i, p in enumerate(processing_times, start=1)]

    lower_bound = max(sum(processing_times) / num_machines, max(processing_times, default=0))

    if all(float(p).is_integer() for p in processing_times):
        lower_bound = ceil(lower_bound)

    start = perf_counter()
    schedule = solve_parallel_machine_milp(jobs, num_machines)
    runtime = perf_counter() - start
    result = evaluate(schedule)
    print(f"Jobs={len(jobs)}, Machines={num_machines}, Status=OPTIMAL")

    if show_schedule:
        for machine_id in range(num_machines):
            items = [item for item in schedule.assignments if item.machine_id == machine_id]
            print(f"M{machine_id}: " + ", ".join(
                f"{item.job.job_id} [{item.start_time}, {item.completion_time}]" for item in items
            ))
        print(result)

    print(f"LB={lower_bound:g}, Cmax={result['makespan']:g}, "
          f"Variables={len(jobs) * num_machines + 1}, "
          f"Constraints={len(jobs) + num_machines}, Runtime={runtime:.4f}s")
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", action="store_true", help="also run 10/20/50/100-job cases")
    args = parser.parse_args()
    run_case([3, 7, 2, 8, 4, 6], 2)
    run_case([3, 7, 2, 8, 4, 6], 3)
    run_case([6, 6, 6, 6, 6], 2)
    if args.scale:
        rng = random.Random(42)
        times = [rng.randint(1, 20) for _ in range(100)]
        for size in (10, 20, 50, 100):
            run_case(times[:size], 3, show_schedule=False)


if __name__ == "__main__":
    main()
