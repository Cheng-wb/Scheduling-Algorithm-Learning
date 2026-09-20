"""M3 Week 4 Day 2：批处理与工序族 —— 同族连续加工免换型，异族必须换型。

模型里**没有 batch 对象**。批处理是靠「工序族 + sequence-dependent setup」编码出来的：
同族紧邻不花换型时间，异族紧邻要花。这个脚本做三件事：

1. 手算一条「同族连排」的排程，看验证器接受它；
2. 把异族逼到相邻位置，看它必须空出换型时间；
3. 同一个实例分别用精确编码与保守编码求解，量一量保守编码切掉了多少。

从任何工作目录都能跑：
    python examples/m3w4d2_batching.py
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
    Setup,
)
from fjsp_core.objective import makespan, total_setup_time
from fjsp_core.schedule_validation import schedule_errors
from fjsp_core.result import validate_result
from fjsp_shop.registry import get, load_week_modules


def build_instance() -> FJSPInstance:
    """两台机器、两个族、四个订单批次里的四道工序。

    ``J0`` 的两道工序同族 ``F0``，``J1`` 的同族 ``F1``。
    换型矩阵：同族 0，``F0 -> F1`` 是 3，``F1 -> F0`` 是 4（**不对称**：
    从干净的 F0 切到 F1 要先清机，反过来更贵）。
    """
    return FJSPInstance(
        jobs=(
            Job("J0", ("A", "B"), release_time=0, due_date=20),
            Job("J1", ("C", "D"), release_time=0, due_date=20),
        ),
        operations=(
            Operation("A", "J0", 0, (("M0", 5), ("M1", 4)), family="F0"),
            Operation("B", "J0", 1, (("M0", 6), ("M1", 5)), family="F0"),
            Operation("C", "J1", 0, (("M0", 4), ("M1", 6)), family="F1"),
            Operation("D", "J1", 1, (("M0", 5), ("M1", 5)), family="F1"),
        ),
        machines=(Machine("M0", "M0"), Machine("M1", "M1")),
        setups=(
            Setup("F0", "F0", 0),
            Setup("F0", "F1", 3),
            Setup("F1", "F0", 4),
            Setup("F1", "F1", 0),
        ),
    )


def main() -> None:
    instance = build_instance()
    print("=== 1. 换型矩阵（不对称）===")
    for item in instance.setups:
        print(f"  {item.from_family} -> {item.to_family} : {item.minutes} 分钟")

    print()
    print("=== 2. 同族连排：A(F0) 与 B(F0) 紧贴，不需要换型 ===")
    grouped = Schedule(
        (
            ScheduledOperation("A", "M1", 0, 4),
            ScheduledOperation("B", "M1", 4, 9),
            ScheduledOperation("C", "M0", 0, 4),
            ScheduledOperation("D", "M0", 4, 9),
        )
    )
    print(f"  诊断：{schedule_errors(instance, grouped) or '无（通过）'}")
    print(
        f"  Cmax={makespan(instance, grouped)}  "
        f"换型总量={total_setup_time(instance, grouped)}"
    )

    print()
    print("=== 3. 异族相邻：B(F0) 后面接 D(F1)，必须空出 setup(F0->F1)=3 ===")
    mixed = Schedule(
        (
            ScheduledOperation("A", "M1", 0, 4),
            ScheduledOperation("B", "M1", 4, 9),
            # M1 上 B 结束于 9，D 是 F1：最早只能 9 + 3 = 12
            ScheduledOperation("D", "M1", 12, 17),
            ScheduledOperation("C", "M0", 0, 4),
        )
    )
    print(f"  诊断：{schedule_errors(instance, mixed) or '无（通过）'}")
    print(f"  换型总量={total_setup_time(instance, mixed)}（一次 F0->F1）")
    too_tight = Schedule(
        (
            ScheduledOperation("A", "M1", 0, 4),
            ScheduledOperation("B", "M1", 4, 9),
            ScheduledOperation("D", "M1", 9, 14),
            ScheduledOperation("C", "M0", 0, 4),
        )
    )
    print(f"  把 D 提前到 9（不空换型）：{schedule_errors(instance, too_tight)}")

    print()
    print("=== 4. 精确编码 vs 保守编码：保守编码切掉了多少 ===")
    load_week_modules()
    for method, label in (
        ("fjsp_cpsat_full", "精确（槽位链 + 查表）"),
        ("fjsp_cpsat_qualified", "保守（区间膨胀 AddNoOverlap）"),
    ):
        result = get(method)(
            instance, {"objective": "makespan", "time_limit": 10.0, "seed": 0}
        )
        print(
            f"  {method:22s} {label:28s} status={result.status:9s} "
            f"Cmax={result.objective:g} 换型={result.breakdown['setup']:g}"
        )
    print("  保守编码为什么更差：它把每道工序的机器占用按 max_outgoing_setup 膨胀，")
    print("  A(F0) 的区间变成 [0, 7)，于是同族的 B 再也贴不上 [4,9) —— 同族连排被切掉了。")


if __name__ == "__main__":
    main()
