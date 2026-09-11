"""可复现的单机与并行机 Benchmark。"""

import argparse
import csv
from dataclasses import asdict
from datetime import datetime
from functools import partial
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling.benchmark import Algorithm, run_benchmark, summarize_results
from scheduling.bounds import parallel_machine_lower_bound
from scheduling.generators import generate_jobs
from scheduling.heuristics.single_machine import fcfs, spt, edd, wspt
from scheduling.heuristics.parallel_machine import greedy_list_scheduling, lpt_list_scheduling

ROOT = Path(__file__).resolve().parents[1]


def algorithm_table(problem, machines, *, use_milp, time_limit_ms):
    if problem == "single":
        algorithms = [Algorithm(name, solve) for name, solve in
                      (("FCFS", fcfs), ("SPT", spt), ("EDD", edd), ("WSPT", wspt))]
        if use_milp:
            from scheduling.exact.single_machine import solve_single_machine_weighted_tardiness
            algorithms.append(Algorithm("MILP_WT", partial(solve_single_machine_weighted_tardiness,
                                                          time_limit_ms=time_limit_ms), "weighted_tardiness"))
    else:
        algorithms = [Algorithm(name, partial(solve, num_machines=machines)) for name, solve in
                      (("Greedy", greedy_list_scheduling), ("LPT", lpt_list_scheduling))]
        if use_milp:
            from scheduling.exact.parallel_machine import solve_parallel_machine_milp
            algorithms.append(Algorithm("MILP", partial(solve_parallel_machine_milp,
                                                        num_machines=machines,
                                                        time_limit_ms=time_limit_ms), "makespan"))
    return algorithms


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_case(suite, problem, size, machines, seed, *, args, output, data_dir, charts=False):
    params = dict(n_jobs=size, processing_time_range=(1, 20), seed=seed)
    if problem == "single":
        params.update(due_date_range=(20, 100) if size == 20 else (10, 40), weight_range=(1, 10))
    jobs = generate_jobs(**params)
    instance = f"{suite}_n{size}_m{machines}_seed{seed}"
    write_json(data_dir / f"{instance}.json", {"parameters": params, "machine_count": machines,
                                              "jobs": [asdict(job) for job in jobs]})
    # 20 个任务展示规则表现；精确单机比较使用独立的小规模组，避免混淆实例。
    use_milp = not args.skip_milp and suite != "single_rules"
    algorithms = algorithm_table(problem, machines, use_milp=use_milp, time_limit_ms=args.time_limit_ms)
    target = "weighted_tardiness" if problem == "single" else "makespan"
    results = run_benchmark(jobs, algorithms, machine_count=machines, target_metric=target)
    bound = parallel_machine_lower_bound(jobs, machines) if problem == "parallel" else None
    print(f"\n{instance}; target={target}")
    if problem == "single":
        print("Algorithm     Cmax    SumC    SumwC    SumT    SumwT  Tardy   Runtime(s)    Gap")
    else:
        print("Algorithm     Cmax     LB   Utilization   Runtime(s)    Gap")
    rows = []
    schedules = {}
    for result in results:
        rows.append(dict(instance=instance, suite=suite, seed=seed, n_jobs=size,
                         machine_count=machines, target_metric=target, algorithm=result.algorithm,
                         status=result.status, runtime=result.runtime, gap=result.gap,
                         lower_bound=bound, error=result.error, **result.metrics))
        if result.status != "OK":
            print(f"{result.algorithm}: {result.status}: {result.error}")
            continue
        metrics = result.metrics
        gap = "N/A" if result.gap is None else f"{result.gap:.2%}"
        if problem == "single":
            values = " ".join(f"{metrics[key]:7g}" for key in
                              ("makespan", "total_completion_time", "weighted_completion_time",
                               "total_tardiness", "weighted_tardiness", "num_tardy_jobs"))
        else:
            values = f"{metrics['makespan']:7g} {bound:6g} {metrics['utilization']:12.2%}"
        print(f"{result.algorithm:10} {values} {result.runtime:12.6f} {gap:>8}")
        schedules[result.algorithm] = asdict(result.schedule)
        selected = (problem == "parallel" or result.algorithm in ("EDD", "MILP_WT"))
        if charts and selected and not args.no_plots:
            from scheduling.visualization.gantt import plot_gantt
            figure = plot_gantt(result.schedule, f"{instance} | {result.algorithm} | {target}={metrics[target]:g}")
            figure.savefig(output / f"{instance}_{result.algorithm}.png", dpi=150)
            figure.clear()
    write_json(output / f"{instance}_schedules.json", schedules)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=5, help="batch seeds 1..N")
    parser.add_argument("--time-limit-ms", type=int, default=5000, help="limit for each MILP")
    parser.add_argument("--skip-milp", action="store_true")
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--scale", action="store_true", help="also run n=10/20/50/100, m=5")
    args = parser.parse_args()
    if args.seeds < 1 or args.time_limit_ms < 1:
        parser.error("--seeds and --time-limit-ms must be positive")
    run_id = datetime.now().strftime("day7_%Y%m%d_%H%M%S_%f")
    output = ROOT / "results" / run_id
    data_dir = ROOT / "data" / "generated" / run_id
    output.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    versions = {}
    for package in ("ortools", "matplotlib"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    write_json(output / "config.json", dict(arguments=vars(args), python=platform.python_version(),
                                            platform=platform.platform(), packages=versions,
                                            data_dir=str(data_dir.relative_to(ROOT))))
    options = dict(args=args, output=output, data_dir=data_dir)
    rows = []
    for suite, problem, size, machines in (("single_rules", "single", 20, 1),
                                           ("single_exact", "single", 6, 1),
                                           ("parallel_fixed", "parallel", 20, 3)):
        rows.extend(run_case(suite, problem, size, machines, 42, charts=True, **options))
    for seed in range(1, args.seeds + 1):
        rows.extend(run_case("single_batch", "single", 6, 1, seed, **options))
        rows.extend(run_case("parallel_batch", "parallel", 20, 3, seed, **options))
    if args.scale:
        for size in (10, 20, 50, 100):
            rows.extend(run_case("parallel_scale", "parallel", size, 5, 42, **options))
    summary = summarize_results(rows)
    write_csv(output / "benchmark.csv", rows)
    write_csv(output / "summary.csv", summary)
    print("\nBatch summary: target mean, gap mean/max, successful samples")
    for row in summary:
        if not row["suite"].endswith("batch"):
            continue
        print(f"{row['suite']:15} {row['algorithm']:10} "
              f"mean={row['avg_' + row['target_metric']]} "
              f"gap={row['avg_gap']}/{row['max_gap']} "
              f"OK={row['success']}/{row['samples']} gap_samples={row['gap_samples']}")
    print(f"\nResults: {output}\nInstances: {data_dir}")


if __name__ == "__main__":
    main()
