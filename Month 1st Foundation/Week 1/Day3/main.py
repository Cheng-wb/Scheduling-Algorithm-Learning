from job import Job
from operation import Operation
from machine import Machine
from utils import *


job1 = Job(
    job_id="J1",
    operations=[
        Operation("O11", "M1", 3),
        Operation("O12", "M2", 5),
        Operation("O13", "M3", 2)
    ]
)

job2 = Job(
    job_id="J2",
    operations=[
        Operation("O21", "M2", 4),
        Operation("O22", "M1", 3),
        Operation("O23", "M3", 5)
    ]
)

job3 = Job(
    job_id="J3",
    operations=[
        Operation("O31", "M3", 2),
        Operation("O32", "M1", 4),
        Operation("O33", "M2", 3)
    ]
)

Jobs = [job1, job2, job3]
print(f"Total operations across all jobs: {get_total_operations(Jobs)}")

job1_total_time = get_job_total_processing_time(job1)
print(f"Total processing time for job {job1.job_id}: {job1_total_time}")

machine = Machine("M1")
operations_on_machine = get_operations_by_machine(Jobs, machine.machine_id)
print(f"Operations on machine {machine.machine_id}: {operations_on_machine}")
