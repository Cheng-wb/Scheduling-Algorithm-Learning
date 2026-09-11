"""统一运行、校验、计时与统计；不依赖具体算法或求解器。"""

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from math import isclose
from statistics import mean
from time import perf_counter

from .evaluator import evaluate
from .models import Job, Schedule
from .validation import validate_schedule


@dataclass(frozen=True)
class Algorithm:
    name: str
    solve: Callable[[list[Job]], Schedule]
    # 仅供“成功返回即已证明最优”的精确求解接口使用。
    optimal_for: str | None = None


@dataclass
class BenchmarkResult:
    algorithm: str
    status: str
    runtime: float
    metrics: dict = field(default_factory=dict)
    schedule: Schedule | None = None
    error: str = ""
    gap: float | None = None


def relative_gap(value, optimum):
    if isclose(value, optimum, rel_tol=1e-9, abs_tol=1e-7):
        return 0.0
    if optimum == 0:
        return float("inf")
    return (value - optimum) / optimum


def run_benchmark(
    jobs: Sequence[Job], algorithms: Sequence[Algorithm], *, machine_count: int,
    target_metric: str,
) -> list[BenchmarkResult]:
    """各算法使用相同任务的独立列表；失败保留原因，不产生虚假的指标。"""
    if type(machine_count) is not int or machine_count <= 0:
        raise ValueError("machine_count must be a positive integer")
    if len({a.name for a in algorithms}) != len(algorithms):
        raise ValueError("algorithm names must be unique")
    if len({job.job_id for job in jobs}) != len(jobs):
        raise ValueError("input job IDs must be unique")
    results = []
    optimum = None
    for algorithm in algorithms:
        inputs = list(jobs)
        start = perf_counter()
        try:
            schedule = algorithm.solve(inputs)
        except Exception as error:
            results.append(BenchmarkResult(algorithm.name, "ERROR", perf_counter() - start,
                                           error=f"{type(error).__name__}: {error}"))
            continue
        runtime = perf_counter() - start
        try:
            validate_schedule(schedule, jobs)
            if schedule.machine_count != machine_count:
                raise ValueError("schedule uses a different machine count")
            metrics = evaluate(schedule)
            if target_metric not in metrics:
                raise ValueError(f"unknown metric: {target_metric}")
        except Exception as error:
            results.append(BenchmarkResult(algorithm.name, "INVALID", runtime,
                                           error=f"{type(error).__name__}: {error}"))
            continue
        results.append(BenchmarkResult(algorithm.name, "OK", runtime, metrics, schedule))
        if algorithm.optimal_for == target_metric:
            optimum = metrics[target_metric]
    if optimum is not None:
        for result in results:
            if result.status == "OK":
                result.gap = relative_gap(result.metrics[target_metric], optimum)
    return results


def summarize_results(rows: list[dict]) -> list[dict]:
    """按问题、规模、目标及算法分组；缺少最优基准的样本不参与 Gap 均值。"""
    keys = ("suite", "n_jobs", "machine_count", "target_metric", "algorithm")
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    summaries = []
    for group, samples in groups.items():
        success = [row for row in samples if row["status"] == "OK"]
        gaps = [row["gap"] for row in success if row["gap"] is not None]
        result = dict(zip(keys, group))
        result.update(samples=len(samples), success=len(success), failed=len(samples) - len(success),
                      gap_samples=len(gaps),
                      avg_runtime=mean(row["runtime"] for row in samples),
                      avg_gap=mean(gaps) if gaps else None,
                      max_gap=max(gaps) if gaps else None)
        for metric in evaluate(Schedule([])):
            result[f"avg_{metric}"] = mean(row[metric] for row in success) if success else None
        summaries.append(result)
    return summaries
