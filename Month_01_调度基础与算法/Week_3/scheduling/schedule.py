from dataclasses import dataclass
from math import isclose
from collections.abc import Sequence

from models.job import Job, _finite
from models.machine import Machine


@dataclass(frozen=True)
class ScheduledJob:
    job: Job
    machine_id: int
    start_time: float
    completion_time: float


    def __post_init__(self):
        Machine(self.machine_id)
        _finite("start_time", self.start_time)
        _finite("completion_time", self.completion_time)
        if self.start_time < self.job.release_time:
            raise ValueError("a job cannot start before its release time")
        if self.completion_time <= self.start_time or not isclose(
            self.completion_time - self.start_time, self.job.processing_time,
            rel_tol=1e-9, abs_tol=1e-9,
        ):
            raise ValueError("completion_time must equal start_time + processing_time")

    @property
    def flow_time(self) -> float:
        return self.completion_time - self.job.release_time

    @property
    def lateness(self) -> float | None:
        if self.job.due_date is None:
            return None
        return self.completion_time - self.job.due_date

    @property
    def tardiness(self) -> float | None:
        if self.job.due_date is None:
            return None
        return max(0, self.completion_time - self.job.due_date)

    @property
    def waiting_time(self) -> float:
        return self.start_time - self.job.release_time


@dataclass
class Schedule:
    assignments: list[ScheduledJob]
    algorithm: str | None = None
    machine_count: int = 1

    def validate(self) -> None:
        """检查重复任务、机器编号与同机重叠，允许不同机器同时加工。"""
        if type(self.machine_count) is not int or self.machine_count <= 0:
            raise ValueError("machine_count must be a positive integer")

        seen = set()
        machine_end = {}
        for item in sorted(self.assignments, key=lambda item: item.start_time):
            if item.job.job_id in seen:
                raise ValueError("a job can only be scheduled once")
            seen.add(item.job.job_id)
            if item.machine_id >= self.machine_count:
                raise ValueError("machine_id is outside the available machines")
            if item.start_time < machine_end.get(item.machine_id, 0):
                raise ValueError("jobs on the same machine cannot overlap")
            machine_end[item.machine_id] = item.completion_time


def build_schedule(ordered_jobs: Sequence[Job]) -> Schedule:
    """严格按输入顺序尽早开工，遇到未释放任务时等待。"""
    if len({job.job_id for job in ordered_jobs}) != len(ordered_jobs):
        raise ValueError("job IDs must be unique")
    current_time = 0
    assignments = []
    for job in ordered_jobs:
        start = max(current_time, job.release_time)
        current_time = start + job.processing_time
        assignments.append(ScheduledJob(job, 0, start, current_time))
    return Schedule(assignments, algorithm="fixed_sequence", machine_count=1)
