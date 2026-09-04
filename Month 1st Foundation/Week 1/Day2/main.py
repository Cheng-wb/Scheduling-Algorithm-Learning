from job import Job
from machine import Machine
from utils import *


jobs = [
    Job('J1', 3, 0, 10, 1),
    Job('J2', 5, 0, 15, 2),
    Job('J3', 2, 0, 8, 3),
    Job('J4', 7, 0, 20, 4),
    Job('J5', 1, 0, 5, 5)
]


M1 = Machine('M1')

print(f"Machine {M1.machine_id}")

print(f"{'job':^10}{'processing_time':^20}{'start_time':^20}{'finish_time':^20}")

for job in jobs:
    start_time, finish_time = M1.process_job(job)
    print(f"{job.job_id:^10}{job.processing_time:^20}{start_time:^20}{finish_time:^20}")

print(f"Machine {M1.machine_id} available time: {M1.available_time}")

# 重置机器
M1.reset()

# 先排序再处理
sorted_jobs = sort_by_processing_time_ascending(jobs)
print(f"Machine {M1.machine_id}")

print(f"{'job':^10}{'processing_time':^20}{'start_time':^20}{'finish_time':^20}")

for job in sorted_jobs:
    start_time, finish_time = M1.process_job(job)
    print(f"{job.job_id:^10}{job.processing_time:^20}{start_time:^20}{finish_time:^20}")

print(f"Machine {M1.machine_id} available time: {M1.available_time}")
