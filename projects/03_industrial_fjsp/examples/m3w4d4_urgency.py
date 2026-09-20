"""M3 Week 4 Day 4：紧急订单与优先级 —— 优先级只进目标函数，不进可行域。

``Job.priority`` 不是约束：它不减掉任何一条排程，只改变**同样的排程值多少分**。
这个脚本用一个「两道工序抢一台机器」的最小实例把这件事算到小数点后：

* 两个订单等权同交期，先做谁都要迟 —— 不带优先级时目标值恒为 5.0；
* 给其中一个订单 ``priority=5``，有效权重变成 ``1·(1+5)=6``，最优顺序翻转，
  目标值变成 10.0。

顺带核对：两次求解的**可行性诊断完全一样**（都是空表），因为可行域没动。

从任何工作目录都能跑：
    python examples/m3w4d4_urgency.py
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.models import FJSPInstance, Job, Machine, Operation
from fjsp_core.objective import total_tardiness, weighted_tardiness
from fjsp_core.result import validate_result
from fjsp_shop.registry import get, load_week_modules

SPEC = {"objective": "weighted_tardiness", "time_limit": 5.0, "seed": 0}


def build() -> FJSPInstance:
    """一台机器、两道各 3 分钟的工序、交期都是 2。

    ``J1`` 是紧急订单：``priority=5``。两台都做同一台机器 ``M0``，
    所以无论如何总完工时刻都是 6，两道工序必然一道迟 1、一道迟 4。
    """
    return FJSPInstance(
        jobs=(
            Job("J0", ("A",), release_time=0, due_date=2, weight=1.0, priority=0),
            Job("J1", ("B",), release_time=0, due_date=2, weight=1.0, priority=5),
        ),
        operations=(
            Operation("A", "J0", 0, (("M0", 3),)),
            Operation("B", "J1", 0, (("M0", 3),)),
        ),
        machines=(Machine("M0", "M0"),),
    )


def main() -> None:
    instance = build()

    print("=== 1. 手算：只有一台机器，两种顺序 ===")
    print("  A 先：[0,3) 与 [3,6) → T_A=1, T_B=4")
    print("  B 先：[0,3) 与 [3,6) → T_B=1, T_A=4")
    print("  不带优先级（w 都是 1）：两种顺序都是 1 + 4 = 5 —— 同分，选谁都一样。")
    print("  带优先级（J1 有效权重 1*(1+5)=6）：A 先 = 1*1 + 6*4 = 25；")
    print("                                    B 先 = 6*1 + 1*4 = 10 —— 最优顺序翻转为 B 先。")

    print()
    print("=== 2. 求解：plain vs urgency ===")
    load_week_modules()
    plain = get("fjsp_cpsat_full")(instance, dict(SPEC))
    urgent = get("fjsp_cpsat_full")(instance, {**SPEC, "urgency": True})
    for label, result in (("plain ", plain), ("urgency", urgent)):
        order = " -> ".join(
            item.operation_id
            for item in sorted(result.schedule.operations, key=lambda x: x.start_time)
        )
        print(
            f"  {label}: status={result.status:9s} objective={result.objective:g}  "
            f"上机顺序 {order}"
        )
        print(f"           可行性诊断：{validate_result(instance, result) or '无（通过）'}")
    print(f"  urgency_applied = {urgent.detail['urgency_applied']}")

    print()
    print("=== 3. 拆开看：目标值到底怎么算出来的 ===")
    # ScheduledOperation 只记 operation_id；订单归属要从实例的工序表查。
    job_of = {op.id: op.job_id for op in instance.operations}
    due_of = {job.id: job.due_date for job in instance.jobs}
    for label, result in (("plain ", plain), ("urgency", urgent)):
        sequence = sorted(result.schedule.operations, key=lambda x: x.start_time)
        tardy = []
        for item in sequence:
            done = item.end_time
            due = due_of[job_of[item.operation_id]]
            tardy.append(f"{item.operation_id}: max(0,{done}-{due})")
        print(f"  {label}  完成时刻：{', '.join(f'{i.operation_id}={i.end_time}' for i in sequence)}")
        print(f"           迟期项：{'；'.join(tardy)}")
        print(
            f"           ΣT（不带权）={total_tardiness(instance, result.schedule):g}   "
            f"ΣwT（只认 Job.weight）={weighted_tardiness(instance, result.schedule):g}"
        )
    print("  两次求解的约束完全一样，只是**同一份排程值多少分**变了。")
    print()
    print("  注意最后那个 ΣwT：两次都读出 5。因为 `fjsp_core.objective.weighted_tardiness`")
    print("  的签名里没有 urgency —— 它只认 `Job.weight`，看不到 `priority`。")
    print("  有效权重 w_j*(1+priority_j) 是由求解器在**目标函数**里算的，")
    print("  它把这件事记在了 detail 里：")
    print(f"      plain   detail 关键项：urgency_applied="
          f"{plain.detail.get('urgency_applied')}")
    print(f"      urgency detail 关键项：urgency_applied="
          f"{urgent.detail.get('urgency_applied')}")
    print("  所以「紧急订单」不是一条可行性规则，而是**读分方式**的开关：")
    print("  想让优先级起作用，必须在 spec 里显式打开 urgency。")


if __name__ == "__main__":
    main()
