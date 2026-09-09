"""Day 3：比较目标函数、Big-M 取值与释放时间的影响。"""

from pathlib import Path
import sys
from time import perf_counter

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling.models import Job
from scheduling.exact.single_machine import (
    solve_single_machine_makespan, solve_single_machine_total_completion,
)
from scheduling.evaluator import evaluate

def generate_jobs(processing_times, release_times=None):
    if release_times is None:
        release_times = [0] * len(processing_times)
    return [Job(f"J{i}", p, r) for i, (p, r) in enumerate(zip(processing_times, release_times), start=1)]

def run_case(title, jobs, solve=solve_single_machine_makespan, big_m=None, show_schedule=True):
    horizon = max((job.release_time for job in jobs), default=0) + sum(
        job.processing_time for job in jobs
    )
    print(f"{title}: solver={solve.__name__}, H={horizon:g}, M={big_m if big_m is not None else horizon:g}")
    start = perf_counter()
    try:
        schedule = solve(jobs, big_m=big_m)
    except RuntimeError as error:
        print(f"{error} Runtime={perf_counter() - start:.4f}s\n")
        return
    runtime = perf_counter() - start
    result = evaluate(schedule)
    if show_schedule:
        print(" -> ".join(item.job.job_id for item in schedule.assignments))
        for item in schedule.assignments:
            print(f"{item.job.job_id}: [{item.start_time:.6g}, {item.completion_time:.6g}]")
    print(f"Status=OPTIMAL (supplied model), Cmax={result['makespan']:.6g}, "
          f"SumC={result['total_completion_time']:.6g}, "
          f"Idle={result['idle_time']:.6g}, Runtime={runtime:.4f}s\n")


def main():
    jobs = generate_jobs([3, 6, 2, 7, 4])
    run_case("1. Makespan", jobs)
    run_case("2. Total completion", jobs, solve_single_machine_total_completion)
    for big_m in (5, 22, 100, 10000):
        run_case("3. M sensitivity", jobs, solve_single_machine_total_completion, big_m, False)
    run_case("4. Two jobs", generate_jobs([3, 5]))
    run_case("5. Release time", generate_jobs([3, 2], [0, 10]))
    # 有释放时间时，最小化总完工时间可能需要主动等待短任务。
    run_case("6. Intentional idle", generate_jobs([10, 1], [0, 1]), solve_single_machine_total_completion)



if __name__ == "__main__":
    main()
