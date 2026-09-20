"""M3 工业 FJSP 领域模型：订单、工艺路线、机器相关工时与真实业务约束。

**为什么不复用 M1 的 `Instance`？**
M1 的 `Operation.processing_time` 是**一个整数**，语义是「这道工序在所有合格机器上
耗时相同」（同质）。FJSP 的定义特征是 ``p_ij`` —— 同一道工序在不同机器上工时不同。
这不是加个可选字段就能兼容的：目标函数、解码器、验证器、CP-SAT 模型全部要按
「工时依赖机器」重写。零散地改动 M1 的模型会同时破坏 M1 与 M2 已封存的实验批次
（它们的 ``source_sha256`` 覆盖 M1 的三个包），所以 M3 自带一套更丰富的核心。

**复用的是纪律而不是代码**：输入不可变（``frozen=True`` + ``tuple``）、输入与结果分离、
独立验证器、确定性平局决胜、参考值分档。M2 的 ``bridge.py`` 只复用 M1 的**领域接口**，
M3 连接口都需要扩展（机器相关工时、日历、资质、次生资源），因此自建。

数据分成三层，不要混：

```text
订单层   Job（Order）   交期、释放时间、权重、优先级、工艺路线
工序层   Operation      在哪些机器上做、各需多久、属于哪个工序族、是否被锁定
资源层   Machine / Calendar / Maintenance / Qualification / Worker
```

``Calendar`` 与 ``Maintenance`` 都表达成「窗口列表」，但语义相反：日历是**可用**窗
（空表示不受限），维护是**不可用**窗（在日历之上再挖掉）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Machine:
    """机器/工位。``calendar_id`` 指向常规可用日历，``None`` 表示全时可用。"""

    id: str
    name: str
    calendar_id: str | None = None
    group: str | None = None  # 同组机器可互换（对称破缺用）


@dataclass(frozen=True, slots=True)
class Calendar:
    """常规可用时间窗 ``[start, end)`` 的并集。

    ``windows`` 为空表示**没有日历约束**（全时可用），而不是「永不可用」。
    这个区分很重要：漏填日历应当被当作「没约束」，而不是静默地让所有工序都排不进去。
    """

    id: str
    windows: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class Maintenance:
    """计划维护窗：在日历之上**再挖掉**的不可用区间。"""

    id: str
    machine_id: str
    windows: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class Qualification:
    """资质：机器 ``machine_id`` 有资格加工工序族 ``family``。

    只有当实例里存在**任何**资质记录时，验证器才检查资质——否则「没填资质」
    会被误判成「没有任何机器有资质」。
    """

    machine_id: str
    family: str


@dataclass(frozen=True, slots=True)
class Worker:
    """次生资源（操作工、工装、夹具）。``capacity`` 是同时在岗数。

    ``machine_ids`` 为空表示「不限机器」；非空表示这名资源只能操作列出的机器。
    """

    id: str
    name: str
    machine_ids: tuple[str, ...] = ()
    capacity: int = 1

    def can_operate(self, machine_id: str) -> bool:
        return not self.machine_ids or machine_id in self.machine_ids


@dataclass(frozen=True, slots=True)
class Operation:
    """一道工序。``machine_times`` 是 FJSP 的核心：逐机器的加工工时。"""

    id: str
    job_id: str
    position: int  # 工艺路线内的序号，0 起
    machine_times: tuple[tuple[str, int], ...]
    family: str | None = None  # 工序族：资质与 sequence-dependent setup 都按它分组
    locked_machine_id: str | None = None  # WIP：已在机/已开工，机器不可再选
    locked_start: int | None = None  # WIP：已定的开工时刻（None = 只锁机器）

    @property
    def eligible_machine_ids(self) -> tuple[str, ...]:
        return tuple(machine_id for machine_id, _ in self.machine_times)

    @property
    def min_time(self) -> int:
        """最快机器上的工时。下界与启发式都要用。"""
        return min(time for _, time in self.machine_times)

    def time_on(self, machine_id: str) -> int | None:
        """在指定机器上的工时；不合格返回 ``None``（不是 0，也不是默认值）。"""
        for candidate, time in self.machine_times:
            if candidate == machine_id:
                return time
        return None

    def __post_init__(self) -> None:
        if self.machine_times and len({m for m, _ in self.machine_times}) != len(
            self.machine_times
        ):
            raise ValueError(f"operation {self.id!r} lists a machine twice")


@dataclass(frozen=True, slots=True)
class Job:
    """订单。``operation_ids`` 的顺序就是工艺路线（顺序即 precedence）。"""

    id: str
    operation_ids: tuple[str, ...]
    release_time: int = 0
    due_date: int | None = None
    weight: float = 1.0
    priority: int = 0  # 紧急订单：数值越大越急；只进目标函数，不改变约束


@dataclass(frozen=True, slots=True)
class Setup:
    """sequence-dependent setup：机器上从工序族 ``from_family`` 换到 ``to_family``。"""

    from_family: str
    to_family: str
    minutes: int


@dataclass(frozen=True, slots=True)
class FJSPInstance:
    """一个 FJSP 问题的完整输入。所有集合都是 ``tuple``，不可变、可被算法公平复用。"""

    jobs: tuple[Job, ...]
    operations: tuple[Operation, ...]
    machines: tuple[Machine, ...]
    calendars: tuple[Calendar, ...] = ()
    maintenances: tuple[Maintenance, ...] = ()
    qualifications: tuple[Qualification, ...] = ()
    workers: tuple[Worker, ...] = ()
    setups: tuple[Setup, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)

    # --- 查找（每次调用重建，实例很小；不做缓存以免破坏 frozen 语义） ---------
    def operation(self, operation_id: str) -> Operation:
        for op in self.operations:
            if op.id == operation_id:
                return op
        raise KeyError(operation_id)

    def job(self, job_id: str) -> Job:
        for job in self.jobs:
            if job.id == job_id:
                return job
        raise KeyError(job_id)

    def machine(self, machine_id: str) -> Machine:
        for machine in self.machines:
            if machine.id == machine_id:
                return machine
        raise KeyError(machine_id)

    @property
    def machine_ids(self) -> tuple[str, ...]:
        return tuple(machine.id for machine in self.machines)

    @property
    def total_operation_count(self) -> int:
        return len(self.operations)

    def calendar_window(self, machine_id: str) -> tuple[tuple[int, int], ...]:
        """机器的可用窗：日历窗（空 = 无约束）。"""
        machine = self.machine(machine_id)
        if machine.calendar_id is None:
            return ()
        for calendar in self.calendars:
            if calendar.id == machine.calendar_id:
                return calendar.windows
        raise KeyError(f"unknown calendar: {machine.calendar_id!r}")

    def maintenance_windows(self, machine_id: str) -> tuple[tuple[int, int], ...]:
        return tuple(
            window
            for item in self.maintenances
            if item.machine_id == machine_id
            for window in item.windows
        )

    def setup_minutes(self, from_family: str | None, to_family: str | None) -> int:
        """换型时间。同一工序族（或任一为空）不需要换型。"""
        if from_family is None or to_family is None or from_family == to_family:
            return 0
        for setup in self.setups:
            if setup.from_family == from_family and setup.to_family == to_family:
                return setup.minutes
        # 未定义的方向按 0 处理会在验证器里掩盖建模缺口，所以显式报错
        raise KeyError(f"no setup time defined for {from_family!r} -> {to_family!r}")


# ---------------------------------------------------------------------------
# 结果表示：输入与结果严格分离
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScheduledOperation:
    """一道已排定工序。``worker_id`` 为 ``None`` 表示未指定次生资源。"""

    operation_id: str
    machine_id: str
    start_time: int
    end_time: int
    worker_id: str | None = None


@dataclass(frozen=True, slots=True)
class Schedule:
    """一个排程。``operations`` 的**顺序不代表时间顺序**——验证器不依赖它。"""

    operations: tuple[ScheduledOperation, ...]

    def by_operation(self) -> dict[str, ScheduledOperation]:
        return {item.operation_id: item for item in self.operations}
