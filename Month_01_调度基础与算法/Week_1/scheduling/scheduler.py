"""固定顺序的单机排程构造，可供后续排序规则复用。"""

from collections.abc import Sequence

from .models import Job, Schedule, ScheduledJob


def schedule_sequence(sequence: Sequence[str], jobs: Sequence[Job], machine_id: int = 0) -> Schedule:
    """严格按指定顺序尽早开工；任务未释放时等待，不跳过。"""

    jobs_by_id = {job.job_id: job for job in jobs}
    if len(jobs_by_id) != len(jobs):
        raise ValueError("jobs contains duplicate job IDs")

    if len(sequence) != len(set(sequence)) or set(sequence) != set(jobs_by_id):
        raise ValueError("sequence must contain every job exactly once")

    assignments = []
    current_time = 0

    for job_id in sequence:
        job = jobs_by_id[job_id]
        start = max(current_time, job.release_time)
        current_time = start + job.processing_time
        assignments.append(ScheduledJob(job, machine_id, start, current_time))
    return Schedule(assignments, algorithm="fixed_sequence")
