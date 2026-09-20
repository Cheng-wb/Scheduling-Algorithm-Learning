"""M3 Week 4 Day 1：机器资质与次生资源（工人）—— 谁能做、同时能做几个。

先手算一个小实例，把「资质」「能力」「容量」三件事各破坏一次，看独立验证器
报出的诊断是不是**那一条**；再让 `fjsp_cpsat_qualified` 在同一实例上给一个
过得了验证器的排程，并检查它给每道工序都指派了资源。

从任何工作目录都能跑：
    python examples/m3w4d1_qualified.py
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.models import (
    FJSPInstance,
    Job,
    Machine,
    Operation,
    Qualification,
    Schedule,
    ScheduledOperation,
    Worker,
)
from fjsp_core.schedule_validation import schedule_errors
from fjsp_core.result import validate_result
from fjsp_shop.registry import get, load_week_modules


def build_instance() -> FJSPInstance:
    """两台机器、两道工序、三个工人，资质只发了两张。

    资质：``(M0, F0)`` 与 ``(M1, F1)`` —— 族 F0 只能在 M0 上做，F1 只能在 M1 上做。
    工人：``W0`` 只会 M0、``W1`` 只会 M1、``W2`` 两台都会，容量都是 1。
    """
    return FJSPInstance(
        jobs=(
            Job("J0", ("A", "B"), release_time=0, due_date=8),
            Job("J1", ("C",), release_time=0, due_date=4),
        ),
        operations=(
            # A 在 M0/M1 上**都能加工**：这样「放到 M1」违反的才是资质，
            # 而不是「这道工序本来就是 M0 专机工序」。
            Operation("A", "J0", 0, (("M0", 5), ("M1", 6)), family="F0"),
            Operation("B", "J0", 1, (("M1", 4),), family="F1"),
            Operation("C", "J1", 0, (("M1", 3),), family="F1"),
        ),
        machines=(Machine("M0", "M0"), Machine("M1", "M1")),
        qualifications=(Qualification("M0", "F0"), Qualification("M1", "F1")),
        workers=(
            Worker("W0", "小张", ("M0",), 1),
            Worker("W1", "小李", ("M1",), 1),
            Worker("W2", "多面手", ("M0", "M1"), 1),
        ),
    )


def hand_schedule() -> Schedule:
    """手算可行排程：A 在 M0[0,5)、C 在 M1[0,3)、B 在 M1[5,9)，Cmax = 9。"""
    return Schedule(
        (
            ScheduledOperation("A", "M0", 0, 5, worker_id="W0"),
            ScheduledOperation("C", "M1", 0, 3, worker_id="W1"),
            ScheduledOperation("B", "M1", 5, 9, worker_id="W1"),
        )
    )


def report(title: str, instance: FJSPInstance, schedule: Schedule) -> None:
    errors = schedule_errors(instance, schedule)
    print(f"  {title}")
    if not errors:
        print("      诊断：无（通过）")
    for item in errors:
        print(f"      诊断：{item}")


def main() -> None:
    instance = build_instance()

    print("=== 1. 手算排程先自证清白 ===")
    report("A@M0[0,5) W0 / C@M1[0,3) W1 / B@M1[5,9) W1", instance, hand_schedule())

    print()
    print("=== 2. 三次故意破坏，看诊断是不是那一条 ===")
    report(
        "把 A 放到 M1（A 是 F0，资质只发了 (M0,F0)）",
        instance,
        Schedule(
            (
                ScheduledOperation("A", "M1", 0, 6, worker_id="W2"),
                ScheduledOperation("C", "M1", 6, 9, worker_id="W1"),
                ScheduledOperation("B", "M1", 9, 13, worker_id="W1"),
            )
        ),
    )
    report(
        "让 W0 去开 M1（W0 的 machine_ids 只有 M0）",
        instance,
        Schedule(
            (
                ScheduledOperation("A", "M0", 0, 5, worker_id="W0"),
                ScheduledOperation("C", "M1", 0, 3, worker_id="W0"),
                ScheduledOperation("B", "M1", 5, 9, worker_id="W1"),
            )
        ),
    )
    report(
        "W1 容量 1，两段占用重叠",
        instance,
        Schedule(
            (
                ScheduledOperation("A", "M0", 0, 5, worker_id="W0"),
                ScheduledOperation("C", "M1", 2, 5, worker_id="W1"),
                ScheduledOperation("B", "M1", 0, 4, worker_id="W1"),
            )
        ),
    )
    report(
        "同一工人两段占用**紧贴**（半开区间 [start,end)，相接不算冲突）",
        instance,
        Schedule(
            (
                ScheduledOperation("A", "M0", 0, 5, worker_id="W2"),
                ScheduledOperation("C", "M1", 5, 8, worker_id="W2"),
                ScheduledOperation("B", "M1", 8, 12, worker_id="W1"),
            )
        ),
    )

    print()
    print("=== 3. fjsp_cpsat_qualified 自己解一遍 ===")
    load_week_modules()
    result = get("fjsp_cpsat_qualified")(
        instance, {"objective": "makespan", "time_limit": 10.0, "seed": 0}
    )
    print(f"  status={result.status} objective={result.objective}")
    print(f"  独立验证器诊断：{validate_result(instance, result) or '无（通过）'}")
    print("  排程（按开工时刻排序）：")
    for item in sorted(result.schedule.operations, key=lambda x: x.start_time):
        print(
            f"      {item.operation_id}  {item.machine_id}"
            f"  [{item.start_time},{item.end_time})  资源={item.worker_id}"
        )
    assigned = [item.worker_id for item in result.schedule.operations]
    print(f"  每道工序都被指派了资源：{all(item is not None for item in assigned)}")
    print(f"  实际用到的资源：{sorted({w for w in assigned if w is not None})}")


if __name__ == "__main__":
    main()
