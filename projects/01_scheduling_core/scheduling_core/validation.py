"""输入校验：判断一个 Instance 在语义上是否合法。

只回答「问题本身是否合法」，不检查某个排程是否可行（那是 Schedule Validator 的职责）。
Month 1 采用 fail-fast：遇到第一个错误就抛出 InstanceValidationError。
"""

from __future__ import annotations

import math

from scheduling_core.models import Instance, Job, Machine, Operation


class InstanceValidationError(ValueError):
    """输入实例不合法时抛出。"""


def _check_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise InstanceValidationError(f"duplicate {label} ids")


def validate_instance(instance: Instance) -> None:
    """校验 Instance 的字段、唯一性、引用完整性与 Job↔Operation 双向一致性。"""
    entities: tuple[Job | Operation | Machine, ...] = (
        *instance.jobs,
        *instance.operations,
        *instance.machines,
    )
    for entity in entities:
        if not isinstance(entity.id, str) or not entity.id.strip():
            raise InstanceValidationError("id must be a nonempty string")
    machine_ids_list = [m.id for m in instance.machines]
    job_ids_list = [j.id for j in instance.jobs]
    operation_ids_list = [o.id for o in instance.operations]

    _check_unique(machine_ids_list, "machine")
    _check_unique(job_ids_list, "job")
    _check_unique(operation_ids_list, "operation")

    machine_ids = set(machine_ids_list)
    job_ids = set(job_ids_list)
    operation_ids = set(operation_ids_list)

    operation_by_id = {op.id: op for op in instance.operations}
    job_by_id = {job.id: job for job in instance.jobs}

    for job in instance.jobs:
        if not job.operation_ids:
            raise InstanceValidationError(f"job {job.id}: no operations")
        if type(job.release_time) is not int or (
            job.due_date is not None and type(job.due_date) is not int
        ):
            raise InstanceValidationError("release_time/due_date must be integers")
        if (
            isinstance(job.weight, bool)
            or not isinstance(job.weight, (int, float))
            or not math.isfinite(job.weight)
        ):
            raise InstanceValidationError("weight must be finite numeric")
        if job.release_time < 0:
            raise InstanceValidationError(f"job {job.id}: release_time must be >= 0")

        if job.due_date is not None and job.due_date < 0:
            raise InstanceValidationError(f"job {job.id}: due_date must be >= 0")

        if job.weight <= 0:
            raise InstanceValidationError(f"job {job.id}: weight must be > 0")

        if len(job.operation_ids) != len(set(job.operation_ids)):
            raise InstanceValidationError(f"job {job.id}: duplicate operation ids")

        for operation_id in job.operation_ids:
            if operation_id not in operation_ids:
                raise InstanceValidationError(
                    f"job {job.id}: unknown operation {operation_id}"
                )

            operation = operation_by_id[operation_id]

            if operation.job_id != job.id:
                raise InstanceValidationError(
                    f"job {job.id} and operation {operation_id} disagree"
                )

    for op in instance.operations:
        if type(op.processing_time) is not int:
            raise InstanceValidationError("processing_time must be an integer")
        if op.processing_time <= 0:
            raise InstanceValidationError(
                f"operation {op.id}: processing_time must be > 0"
            )

        if op.job_id not in job_ids:
            raise InstanceValidationError(f"operation {op.id}: unknown job {op.job_id}")

        if not op.eligible_machine_ids:
            raise InstanceValidationError(f"operation {op.id}: no eligible machines")

        for machine_id in op.eligible_machine_ids:
            if machine_id not in machine_ids:
                raise InstanceValidationError(
                    f"operation {op.id}: unknown machine {machine_id}"
                )

        job = job_by_id[op.job_id]

        if op.id not in job.operation_ids:
            raise InstanceValidationError(
                f"operation {op.id} missing from job {job.id}"
            )
