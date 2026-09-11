"""实验公共接口：统一算法调用、计时、目标计数与结果统计。"""

from math import isclose
from statistics import mean, stdev
from time import perf_counter

from evaluation.evaluate import evaluate
from evaluation.objective import objective
from scheduling.dispatching import dispatch
from scheduling.schedule import build_schedule
from scheduling.validation import validate_schedule
from search.local_search import best_improvement_local_search, multi_start_local_search
from search.simulated_annealing import simulated_annealing
from search.neighborhood import generate_swap_neighbors, random_swap_neighbor


DEFAULT_CONFIG = dict(restarts=20, ls_max_iterations=1000, sa_max_iterations=1000,
                      temperature=100.0, cooling_rate=0.95, min_temperature=1e-6)


def algorithm_table(config, seed, *, initializer=None,
                    neighbors=generate_swap_neighbors, random_neighbor=random_swap_neighbor):
    """适配为 solver(jobs, decode, score) -> 搜索结果字典。"""
    config = dict(config)
    initial_name = "SPT" if initializer is None else "Initial"
    if initializer is None:
        initializer = lambda jobs: dispatch(jobs, "spt")

    def rule_solver(rule):
        def solve(jobs, decode, score):
            solution = dispatch(jobs, rule)
            return {"solution": solution, "score": score(decode(solution)), "iterations": 0,
                    "stop_reason": "rule", "expected_evaluations": 1, "restarts": 0}
        return solve

    def local(jobs, decode, score):
        result = best_improvement_local_search(initializer(jobs), decode, score, neighbors=neighbors,
                                              max_iterations=config["ls_max_iterations"])
        result["expected_evaluations"] = result["neighbor_evaluations"] + 1
        result["restarts"] = 0
        return result

    def multi(jobs, decode, score):
        result = multi_start_local_search(jobs, decode, score, seed=seed,
                                         num_restarts=config["restarts"], neighbors=neighbors,
                                         max_iterations=config["ls_max_iterations"])
        result["iterations"] = sum(row["iterations"] for row in result["history"])
        result["expected_evaluations"] = sum(row["neighbor_evaluations"] + 1 for row in result["history"])
        capped = sum(row["stop_reason"] == "max_iterations" for row in result["history"])
        result["stop_reason"] = f"completed; capped={capped}"
        result["restarts"] = len(result["history"])
        return result

    def sa(jobs, decode, score):
        result = simulated_annealing(initializer(jobs), decode, score, seed=seed, neighbor_fn=random_neighbor,
                                     initial_temperature=config["temperature"], cooling_rate=config["cooling_rate"],
                                     min_temperature=config["min_temperature"],
                                     max_iterations=config["sa_max_iterations"])
        result["expected_evaluations"] = result["objective_evaluations"]
        result["restarts"] = 0
        return result

    return {"FCFS": rule_solver("fcfs"), "SPT": rule_solver("spt"), "EDD": rule_solver("edd"),
            f"{initial_name}+LS": local, "Multi-start": multi, f"{initial_name}+SA": sa}


def run_algorithm(name, solver, jobs, *, instance_id, instance_seed, algorithm_seed=None):
    """所有初始化与搜索计入耗时；最终复核和报表评价不计入搜索次数。"""
    inputs = list(jobs)
    evaluations = 0

    def decode(sequence):
        schedule = build_schedule(sequence)
        validate_schedule(schedule, jobs)
        return schedule

    def counted_objective(schedule):
        nonlocal evaluations
        evaluations += 1
        return objective(schedule)

    row = dict(algorithm=name, instance=instance_id, instance_seed=instance_seed,
               algorithm_seed=algorithm_seed, n_jobs=len(jobs), objective_name="total_tardiness",
               status="OK", error="", objective=None, improvement=None, improvement_rate=None,
               iterations=None, restarts=None, stop_reason="", solution=[])
    start = perf_counter()
    try:
        result = solver(inputs, decode, counted_objective)
    except Exception as error:
        row.update(status="ERROR", error=f"{type(error).__name__}: {error}")
        row.update(runtime=perf_counter()-start, evaluations=evaluations)
        return row
    row.update(runtime=perf_counter()-start, evaluations=evaluations)
    try:
        if inputs != list(jobs):
            raise ValueError("algorithm modified its shared instance copy")
        schedule = decode(result["solution"])
        metrics = evaluate(schedule)
        if not isclose(result["score"], metrics["total_tardiness"], rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("reported score does not match returned schedule")
        if evaluations != result["expected_evaluations"]:
            raise ValueError("algorithm evaluation count disagrees with the measured count")
        row.update(objective=metrics["total_tardiness"], iterations=result["iterations"],
                   restarts=result["restarts"], stop_reason=result["stop_reason"],
                   solution=[job.job_id for job in result["solution"]],
                   makespan=metrics["makespan"], average_completion_time=metrics["average_completion_time"],
                   max_lateness=metrics["max_lateness"])
    except Exception as error:
        row.update(status="INVALID", error=f"{type(error).__name__}: {error}", objective=None)
    return row


def set_improvements(rows, baseline):
    """SPT 为零时相对改善率留空；负改善表示结果更差。"""
    for row in rows:
        if row["status"] == "OK" and baseline is not None:
            row["improvement"] = baseline - row["objective"]
            row["improvement_rate"] = row["improvement"] / baseline if baseline else None


def summarize(rows):
    """调用者传入同一实例、同一算法与配置的多种子结果。"""
    good = [row for row in rows if row["status"] == "OK"]
    values = [row["objective"] for row in good]
    return dict(samples=len(rows), success=len(good), failed=len(rows)-len(good),
                best=min(values) if values else None, mean=mean(values) if values else None,
                worst=max(values) if values else None, std=stdev(values) if len(values)>1 else 0.0 if values else None,
                mean_runtime=mean(row["runtime"] for row in good) if good else None,
                mean_evaluations=mean(row["evaluations"] for row in good) if good else None)
