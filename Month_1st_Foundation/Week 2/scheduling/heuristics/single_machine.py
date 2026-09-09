"""单机调度：静态模式固定全局顺序，动态模式只选择已释放任务。"""

from collections.abc import Sequence

from ..models import Job, Schedule, ScheduledJob
from ..scheduler import schedule_sequence
from .rules import PriorityKey, edd_key, fcfs_key, lpt_key, spt_key, wspt_key


def _validate_jobs(jobs: Sequence[Job]) -> list[Job]:
    jobs = list(jobs)
    if len({job.job_id for job in jobs}) != len(jobs):
        raise ValueError("jobs must have unique job IDs")
    return jobs


def schedule_static_rule(
    jobs: Sequence[Job],
    priority_fn: PriorityKey,
    *,
    algorithm: str = "static_rule",
) -> Schedule:
    """Sort all jobs once, then schedule them in that fixed order."""
    jobs = _validate_jobs(jobs)
    ordered_jobs = sorted(jobs, key=priority_fn)
    schedule = schedule_sequence(
        [job.job_id for job in ordered_jobs], jobs,
    )
    schedule.algorithm = algorithm
    schedule.validate()
    return schedule


def schedule_dynamic_rule(
    jobs: Sequence[Job],
    priority_fn: PriorityKey,
    *,
    algorithm: str = "dynamic_rule",
) -> Schedule:
    """Choose the best currently released job whenever the machine is free."""
    jobs = _validate_jobs(jobs)
    if not jobs:
        return Schedule([], algorithm=algorithm)

    # 保留输入顺序，避免相同优先级受 set 迭代顺序影响。
    # 优先级仅依赖 Job，预先计算也能尽早发现非法权重等输入。
    priorities = {job.job_id: priority_fn(job) for job in jobs}
    pending = list(jobs)
    assignments = []
    current_time = 0.0

    while pending:
        available = [job for job in pending if job.release_time <= current_time]
        if not available:
            current_time = min(job.release_time for job in pending)
            available = [job for job in pending if job.release_time <= current_time]

        job = min(available, key=lambda job: priorities[job.job_id])
        start_time = max(current_time, job.release_time)
        completion_time = start_time + job.processing_time
        assignments.append(ScheduledJob(job, 0, start_time, completion_time))
        pending.remove(job)
        current_time = completion_time

    schedule = Schedule(assignments, algorithm=algorithm)
    schedule.validate()
    return schedule


def schedule_by_rule(
    jobs: Sequence[Job],
    priority_fn: PriorityKey,
    *,
    dynamic: bool = False,
    algorithm: str | None = None,
) -> Schedule:
    """Apply one priority rule in static or release-aware dynamic mode."""
    mode = "dynamic" if dynamic else "static"
    algorithm = algorithm or f"{mode}_rule"
    if dynamic:
        return schedule_dynamic_rule(jobs, priority_fn, algorithm=algorithm)
    return schedule_static_rule(jobs, priority_fn, algorithm=algorithm)


def fcfs(jobs: Sequence[Job], *, dynamic: bool = False) -> Schedule:
    """先到先服务。"""
    return schedule_by_rule(jobs, fcfs_key, dynamic=dynamic,
                            algorithm=f"{'dynamic' if dynamic else 'static'}_fcfs")


def spt(jobs: Sequence[Job], *, dynamic: bool = False) -> Schedule:
    """最短加工时间优先。"""
    return schedule_by_rule(jobs, spt_key, dynamic=dynamic,
                            algorithm=f"{'dynamic' if dynamic else 'static'}_spt")


def lpt(jobs: Sequence[Job], *, dynamic: bool = False) -> Schedule:
    """最长加工时间优先。"""
    return schedule_by_rule(jobs, lpt_key, dynamic=dynamic,
                            algorithm=f"{'dynamic' if dynamic else 'static'}_lpt")


def edd(jobs: Sequence[Job], *, dynamic: bool = False) -> Schedule:
    """最早交期优先；无交期任务在有交期任务后。"""
    return schedule_by_rule(jobs, edd_key, dynamic=dynamic,
                            algorithm=f"{'dynamic' if dynamic else 'static'}_edd")


def wspt(jobs: Sequence[Job], *, dynamic: bool = False) -> Schedule:
    """加工时间与权重之比升序；要求权重为正。"""
    return schedule_by_rule(jobs, wspt_key, dynamic=dynamic,
                            algorithm=f"{'dynamic' if dynamic else 'static'}_wspt")
