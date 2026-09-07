from dataclasses import dataclass
from job import Job

@dataclass
class Machine:
    machine_id: str
    available_time: int = 0

    def process_job(self, job: Job):
        start_time = max(self.available_time, job.release_time)
        finish_time = start_time + job.processing_time
        self.available_time = finish_time
        return start_time, finish_time

    def reset(self):
        self.available_time = 0