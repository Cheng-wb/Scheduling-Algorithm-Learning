"""统一运行六种方法，输出 Benchmark 和最佳完整排程。"""

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.instances import comparison_jobs
from evaluation.evaluate import evaluate
from experiments.benchmark import DEFAULT_CONFIG, algorithm_table, run_algorithm, set_improvements
from experiments.tables import print_table, result_table, write_csv
from scheduling.schedule import build_schedule
from scheduling.validation import validate_schedule


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=20)
    parser.add_argument("--instance-seed", type=int, default=100)
    parser.add_argument("--algorithm-seed", type=int, default=0)
    parser.add_argument("--restarts", type=int, default=DEFAULT_CONFIG["restarts"])
    args = parser.parse_args()
    if args.jobs < 1 or args.restarts < 1:
        parser.error("jobs and restarts must be positive")
    config = dict(DEFAULT_CONFIG, restarts=args.restarts)
    jobs = comparison_jobs(args.jobs, args.instance_seed)
    original = jobs.copy()
    print(f"Jobs={len(jobs)}; instance_seed={args.instance_seed}; algorithm_seed={args.algorithm_seed}")
    print("Objective: total_tardiness; baseline: SPT; neighborhood: Swap")
    print("Parameters:", config)
    print_table("Instance", ["Job", "Processing", "Release", "Due"],
                [(j.job_id, j.processing_time, j.release_time, j.due_date) for j in jobs], text_columns=(0,))
    rows = []
    for name, solver in algorithm_table(config, args.algorithm_seed).items():
        print(f"Running {name} ...", flush=True)
        rows.append(run_algorithm(name, solver, jobs,
                    instance_id=f"n{args.jobs}_seed{args.instance_seed}", instance_seed=args.instance_seed,
                    algorithm_seed=args.algorithm_seed if name in ("Multi-start", "SPT+SA") else None))
    if jobs != original:
        raise RuntimeError("shared input changed")
    baseline = next(r["objective"] for r in rows if r["algorithm"] == "SPT")
    set_improvements(rows, baseline)
    result_table("Final benchmark (configured, unequal budgets)", rows)
    output = Path(__file__).resolve().parents[1] / "results" / datetime.now().strftime("day7_%Y%m%d_%H%M%S_%f")
    output.mkdir(parents=True)
    write_csv(output / "runs.csv", rows)
    (output / "config.json").write_text(json.dumps(dict(arguments=vars(args), parameters=config,
        objective="total_tardiness", baseline="SPT", budget_mode="unequal", python=sys.version), indent=2), encoding="utf-8")
    (output / "instance.json").write_text(json.dumps([asdict(j) for j in jobs], indent=2), encoding="utf-8")
    good = [r for r in rows if r["status"] == "OK"]
    if not good:
        raise SystemExit(f"No valid result. Logs: {output}")
    best = min(good, key=lambda r: r["objective"])
    tied = [r["algorithm"] for r in good if r["objective"] == best["objective"]]
    lookup = {j.job_id: j for j in jobs}
    schedule = build_schedule([lookup[job_id] for job_id in best["solution"]])
    validate_schedule(schedule, jobs)
    metrics = evaluate(schedule)
    if metrics["total_tardiness"] != best["objective"]:
        raise RuntimeError("best schedule score mismatch")
    print("\nBest objective algorithms:", ", ".join(tied))
    print("Displayed schedule:", best["algorithm"], "(first listed in a tie)")
    print(" -> ".join(best["solution"]))
    items = [dict(job=a.job.job_id, machine=a.machine_id, start=a.start_time,
                  completion=a.completion_time, due=a.job.due_date, tardiness=a.tardiness)
             for a in schedule.assignments]
    print_table("Best schedule", ["Job", "Machine", "Start", "Completion", "Due", "Tardiness"],
                [list(item.values()) for item in items], text_columns=(0,))
    print_table("Best schedule metrics", ["Total tardiness", "Makespan", "Average completion"],
                [(metrics["total_tardiness"], metrics["makespan"], f"{metrics['average_completion_time']:.2f}")])
    write_csv(output / "best_schedule.csv", items)
    print(f"Saved: {output}")
    print("Best observed result is not a proof of global optimality. Budgets differ.")
    if len(good) != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
