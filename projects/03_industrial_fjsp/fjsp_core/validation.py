"""输入校验：fail-fast，检查**问题数据**本身是否合法。

与 ``schedule_validation`` 的分工必须分清：

* 本模块管**输入**：ID 重复、引用不存在、工时非正、工艺路线为空、窗口倒置……
  一旦不合法就没有「继续算」的意义，所以第一条错误就抛。
* ``schedule_validation`` 管**结果**：求解器返回的排程是否可行，收集全部诊断。

把两者混在一起，会让「输入写错了」和「算法算错了」变得无法区分。
"""

from __future__ import annotations

import math

from fjsp_core.models import FJSPInstance


class FJSPInstanceError(ValueError):
    """输入实例不合法。"""


def _check_unique(values: list[str], label: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise FJSPInstanceError(f"duplicate {label} ids: {value!r}")
        seen.add(value)


def _check_id(value: object, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise FJSPInstanceError(f"{label} must be a non-empty string, got {value!r}")


def _check_window(start: object, end: object, label: str) -> None:
    if type(start) is not int or type(end) is not int:
        raise FJSPInstanceError(f"{label} window bounds must be int: {(start, end)!r}")
    if start < 0 or end <= start:
        raise FJSPInstanceError(f"{label} window must be non-empty and non-negative: {(start, end)!r}")


def validate_instance(instance: FJSPInstance) -> None:
    """校验实例；不合法时抛 :class:`FJSPInstanceError`。"""
    if not instance.machines:
        raise FJSPInstanceError("instance has no machines")
    if not instance.jobs:
        raise FJSPInstanceError("instance has no jobs")

    _check_unique([m.id for m in instance.machines], "machine")
    _check_unique([j.id for j in instance.jobs], "job")
    _check_unique([o.id for o in instance.operations], "operation")
    _check_unique([c.id for c in instance.calendars], "calendar")
    _check_unique([w.id for w in instance.workers], "worker")
    for item in instance.machines + instance.jobs + instance.operations:
        _check_id(item.id, type(item).__name__)

    machine_ids = set(instance.machine_ids)
    calendar_ids = {c.id for c in instance.calendars}
    job_ids = {j.id for j in instance.jobs}
    operations = {op.id: op for op in instance.operations}

    # --- 机器 --------------------------------------------------------------
    for machine in instance.machines:
        if machine.calendar_id is not None and machine.calendar_id not in calendar_ids:
            raise FJSPInstanceError(
                f"machine {machine.id!r} references unknown calendar {machine.calendar_id!r}"
            )

    # --- 日历 / 维护 -------------------------------------------------------
    for calendar in instance.calendars:
        for start, end in calendar.windows:
            _check_window(start, end, f"calendar {calendar.id!r}")
    for item in instance.maintenances:
        if item.machine_id not in machine_ids:
            raise FJSPInstanceError(
                f"maintenance {item.id!r} references unknown machine {item.machine_id!r}"
            )
        if not item.windows:
            raise FJSPInstanceError(f"maintenance {item.id!r} has no windows")
        for start, end in item.windows:
            _check_window(start, end, f"maintenance {item.id!r}")

    # --- 资质 / 资源 -------------------------------------------------------
    for qualification in instance.qualifications:
        if qualification.machine_id not in machine_ids:
            raise FJSPInstanceError(
                f"qualification references unknown machine {qualification.machine_id!r}"
            )
        if not qualification.family:
            raise FJSPInstanceError("qualification family must be non-empty")
    for worker in instance.workers:
        if worker.capacity < 1:
            raise FJSPInstanceError(f"worker {worker.id!r} capacity must be >= 1")
        for machine_id in worker.machine_ids:
            if machine_id not in machine_ids:
                raise FJSPInstanceError(
                    f"worker {worker.id!r} references unknown machine {machine_id!r}"
                )
    for setup in instance.setups:
        if setup.minutes < 0:
            raise FJSPInstanceError(
                f"setup {setup.from_family!r} -> {setup.to_family!r} has negative minutes"
            )

    # --- 工序 --------------------------------------------------------------
    for op in instance.operations:
        if op.job_id not in job_ids:
            raise FJSPInstanceError(f"operation {op.id!r} references unknown job {op.job_id!r}")
        if not op.machine_times:
            raise FJSPInstanceError(f"operation {op.id!r} has no eligible machine")
        if op.position < 0:
            raise FJSPInstanceError(f"operation {op.id!r} has negative position")
        for machine_id, minutes in op.machine_times:
            if machine_id not in machine_ids:
                raise FJSPInstanceError(
                    f"operation {op.id!r} lists unknown machine {machine_id!r}"
                )
            if type(minutes) is not int or minutes <= 0:
                raise FJSPInstanceError(
                    f"operation {op.id!r} on {machine_id!r} has non-positive time {minutes!r}"
                )
        if op.locked_start is not None and (
            type(op.locked_start) is not int or op.locked_start < 0
        ):
            raise FJSPInstanceError(f"operation {op.id!r} has invalid locked_start")
        if op.locked_machine_id is not None:
            if op.locked_machine_id not in machine_ids:
                raise FJSPInstanceError(
                    f"operation {op.id!r} is locked to unknown machine {op.locked_machine_id!r}"
                )
            if op.locked_machine_id not in op.eligible_machine_ids:
                raise FJSPInstanceError(
                    f"operation {op.id!r} is locked to ineligible machine "
                    f"{op.locked_machine_id!r}"
                )

    # --- 订单与工艺路线 ----------------------------------------------------
    for job in instance.jobs:
        if not job.operation_ids:
            raise FJSPInstanceError(f"job {job.id!r} has an empty process route")
        if type(job.release_time) is not int or job.release_time < 0:
            raise FJSPInstanceError(f"job {job.id!r} has invalid release_time")
        if job.due_date is not None and (
            type(job.due_date) is not int or job.due_date < 0
        ):
            raise FJSPInstanceError(f"job {job.id!r} has invalid due_date")
        if (
            isinstance(job.weight, bool)
            or not isinstance(job.weight, (int, float))
            or not math.isfinite(job.weight)
            or job.weight <= 0
        ):
            raise FJSPInstanceError(f"job {job.id!r} weight must be finite and positive")
        if len(set(job.operation_ids)) != len(job.operation_ids):
            raise FJSPInstanceError(f"job {job.id!r} repeats an operation id")
        for position, operation_id in enumerate(job.operation_ids):
            if operation_id not in operations:
                raise FJSPInstanceError(
                    f"job {job.id!r} references unknown operation {operation_id!r}"
                )
            op = operations[operation_id]
            if op.job_id != job.id:
                raise FJSPInstanceError(
                    f"operation {op.id!r} claims job {op.job_id!r} but "
                    f"job {job.id!r} lists it"
                )
            if op.position != position:
                raise FJSPInstanceError(
                    f"operation {op.id!r} has position {op.position} but sits at "
                    f"index {position} of job {job.id!r}"
                )
