
def get_jobs_num(jobs):
    return len(jobs)

def get_total_processing_time(jobs):
    return sum(job.processing_time for job in jobs)

def get_average_processing_time(jobs):
    total_time = get_total_processing_time(jobs)
    num_jobs = get_jobs_num(jobs)
    return total_time / num_jobs if num_jobs > 0 else 0

def get_shortest_job(jobs):
    return min(jobs, key=lambda job: job.processing_time) if jobs else None

def get_longest_job(jobs):
    return max(jobs, key=lambda job: job.processing_time) if jobs else None

def sort_by_processing_time_ascending(jobs):
    return sorted(jobs, key=lambda job: job.processing_time)

def sort_by_processing_time_descending(jobs):
    return sorted(jobs, key=lambda job: job.processing_time, reverse=True)

def sort_by_priority(jobs):
    return sorted(jobs, key=lambda job: job.priority, reverse=True)
