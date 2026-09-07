
def schedule_jobs(jobs):
    current_time = 0

    for job in jobs:
        job.start_time = max(current_time, job.release_time)
        job.completion_time = job.start_time + job.processing_time
        current_time = job.completion_time

    return jobs