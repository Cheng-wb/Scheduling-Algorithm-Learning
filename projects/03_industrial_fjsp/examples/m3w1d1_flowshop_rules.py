"""M3 Week 1 Day 1：Flow Shop 的两条构造规则 —— Johnson 规则与 NEH 插入。

本脚本把两条规则的**构造过程**逐步打印出来，用的是脚本里手写的实现，
不调用 ``fjsp_shop.flowshop`` 里的注册方法；最后再让注册方法跑同样的实例，
用「两套实现给出同一个答案」来交叉验证。

三个实例：

```text
4x2 flow shop   4 个订单 × 2 台机器，Johnson 精确，手算 Cmax = 12
3x3 flow shop   3 个订单 × 3 台机器，Johnson 不适用（>=3 台机器是 NP-hard），NEH 手算 10
3x3 对照        把 Johnson 硬套到 (M0, M2) 两台机器上，看它给出什么
```

运行：``python examples/m3w1d1_flowshop_rules.py``
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.models import FJSPInstance, Job, Machine, Operation, Schedule
from fjsp_core.objective import makespan
from fjsp_core.result import validate_result
from fjsp_shop.flowshop import flow_johnson, flow_neh, neh_insertion_trace
from fjsp_shop.gantt import to_gantt_rows

# 实例数据：(订单, 机器 M0 工时, 机器 M1 工时) —— Day 2~7 一直用这两组数
TWO_MACHINE = (
    ("J0", 2, 3),
    ("J1", 4, 1),
    ("J2", 1, 5),
    ("J3", 3, 2),
)

# 3x3：每个订单都在 M0 → M1 → M2 上各做一道
THREE_MACHINE = (
    ("J0", (3, 2, 2)),
    ("J1", (2, 1, 3)),
    ("J2", (1, 3, 1)),
)


def split_row(row) -> tuple[str, tuple[int, ...]]:
    """兼容两种写法：``("J0", 2, 3)`` 与 ``("J0", (3, 2, 2))`` 都读成 (订单, 工时向量)。"""
    job_id, *rest = row
    if len(rest) == 1 and isinstance(rest[0], (tuple, list)):
        return job_id, tuple(rest[0])
    return job_id, tuple(rest)


def build_flow_shop(rows) -> FJSPInstance:
    """把「每个订单一条工时向量」变成 instance：第 k 道工序固定在 M{k} 上。"""
    jobs: list[Job] = []
    operations: list[Operation] = []
    normalized = [split_row(row) for row in rows]
    machine_width = len(normalized[0][1])
    for job_id, times in normalized:
        operation_ids = tuple(f"{job_id}_O{index}" for index in range(len(times)))
        jobs.append(Job(job_id, operation_ids))
        for index, minutes in enumerate(times):
            operations.append(
                Operation(
                    id=operation_ids[index],
                    job_id=job_id,
                    position=index,
                    machine_times=((f"M{index}", minutes),),
                )
            )
    return FJSPInstance(
        jobs=tuple(jobs),
        operations=tuple(operations),
        machines=tuple(Machine(f"M{index}", f"Machine {index}") for index in range(machine_width)),
    )


def johnson_two_ended(rows) -> list[str]:
    """Johnson 规则的两端构造法：每次取全表最小工时，属于 M0 就接在头部，否则接在尾部。

    平局按订单号升序取，且 ``p1 < p2`` 才算「属于 M0」——这两条都是为了确定性，
    也是 ``fjsp_shop.flowshop.johnson_order`` 用的同一套判定。
    """
    remaining = [(job_id, p1, p2) for job_id, p1, p2 in rows]
    front: list[str] = []
    back: list[str] = []
    while remaining:
        pick = min(remaining, key=lambda item: (min(item[1], item[2]), item[0]))
        remaining.remove(pick)
        job_id, p1, _ = pick
        if p1 < pick[2]:
            front.append(job_id)
        else:
            back.insert(0, job_id)
    return front + back


def johnson_set_form(rows) -> list[str]:
    """同一个规则的集合写法：集合 A（p1 < p2）按 p1 升序，集合 B（p1 >= p2）按 p2 降序。"""
    a = [item for item in rows if item[1] < item[2]]
    b = [item for item in rows if item[1] >= item[2]]
    a.sort(key=lambda item: (item[1], item[0]))
    b.sort(key=lambda item: (-item[2], item[0]))
    return [item[0] for item in a] + [item[0] for item in b]


def decode_two_machine(sequence, rows) -> tuple[list[tuple], int]:
    """两台机器上的解码：M0 上一台接一台不停，M1 上取「前一道完工」与「M0 上自己完工」的较大者。"""
    times = {job_id: (p1, p2) for job_id, p1, p2 in rows}
    m0_end = 0
    m1_end = 0
    timeline: list[tuple] = []
    for job_id in sequence:
        p1, p2 = times[job_id]
        s0, e0 = m0_end, m0_end + p1
        s1 = max(e0, m1_end)
        e1 = s1 + p2
        timeline.append((job_id, s0, e0, s1, e1))
        m0_end, m1_end = e0, e1
    return timeline, m1_end


def decode_three_machine(ordered_jobs) -> tuple[list[tuple], int]:
    """m 台机器的解码：第 k 道工序的开工 = max(同订单上一道完工, 该机器上一道完工)。

    入参是**按排列排好序**的 ``[(订单, 工时向量), ...]``；本函数不重排，谁在前谁先做。
    """
    machine_free = [0] * len(ordered_jobs[0][1])
    timeline: list[tuple] = []
    for job_id, times in ordered_jobs:
        job_free = 0
        for index, minutes in enumerate(times):
            start = max(job_free, machine_free[index])
            end = start + minutes
            timeline.append((job_id, index, start, end))
            machine_free[index] = end
            job_free = end
    return timeline, max(machine_free)


def main() -> None:
    print("=" * 72)
    print("Day 1 / 第 1 节：4x2 flow shop 上的 Johnson 规则")
    print("=" * 72)
    print("订单   p1(M0)   p2(M1)   分派集合")
    for job_id, p1, p2 in TWO_MACHINE:
        group = "A" if p1 < p2 else "B"
        print(f"{job_id:5s} {p1:8d} {p2:8d}   -> 集合 {group}")

    two_ended = johnson_two_ended(TWO_MACHINE)
    set_form = johnson_set_form(TWO_MACHINE)
    print(f"\n两端构造法给出：{two_ended}")
    print(f"集合写法给出：  {set_form}")
    print(f"两种写法在本实例上一致：{two_ended == set_form}")

    timeline, cmax = decode_two_machine(two_ended, TWO_MACHINE)
    print("\n解码（手写实现）：")
    print("订单   M0 开工  M0 完工   M1 开工  M1 完工")
    for job_id, s0, e0, s1, e1 in timeline:
        print(f"{job_id:5s} {s0:8d} {e0:8d} {s1:9d} {e1:9d}")
    print(f"makespan = {cmax}")

    print("\n再用注册方法跑同一个实例，看是否给出同一个答案：")
    instance_two = build_flow_shop(TWO_MACHINE)
    johnson_result = flow_johnson(instance_two, {"objective": "makespan"})
    validate_result(instance_two, johnson_result)
    print(f"  flow_johnson 状态 = {johnson_result.status}，目标值 = {johnson_result.objective}")
    print(f"  排列 = {johnson_result.detail['job_sequence']}，是否精确适用 = "
          f"{johnson_result.detail['applies_directly']}")
    print(f"  模块给出的 makespan = {makespan(instance_two, johnson_result.schedule)}"
          f"（手写解码 = {cmax}）")
    neh_result = flow_neh(instance_two, {"objective": "makespan"})
    print(f"  flow_neh      状态 = {neh_result.status}，目标值 = {neh_result.objective}，"
          f"排列 = {neh_result.detail['job_sequence']}")

    print()
    print("=" * 72)
    print("Day 1 / 第 2 节：3x3 flow shop —— Johnson 不再适用，改用 NEH")
    print("=" * 72)
    instance_three = build_flow_shop(THREE_MACHINE)
    print("订单   M0   M1   M2   总工时")
    for job_id, times in THREE_MACHINE:
        print(f"{job_id:5s} {times[0]:4d} {times[1]:4d} {times[2]:4d} {sum(times):7d}")

    trace = neh_insertion_trace(instance_three)
    print("\nNEH 的插入过程（总工时降序，逐个插到最靠前的并列最优位置）：")
    for number, step in enumerate(trace, start=1):
        print(f"  第 {number} 步：插入 {step['job']}（总工时 {step['total_time']}）")
        print(f"          候选位置与对应 makespan：{list(enumerate(step['candidates']))}")
        print(f"          选中位置 {step['position']}，当前排列 {step['partial']}，"
              f"makespan = {step['makespan']}")
    neh_sequence = [job for job in trace[-1]["partial"]]
    print(f"\nNEH 最终排列 = {neh_sequence}，makespan = {trace[-1]['makespan']}")

    order_by_id = {job_id: times for job_id, times in THREE_MACHINE}
    hand_timeline, hand_cmax = decode_three_machine(
        [(job_id, order_by_id[job_id]) for job_id in neh_sequence]
    )
    print(f"手写解码复核 = {hand_cmax}（与 NEH 的 {trace[-1]['makespan']} 相同："
          f"{hand_cmax == trace[-1]['makespan']}）")

    print("\n把 Johnson 硬套到 (M0, M2) 这两台机器上会得到什么：")
    bottleneck_rows = tuple((job_id, times[0], times[2]) for job_id, times in THREE_MACHINE)
    bottleneck_sequence = johnson_set_form(bottleneck_rows)
    _, hand2_cmax = decode_three_machine(
        [(job_id, order_by_id[job_id]) for job_id in bottleneck_sequence]
    )
    print(f"  (M0, M2) 上的 Johnson 排列 = {bottleneck_sequence}，"
          f"放回 3 台机器解码 = {hand2_cmax}")
    print(f"  与 NEH 的 {trace[-1]['makespan']} 相比："
          f"{'更差' if hand2_cmax > trace[-1]['makespan'] else '不差于'}")

    neh_registered = flow_neh(instance_three, {"objective": "makespan"})
    validate_result(instance_three, neh_registered)
    johnson_registered = flow_johnson(instance_three, {"objective": "makespan"})
    validate_result(instance_three, johnson_registered)
    print("\n注册方法复核：")
    print(f"  flow_neh     状态 = {neh_registered.status}，目标值 = "
          f"{neh_registered.objective}，排列 = {neh_registered.detail['job_sequence']}")
    print(f"  flow_johnson 状态 = {johnson_registered.status}，目标值 = "
          f"{johnson_registered.objective}，适用性 = {johnson_registered.detail['applicability']}")
    print(f"  flow_johnson 自报的下界 = {johnson_registered.best_bound}（启发式必须为 None）")

    rows = to_gantt_rows(instance_three, neh_registered.schedule)
    print("\nNEH 排程的甘特行（前 4 条，字段固定为六列）：")
    for row in rows[:4]:
        print("  " + " | ".join(f"{key}={row[key]}" for key in
                                ("machine_id", "job_id", "operation_id",
                                 "start_time", "end_time", "duration")))

    print()
    print("=" * 72)
    print("当日结论")
    print("=" * 72)
    print("1. Johnson 规则只对 F2||Cmax 精确；>=3 台机器的 flow shop 是 NP-hard，")
    print("   只能给启发式，不能声称最优。")
    print("2. NEH 是启发式：插入顺序按总工时降序，位置取第一个达到最小 makespan 的点。")
    print("3. 同样两台机器时，手写解码与注册方法的 makespan 必须一致 —— 这是对拍基线。")
    print(f"4. 本实例观察：NEH {neh_registered.objective} vs 瓶颈对 Johnson "
          f"{johnson_registered.objective}。")


if __name__ == "__main__":
    main()
