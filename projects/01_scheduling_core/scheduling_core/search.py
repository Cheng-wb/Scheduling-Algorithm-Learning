"""统一评价预算（包括初始解、拒绝解和重启），最小化目标。"""

from collections.abc import Callable
from dataclasses import dataclass
from math import exp, isfinite
from random import Random
from time import perf_counter

from .models import Instance
from .objective import makespan, total_tardiness, weighted_completion_time
from .schedule import Schedule
from .schedule_validation import validate_schedule
from .solution import (
    Candidate,
    decode,
    initial_candidate,
    insert,
    neighbors,
    reassign,
    swap,
)

OBJECTIVES: dict[str, Callable[[Instance, Schedule], float]] = {
    "makespan": makespan,
    "total_tardiness": total_tardiness,
    "weighted_completion_time": weighted_completion_time,
}
ALGORITHMS = ("lpt", "random", "first", "best", "multistart", "sa")


@dataclass(frozen=True, slots=True)
class SearchConfig:
    algorithm: str = "sa"
    objective: str = "makespan"
    budget: int = 200
    seed: int = 0
    temperature: float = 10.0
    cooling: float = 0.98
    restart_interval: int = 40

    def __post_init__(self) -> None:
        if self.algorithm not in ALGORITHMS or self.objective not in OBJECTIVES:
            raise ValueError("unknown algorithm/objective")
        if type(self.budget) is not int or self.budget < 1 or self.restart_interval < 1:
            raise ValueError("budget/restart_interval must be positive")
        if (
            not isfinite(self.temperature)
            or self.temperature <= 0
            or not 0 < self.cooling <= 1
        ):
            raise ValueError("invalid annealing parameters")


@dataclass(frozen=True, slots=True)
class TracePoint:
    evaluation: int
    proposed: float
    current: float
    best: float
    accepted: bool
    temperature: float | None


@dataclass(frozen=True, slots=True)
class SearchResult:
    candidate: Candidate
    schedule: Schedule
    objective: float
    evaluations: int
    status: str
    elapsed_seconds: float
    trace: tuple[TracePoint, ...]


def solve(
    instance: Instance, config: SearchConfig, initial: Candidate | None = None
) -> SearchResult:
    started = perf_counter()
    rng = Random(config.seed)
    objective = OBJECTIVES[config.objective]
    current = initial if initial is not None else initial_candidate(instance)
    current_schedule = decode(instance, current)
    validate_schedule(instance, current_schedule)
    value = float(objective(instance, current_schedule))
    best, best_schedule, best_value = current, current_schedule, value
    trace = [TracePoint(1, value, value, value, True, None)]
    temperature = config.temperature
    status = "BUDGET"

    def evaluate(candidate: Candidate) -> tuple[Schedule, float]:
        schedule = decode(instance, candidate)
        validate_schedule(instance, schedule)
        return schedule, float(objective(instance, schedule))

    def record(
        candidate: Candidate,
        schedule: Schedule,
        score: float,
        accepted: bool,
        temp: float | None = None,
    ) -> None:
        nonlocal best, best_schedule, best_value
        if score < best_value:
            best, best_schedule, best_value = candidate, schedule, score
        trace.append(
            TracePoint(len(trace) + 1, score, value, best_value, accepted, temp)
        )

    def random_candidate() -> Candidate:
        order = list(current.order)
        rng.shuffle(order)
        return Candidate(
            tuple(order),
            tuple(rng.choice(op.eligible_machine_ids) for op in instance.operations),
        )

    def random_move() -> Candidate:
        # 允许 no-op，仍计入评价，避免单元素/单资格情况下死循环。
        if not current.order:
            return current
        kind = rng.randrange(3)
        i = rng.randrange(len(current.order))
        j = rng.randrange(len(current.order))
        if kind == 0:
            return swap(current, i, j)
        if kind == 1:
            return insert(current, i, j)
        return reassign(
            instance,
            current,
            i,
            rng.choice(instance.operations[i].eligible_machine_ids),
        )

    if config.algorithm == "lpt":
        status = "BASELINE"
    elif config.algorithm in ("random", "sa"):
        while len(trace) < config.budget:
            candidate = (
                random_candidate() if config.algorithm == "random" else random_move()
            )
            schedule, score = evaluate(candidate)
            delta = score - value
            accepted = (
                score < value
                if config.algorithm == "random"
                else delta <= 0 or rng.random() < exp(-delta / max(temperature, 1e-12))
            )
            if accepted:
                current, value = candidate, score
            record(
                candidate,
                schedule,
                score,
                accepted,
                temperature if config.algorithm == "sa" else None,
            )
            temperature *= config.cooling
    else:
        segment_start = 0
        while len(trace) < config.budget:
            scan_current = current
            chosen, chosen_value = current, value
            for candidate in neighbors(instance, current):
                if len(trace) >= config.budget:
                    break
                if (
                    config.algorithm == "multistart"
                    and len(trace) - segment_start >= config.restart_interval
                ):
                    break
                schedule, score = evaluate(candidate)
                improved = score < chosen_value
                if improved:
                    chosen, chosen_value = candidate, score
                if config.algorithm != "best" and improved:
                    current, value = chosen, chosen_value
                # Best 的扫描阶段没有移动；选定一步后回填最后一个点的 current。
                record(
                    candidate, schedule, score, config.algorithm != "best" and improved
                )
                if improved and config.algorithm != "best":
                    break
            moved = chosen != scan_current
            if config.algorithm == "best":
                current, value = chosen, chosen_value
                last = trace[-1]
                trace[-1] = TracePoint(
                    last.evaluation, last.proposed, value, last.best, moved, None
                )
            if len(trace) >= config.budget:
                break
            restart = config.algorithm == "multistart" and (
                not moved or len(trace) - segment_start >= config.restart_interval
            )
            if restart:
                candidate = random_candidate()
                schedule, score = evaluate(candidate)
                current, value = candidate, score
                record(candidate, schedule, score, True)
                segment_start = len(trace) - 1
            elif not moved:
                status = "LOCAL_OPTIMUM"
                break
    return SearchResult(
        best,
        best_schedule,
        best_value,
        len(trace),
        status,
        perf_counter() - started,
        tuple(trace),
    )
