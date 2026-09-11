"""不同起点、随机重启预算与跨种子稳定性比较。"""

import argparse
from collections import Counter
from pathlib import Path
from random import Random
from statistics import mean
import sys
from time import perf_counter

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.instances import restart_jobs
from evaluation.objective import objective
from scheduling.dispatching import dispatch, random_solution
from scheduling.schedule import build_schedule
from scheduling.validation import validate_schedule
from search.local_search import best_improvement_local_search, multi_start_local_search
from search.neighborhood import generate_swap_neighbors


def verify_result(jobs, sequence, score, stop_reason):
    schedule = build_schedule(sequence)
    validate_schedule(schedule, jobs)
    if objective(schedule) != score:
        raise RuntimeError("score does not match the returned schedule")
    if stop_reason == "no_improvement":
        if any(objective(build_schedule(n)) < score for n in generate_swap_neighbors(sequence)):
            raise RuntimeError("reported local optimum has an improving swap neighbor")


def run_experiment(data_seed=42, search_seed=42, counts=(1, 5, 10, 20, 50), seeds=range(5), max_iterations=1000):
    jobs = restart_jobs(data_seed)
    original = jobs.copy()

    def decode(sequence):
        schedule = build_schedule(sequence)
        validate_schedule(schedule, jobs)
        return schedule

    print(f"Data seed={data_seed}; search seed={search_seed}; n=20; objective=total_tardiness; Swap / Best")
    print("Jobs: " + ", ".join(f"{j.job_id}(p={j.processing_time:g},d={j.due_date})" for j in jobs))
    print("\nInitial rule    Initial Final Iterations Evaluations Runtime(s) Stop")
    for name in ("fcfs", "spt", "edd", "random"):
        initial = random_solution(jobs, Random(search_seed)) if name == "random" else dispatch(jobs, name)
        start = perf_counter()
        result = best_improvement_local_search(initial, decode, objective, max_iterations=max_iterations)
        runtime = perf_counter() - start
        verify_result(jobs, result["solution"], result["score"], result["stop_reason"])
        print(f"{name:14} {result['history'][0]:7g} {result['score']:5g} {result['iterations']:10} "
              f"{result['neighbor_evaluations']:11} {runtime:10.4f} {result['stop_reason']}")

    # 一次运行最大预算，比较其前缀；随机单次与多起点第一轮完全相同。
    multi = multi_start_local_search(jobs, decode, objective, num_restarts=max(counts),
                                    seed=search_seed, max_iterations=max_iterations)
    print("\nRestart history: initial / final / best-so-far / accepted moves / stop")
    best = float("inf")
    for row in multi["history"]:
        best = min(best, row["final_score"])
        if row["best_score"] != best or row["final_score"] > row["initial_score"]:
            raise RuntimeError("inconsistent restart history")
        verify_result(jobs, row["solution"], row["final_score"], row["stop_reason"])
        print(f"{row['restart']:3}: {row['initial_score']:5g} / {row['final_score']:5g} / "
              f"{best:5g} / {row['iterations']:3} / {row['stop_reason']}")
    if jobs != original or multi["score"] != best:
        raise RuntimeError("input changed or incorrect historical best")
    winning_row = multi["history"][multi["best_restart"] - 1]
    verify_result(jobs, multi["solution"], multi["score"], winning_row["stop_reason"])
    print(f"Best restart={multi['best_restart']}; best score={multi['score']}; "
          f"total runtime={multi['runtime']:.4f}s")
    print("Best sequence: " + " -> ".join(j.job_id for j in multi["solution"]))
    print("\nNested budgets: Starts Best Evaluations Elapsed(s)")
    for count in counts:
        prefix = multi["history"][:count]
        print(f"{count:6} {prefix[-1]['best_score']:4g} "
              f"{sum(r['neighbor_evaluations'] for r in prefix):11} {prefix[-1]['elapsed']:10.4f}")
    print("Final-score frequencies (equal scores may represent different schedules):",
          dict(sorted(Counter(r["final_score"] for r in multi["history"]).items())))

    print("\nStability on the SAME instance; independent search seeds")
    records = {count: [] for count in counts}
    for seed in seeds:
        result = multi if seed == search_seed else multi_start_local_search(
            jobs, decode, objective, num_restarts=max(counts), seed=seed, max_iterations=max_iterations)
        verify_result(jobs, result["solution"], result["score"],
                      result["history"][result["best_restart"] - 1]["stop_reason"])
        scores = [result["history"][count-1]["best_score"] for count in counts]
        print(f"seed={seed}: {dict(zip(counts, scores))}; "
              f"capped searches={sum(r['stop_reason']=='max_iterations' for r in result['history'])}")
        for count, value in zip(counts, scores):
            records[count].append(value)
    print("Starts  Best    Mean   Worst")
    for count, values in records.items():
        print(f"{count:6} {min(values):5g} {mean(values):7.2f} {max(values):7g}")
    return multi


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-seed", type=int, default=42)
    parser.add_argument("--search-seed", type=int, default=42)
    parser.add_argument("--restart-counts", type=int, nargs="+", default=[1, 5, 10, 20, 50])
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument("--max-iterations", type=int, default=1000)
    args = parser.parse_args()
    if min(args.restart_counts) < 1 or args.max_iterations < 0:
        parser.error("restart counts must be positive; max iterations must be non-negative")
    run_experiment(args.data_seed, args.search_seed, sorted(set(args.restart_counts)),
                   list(dict.fromkeys(args.seeds)), args.max_iterations)


if __name__ == "__main__":
    main()
