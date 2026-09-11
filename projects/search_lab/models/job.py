"""统一的任务输入和排程输出；当前每个任务只有一道不可抢占工序。"""

from dataclasses import dataclass
from math import isfinite


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
