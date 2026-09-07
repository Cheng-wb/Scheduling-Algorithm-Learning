from job import Job
from scheduler import *
from metrics import evaluate_schedule
from tabulate import tabulate

def create_jobs():
    return [
        Job("J1", processing_time=5, due_date=7),
        Job("J2", processing_time=2, due_date=4),
        Job("J3", processing_time=8, due_date=15),
        Job("J4", processing_time=3, due_date=6),
        Job("J5", processing_time=6, due_date=12),
    ]

# fcfs

fcfs_jobs = fcfs( create_jobs() )
fcfs_result = schedule_jobs(fcfs_jobs)

# spt
spt_jobs = spt( create_jobs() )
spt_result = schedule_jobs(spt_jobs)

# lpt
lpt_jobs = lpt( create_jobs() )
lpt_result = schedule_jobs(lpt_jobs)

# 准备数据
headers = [
    "Algorithm", 
    "Makespan", 
    "Avg_Completion", 
    "Avg_Flow_time", 
    "Avg_Tardiness", 
    "Max_Tardiness"
]

data = []
for result, algo in zip([fcfs_result, spt_result, lpt_result], ["FCFS", "SPT", "LPT"]):
    metrics = evaluate_schedule(result)
    data.append([
        algo,
        metrics['makespan'],
        f"{metrics['average_completion_time']:.2f}",
        f"{metrics['average_flow_time']:.2f}",
        f"{metrics['average_tardiness']:.2f}",
        metrics['max_tardiness']
    ])

# 打印表格
print(tabulate(data, headers=headers, tablefmt="grid"))