from dataclasses import dataclass


@dataclass
class Job:
    job_id: str
    processing_time: int
    release_time: int = 0
    due_date: int = 0

    start_time: int = 0
    completion_time: int = 0

    def __post_init__(self):
        if self.release_time < 0:
            raise ValueError("Release time must be a non-negative integer")
        if self.processing_time <= 0:
            raise ValueError("Processing time must be a positive integer")

    @property
    def flow_time(self):
        return self.completion_time - self.release_time

    @property
    def tardiness(self):
        return max(0, self.completion_time - self.due_date)