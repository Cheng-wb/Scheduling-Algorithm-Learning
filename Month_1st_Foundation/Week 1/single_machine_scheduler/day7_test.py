from job import Job
from scheduler import schedule_jobs
from metrics import evaluate_schedule
from rules import fcfs, spt, lpt, edd
from main import single_machine_scheduling

# =========================== test A ==========================
jobs_a = [
    Job('J1', processing_time=4),
    Job('J2', processing_time=5),
    Job('J3', processing_time=3),
    Job('J4', processing_time=4),
    Job('J5', processing_time=5)
]

algorithms_a = {
    "FCFS": fcfs,
    "SPT": spt,
    "LPT": lpt,
}

single_machine_scheduling(jobs_a, algorithms_a, show_schedule=False)


# =========================== test B ==========================
jobs_b = [
    Job('J1', processing_time=20),
    Job('J2', processing_time=2),
    Job('J3', processing_time=1),
    Job('J4', processing_time=3),
    Job('J5', processing_time=2)
]

algorithms_b = {
    "FCFS": fcfs,
    "SPT": spt,
    "LPT": lpt,
}

single_machine_scheduling(jobs_b, algorithms_b, show_schedule=False)

# =========================== test C ==========================
jobs_c = [
    Job('J1', processing_time=6, due_date=20),
    Job('J2', processing_time=2, due_date=3),
    Job('J3', processing_time=5, due_date=8),
    Job('J4', processing_time=3, due_date=5)
]

algorithms_c = {
    "FCFS": fcfs,
    "SPT": spt,
    "LPT": lpt,
    "EDD": edd
}

single_machine_scheduling(jobs_c, algorithms_c, show_schedule=False)



