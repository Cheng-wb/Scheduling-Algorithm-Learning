"""独立排程验证器：工业约束下的可行性判定。

**独立性契约**（与 M1 一脉相承）：

* 不调用任何解码器或求解器；
* 不假设 ``Schedule.operations`` 按时间排序，也不假设它的顺序有意义；
* 不读取任何算法内部状态；
* 接受任意工序列表顺序。

十一项检查，任何一项单独成立都不够：

| # | 检查 | 诊断标签 |
|---|---|---|
| 1 | 每道工序恰好出现一次 | `missing` / `duplicate` / `unknown operation` |
| 2 | 机器存在且在该工序的 ``machine_times`` 里 | `illegal assignment` |
| 3 | 时刻为整数、``start >= 0``、``end - start = p_ij`` | `invalid time type` / `duration` |
| 4 | 开工不早于所属订单的释放时刻 | `release` |
| 5 | 同一订单内相邻工序满足 ``end(before) <= start(after)`` | `precedence` |
| 6 | 同机器区间不重叠 | `overlap` |
| 7 | 工序落在机器的**日历可用窗**内 | `calendar` |
| 8 | 工序不与**计划维护窗**重叠 | `maintenance` |
| 9 | 机器有该工序族的**资质**（仅当实例给了资质） | `qualification` |
| 10 | 次生资源能操作该机器，且同时占用数不超过容量 | `worker` |
| 11 | 被锁定的工序（WIP）机器与开工时刻与给定值一致 | `locked` |

**换型时间属于第 6 项**：同一机器上相邻两道工序之间必须留出
``setup(from_family, to_family)`` 的间隔。换型是顺序相关的，所以它只能在
「已知机器上的加工顺序」之后检查，不能像日历那样逐工序独立检查。
"""

from __future__ import annotations

from collections import Counter

from fjsp_core.models import FJSPInstance, Schedule

#: 时间区间的边界约定：``[start, end)``，因此 ``start == 前一个 end`` 合法。
SETUP_UNKNOWN = -1


def schedule_errors(instance: FJSPInstance, schedule: Schedule) -> list[str]:
    """返回诊断列表（空 = 通过）。**不抛异常**，尽量一次报出全部问题。"""
    errors: list[str] = []
    operations = {op.id: op for op in instance.operations}
    machines = {machine.id: machine for machine in instance.machines}
    jobs = {job.id: job for job in instance.jobs}

    # --- 1. 完整性 --------------------------------------------------------
    counts = Counter(item.operation_id for item in schedule.operations)
    for operation_id in operations:
        if counts[operation_id] == 0:
            errors.append(f"missing: {operation_id}")
        elif counts[operation_id] > 1:
            errors.append(f"duplicate: {operation_id}")

    # --- 2/3/4：逐工序的局部检查 ------------------------------------------
    valid: list[tuple[object, object]] = []  # (ScheduledOperation, Operation) 且时刻可信
    for item in schedule.operations:
        if item.operation_id not in operations:
            errors.append(f"unknown operation: {item.operation_id}")
            continue
        op = operations[item.operation_id]

        if item.machine_id not in machines:
            errors.append(f"illegal assignment: {op.id} -> {item.machine_id}")
            continue
        duration = op.time_on(item.machine_id)
        if duration is None:
            errors.append(f"illegal assignment: {op.id} -> {item.machine_id}")
            continue

        if type(item.start_time) is not int or type(item.end_time) is not int:
            errors.append(f"invalid time type: {op.id}")
            continue
        valid.append((item, op))

        if item.start_time < 0 or item.end_time - item.start_time != duration:
            errors.append(f"duration: {op.id}")
        if item.start_time < jobs[op.job_id].release_time:
            errors.append(f"release: {op.id}")
        if op.locked_start is not None and item.start_time != op.locked_start:
            errors.append(f"locked: {op.id} start {item.start_time} != {op.locked_start}")
        if op.locked_machine_id is not None and item.machine_id != op.locked_machine_id:
            errors.append(
                f"locked: {op.id} machine {item.machine_id} != {op.locked_machine_id}"
            )

        # --- 7/8：日历与维护窗口 ------------------------------------------
        windows = instance.calendar_window(item.machine_id)
        if windows and not any(
            lo <= item.start_time and item.end_time <= hi for lo, hi in windows
        ):
            errors.append(f"calendar: {op.id} on {item.machine_id}")
        for lo, hi in instance.maintenance_windows(item.machine_id):
            if item.start_time < hi and lo < item.end_time:
                errors.append(f"maintenance: {op.id} on {item.machine_id}")
                break

        # --- 9：资质 ------------------------------------------------------
        if instance.qualifications and op.family is not None:
            allowed = {
                q.machine_id
                for q in instance.qualifications
                if q.family == op.family
            }
            if item.machine_id not in allowed:
                errors.append(f"qualification: {op.id} on {item.machine_id}")

    by_id = {item.operation_id: item for item, _ in valid}

    # --- 5：订单内 precedence ---------------------------------------------
    for job in instance.jobs:
        for before, after in zip(job.operation_ids, job.operation_ids[1:]):
            a, b = by_id.get(before), by_id.get(after)
            if a is not None and b is not None and a.end_time > b.start_time:
                errors.append(f"precedence: {before} -> {after}")

    # --- 6：机器不重叠 + 换型间隔 -----------------------------------------
    # 换型只在实例**确实定义了换型矩阵**时才有意义。只给工序族而不给换型矩阵，
    # 可能是把族用于资质或 batching 分组，此时不该逼出一堆「换型未定义」。
    check_setup = bool(instance.setups)
    for machine_id in machines:
        timeline = sorted(
            (item for item, _ in valid if item.machine_id == machine_id),
            key=lambda item: item.start_time,
        )
        frontier = 0
        previous_family: str | None = None
        for item in timeline:
            op = operations[item.operation_id]
            gap = 0
            if check_setup and previous_family is not None and item.start_time >= frontier:
                try:
                    gap = instance.setup_minutes(previous_family, op.family)
                except KeyError:
                    errors.append(f"setup undefined: {previous_family!r} -> {op.family!r}")
                    gap = 0
            if item.start_time < frontier + gap:
                errors.append(f"overlap: {machine_id}/{item.operation_id}")
            frontier = max(frontier, item.end_time)
            previous_family = op.family

    # --- 10：次生资源 -----------------------------------------------------
    errors.extend(_worker_errors(instance, valid))

    return errors


