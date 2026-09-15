"""单机经典调度规则（dispatching rules）与释放时间处理。

对应 Day4.md：实现单机 SPT / EDD / WSPT / LPT 规则，并用
「非延迟列表调度」（non-delay list scheduling）处理释放时间 rj。

设计约定：
- 每个规则都返回一个不可变 Schedule，符合「solve(instance) -> Schedule」的统一约定。
- 本模块只服务单机 1||... 模型：每个 Job 必须恰好一道工序。
- 释放时间处理采用贪心：机器空闲时，只在「已释放（rj <= t）」的 job 中按优先级
  挑一个；若没有已释放 job，则空转到剩余 job 的最小释放时间。
- 有释放时间时这些规则是启发式基线，不一定最优（见 Day4.md 理论部分）。
"""

from __future__ import annotations

import math
from collections.abc import Callable
from fractions import Fraction
from typing import Any

from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.schedule import Schedule, ScheduledOperation
from scheduling_core.validation import validate_instance

# 优先级函数：给定 (job, operation) 返回一个可比较的排序键。
# list_schedule 按「键值升序 = 优先级从高到低」挑选。
Priority = Callable[[Job, Operation], Any]


def _resolve_machine(instance: Instance, machine_id: str | None) -> Machine:
    """解析目标机器；单机规则默认要求恰好一台机器。"""
    if machine_id is not None:
        for machine in instance.machines:
            if machine.id == machine_id:
                return machine
        raise ValueError(f"unknown machine {machine_id!r}")

    if len(instance.machines) != 1:
        raise ValueError(
            "single-machine rules require exactly one machine; "
            "pass machine_id to select one explicitly"
        )
    return instance.machines[0]


def _single_operation(
    job: Job,
    operations_by_id: dict[str, Operation],
) -> Operation:
    """返回 job 的唯一工序；单机规则要求每个 Job 恰好一道工序。"""
    operations = [operations_by_id[oid] for oid in job.operation_ids]

    if len(operations) != 1:
        raise ValueError(
            f"single-machine rules require exactly one operation per job; "
            f"job {job.id!r} has {len(operations)}"
        )

    return operations[0]


def list_schedule(
    instance: Instance,
    priority: Priority,
    *,
    machine_id: str | None = None,
) -> Schedule:
    """按优先级做带释放时间的单机列表调度（non-delay）。

    参数 ``priority`` 返回排序键，键值越小优先级越高。排序稳定，并用 job.id
    做次级平局决胜，保证结果确定。

    释放时间处理（非延迟策略）：

    1. 维护当前时间 t，初始 0；
    2. 在尚未排程的 job 中，找「已释放（rj <= t）且优先级最高」的一个；
    3. 若无 job 已释放，则把 t 推进到剩余 job 的最小 rj（空转等待）；
    4. 该 job 的开始时间 = max(t, rj)，加工后 t 推进到其完工时间。
    """
    validate_instance(instance)
    machine = _resolve_machine(instance, machine_id)

    operations_by_id = {op.id: op for op in instance.operations}
    tasks = [(job, _single_operation(job, operations_by_id)) for job in instance.jobs]
    for _, operation in tasks:
        if machine.id not in operation.eligible_machine_ids:
            raise ValueError(f"illegal assignment: {operation.id} -> {machine.id}")

    # 稳定排序：优先级升序，平局按 job.id 升序
    ordered = sorted(tasks, key=lambda t: (priority(t[0], t[1]), t[0].id))

    remaining = list(ordered)
    scheduled: list[ScheduledOperation] = []
    t = 0

    while remaining:
        selected_index = None

        for i, (job, _) in enumerate(remaining):
            if job.release_time <= t:
                selected_index = i
                break

        if selected_index is None:
            t = min(job.release_time for job, _ in remaining)
            continue

        job, operation = remaining.pop(selected_index)
        start = max(t, job.release_time)
        end = start + operation.processing_time

        scheduled.append(
            ScheduledOperation(
                operation_id=operation.id,
                machine_id=machine.id,
                start_time=start,
                end_time=end,
            )
        )

        t = end

    return Schedule(operations=tuple(scheduled))


def spt(instance: Instance, *, machine_id: str | None = None) -> Schedule:
    """SPT：加工时间从短到长。对 1||ΣCj 最优。"""
    return list_schedule(
        instance,
        lambda job, op: op.processing_time,
        machine_id=machine_id,
    )


def lpt(instance: Instance, *, machine_id: str | None = None) -> Schedule:
    """LPT：加工时间从长到短。单机上是 SPT 的逆序；并行机 P||Cmax 的列表调度基线。"""
    return list_schedule(
        instance,
        lambda job, op: -op.processing_time,
        machine_id=machine_id,
    )


def edd(instance: Instance, *, machine_id: str | None = None) -> Schedule:
    """EDD：交期从早到晚；无交期（due_date=None）的 job 排最后。对 1||Lmax 最优。"""

    def key(job: Job, op: Operation) -> Any:
        if job.due_date is None:
            return (1, 0)
        return (0, job.due_date)

    return list_schedule(instance, key, machine_id=machine_id)


def wspt(instance: Instance, *, machine_id: str | None = None) -> Schedule:
    """WSPT / Smith 规则：按 p/w 从小到大。对 1||ΣwjCj 最优。

    用 Fraction 精确表示 p/w，避免浮点比较的精度问题。
    """

    def key(job: Job, op: Operation) -> Any:
        return Fraction(op.processing_time) / Fraction(job.weight)

    return list_schedule(instance, key, machine_id=machine_id)


def parallel_lpt(instance: Instance) -> Schedule:
    """并行机 LPT 列表基线。r=0、同质且全资格时为经典 P||Cmax。"""
    from scheduling_algorithms.decoder import decode, initial_candidate

    validate_instance(instance)
    if any(len(job.operation_ids) != 1 for job in instance.jobs):
        raise ValueError("parallel LPT requires one operation per job")
    return decode(instance, initial_candidate(instance))


def parallel_makespan_lower_bound(instance: Instance) -> int:
    """P||Cmax 的下界：max(最长加工时间, ceil(总加工时间 / 机器数))。

    任一可行排程的 makespan 既不能小于最长单个 Job 的加工时间，也不能小于
    总工作量被 m 台机器平摊的平均负载。LPT 结果等于该下界时，即可证明在
    该实例上 LPT 已经最优。
    """
    operation_by_id = {op.id: op for op in instance.operations}

    processing_times = [
        operation_by_id[job.operation_ids[0]].processing_time
        for job in instance.jobs
    ]

    if not processing_times:
        return 0

    total = sum(processing_times)
    longest = max(processing_times)
    machine_count = len(instance.machines)

    return max(longest, math.ceil(total / machine_count))
