"""单工序极小实例穷举：独立于 decoder，regular 目标下证明最优。

固定每台机器上的任务顺序后，最早开工不会恶化本月三种目标。
全局排列与指派的笛卡尔积覆盖所有机器顺序；重复覆盖只影响速度。
"""

from itertools import permutations, product
from math import factorial, prod

from scheduling_core.models import Instance
from scheduling_core.schedule import Schedule, ScheduledOperation
from scheduling_algorithms.search import OBJECTIVES
from scheduling_core.validation import validate_instance


def exhaustive_optimum(
    instance: Instance, objective: str = "makespan", limit: int = 100_000
) -> tuple[float, Schedule, int]:
    validate_instance(instance)
    if any(len(job.operation_ids) != 1 for job in instance.jobs):
        raise ValueError("oracle supports only one operation per job")
    size = factorial(len(instance.operations)) * prod(
        len(op.eligible_machine_ids) for op in instance.operations
    )
    if size > limit:
        raise ValueError(f"enumeration too large: {size} > {limit}")
    jobs = {job.id: job for job in instance.jobs}
    best_value = float("inf")
    best_schedule = Schedule(())
    count = 0
    for assignments in product(
        *(op.eligible_machine_ids for op in instance.operations)
    ):
        for order in permutations(range(len(instance.operations))):
            available = {machine.id: 0 for machine in instance.machines}
            output = []
            for index in order:
                op = instance.operations[index]
                machine = assignments[index]
                start = max(available[machine], jobs[op.job_id].release_time)
                end = start + op.processing_time
                output.append(ScheduledOperation(op.id, machine, start, end))
                available[machine] = end
            schedule = Schedule(tuple(output))
            value = float(OBJECTIVES[objective](instance, schedule))
            count += 1
            if value < best_value:
                best_value, best_schedule = value, schedule
    return best_value, best_schedule, count
