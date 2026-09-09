"""相同并行机列表调度：扫描机器负载，不使用优先队列。"""

from collections.abc import Sequence

from ..models import Job, Schedule, ScheduledJob
from .rules import lpt_key


def list_schedule(jobs: Sequence[Job], num_machines: int) -> Schedule:
    """按给定顺序分配至最小负载机器；要求所有任务在 0 时刻可用。"""
    jobs = list(jobs)
    if type(num_machines) is not int or num_machines <= 0:
        raise ValueError("num_machines must be a positive integer")
    if len({job.job_id for job in jobs}) != len(jobs):
        raise ValueError("job IDs must be unique")
    if any(job.release_time != 0 for job in jobs):
        raise ValueError("list scheduling requires release_time == 0 for every job")

    machine_loads = [0.0] * num_machines
    assignments = []
    for job in jobs:
        # min 在并列时保留第一个编号，使分配可复现。
        machine_id = min(range(num_machines), key=lambda j: machine_loads[j])
        start = machine_loads[machine_id]
        completion = start + job.processing_time
        assignments.append(ScheduledJob(job, machine_id, start, completion))
        machine_loads[machine_id] = completion

    schedule = Schedule(assignments, algorithm="list_scheduling", machine_count=num_machines)
    schedule.validate()
    return schedule


def greedy_list_scheduling(jobs: Sequence[Job], num_machines: int) -> Schedule:
    """保留输入顺序的 Greedy 列表调度。"""
    schedule = list_schedule(jobs, num_machines)
    schedule.algorithm = "greedy_list_scheduling"
    return schedule


def lpt_list_scheduling(jobs: Sequence[Job], num_machines: int) -> Schedule:
    """加工时间降序后执行列表调度；不修改输入列表。"""
    schedule = list_schedule(sorted(jobs, key=lpt_key), num_machines)
    schedule.algorithm = "lpt_list_scheduling"
    return schedule
