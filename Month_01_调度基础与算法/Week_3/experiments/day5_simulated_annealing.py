"""模拟退火轨迹、温度参数和搜索方法比较。"""

import argparse
from math import isclose
from pathlib import Path
from statistics import mean
import sys
from time import perf_counter
from textwrap import fill

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.instances import restart_jobs
from evaluation.objective import objective
from scheduling.dispatching import dispatch
from scheduling.schedule import build_schedule
from scheduling.validation import validate_schedule
from search.local_search import best_improvement_local_search, multi_start_local_search
from search.simulated_annealing import simulated_annealing


from experiments.tables import print_table


def verify_sa(result, initial, decode):
    """直接复核实验结果和接受历史，不计入搜索时间。"""
    current_score = best_score = objective(decode(initial))
    for row in result["history"]:
        if not isclose(row["neighbor_score"] - current_score, row["delta"], abs_tol=1e-9):
            raise RuntimeError("delta is inconsistent with the previous current score")
        if row["accepted"] != (row["delta"] <= 0 or row["draw"] < row["probability"]):
            raise RuntimeError("acceptance decision is inconsistent")
        if row["accepted"]:
            current_score = row["neighbor_score"]
        best_score = min(best_score, current_score)
        if (row["current_score"], row["best_score"]) != (current_score, best_score):
            raise RuntimeError("current/best history is inconsistent")
    if objective(decode(result["solution"])) != best_score or result["score"] != best_score:
        raise RuntimeError("returned solution is not the historical best")
    if objective(decode(result["current_solution"])) != current_score:
        raise RuntimeError("final current score does not match its schedule")
    if result["accepted_worse"] != sum(r["accepted"] and r["delta"] > 0 for r in result["history"]):
        raise RuntimeError("incorrect accepted-worse count")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-seed", type=int, default=42)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument("--max-iterations", type=int, default=1000, help="SA candidate evaluation limit")
    parser.add_argument("--restarts", type=int, default=20)
    args = parser.parse_args()
    if args.max_iterations < 0 or args.restarts < 1:
        parser.error("max iterations must be non-negative; restarts must be positive")
    jobs = restart_jobs(args.data_seed)
    initial = dispatch(jobs, "spt")
    original = initial.copy()

    def decode(sequence):
        schedule = build_schedule(sequence)
        validate_schedule(schedule, jobs)
        return schedule

    # 缓存完全相同的设置，默认配置在参数表和对照表中复用。
    cache = {}

    def run_sa(temperature=100.0, cooling=0.95, seed=args.seed):
        key = (temperature, cooling, seed)
        if key not in cache:
            start = perf_counter()
            result = simulated_annealing(initial, decode, objective, initial_temperature=temperature,
                                         cooling_rate=cooling, max_iterations=args.max_iterations, seed=seed)
            result["runtime"] = perf_counter() - start
            verify_sa(result, initial, decode)
            if initial != original:
                raise RuntimeError("SA changed the initial solution")
            cache[key] = result
        return cache[key]

    print(f"n=20; data_seed={args.data_seed}; search_seed={args.seed}; SPT / Swap / total_tardiness")
    print_table("Input jobs", ["Job", "Processing", "Due date"],
                [(j.job_id, f"{j.processing_time:g}", f"{j.due_date:g}") for j in jobs], text_columns=(0,))
    print("\nInitial sequence:")
    print(fill(" -> ".join(j.job_id for j in initial), width=90, initial_indent="  ", subsequent_indent="  "))
    print(f"Initial score: {objective(decode(initial)):g}")
    sa = run_sa()
    print_table("First 20 candidate decisions", ["Step", "T", "Delta", "Probability", "Accept", "Current", "Best"],
                [(r["iteration"], f"{r['temperature']:.4f}", f"{r['delta']:g}", f"{r['probability']:.5f}",
                  "Yes" if r["accepted"] else "No", f"{r['current_score']:g}", f"{r['best_score']:g}")
                 for r in sa["history"][:20]], text_columns=(4,))
    print("\nBest sequence:")
    print(fill(" -> ".join(j.job_id for j in sa["solution"]), width=90, initial_indent="  ", subsequent_indent="  "))
    print_table("SA result", ["Current", "Best", "Improvement", "Worse accepted", "Stop"],
                [(f"{sa['current_score']:g}", f"{sa['score']:g}", f"{sa['initial_score']-sa['score']:g}",
                  sa["accepted_worse"], sa["stop_reason"])], text_columns=(4,))
    midpoint = len(sa["history"]) // 2
    acceptance_rows = []
    for label, rows in (("first half", sa["history"][:midpoint]), ("second half", sa["history"][midpoint:])):
        worse = [r for r in rows if r["delta"] > 0]
        acceptance_rows.append((label, len(worse), sum(r["accepted"] for r in worse)))
    print_table("Worse-move acceptance", ["Period", "Worse proposals", "Accepted"], acceptance_rows, text_columns=(0,))

    parameter_rows = []
    settings = [(t, 0.95) for t in (1, 10, 100, 1000)] + [(100, a) for a in (0.80, 0.90, 0.99)]
    for t, a in settings:
        r = run_sa(t, a)
        parameter_rows.append((f"{t:g}", f"{a:.2f}", f"{r['score']:g}", f"{r['current_score']:g}",
                               r["accepted_worse"], r["objective_evaluations"], f"{r['runtime']:.4f}", r["stop_reason"]))
    print_table("Parameter sweeps", ["T0", "Alpha", "Best", "Current", "Worse accepted", "Evaluations", "Time(s)", "Stop"],
                parameter_rows, text_columns=(7,))
    values = []
    stability_rows = []
    for seed in dict.fromkeys(args.seeds):
        r = run_sa(seed=seed)
        values.append(r["score"])
        stability_rows.append((seed, f"{r['score']:g}", r["accepted_worse"], r["objective_evaluations"]))
    print_table("SA stability", ["Seed", "Best", "Worse accepted", "Evaluations"], stability_rows)
    print_table("Stability summary", ["Best", "Mean", "Worst"],
                [(f"{min(values):g}", f"{mean(values):.2f}", f"{max(values):g}")])

    print("\nRunning Local Search and Multi-start baselines...", flush=True)
    start = perf_counter()
    ls = best_improvement_local_search(initial, decode, objective)
    ls_time = perf_counter() - start
    start = perf_counter()
    multi = multi_start_local_search(jobs, decode, objective, num_restarts=args.restarts, seed=args.seed)
    multi_time = perf_counter() - start
    for result in (ls, multi):
        if objective(decode(result["solution"])) != result["score"]:
            raise RuntimeError("baseline score does not match returned schedule")
    start = perf_counter()
    baseline = objective(decode(initial))
    baseline_time = perf_counter() - start
    comparison_rows = []
    for name, score, calls, runtime in (
        ("SPT", baseline, 1, baseline_time),
        ("SPT+LS", ls["score"], ls["neighbor_evaluations"]+1, ls_time),
        (f"{args.restarts}-start LS", multi["score"], sum(r["neighbor_evaluations"]+1 for r in multi["history"]), multi_time),
        ("SPT+SA", sa["score"], sa["objective_evaluations"], sa["runtime"]),
    ):
        comparison_rows.append((name, f"{score:g}", f"{baseline-score:g}", calls, f"{runtime:.4f}"))
    print_table("Algorithm comparison", ["Method", "Best", "Improvement", "ObjectiveCalls", "Time(s)"],
                comparison_rows, text_columns=(0,))
    print("Budgets differ: these are configured runs, not an equal-budget ranking.")
    print("ObjectiveCalls includes each initial score; excludes reporting and post-run verification.")


if __name__ == "__main__":
    main()
