"""调度问题的不可变输入数据模型。

设计约定（对应 Day2.md）：
- 输入实体用 ``@dataclass(frozen=True, slots=True)``，集合用 ``tuple``。
- 关系使用稳定 ID（``Job.operation_ids``、``Operation.job_id``、
  ``Operation.eligible_machine_ids``），不做对象嵌套，避免循环引用。
- 输入与求解结果分离：``start_time / assigned_machine / completion_time``
  等属于 Schedule / Solution 层，不属于输入模型。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Machine:
    """机器/资源。"""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class Operation:
    """工序。``eligible_machine_ids`` 为可加工机器集合。"""

    id: str
    job_id: str
    processing_time: int
    eligible_machine_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Job:
    """作业/订单。``operation_ids`` 为有序工序序列（顺序即 precedence）。"""

    id: str
    operation_ids: tuple[str, ...]
    release_time: int = 0
    due_date: int | None = None
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class Instance:
    """整个调度问题的输入容器，作为所有算法的统一入口。"""

    jobs: tuple[Job, ...]
    operations: tuple[Operation, ...]
    machines: tuple[Machine, ...]
