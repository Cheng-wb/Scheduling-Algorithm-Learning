
def get_job_total_processing_time(job):
    return sum(op.processing_time for op in job.operations)

def get_total_operations(jobs):
    return sum(len(job.operations) for job in jobs)

def get_operations_by_machine(jobs, machine_id):
    operations = []
    for job in jobs:
        for op in job.operations:
            if op.machine_id == machine_id:
                operations.append(op.operation_id)
    return operations