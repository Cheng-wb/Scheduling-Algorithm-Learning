from scheduler import schedule_jobs
from metrics import evaluate_schedule
from job import Job


job1 = Job(
    job_id="J1",
    processing_time=5,
    due_date=10
)

job2 = Job(
    job_id="J2",
    processing_time=2,
    due_date=10
)

job3 = Job(
    job_id="J3",
    processing_time=4,
    due_date=8
)

jobs = [job1, job2, job3]

scheduled_jobs = schedule_jobs(jobs)
metrics = evaluate_schedule(scheduled_jobs)
print(metrics)

jobs2 = [job2, job1, job3]
scheduled_jobs2 = schedule_jobs(jobs2)
metrics2 = evaluate_schedule(scheduled_jobs2)
print(metrics2)