def _worker_errors(instance: FJSPInstance, valid: list[tuple[object, object]]) -> list[str]:
    """资源能否操作该机器 + 同时占用数不超过容量。

    只对**被指派了资源**的工序检查：是否强制每道工序都必须占用资源由业务决定，
    不在本验证器的职责内（有些工序是纯机加工的自动工序）。
    """
    if not instance.workers:
        return []
    errors: list[str] = []
    workers = {worker.id: worker for worker in instance.workers}
    assigned: dict[str, list[tuple[int, int]]] = {}
    for item, _ in valid:  # valid 里存的是 (ScheduledOperation, Operation) 成对元素
        worker_id = item.worker_id
        if worker_id is None:
            continue
        if worker_id not in workers:
            errors.append(f"worker: unknown {worker_id!r}")
            continue
        worker = workers[worker_id]
        if not worker.can_operate(item.machine_id):
            errors.append(f"worker: {worker_id} cannot operate {item.machine_id}")
        assigned.setdefault(worker_id, []).append((item.start_time, item.end_time))

    for worker_id, intervals in assigned.items():
        capacity = workers[worker_id].capacity
        if capacity <= 1:
            ordered = sorted(intervals)
            for (_, previous_end), (start, _) in zip(ordered, ordered[1:]):
                if start < previous_end:
                    errors.append(f"worker: {worker_id} double-booked")
                    break
        else:
            # 容量 >1：扫事件点，检查同时占用数
            events: list[tuple[int, int]] = []
            for start, end in intervals:
                events.append((start, 1))
                events.append((end, -1))
            current = peak = 0
            for _, delta in sorted(events, key=lambda pair: (pair[0], pair[1])):
                current += delta
                peak = max(peak, current)
            if peak > capacity:
                errors.append(f"worker: {worker_id} peak {peak} > capacity {capacity}")
    return errors


def validate_schedule(instance: FJSPInstance, schedule: Schedule) -> None:
    """有诊断就抛 ``ValueError``；诊断内容用 ``; `` 拼接，一次暴露尽可能多。"""
    errors = schedule_errors(instance, schedule)
    if errors:
        raise ValueError("; ".join(errors))
