
def schedule_jobs(jobs):
    current_time = 0

    for job in jobs:
        job.start_time = max(current_time, job.release_time)
        job.completion_time = job.start_time + job.processing_time
        current_time = job.completion_time

    return jobs

def fcfs(jobs):
    return jobs.copy()

def spt(jobs):
    return sorted(
        jobs,
        key=lambda job: job.processing_time
    )

def lpt(jobs):
    return sorted(
        jobs,
        key=lambda job: job.processing_time,
        reverse=True
    )