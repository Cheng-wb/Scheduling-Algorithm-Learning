"""moves and one-layer neighborhood comparison."""

import argparse
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from random import Random
from data.instances import neighborhood_jobs
from evaluation.objective import objective
from models.job import Job
from scheduling.dispatching import dispatch
from scheduling.schedule import build_schedule
from scheduling.validation import validate_schedule
from search.neighborhood import generate_neighbors, swap, insert, reverse, random_swap_neighbor


def compare_neighborhood(jobs: list[Job], *, kind: str = "swap", seed: int = 42):
    """只检查同一个 SPT 初始解的邻域，不接受邻居或继续迭代。"""
    current = dispatch(jobs, "spt")

    def score(sequence):
        schedule = build_schedule(sequence)
        validate_schedule(schedule, jobs)
        return objective(schedule)

    def show(label, sequence, value):
        print(f"{label}: " + " -> ".join(job.job_id for job in sequence) + f"; total_tardiness={value:g}")

    current_score = score(current)
    print(f"\n=== One-layer {kind} neighborhood; minimize total_tardiness ===")
    print("Jobs: " + ", ".join(f"{job.job_id}(p={job.processing_time:g},d={job.due_date})" for job in jobs))
    show("Initial SPT", current, current_score)
    if len(current) >= 4:
        for label, candidate in (("swap(1,3)", swap(current, 1, 3)),
                                 ("insert(3,1)", insert(current, 3, 1)),
                                 ("reverse(1,3)", reverse(current, 1, 3))):
            show(label, candidate, score(candidate))
    if len(current) >= 2:
        candidate = random_swap_neighbor(current, Random(seed))
        show(f"Random swap, seed={seed}", candidate, score(candidate))

    print("\nAll neighbors (relative to the same initial sequence):")
    best_neighbor = None
    best_score = None
    counts = {"better": 0, "equal": 0, "worse": 0}
    for number, neighbor in enumerate(generate_neighbors(current, kind), start=1):
        value = score(neighbor)
        relation = "better" if value < current_score else "equal" if value == current_score else "worse"
        counts[relation] += 1
        show(f"{number:2} {relation:6}", neighbor, value)
        # 同分保留枚举中最先出现的邻居；即使所有邻居更差，也能记录真实最佳邻居。
        if best_score is None or value < best_score:
            best_neighbor, best_score = neighbor, value
    print(f"\nCount={sum(counts.values())}; {counts}")
    if best_neighbor is None:
        print("No neighbors; improvement=N/A")
    else:
        show("Best neighbor", best_neighbor, best_score)
        improvement = current_score - best_score
        rate = f"{improvement / current_score:.2%}" if current_score != 0 else "N/A (initial objective is zero)"
        print(f"Improvement={improvement:g}; rate={rate}")
        if improvement <= 0:
            print("No strictly improving neighbor in this neighborhood.")
    return best_neighbor, best_score, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="seed for the random swap")
    parser.add_argument("--neighborhood", choices=("swap", "insert", "reverse"), default="swap")
    args = parser.parse_args()
    compare_neighborhood(neighborhood_jobs(), kind=args.neighborhood, seed=args.seed)


if __name__ == "__main__":
    main()
