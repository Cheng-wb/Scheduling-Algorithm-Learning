"""M3 Week 4 Day 3：WIP 与锁定工序 —— 已经在机上的活，排程只能绕开它。

``Operation.locked_machine_id`` 与 ``locked_start`` 是一对：机器和开工时刻
**同时**钉死。锁定值不当约束看就只是个建议，所以它必须能挡住两类错误：
换机器、改时刻。这个脚本先手工制造这两类错误看诊断，再量一次「锁定本身的代价」。

实例直接复用 ``fjsp_experiments/w4_industrial.py`` 的消融构造函数，所以这里的
数字与 ``artifacts/month3_w4/ablation.json`` 的 ``+worker`` / ``+locked`` 两行
对得上 —— 两处是同一份工序数据，只是加锁与否。

从任何工作目录都能跑：
    python examples/m3w4d3_locked.py
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
    Schedule,
    ScheduledOperation,
)
from fjsp_core.schedule_validation import schedule_errors
from fjsp_experiments.w4_industrial import ablation_instance
from fjsp_shop.registry import get, load_week_modules

SPEC = {"objective": "makespan", "time_limit": 15.0, "seed": 0}


def minimal_instance() -> FJSPInstance:
    """一个「只有锁定」的最小实例：没有日历、没有资质、没有工人。

    这样故意改锁时，诊断里只会有 ``locked:`` 那一条 —— 一条错误对应一条诊断，
    才看得出验证器到底在查什么。
    """
    return FJSPInstance(
        jobs=(
            Job("J0", ("X",), release_time=0, due_date=20),
            Job("J1", ("Y",), release_time=0, due_date=20),
        ),
        operations=(
            Operation(
                "X", "J0", 0, (("M0", 4), ("M1", 3)),
                locked_machine_id="M1", locked_start=0,
            ),
            Operation("Y", "J1", 0, (("M0", 2), ("M1", 2))),
        ),
        machines=(Machine("M0", "M0"), Machine("M1", "M1")),
    )


def show(instance, schedule) -> None:
    print(f"  诊断：{schedule_errors(instance, schedule) or '无（通过）'}")


def main() -> None:
    locked = ablation_instance("+locked")
    pinned = next(op for op in locked.operations if op.id == "C")
    print("=== 1. 锁定的内容 ===")
    print(
        f"  工序 C：locked_machine_id={pinned.locked_machine_id} "
        f"locked_start={pinned.locked_start}"
    )
    print(f"  C 的可选机器（工时表）：{dict(pinned.machine_times)}")
    print("  锁定的意思是：机器由 locked_machine_id 指定，开工时刻由 locked_start 指定，")
    print("  求解器没有自由裁量权 —— 这两条都要能挡住手写的排程。")

    print()
    print("=== 2. 两类改锁错误，看诊断 ===")
    print("  先用一个干净的小实例（只有锁定这一条约束），一条错误只对应一条诊断：")
    minimal = minimal_instance()
    show(
        minimal,
        Schedule(
            (
                ScheduledOperation("X", "M1", 0, 3),
                ScheduledOperation("Y", "M0", 0, 2),
            )
        ),
    )
    print("      这是**遵守锁定**的排程，先自证一遍。")
    print("  把 X 挪到 M0（它锁在 M1，工时 4）：")
    show(
        minimal,
        Schedule(
            (
                ScheduledOperation("X", "M0", 0, 4),
                ScheduledOperation("Y", "M1", 0, 2),
            )
        ),
    )
    print("  X 留在 M1，但开工时刻从 0 改成 3：")
    show(
        minimal,
        Schedule(
            (
                ScheduledOperation("X", "M1", 3, 6),
                ScheduledOperation("Y", "M0", 0, 2),
            )
        ),
    )
    print("  锁定是「机器 + 开工时刻」两个字段一起钉住，任缺其一都不算数。")
    print("  回到消融实例上再看一次（那里的 C 还带着日历与资质）：")
    time_shift = Schedule(
        (
            ScheduledOperation("A", "M1", 0, 4, worker_id="W1"),
            ScheduledOperation("B", "M1", 4, 9, worker_id="W1"),
            ScheduledOperation("C", "M1", 16, 22, worker_id="W1"),
            ScheduledOperation("D", "M1", 22, 27, worker_id="W1"),
        )
    )
    print("      其余三行都合规，只把 C 的开工时刻从 20 改成 16：")
    for item in schedule_errors(locked, time_shift):
        print(f"          {item}")
    print("      一条违反就够把整条排程判掉 —— 验证器不给「差不多」留余地。")

    print()
    print("=== 3. 锁定本身的代价：同一天数据，加锁前后 ===")
    load_week_modules()
    for stage in ("+worker", "+locked"):
        instance = ablation_instance(stage)
        result = get("fjsp_cpsat_full")(instance, dict(SPEC))
        print(f"  {stage:9s} status={result.status:9s} Cmax={result.objective:g}")
        for item in sorted(result.schedule.operations, key=lambda x: x.start_time):
            mark = " <- 锁定" if stage == "+locked" and item.operation_id == "C" else ""
            print(
                f"      {item.operation_id}  {item.machine_id}"
                f"  [{item.start_time},{item.end_time})  {item.worker_id}{mark}"
            )
    print("  27 -> 31：把 C 钉在 [20,26) 上，C 之后的 D 与 J0 的收尾都被推后。")
    print("  这就是「已经做出的生产决策」的代价 —— WIP 锁定的现实含义。")


if __name__ == "__main__":
    main()
