def fcfs(jobs):
    return list(jobs)


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

def edd(jobs):
    return sorted(
        jobs,
        key=lambda job: job.due_date
    )