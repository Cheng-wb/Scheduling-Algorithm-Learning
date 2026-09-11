"""基础模拟退火：随机邻居、Metropolis 接受规则与逐步几何降温。"""

from math import exp, isfinite
from random import Random

from .neighborhood import random_swap_neighbor


def simulated_annealing(
    initial_solution, build_schedule, objective, *, initial_temperature=100.0,
    cooling_rate=0.95, max_iterations=1000, min_temperature=1e-6,
    seed=42, neighbor_fn=random_swap_neighbor,
):
    """最小化标量目标，返回历史最好解以及最终 Current。

    每次评价一个随机邻居后降温，拒绝候选也降温。
    history 记录本轮使用的温度和接受判断后的 Current / Best。
    """
    for name, value in (("initial_temperature", initial_temperature),
                        ("min_temperature", min_temperature)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if isinstance(cooling_rate, bool) or not isinstance(cooling_rate, (int, float)) or not 0 < cooling_rate < 1:
        raise ValueError("cooling_rate must be between 0 and 1")
    if type(max_iterations) is not int or max_iterations < 0:
        raise ValueError("max_iterations must be a non-negative integer")

    def score(sequence):
        value = objective(build_schedule(sequence))
        if not isfinite(value):
            raise ValueError("objective must return a finite scalar")
        return value

    rng = Random(seed)
    current = list(initial_solution)
    current_score = initial_score = score(current)
    best, best_score = current.copy(), current_score
    temperature = initial_temperature
    history = []
    counts = {"better": 0, "equal": 0, "worse": 0}
    stop_reason = "max_iterations"
    for iteration in range(1, max_iterations + 1):
        if len(current) < 2:
            stop_reason = "no_neighbors"
            break
        if temperature < min_temperature:
            stop_reason = "min_temperature"
            break
        neighbor = neighbor_fn(current, rng)
        neighbor_score = score(neighbor)
        delta = neighbor_score - current_score
        probability = 1.0 if delta <= 0 else exp(-delta / temperature)
        draw = None if delta <= 0 else rng.random()
        accepted = delta <= 0 or draw < probability
        if accepted:
            current, current_score = list(neighbor), neighbor_score
            counts["better" if delta < 0 else "equal" if delta == 0 else "worse"] += 1
        if current_score < best_score:
            best, best_score = current.copy(), current_score
        history.append({
            "iteration": iteration, "temperature": temperature,
            "neighbor_score": neighbor_score, "delta": delta,
            "probability": probability, "draw": draw, "accepted": accepted,
            "current_score": current_score, "best_score": best_score,
        })
        temperature *= cooling_rate
    return {
        "solution": best, "score": best_score, "initial_score": initial_score,
        "current_solution": current, "current_score": current_score,
        "iterations": len(history), "neighbor_evaluations": len(history),
        "objective_evaluations": len(history) + 1,
        "accepted_better": counts["better"], "accepted_equal": counts["equal"],
        "accepted_worse": counts["worse"], "history": history,
        "final_temperature": temperature, "stop_reason": stop_reason, "seed": seed,
    }
