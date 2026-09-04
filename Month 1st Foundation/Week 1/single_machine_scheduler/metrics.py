def calculate_makespan(jobs):
    if not jobs:
        return 0
    return max(job.completion_time for job in jobs)


def calculate_average_completion_time(jobs):
    if not jobs:
        return 0
    return sum(job.completion_time for job in jobs) / len(jobs)


def calculate_average_flow_time(jobs):
    if not jobs:
        return 0
    return sum(job.flow_time for job in jobs) / len(jobs)

def calculate_average_tardiness(jobs):
    if not jobs:
        return 0
    return sum(job.tardiness for job in jobs) / len(jobs)

def calculate_max_tardiness(jobs):
    if not jobs:
        return 0
    return max(job.tardiness for job in jobs)


def evaluate_schedule(jobs):
    return {
        "makespan": calculate_makespan(jobs),
        "average_completion_time": calculate_average_completion_time(jobs),
        "average_flow_time": calculate_average_flow_time(jobs),
        "average_tardiness": calculate_average_tardiness(jobs),     
        "max_tardiness": calculate_max_tardiness(jobs),
    }
