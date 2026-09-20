"""M3 Week 1 Day 2：Flow Shop baseline 与逐项手算复核。

脚本做四件事：

```text
1. 用 cfg 同款参数生成 flow_5x3（seed 100, 5 订单 x 3 机器, flow_shop）
2. 跑 flow_johnson / flow_neh，打印 ShopResult 的每个字段
3. 手算复核：从甘特行反推 makespan、逐机器查重叠、逐订单查先后顺序、
   并把 4x2 实例的时间线与 Day 1 手算的六个区间逐项对齐
4. 退化情形：只有一台机器时，两个方法的 Cmax 都必须等于总工时
```

关键纪律：**启发式的 ``best_bound`` 必须是 ``None``**，不能拿目标值冒充下界；
每个返回的排程都要过 ``validate_schedule``。

运行：``python examples/m3w1d2_flowshop_baseline.py``
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.models import FJSPInstance
from fjsp_core.objective import makespan
from fjsp_core.result import validate_result
from fjsp_core.schedule_validation import validate_schedule
from fjsp_io.generator import generate_instance
from fjsp_shop.flowshop import flow_johnson, flow_neh, flow_shop_route
from fjsp_shop.gantt import to_gantt_rows

# Day 1 已经手算过的 4x2 时间线：(操作, 机器, 开工, 完工)
HAND_CHECKED = (
    ("J2_O0", "M0", 0, 1),
    ("J0_O0", "M0", 1, 3),
    ("J3_O0", "M0", 3, 6),
    ("J1_O0", "M0", 6, 10),
    ("J2_O1", "M1", 1, 6),
    ("J0_O1", "M1", 6, 9),
    ("J3_O1", "M1", 9, 11),
    ("J1_O1", "M1", 11, 12),
)


def one_machine_instance() -> FJSPInstance:
    """3 个订单、1 台机器：Cmax 与顺序无关，恒等于总工时 3+4+2 = 9。"""
    from fjsp_core.models import Job, Machine, Operation

    minutes = {"J0": 3, "J1": 4, "J2": 2}
    jobs = tuple(Job(job_id, (f"{job_id}_O0",)) for job_id in minutes)
    operations = tuple(
        Operation(f"{job_id}_O0", job_id, 0, (("M0", value),))
        for job_id, value in minutes.items()
    )
    return FJSPInstance(jobs=jobs, operations=operations, machines=(Machine("M0", "M0"),))


def print_result(instance: FJSPInstance, result, label: str) -> None:
    print(f"--- {label} ---")
    print(f"method       = {result.method}")
    print(f"status       = {result.status}")
    print(f"objective    = {result.objective}")
    print(f"best_bound   = {result.best_bound}   （启发式必须为 None）")
    print(f"gap          = {result.gap}")
    print(f"build_time   = {result.build_time:.6f} s")
    print(f"solve_time   = {result.solve_time:.6f} s")
    print(f"iterations   = {result.iterations}")
    print(f"breakdown    = {result.breakdown}")
    print(f"排列          = {result.detail.get('job_sequence')}")
    validate_schedule(instance, result.schedule)
    validate_result(instance, result)
    print("validate_schedule / validate_result 均通过")


def hand_check(instance: FJSPInstance, schedule) -> None:
    """四道手算复核，只要有一条不成立就抛异常 —— 不让脚本带着可疑结果跑完。"""
    rows = to_gantt_rows(instance, schedule)

    # 复核 1：makespan = 所有完工时刻的最大值
    cmax_by_hand = max(row["end_time"] for row in rows)
    assert cmax_by_hand == makespan(instance, schedule), "makespan 与甘特行不一致"
    print(f"复核 1  甘特行最大完工时刻 = {cmax_by_hand}，与 makespan() 一致")

    # 复核 2：逐机器查重叠
    by_machine: dict[str, list[dict]] = {}
    for row in rows:
        by_machine.setdefault(row["machine_id"], []).append(row)
    for machine_id, machine_rows in sorted(by_machine.items()):
        machine_rows.sort(key=lambda row: row["start_time"])
        busy = sum(row["duration"] for row in machine_rows)
        for earlier, later in zip(machine_rows, machine_rows[1:]):
            assert earlier["end_time"] <= later["start_time"], f"{machine_id} 上有重叠"
        print(f"复核 2  {machine_id}：{len(machine_rows)} 道工序，占用 {busy}，无重叠")

    # 复核 3：逐订单查先后顺序与「不早于上一道完工」
    for job in instance.jobs:
        job_rows = [row for row in rows if row["job_id"] == job.id]
        job_rows.sort(key=lambda row: row["start_time"])
        for earlier, later in zip(job_rows, job_rows[1:]):
            assert earlier["end_time"] <= later["start_time"], f"{job.id} 的工序顺序有冲突"
        print(f"复核 3  {job.id}：{len(job_rows)} 道工序按工艺顺序排开，"
              f"从 {job_rows[0]['start_time']} 到 {job_rows[-1]['end_time']}")


def compare_with_hand_checked(instance: FJSPInstance, schedule) -> None:
    """把 4x2 实例的排程与 Day 1 手算的八个区间逐项对齐。"""
    by_id = schedule.by_operation()
    ok = True
    for operation_id, machine_id, start, end in HAND_CHECKED:
        item = by_id[operation_id]
        match = (item.machine_id, item.start_time, item.end_time) == (machine_id, start, end)
        ok = ok and match
        print(f"  {operation_id}  期望 {machine_id} [{start},{end})  "
              f"实际 {item.machine_id} [{item.start_time},{item.end_time})  "
              f"{'一致' if match else '不一致'}")
    print(f"八个区间全部与手算一致：{ok}")
    assert ok, "排程与 Day 1 的手算时间线不符"


def main() -> None:
    print("=" * 72)
    print("第 1 节：手算实例（4x2）逐区间对齐")
    print("=" * 72)
    from examples.m3w1d1_flowshop_rules import TWO_MACHINE, build_flow_shop

    instance_two = build_flow_shop(TWO_MACHINE)
    johnson_two = flow_johnson(instance_two, {"objective": "makespan"})
    print_result(instance_two, johnson_two, "4x2 flow shop / flow_johnson")
    print("\n与 Day 1 手算时间线对齐：")
    compare_with_hand_checked(instance_two, johnson_two.schedule)

    print()
    print("=" * 72)
    print("第 2 节：configs/month3.json 的 flow_5x3（seed 100）")
    print("=" * 72)
    instance = generate_instance(
        seed=100, jobs=5, machines=3, operations_per_job=3, flow_shop=True, flexibility=1
    )
    route, reason = flow_shop_route(instance)
    print(f"识别出的机器序列 = {route}")
    print("\n订单   " + "  ".join(f"{machine_id:>4s}" for machine_id in route) + "   总工时")
    for job in instance.jobs:
        times = [instance.operation(oid).time_on(route[index]) or 0
                 for index, oid in enumerate(job.operation_ids)]
        print(f"{job.id:6s} " + "  ".join(f"{value:4d}" for value in times) + f" {sum(times):7d}")

    for label, method in (("flow_johnson", flow_johnson), ("flow_neh", flow_neh)):
        print()
        result = method(instance, {"objective": "makespan", "time_limit": 10.0, "seed": 0})
        print_result(instance, result, f"flow_5x3 / {label}")

    print()
    print("=" * 72)
    print("第 3 节：手算复核（用 NEH 的排程）")
    print("=" * 72)
    neh = flow_neh(instance, {"objective": "makespan"})
    hand_check(instance, neh.schedule)

    rows = to_gantt_rows(instance, neh.schedule)
    print("\nNEH 排程的全部甘特行：")
    print("machine_id | job_id | operation_id | start | end | duration")
    for row in rows:
        print(f"{row['machine_id']:>10s} | {row['job_id']:>6s} | {row['operation_id']:>9s} | "
              f"{row['start_time']:5d} | {row['end_time']:3d} | {row['duration']:8d}")

    print()
    print("=" * 72)
    print("第 4 节：退化情形 —— 只有一台机器")
    print("=" * 72)
    single = one_machine_instance()
    total_load = sum(op.min_time for op in single.operations)
    for label, method in (("flow_johnson", flow_johnson), ("flow_neh", flow_neh)):
        result = method(single, {"objective": "makespan"})
        print(f"{label:13s} status={result.status:9s} Cmax={result.objective} "
              f"适用性={result.detail.get('applicability', '-')}")
    print(f"总工时 = {total_load}：单机时任何顺序的 Cmax 都等于它。")

    print()
    print("=" * 72)
    print("当日结论")
    print("=" * 72)
    johnson = flow_johnson(instance, {"objective": "makespan"})
    print(f"1. flow_5x3 上 Johnson = {johnson.objective}，NEH = {neh.objective}。")
    print("2. 两者都是启发式（此实例有 3 台机器），best_bound 都是 None。")
    print("3. 手算复核的四道关：makespan 最大完工时刻、机器无重叠、订单有序、"
          "与 Day 1 手算区间逐项一致。")
    print("4. 单机退化情形下两个方法都给出总工时，可作为实现的边界检查。")


if __name__ == "__main__":
    main()
