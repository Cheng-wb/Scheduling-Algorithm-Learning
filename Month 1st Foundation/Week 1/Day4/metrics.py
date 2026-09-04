
def makespan(jobs):
    return max(job.completion_time for job in jobs)

def average_completion_time(jobs):
    return sum(job.completion_time for job in jobs) / len(jobs) if jobs else 0

def average_flow_time(jobs):
    return sum(job.flow_time for job in jobs) / len(jobs) if jobs else 0

def average_tardiness(jobs):
    return sum(job.tardiness for job in jobs) / len(jobs) if jobs else 0

def max_tardiness(jobs):
    return max(job.tardiness for job in jobs) if jobs else 0


def evaluate_schedule(jobs):
    return {
        "makespan": makespan(jobs),
        "average_completion_time": average_completion_time(jobs),
        "average_flow_time": average_flow_time(jobs),
        "average_tardiness": average_tardiness(jobs),
        "max_tardiness": max_tardiness(jobs)
    }