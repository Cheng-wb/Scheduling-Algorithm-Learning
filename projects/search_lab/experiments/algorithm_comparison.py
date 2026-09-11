"""统一算法对照、随机稳定性与问题规模实验。"""

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import platform
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.instances import comparison_jobs
from experiments.benchmark import DEFAULT_CONFIG, algorithm_table, run_algorithm, set_improvements, summarize
from experiments.tables import print_table, result_table, write_csv, number

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance-seed", type=int, default=42)
    parser.add_argument("--algorithm-seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument("--sizes", type=int, nargs="+", default=[10, 20, 30])
    parser.add_argument("--restarts", type=int, default=20)
    parser.add_argument("--ls-max-iterations", type=int, default=1000)
    parser.add_argument("--sa-max-iterations", type=int, default=1000)
    args = parser.parse_args()
    if min(args.sizes) < 1 or args.restarts < 1 or min(args.ls_max_iterations, args.sa_max_iterations) < 0:
        parser.error("sizes/restarts must be positive; iteration limits must be non-negative")
    config = dict(DEFAULT_CONFIG, restarts=args.restarts, ls_max_iterations=args.ls_max_iterations,
                  sa_max_iterations=args.sa_max_iterations)
    output = ROOT / "results" / datetime.now().strftime("day6_%Y%m%d_%H%M%S_%f")
    output.mkdir(parents=True)
    instances = {size: comparison_jobs(size, args.instance_seed) for size in sorted(set([20] + args.sizes))}
    (output / "config.json").write_text(json.dumps(dict(arguments=vars(args), parameters=config,
        python=platform.python_version(), platform=platform.platform(), objective="total_tardiness",
        baseline="SPT", instance_ranges=dict(processing_time=[1,20], due_date=[20,150], release_time=[0,0]),
        budget_mode="configured_runs_without_equal_budget"), indent=2), encoding="utf-8")
    (output / "instances.json").write_text(json.dumps({str(n): [asdict(j) for j in jobs]
        for n, jobs in instances.items()}, indent=2), encoding="utf-8")
    all_rows, cache = [], {}

    def run(name, size=20, seed=args.algorithm_seed):
        stochastic = name in ("Multi-start", "SPT+SA")
        key = (name, size, seed if stochastic else None)
        if key not in cache:
            print(f"Running n={size}, {name}, seed={key[2]} ...", flush=True)
            solver = algorithm_table(config, seed)[name]
            cache[key] = run_algorithm(name, solver, instances[size],
                instance_id=f"n{size}_seed{args.instance_seed}", instance_seed=args.instance_seed,
                algorithm_seed=key[2])
        return cache[key].copy()

    def record(suite, rows):
        for row in rows:
            row["suite"] = suite
        all_rows.extend(rows)
        # 每组完成即保存，避免长实验结束前看不到结果文件。
        write_csv(output / "runs.csv", all_rows)

    print("Objective: total_tardiness; baseline: SPT; same instance and evaluation pipeline.")
    print("Configured budgets differ. Iterations have algorithm-specific meanings.")
    print("Parameters:", config)
    rows = [run(name) for name in algorithm_table(config, args.algorithm_seed)]
    baseline = next(r["objective"] for r in rows if r["algorithm"] == "SPT")
    set_improvements(rows, baseline)
    record("single", rows)
    result_table("Single-instance comparison (n=20)", rows)
    print_table("Schedule metrics", ["Algorithm", "Cmax", "Avg C", "Max lateness", "Stop"],
                [(r["algorithm"], number(r.get("makespan")), number(r.get("average_completion_time"), ".2f"),
                  number(r.get("max_lateness")), r["stop_reason"]) for r in rows], text_columns=(0,4))

    summaries = []
    for name in ("Multi-start", "SPT+SA"):
        repetitions = [run(name, seed=seed) for seed in dict.fromkeys(args.seeds)]
        set_improvements(repetitions, baseline)
        record("stability", repetitions)
        summary = dict(algorithm=name, instance=f"n20_seed{args.instance_seed}", **summarize(repetitions))
        summaries.append(summary)
    print_table("Stability on one fixed instance", ["Algorithm", "OK/N", "Best", "Mean", "Worst", "Std", "Avg time(s)", "Avg eval"],
        [(r["algorithm"], f"{r['success']}/{r['samples']}", number(r["best"]), number(r["mean"], ".2f"),
          number(r["worst"]), number(r["std"], ".2f"), number(r["mean_runtime"], ".4f"),
          number(r["mean_evaluations"], ".1f")) for r in summaries], text_columns=(0,))
    write_csv(output / "summary.csv", summaries)

    scale_rows = []
    for size in sorted(set(args.sizes)):
        group = [run(name, size) for name in ("SPT", "SPT+LS", "SPT+SA")]
        set_improvements(group, group[0]["objective"])
        record("scale", group)
        scale_rows.extend(group)
    print_table("Problem size comparison", ["Jobs", "Algorithm", "Objective", "Improve%", "Time(s)", "Eval", "Status"],
        [(r["n_jobs"], r["algorithm"], number(r["objective"]), number(r["improvement_rate"], ".2%"),
          number(r["runtime"], ".4f"), r["evaluations"], r["status"]) for r in scale_rows], text_columns=(1,6))
    failures = [r for r in all_rows if r["status"] != "OK"]
    print(f"\nSaved: {output}\nFailed/invalid rows: {len(failures)}")
    print("Repeated identical settings reuse the same measured run; summaries only use stability rows.")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
