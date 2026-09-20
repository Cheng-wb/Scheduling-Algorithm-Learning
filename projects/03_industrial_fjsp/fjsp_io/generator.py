"""可复现实例生成器：一个入口覆盖 Flow Shop / JSP / FJSP 与工业约束。

用局部 ``Random(seed)``，**不修改全局随机状态**——与 M1 同一条纪律。

四个旋钮决定问题族：

```text
flexibility = 1 且 flow_shop = True   → Flow Shop（所有订单同一条机器序列）
flexibility = 1 且 flow_shop = False  → Job Shop （每道工序固定一台机器，路径不同）
flexibility >= 2                      → FJSP     （同一工序可在多台机器上做，工时不同）
再加上 setup_families / calendar / maintenance / workers / locked 就是工业约束实例
```

**为什么工时随机器变化？** 这正是 FJSP 的定义特征。生成时给定「基准工时」，
再对每台附加机器施加一个乘性扰动，保证同一工序在不同机器上确实不同——
否则 `flexibility >= 2` 会退化成「有选择但选谁都一样」，实验就测不出机器选择的
价值了。
"""

from __future__ import annotations

from random import Random

from fjsp_core.models import (
    Calendar,
    FJSPInstance,
    Job,
    Machine,
    Maintenance,
    Operation,
    Qualification,
    Setup,
    Worker,
)


def generate_instance(
    seed: int,
    jobs: int = 6,
    machines: int = 4,
    operations_per_job: int = 3,
    *,
    flexibility: int = 2,
    flow_shop: bool = False,
    release_max: int = 0,
    due_factor: float | None = 1.6,
    setup_families: int = 0,
    calendar_windows: int = 0,
    maintenance_count: int = 0,
    worker_count: int = 0,
    locked_count: int = 0,
    time_min: int = 1,
    time_max: int = 20,
    setup_min: int = 1,
    setup_max: int = 5,
) -> FJSPInstance:
    """生成一个可复现的实例。参数非法时抛 ``ValueError``。"""
    if min(jobs, machines, operations_per_job) < 1:
        raise ValueError("jobs / machines / operations_per_job must be >= 1")
    if not 1 <= flexibility <= machines:
        raise ValueError("flexibility must be between 1 and the machine count")
    if release_max < 0:
        raise ValueError("release_max must be >= 0")
    if due_factor is not None and due_factor <= 0:
        raise ValueError("due_factor must be > 0")
    if time_min < 1 or time_max < time_min:
        raise ValueError("need 1 <= time_min <= time_max")
    if not 0 <= calendar_windows <= 1:
        raise ValueError("calendar_windows is 0 (none) or 1 (a single window)")

    rng = Random(seed)
    machine_ids = [f"M{i}" for i in range(machines)]
    resources = tuple(Machine(mid, f"Machine {i}", group=f"G{i % 2}")
                      for i, mid in enumerate(machine_ids))

    # --- 工序族与换型矩阵 --------------------------------------------------
    families = [f"F{i}" for i in range(setup_families)]
    setups: list[Setup] = []
    if setup_families:
        for a in families:
            for b in families:
                if a != b:
                    setups.append(Setup(a, b, rng.randint(setup_min, setup_max)))

    # --- 订单与工序 --------------------------------------------------------
    orders: list[Job] = []
    tasks: list[Operation] = []
    routes: dict[str, list[Operation]] = {}

    for j in range(jobs):
        job_id = f"J{j:03}"
        route_times: list[int] = []
        route_ops: list[Operation] = []
        for k in range(operations_per_job):
            op_id = f"{job_id}_O{k}"
            base = rng.randint(time_min, time_max)
            if flow_shop:
                # 所有订单同一条机器序列：第 k 道在第 k % machines 台机器上，且固定
                chosen = [machine_ids[k % machines]]
            elif flexibility == 1:
                chosen = [rng.choice(machine_ids)]
            else:
                chosen = rng.sample(machine_ids, flexibility)

            machine_times: list[tuple[str, int]] = []
            for index, machine_id in enumerate(chosen):
                if index == 0 or flexibility == 1:
                    minutes = base
                else:
                    # 乘性扰动：保证「不同机器工时确实不同」，否则机器选择没有区分度
                    factor = rng.choice([0.6, 0.8, 1.25, 1.6, 2.0])
                    minutes = max(1, round(base * factor))
                machine_times.append((machine_id, minutes))
            machine_times.sort()  # 确定性：按机器 id 升序

            family = rng.choice(families) if families else None
            route_ops.append(
                Operation(op_id, job_id, k, tuple(machine_times), family=family)
            )
            route_times.append(min(t for _, t in machine_times))

        release = rng.randint(0, release_max) if release_max else 0
        total = sum(route_times)
        due = release + int(total * due_factor) if due_factor is not None else None
        orders.append(
            Job(
                job_id,
                tuple(op.id for op in route_ops),
                release,
                due,
                float(rng.randint(1, 5)),
                0,
            )
        )
        tasks.extend(route_ops)
        routes[job_id] = route_ops

    # --- 锁定工序（WIP） ---------------------------------------------------
    if locked_count:
        if locked_count > len(tasks):
            raise ValueError("locked_count exceeds the operation count")
        for op in rng.sample(tasks, locked_count):
            # frozen dataclass：用 replace 生成新对象
            index = tasks.index(op)
            tasks[index] = _with_lock(op, rng.choice(op.eligible_machine_ids))

    # --- 日历 --------------------------------------------------------------
    calendars: tuple[Calendar, ...] = ()
    if calendar_windows:
        horizon = max((job.due_date or 0) for job in orders) + 50
        calendars = (Calendar("CAL0", ((0, max(1, horizon // 2)), (horizon // 2 + 10, horizon))),)
        resources = tuple(
            Machine(m.id, m.name, "CAL0", m.group) for m in resources
        )

    # --- 维护 --------------------------------------------------------------
    maintenances: list[Maintenance] = []
    for i in range(maintenance_count):
        machine_id = machine_ids[i % machines]
        start = 5 + i * 7
        maintenances.append(Maintenance(f"MT{i}", machine_id, ((start, start + 3),)))

    # --- 资质 --------------------------------------------------------------
    qualifications: tuple[Qualification, ...] = ()
    if families:
        qualifications = tuple(
            Qualification(mid, family) for mid in machine_ids for family in families
        )

    # --- 次生资源 ----------------------------------------------------------
    workers: tuple[Worker, ...] = ()
    if worker_count:
        workers = tuple(
            Worker(f"W{i}", f"Worker {i}", (), 1) for i in range(worker_count)
        )

    return FJSPInstance(
        jobs=tuple(orders),
        operations=tuple(tasks),
        machines=resources,
        calendars=calendars,
        maintenances=tuple(maintenances),
        qualifications=qualifications,
        workers=workers,
        setups=tuple(setups),
        meta={
            "seed": seed,
            "jobs": jobs,
            "machines": machines,
            "operations_per_job": operations_per_job,
            "flexibility": flexibility,
            "flow_shop": flow_shop,
        },
    )


def _with_lock(op: Operation, machine_id: str) -> Operation:
    """返回一个「锁定到指定机器」的副本（``frozen`` 不可原地修改）。"""
    from dataclasses import replace

    return replace(op, locked_machine_id=machine_id)
