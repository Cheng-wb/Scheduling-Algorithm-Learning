"""严格下降的局部搜索；初始解、解码器、目标和邻域均由调用方提供。"""

from math import isfinite
from random import Random
from time import perf_counter

from .neighborhood import generate_swap_neighbors


def _search(initial_solution, build_schedule, objective, neighbors, max_iterations, *, first):
    if type(max_iterations) is not int or max_iterations < 0:
        raise ValueError("max_iterations must be a non-negative integer")

    def score(sequence):
        value = objective(build_schedule(sequence))
        if not isfinite(value):
            raise ValueError("objective must return a finite scalar")
        return value

    current = list(initial_solution)
    current_score = score(current)
    history = [current_score]
    path = [current.copy()]
    iterations = 0
    neighbor_evaluations = 0
    stop_reason = "max_iterations"

    while iterations < max_iterations:
        chosen = None
        chosen_score = current_score
        for neighbor in neighbors(current):
            value = score(neighbor)
            neighbor_evaluations += 1
            if value < chosen_score:
                chosen, chosen_score = list(neighbor), value
                if first:
                    break
        if chosen is None:
            stop_reason = "no_improvement"
            break
        current, current_score = chosen, chosen_score
        iterations += 1
        history.append(current_score)
        path.append(current.copy())

    return {
        "solution": current,
        "score": current_score,
        "iterations": iterations,
        "history": history,
        "path": path,
        "neighbor_evaluations": neighbor_evaluations,
        "stop_reason": stop_reason,
    }


def best_improvement_local_search(
    initial_solution, build_schedule, objective,
    neighbors=generate_swap_neighbors, *, max_iterations=1000,
):
    """每轮扫描全部邻居，接受最好的严格改进；同分保留最先枚举的解。"""
    return _search(initial_solution, build_schedule, objective, neighbors, max_iterations, first=False)


def first_improvement_local_search(
    initial_solution, build_schedule, objective,
    neighbors=generate_swap_neighbors, *, max_iterations=1000,
):
    """每轮遇到第一个严格改进即接受，再从新解重新枚举邻域。"""
    return _search(initial_solution, build_schedule, objective, neighbors, max_iterations, first=True)


def multi_start_local_search(
    jobs, build_schedule, objective, *, num_restarts=20, seed=42,
    neighbors=generate_swap_neighbors, max_iterations=1000,
    search=best_improvement_local_search, initialize=None,
):
    """执行 num_restarts 次随机起点搜索（含第一次），同分保留先发现的结果。

    initialize(jobs, rng) 负责生成起点；不在每次重启时重新设置 seed。
    history 中的 elapsed 是从整次调用开始计时的累计耗时。
    """
    if type(num_restarts) is not int or num_restarts < 1:
        raise ValueError("num_restarts must be a positive integer")
    if type(max_iterations) is not int or max_iterations < 0:
        raise ValueError("max_iterations must be a non-negative integer")
    if initialize is None:
        from scheduling.dispatching import random_solution
        initialize = random_solution
    rng = Random(seed)
    best_solution, best_score, best_restart = None, float("inf"), None
    history = []
    start = perf_counter()
    for restart in range(1, num_restarts + 1):
        initial = initialize(list(jobs), rng)
        result = search(initial, build_schedule, objective, neighbors, max_iterations=max_iterations)
        if result["score"] < best_score:
            best_solution = list(result["solution"])
            best_score, best_restart = result["score"], restart
        history.append({
            "restart": restart, "initial_solution": list(initial),
            "solution": list(result["solution"]),
            "initial_score": result["history"][0], "final_score": result["score"],
            "best_score": best_score, "iterations": result["iterations"],
            "neighbor_evaluations": result["neighbor_evaluations"],
            "stop_reason": result["stop_reason"], "elapsed": perf_counter() - start,
        })
    return {"solution": best_solution, "score": best_score, "best_restart": best_restart,
            "history": history, "seed": seed, "runtime": perf_counter() - start}
