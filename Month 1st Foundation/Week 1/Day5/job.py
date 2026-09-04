from dataclasses import dataclass


@dataclass
class Job:
    job_id: str
    processing_time: int

    release_time: int = 0
    due_date: int = 0

    start_time: int = 0
    completion_time: int = 0

    @property
    def flow_time(self):
        return (
            self.completion_time
            - self.release_time
        )

    @property
    def lateness(self):
        return (
            self.completion_time
            - self.due_date
        )

    @property
    def tardiness(self):
        return max(
            0,
            self.lateness
        )
    