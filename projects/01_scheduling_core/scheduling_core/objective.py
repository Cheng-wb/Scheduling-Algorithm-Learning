"""统一的目标评估器：由 Schedule 计算指标。

所有算法都输出统一的 Schedule，再由本模块统一计算目标，保证比较公平。
约定：due_date=None 的 Job 不参与 tardiness 目标。
"""

from __future__ import annotations

from scheduling_core.models import Instance
from scheduling_core.schedule import Schedule


def job_completion_times(instance: Instance, schedule: Schedule) -> dict[str, int]:
    """每个 Job 的完工时间：该 Job 最后完成的工序的 end_time。"""
    operation_by_id = {op.id: op for op in instance.operations}

    completion_times: dict[str, int] = {}

    for scheduled in schedule.operations:
        operation = operation_by_id[scheduled.operation_id]
        job_id = operation.job_id

        completion_times[job_id] = max(
            completion_times.get(job_id, 0),
            scheduled.end_time,
        )

    return completion_times


def makespan(instance: Instance, schedule: Schedule) -> int:
    """最后一个 Job 完成的时间。"""
    completion_times = job_completion_times(instance, schedule)
    return max(completion_times.values(), default=0)


def total_completion_time(instance: Instance, schedule: Schedule) -> int:
    """所有 Job 完工时间之和。"""
    completion_times = job_completion_times(instance, schedule)
    return sum(completion_times.values())


def total_flow_time(instance: Instance, schedule: Schedule) -> int:
    """总流动时间：Σ (Cj - rj)。"""
    completion_times = job_completion_times(instance, schedule)
    return sum(completion_times[job.id] - job.release_time for job in instance.jobs)


def max_lateness(instance: Instance, schedule: Schedule) -> int:
    """最大延迟：max_j (Cj - dj)。due_date=None 的 Job 不参与。

    与 total_tardiness 不同，Lmax 可以是负数（所有 job 都提前完成时）。
    """
    completion_times = job_completion_times(instance, schedule)

    lateness_values = [
        completion_times[job.id] - job.due_date
        for job in instance.jobs
        if job.due_date is not None
    ]

    return max(lateness_values, default=0)


def total_tardiness(instance: Instance, schedule: Schedule) -> int:
    """总迟交时间：Σ max(0, Cj - dj)。due_date=None 的 Job 不参与。"""
    completion_times = job_completion_times(instance, schedule)

    total = 0

    for job in instance.jobs:
        if job.due_date is None:
            continue

        completion = completion_times[job.id]
        total += max(0, completion - job.due_date)

    return total


def weighted_completion_time(instance: Instance, schedule: Schedule) -> float:
    """加权总完工时间：Σ wj·Cj。"""
    completion_times = job_completion_times(instance, schedule)

    return sum(job.weight * completion_times[job.id] for job in instance.jobs)
