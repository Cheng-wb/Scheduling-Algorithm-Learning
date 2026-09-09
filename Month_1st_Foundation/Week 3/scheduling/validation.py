"""将排程与原始任务核对；合法时返回 None，非法时抛出 ValueError。"""

from collections import Counter
from collections.abc import Sequence

from models.job import Job
from .schedule import Schedule


def validate_all_jobs_scheduled(schedule: Schedule, jobs: Sequence[Job]) -> None:
    expected = {job.job_id: job for job in jobs}
    if len(expected) != len(jobs):
        raise ValueError("input job IDs must be unique")
    actual = Counter(item.job.job_id for item in schedule.assignments)
    if actual != Counter(expected.keys()):
        raise ValueError("schedule must contain every input job exactly once")
    if any(item.job != expected[item.job.job_id] for item in schedule.assignments):
        raise ValueError("scheduled job attributes differ from the input")


def validate_schedule(schedule: Schedule, jobs: Sequence[Job]) -> None:
    """核对任务覆盖和属性，复用模型中的时长、释放时间及资源约束检查。"""
    validate_all_jobs_scheduled(schedule, jobs)
    for item in schedule.assignments:
        item.__post_init__()
    schedule.validate()
