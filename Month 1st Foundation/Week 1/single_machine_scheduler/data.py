from job import Job


def create_jobs():
    return [
        Job(job_id="J1", processing_time=5, due_date=7),
        Job(job_id="J2", processing_time=2, due_date=4),
        Job(job_id="J3", processing_time=8, due_date=15),
        Job(job_id="J4", processing_time=3, due_date=6),
        Job(job_id="J5", processing_time=6, due_date=12),
    ]
