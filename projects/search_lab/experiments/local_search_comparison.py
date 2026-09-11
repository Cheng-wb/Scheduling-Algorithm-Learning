"""初始解、邻域与局部搜索策略比较。"""

import argparse
from pathlib import Path
import sys
from time import perf_counter

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.instances import homework_jobs, neighborhood_jobs
from evaluation.objective import objective
from scheduling.dispatching import dispatch
from scheduling.schedule import build_schedule
from scheduling.validation import validate_schedule
from search.local_search import best_improvement_local_search, first_improvement_local_search
from search.neighborhood import generate_swap_neighbors, generate_insert_neighbors

STRATEGIES = {"best": best_improvement_local_search, "first": first_improvement_local_search}
NEIGHBORHOODS = {"swap": generate_swap_neighbors, "insert": generate_insert_neighbors}


def sequence_text(sequence):
    return " -> ".join(job.job_id for job in sequence)


def run_search(jobs, initial, strategy, neighbors, max_iterations):
    """搜索外部计时；复核每步排程和最终邻域，复核不计入搜索耗时。"""
    original = initial.copy()

    def decode(sequence):
        schedule = build_schedule(sequence)
        validate_schedule(schedule, jobs)
        return schedule

    start = perf_counter()
    result = strategy(initial, decode, objective, neighbors, max_iterations=max_iterations)
    result["runtime"] = perf_counter() - start
    if initial != original:
        raise RuntimeError("search changed the initial solution")
    if len(result["history"]) != result["iterations"] + 1 or len(result["path"]) != len(result["history"]):
        raise RuntimeError("history and accepted iterations are inconsistent")
    if any(after >= before for before, after in zip(result["history"], result["history"][1:])):
        raise RuntimeError("accepted scores must strictly decrease")
    for sequence, value in zip(result["path"], result["history"]):
        if objective(decode(sequence)) != value:
            raise RuntimeError("recorded score does not match its schedule")
    if result["solution"] != result["path"][-1] or result["score"] != result["history"][-1]:
        raise RuntimeError("final result does not match the search path")
    # 即使因上限退出，也展示实际是否仍存在改进，但保留真实停止原因。
    result["better_neighbors"] = sum(
        objective(decode(neighbor)) < result["score"] for neighbor in neighbors(result["solution"])
    )
    if result["stop_reason"] == "no_improvement" and result["better_neighbors"]:
        raise RuntimeError("the reported local optimum still has improving neighbors")
    return result


def print_path(label, result):
    print(f"\n{label}")
    for iteration, (sequence, value) in enumerate(zip(result["path"], result["history"])):
        print(f"  {iteration}: {sequence_text(sequence)}; total_tardiness={value:g}")
    improvement = result["history"][0] - result["score"]
    rate = f"{improvement / result['history'][0]:.2%}" if result["history"][0] else "N/A (initial=0)"
    print(f"  Improvement={improvement:g} ({rate}); iterations={result['iterations']}; "
          f"neighbor evaluations={result['neighbor_evaluations']}")
    print(f"  Stop={result['stop_reason']}; improving neighbors remaining={result['better_neighbors']}; "
          f"search runtime={result['runtime']:.6f}s")


def compare_searches(jobs, max_iterations):
    print("\n=== Ten-job comparison: minimize total_tardiness ===")
    print("Jobs: " + ", ".join(f"{j.job_id}(p={j.processing_time:g},d={j.due_date})" for j in jobs))
    rows = []
    for rule in ("spt", "edd"):
        initial = dispatch(jobs, rule)
        initial_score = objective(build_schedule(initial))
        rows.append((rule, "-", "none", initial_score, initial_score, 0, 0, 0.0, "baseline"))
        for kind, neighbors in NEIGHBORHOODS.items():
            for name, strategy in STRATEGIES.items():
                result = run_search(jobs, initial, strategy, neighbors, max_iterations)
                print_path(f"{rule.upper()} / {kind} / {name}", result)
                other_kind = "insert" if kind == "swap" else "swap"
                other_best = None
                for neighbor in NEIGHBORHOODS[other_kind](result["solution"]):
                    schedule = build_schedule(neighbor)
                    validate_schedule(schedule, jobs)
                    value = objective(schedule)
                    other_best = value if other_best is None else min(other_best, value)
                print(f"  Best neighbor under {other_kind}: {other_best} (post-search comparison)")
                rows.append((rule, kind, name, initial_score, result["score"], result["iterations"],
                             result["neighbor_evaluations"], result["runtime"], result["stop_reason"]))
    print("\nInitial  Neighborhood Strategy Initial Final Improve Iterations Evaluations Runtime(s) Stop")
    for rule, kind, name, initial, final, iterations, evaluations, runtime, stop in rows:
        print(f"{rule:8} {kind:12} {name:8} {initial:7g} {final:5g} {initial-final:7g} "
              f"{iterations:10} {evaluations:11} {runtime:10.6f} {stop}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="seed for the ten-job instance")
    parser.add_argument("--max-iterations", type=int, default=1000, help="maximum accepted moves per search")
    args = parser.parse_args()
    if args.max_iterations < 0:
        parser.error("--max-iterations must be non-negative")
    jobs = neighborhood_jobs()
    result = run_search(jobs, dispatch(jobs, "spt"), best_improvement_local_search,
                        generate_swap_neighbors, args.max_iterations)
    print_path("Six-job worked example: SPT / swap / best", result)
    compare_searches(homework_jobs(args.seed), args.max_iterations)


if __name__ == "__main__":
    main()
