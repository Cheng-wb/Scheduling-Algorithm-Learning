"""优先级越小越先加工；本模块只定义排序键，不生成排程。"""

from collections.abc import Callable

from ..models import Job

PriorityKey = Callable[[Job], tuple]


def fcfs_key(job: Job) -> tuple:
    """先释放先加工；同一时刻释放时由稳定选择保留输入顺序。"""
    return (job.release_time,)


def spt_key(job: Job) -> tuple:
    """Shortest processing time first."""
    return job.processing_time, job.release_time, job.job_id


def lpt_key(job: Job) -> tuple:
    """Longest processing time first."""
    return -job.processing_time, job.release_time, job.job_id


def edd_key(job: Job) -> tuple:
    """Earliest due date first; jobs without a due date go last."""
    due_date = float("inf") if job.due_date is None else job.due_date
    return due_date, job.release_time, job.job_id


def wspt_key(job: Job) -> tuple:
    """Weighted shortest processing time: p / w ascending."""
    if job.weight <= 0:
        raise ValueError("WSPT requires every job to have positive weight")
    return job.processing_time / job.weight, job.release_time, job.job_id
