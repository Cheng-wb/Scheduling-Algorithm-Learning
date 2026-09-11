"""派工规则只返回新的任务顺序，不计算时间或指标。"""

from collections.abc import Sequence
from random import Random

from models.job import Job


def random_solution(jobs: Sequence[Job], rng: Random | None = None) -> list[Job]:
    """复制后打乱；传入同一个局部 RNG 可连续生成可复现的不同起点。"""
    solution = list(jobs)
    (rng if rng is not None else Random()).shuffle(solution)
    return solution


def fcfs(jobs: Sequence[Job]) -> list[Job]:
    """按释放时间升序；同时到达时保留输入顺序。"""
    return sorted(jobs, key=lambda job: job.release_time)


def spt(jobs: Sequence[Job]) -> list[Job]:
    """短任务优先；加工时间相同时按 job_id 字典序。"""
    return sorted(jobs, key=lambda job: (job.processing_time, job.job_id))


def lpt(jobs: Sequence[Job]) -> list[Job]:
    """长任务优先；加工时间相同时按 job_id 字典序。"""
    return sorted(jobs, key=lambda job: (-job.processing_time, job.job_id))


def edd(jobs: Sequence[Job]) -> list[Job]:
    """交期升序；缺少交期的任务排最后，同优先级按 job_id 字典序。"""
    return sorted(jobs, key=lambda job: (
        float("inf") if job.due_date is None else job.due_date, job.job_id,
    ))


RULES = {"fcfs": fcfs, "spt": spt, "lpt": lpt, "edd": edd}


def dispatch(jobs: Sequence[Job], rule: str) -> list[Job]:
    if rule not in RULES:
        raise ValueError(f"unknown rule {rule!r}; choose from {', '.join(RULES)}")
    return RULES[rule](jobs)
