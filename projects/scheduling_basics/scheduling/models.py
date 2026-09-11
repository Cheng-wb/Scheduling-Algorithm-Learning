"""统一的任务输入和排程输出；当前每个任务只有一道不可抢占工序。"""

from dataclasses import dataclass
from math import isclose, isfinite


def _finite(name, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number")


@dataclass(frozen=True)
class Job:
    job_id: str
    processing_time: float
    release_time: float = 0
    due_date: float | None = None
    weight: float = 1

    def __post_init__(self):
        if not isinstance(self.job_id, str) or not self.job_id.strip():
            raise ValueError("job_id must be a non-empty string")
        for name in ("processing_time", "release_time", "weight"):
            _finite(name, getattr(self, name))
        if self.due_date is not None:
            _finite("due_date", self.due_date)
        if self.processing_time <= 0:
            raise ValueError("processing_time must be positive")
        if self.release_time < 0 or self.weight < 0:
            raise ValueError("release_time and weight must be non-negative")


@dataclass(frozen=True)
class ScheduledJob:
    job: Job
    machine_id: int
    start_time: float
    completion_time: float


    def __post_init__(self):
        if type(self.machine_id) is not int or self.machine_id < 0:
            raise ValueError("machine_id must be a non-negative integer")
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
