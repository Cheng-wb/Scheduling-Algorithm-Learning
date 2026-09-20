"""M3 Week 2 Day 2：FJSP 解码器 —— 把 (assignment, order) 变成合法排程。

脚本做六件事：

```text
1. gap_2x2 的结构：M0 上那段被工艺路线逼出来的空档 [0, 12)
2. 同一个 (assignment, order)，附加式解码 vs 插入式解码：17 对 14
3. 穷举该指派下的 6 个拓扑序，两种解码各取最好 -> 静态顺序族的上限
4. 动态派工（非延迟 ECT）在同一指派上的结果：顺序不再由外部给定
5. 拒绝非法输入：非拓扑序、缺工序、不合格机器，三种都要有可读的报错
6. 纪律复核：每个返回的排程都过 validate_schedule
```

运行：``python examples/m3w2d2_decoder.py``
"""

import sys
from itertools import permutations
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.models import FJSPInstance
from fjsp_core.schedule_validation import validate_schedule
from fjsp_shop.fjsp import decode, dispatch
from fjsp_shop.toy_instances import TOY_INSTANCES

#: gap_2x2 上待手算的那个指派（Day 1 已用过）
ASSIGNMENT = {"O00": "M1", "O01": "M0", "O10": "M1", "O11": "M0"}
ORDER = ("O00", "O10", "O11", "O01")


def makespan(schedule) -> int:
    return max(item.end_time for item in schedule.operations)


def timeline(schedule) -> str:
    return "  ".join(
        f"{item.operation_id}@{item.machine_id}[{item.start_time},{item.end_time})"
        for item in schedule.operations
    )


def topological_orders(instance: FJSPInstance) -> list[tuple[str, ...]]:
    """从全部 ``n!`` 个排列里挑出拓扑序：每道工序都在它同订单前道工序之后。"""
    ids = [op.id for op in instance.operations]
    kept = []
    for permutation in permutations(ids):
        position = {op_id: index for index, op_id in enumerate(permutation)}
        if all(
            position[before] < position[after]
            for job in instance.jobs
            for before, after in zip(job.operation_ids, job.operation_ids[1:])
        ):
            kept.append(permutation)
    return kept


def machine_loads(instance, schedule) -> dict[str, int]:
    by_id = {op.id: op for op in instance.operations}
    loads = {machine.id: 0 for machine in instance.machines}
    for item in schedule.operations:
        loads[item.machine_id] += by_id[item.operation_id].time_on(item.machine_id)
    return loads


def refuse(label: str, action) -> None:
    """执行一个必须失败的调用，把拒绝原因原样打印出来。"""
    try:
        action()
    except ValueError as exc:
        print(f"  {label}")
        print(f"    拒绝：{exc}")
    else:  # pragma: no cover - 走到这里说明闸门失效了
        raise AssertionError(f"{label} 本该被拒绝")


