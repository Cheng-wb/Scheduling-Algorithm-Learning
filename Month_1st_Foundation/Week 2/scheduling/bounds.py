"""相同并行机、全部任务在零时刻可用时的 Makespan 下界。"""

from math import ceil


def parallel_machine_lower_bound(jobs, num_machines):
    if type(num_machines) is not int or num_machines <= 0:
        raise ValueError("num_machines must be a positive integer")
    if any(job.release_time != 0 for job in jobs):
        raise ValueError("this bound assumes zero release times")
    average = sum(job.processing_time for job in jobs) / num_machines
    if all(float(job.processing_time).is_integer() for job in jobs):
        average = ceil(average)
    return max(average, max((job.processing_time for job in jobs), default=0))
