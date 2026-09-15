"""标准库局部 RNG；生成器不修改全局随机状态。"""

from random import Random

from .models import Instance, Job, Machine, Operation


def generate_instance(
    seed: int,
    jobs: int = 12,
    machines: int = 3,
    operations_per_job: int = 1,
    release_max: int = 10,
    due_factor: float = 1.5,
) -> Instance:
    if (
        min(jobs, machines, operations_per_job) < 1
        or release_max < 0
        or due_factor <= 0
    ):
        raise ValueError("invalid generator parameters")
    rng = Random(seed)
    resources = tuple(Machine(f"M{i}", f"Machine {i}") for i in range(machines))
    machine_ids = tuple(machine.id for machine in resources)
    tasks: list[Operation] = []
    orders = []
    for j in range(jobs):
        jid = f"J{j:03}"
        route = tuple(f"{jid}_O{k}" for k in range(operations_per_job))
        processing = [rng.randint(1, 20) for _ in route]
        release = rng.randint(0, release_max)
        orders.append(
            Job(
                jid,
                route,
                release,
                release + int(sum(processing) * due_factor),
                float(rng.randint(1, 5)),
            )
        )
        tasks.extend(
            Operation(oid, jid, p, machine_ids)
            for oid, p in zip(route, processing, strict=True)
        )
    return Instance(tuple(orders), tuple(tasks), resources)
