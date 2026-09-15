"""构造式解码与确定性初始候选解。"""

from scheduling_core.models import Instance
from scheduling_core.schedule import Schedule, ScheduledOperation
from scheduling_core.solution import Candidate, validate_candidate
from scheduling_core.validation import validate_instance


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
