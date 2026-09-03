from dataclasses import dataclass

@dataclass
class Job:
    job_id: str
    processing_time: int
    release_time: int = 0
    due_date: int = 0
    priority: int = 0

    def __post_init__(self):
        if self.processing_time <= 0:
            raise ValueError(
                "processing_time must be greater than 0"
            )

        if self.release_time < 0:
            raise ValueError(
                "release_time cannot be negative"
            )

    def is_long_job(self):
        return self.processing_time >= 5

    def calculate_finish_time(self, start_time):
        return start_time + self.processing_time


if __name__ == "__main__":
    job1 = Job('J1', 3)
    print(job1)

    try:
        job2 = Job('J2', -5)
    except ValueError as e:
        print(e)  