def main() -> None:
    instance = TOY_INSTANCES["gap_2x2"]()

    print("=== FJSP 解码器：assignment + order -> Schedule ===")
    print()

    # ---------------------------------------------------------------- 1
    print("== 1. gap_2x2 的结构 ==")
    print("  工序   订单  M0   M1     （-- = 不合格）")
    for op in instance.operations:
        m0 = op.time_on("M0")
        m1 = op.time_on("M1")
        print(f"  {op.id:<6} {op.job_id:<5} {m0:>2}   {m1:>2}")
    print("  工艺路线：J0 = O00 -> O01，J1 = O10 -> O11。")
    print("  待手算的指派：O00->M1, O01->M0, O10->M1, O11->M0")
    print("  待手算的顺序：O00, O10, O11, O01")
    print()

    # ---------------------------------------------------------------- 2
    print("== 2. 同一个输入，两种解码 ==")
    append = decode(instance, ASSIGNMENT, ORDER, insert=False)
    insert = decode(instance, ASSIGNMENT, ORDER, insert=True)
    validate_schedule(instance, append)
    validate_schedule(instance, insert)
    print(f"  附加式（append）：makespan = {makespan(append)}")
    print(f"    {timeline(append)}")
    print(f"  插入式（insert）：makespan = {makespan(insert)}")
    print(f"    {timeline(insert)}")
    print("  差别在 O01：它的前道 O00 在 t=4 完工，而 M0 从 t=0 起一直空着，")
    print("  直到 O11 在 t=12 被放进来。插入式把 O01 放进 [4, 7)，附加式只肯接在 14 之后。")
    print(f"  省下的时间 = {makespan(append)} - {makespan(insert)} 分钟。")
    print()

    # ---------------------------------------------------------------- 3
    print("== 3. 静态顺序族的上限：穷举该指派下的全部拓扑序 ==")
    total = 1
    for number in range(2, len(instance.operations) + 1):
        total *= number
    orders = topological_orders(instance)
    print(f"  全部排列 = 4! = {total}，其中拓扑序 = {len(orders)}"
          f"（= 4! / (2! * 2!)，被排除的 {total - len(orders)} 个都违反工艺路线）")
    for label, flag in (("附加式", False), ("插入式", True)):
        values = {}
        for order in orders:
            schedule = decode(instance, ASSIGNMENT, order, insert=flag)
            validate_schedule(instance, schedule)
            values[order] = makespan(schedule)
        best = min(values.values())
        worst = max(values.values())
        best_order = min(values, key=lambda key: values[key])
        print(f"  {label}：最好 {best}，最差 {worst}，最好的顺序 = {best_order}")
    print("  同一个指派下只换顺序，附加式就在 14~17 之间摆动（差 3 分钟）——")
    print("  顺序确实有分量，但两种解码在本指派下都停在 14：")
    print("  顺序这一维能收多少，取决于机器指派已经把它逼到了什么位置。")
    print()

    # ---------------------------------------------------------------- 4
    print("== 4. 动态派工：不给定顺序，让状态自己决定 ==")
    for rule in ("ect", "est", "spt", "mwkr"):
        schedule = dispatch(instance, ASSIGNMENT, rule=rule)
        validate_schedule(instance, schedule)
        print(f"  rule={rule:<5} makespan = {makespan(schedule):>2}   {timeline(schedule)}")
    print("  派工不需要外部顺序，但它只覆盖「非延迟」这一族：机器有空闲就立刻填。")
    print()

    # ---------------------------------------------------------------- 5
    print("== 5. 拒绝非法输入 ==")
    refuse(
        "顺序违反工艺路线（O01 排到 O00 之前）：",
        lambda: decode(instance, ASSIGNMENT, ("O01", "O00", "O10", "O11")),
    )
    refuse(
        "顺序少一道工序：",
        lambda: decode(instance, ASSIGNMENT, ("O00", "O10", "O11")),
    )
    refuse(
        "工序被指到不合格的机器（O00 -> M9）：",
        lambda: decode(instance, dict(ASSIGNMENT, O00="M9"), ORDER),
    )
    refuse(
        "指派缺一道工序：",
        lambda: decode(instance, {"O00": "M1", "O01": "M0", "O10": "M1"}, ORDER),
    )
    print()

    # ---------------------------------------------------------------- 6
    print("== 6. 纪律复核 ==")
    print("  上面每一个排程都调用过 validate_schedule，没有抛错。")
    print("  独立验证器不经过解码器的任何代码：它重新查机器重叠、工艺路线、释放时间。")
    schedule = decode(instance, ASSIGNMENT, ORDER, insert=True)
    loads = machine_loads(instance, schedule)
    print(f"  插入式排程的机器负载 = {loads}")
    print(f"  每道工序各取最快机器的总工时 = {sum(op.min_time for op in instance.operations)}，"
          f"本指派的负载合计 = {sum(loads.values())}。")
    print("  多出的 2 分钟来自 O00：它被指到 M1（4 分钟），而它最快的机器是 M0（2 分钟）。")
    print("  解码器不判断好坏，只保证合法：指派是它的输入，不是它的输出。")


if __name__ == "__main__":
    main()
