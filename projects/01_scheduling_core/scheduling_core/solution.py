"""优先级排列 + 机器指派；指派位置始终对应 instance.operations。"""

from dataclasses import dataclass, replace
from collections.abc import Iterator

from .models import Instance
from .schedule import Schedule, ScheduledOperation
from .validation import validate_instance


@dataclass(frozen=True, slots=True)
class Candidate:
    order: tuple[str, ...]
    assignments: tuple[str, ...]


def validate_candidate(instance: Instance, candidate: Candidate) -> None:
    ids = {op.id for op in instance.operations}
    if len(candidate.order) != len(ids) or set(candidate.order) != ids:
        raise ValueError("order must contain every operation exactly once")
    if len(candidate.assignments) != len(instance.operations):
        raise ValueError("assignment length mismatch")
    for op, machine in zip(instance.operations, candidate.assignments, strict=True):
        if machine not in op.eligible_machine_ids:
            raise ValueError(f"illegal assignment: {op.id} -> {machine}")


def decode(instance: Instance, candidate: Candidate) -> Schedule:
    """串行追加解码：扫描优先级，取第一道前驱已排定的工序。

    指派机器固定，s=max(machine_ready, predecessor_end, release)。
    不向机器已有空隙插入；order 是优先级，不承诺等于时间顺序。
    """
    validate_instance(instance)
    validate_candidate(instance, candidate)
    operations = {op.id: op for op in instance.operations}
    jobs = {job.id: job for job in instance.jobs}
    predecessors = {
        oid: (job.operation_ids[i - 1] if i else None)
        for job in instance.jobs
        for i, oid in enumerate(job.operation_ids)
    }
    machines = dict(zip(operations, candidate.assignments, strict=True))
    machine_ready = {machine.id: 0 for machine in instance.machines}
    ends: dict[str, int] = {}
    remaining = list(candidate.order)
    output = []
    while remaining:
        oid = next(
            oid
            for oid in remaining
            if predecessors[oid] is None or predecessors[oid] in ends
        )
        remaining.remove(oid)
        op = operations[oid]
        machine = machines[oid]
        predecessor = predecessors[oid]
        start = max(
            machine_ready[machine],
            ends[predecessor] if predecessor is not None else 0,
            jobs[op.job_id].release_time,
        )
        end = start + op.processing_time
        output.append(ScheduledOperation(oid, machine, start, end))
        machine_ready[machine] = ends[oid] = end
    return Schedule(tuple(output))


def initial_candidate(instance: Instance) -> Candidate:
    """LPT 优先级 + 最早完工指派。多工序时仅作通用初始解。"""
    validate_instance(instance)
    loads = {machine.id: 0 for machine in instance.machines}
    jobs = {job.id: job for job in instance.jobs}
    ordered = sorted(instance.operations, key=lambda op: (-op.processing_time, op.id))
    assignments = {}
    for op in ordered:
        machine = min(
            op.eligible_machine_ids,
            key=lambda mid: (max(loads[mid], jobs[op.job_id].release_time), mid),
        )
        loads[machine] = (
            max(loads[machine], jobs[op.job_id].release_time) + op.processing_time
        )
        assignments[op.id] = machine
    return Candidate(
        tuple(op.id for op in ordered),
        tuple(assignments[op.id] for op in instance.operations),
    )


def swap(candidate: Candidate, i: int, j: int) -> Candidate:
    _indices(candidate, i, j)
    order = list(candidate.order)
    order[i], order[j] = order[j], order[i]
    return replace(candidate, order=tuple(order))


def insert(candidate: Candidate, i: int, j: int) -> Candidate:
    """把原位置 i 的元素移到结果的 j 位置。"""
    _indices(candidate, i, j)
    order = list(candidate.order)
    order.insert(j, order.pop(i))
    return replace(candidate, order=tuple(order))


def _indices(candidate: Candidate, i: int, j: int) -> None:
    if not (0 <= i < len(candidate.order) and 0 <= j < len(candidate.order)):
        raise IndexError("move indices outside permutation")


def reassign(
    instance: Instance, candidate: Candidate, index: int, machine: str
) -> Candidate:
    if not 0 <= index < len(instance.operations):
        raise IndexError("operation index outside instance")
    if machine not in instance.operations[index].eligible_machine_ids:
        raise ValueError("illegal assignment")
    assignments = list(candidate.assignments)
    assignments[index] = machine
    return replace(candidate, assignments=tuple(assignments))


def neighbors(instance: Instance, candidate: Candidate) -> Iterator[Candidate]:
    """固定扫描顺序，去除 swap/insert 重合解以及自身。"""
    seen = {candidate}
    for i in range(len(candidate.order)):
        for j in range(len(candidate.order)):
            for moved in (swap(candidate, i, j), insert(candidate, i, j)):
                if moved not in seen:
                    seen.add(moved)
                    yield moved
    for i, op in enumerate(instance.operations):
        for machine in sorted(op.eligible_machine_ids):
            moved = reassign(instance, candidate, i, machine)
            if moved not in seen:
                seen.add(moved)
                yield moved
