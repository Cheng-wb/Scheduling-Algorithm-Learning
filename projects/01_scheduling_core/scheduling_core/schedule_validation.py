"""独立验证结果，不调用 decoder，也不信任结果顺序。"""

from collections import Counter

from scheduling_core.models import Instance
from scheduling_core.schedule import Schedule
from scheduling_core.validation import validate_instance


def schedule_errors(instance: Instance, schedule: Schedule) -> list[str]:
    validate_instance(instance)
    errors = []
    operations = {op.id: op for op in instance.operations}
    jobs = {job.id: job for job in instance.jobs}
    machines = {machine.id for machine in instance.machines}
    counts = Counter(item.operation_id for item in schedule.operations)
    for oid in operations:
        if counts[oid] == 0:
            errors.append(f"missing: {oid}")
        elif counts[oid] > 1:
            errors.append(f"duplicate: {oid}")
    valid_times = []
    for item in schedule.operations:
        if item.operation_id not in operations:
            errors.append(f"unknown operation: {item.operation_id}")
            continue
        op = operations[item.operation_id]
        if (
            item.machine_id not in machines
            or item.machine_id not in op.eligible_machine_ids
        ):
            errors.append(f"illegal assignment: {op.id}")
        if type(item.start_time) is not int or type(item.end_time) is not int:
            errors.append(f"invalid time type: {op.id}")
            continue
        valid_times.append(item)
        if item.start_time < 0 or item.end_time - item.start_time != op.processing_time:
            errors.append(f"duration: {op.id}")
        if item.start_time < jobs[op.job_id].release_time:
            errors.append(f"release: {op.id}")
    by_id = {item.operation_id: item for item in valid_times}
    for job in instance.jobs:
        for before, after in zip(job.operation_ids, job.operation_ids[1:]):
            if (
                before in by_id
                and after in by_id
                and by_id[before].end_time > by_id[after].start_time
            ):
                errors.append(f"precedence: {before} -> {after}")
    for machine in machines:
        timeline = sorted(
            (item for item in valid_times if item.machine_id == machine),
            key=lambda item: item.start_time,
        )
        frontier = 0
        for item in timeline:
            if item.start_time < frontier:
                errors.append(f"overlap: {machine}/{item.operation_id}")
            frontier = max(frontier, item.end_time)
    return errors


def validate_schedule(instance: Instance, schedule: Schedule) -> None:
    errors = schedule_errors(instance, schedule)
    if errors:
        raise ValueError("; ".join(errors))
