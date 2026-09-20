"""M3 Week 1 Day 3：析取图、关键路径、关键块。

五节：

```text
1. 建图     手写排程 -> 节点/弧（源弧、路线弧、机器弧、汇弧）、每台机器的定向
2. 关键路径 最长路径，逐条弧验证，长度必须等于 makespan（左移排程上成立）
3. 关键块   关键路径上同机器且相邻的极大段
4. 定理前提 把 M2 的末道工序人工推迟 -> 出现松弛、路径长度 < makespan、检查函数报错
5. 归一化   左移排程把定理前提补回来：makespan 不升、路径长度重新等于 makespan
```

运行：``python examples/m3w1d3_disjunctive_graph.py``
"""

import sys
from dataclasses import replace
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.models import Schedule, ScheduledOperation
from fjsp_core.objective import makespan
from fjsp_core.schedule_validation import validate_schedule
from fjsp_io.standard import load_standard_jsp
from fjsp_shop.graph import (
    analyze,
    build_graph,
    check_critical_path,
    critical_block_machines,
    critical_blocks,
    critical_path,
    left_shift_schedule,
    path_length,
)
from fjsp_shop.jsp import jsp_priority

DATA = Path(__file__).resolve().parents[1] / "tests" / "data" / "tiny3x3.jsp"

# 手算的最优排程（makespan = 7 = 最大机器负载）。逐条写死，不经过任何算法。
HAND_MADE = (
    ("J0_O0", "M0", 0, 2),
    ("J0_O1", "M1", 2, 5),
    ("J0_O2", "M2", 5, 6),
    ("J1_O0", "M1", 0, 2),
    ("J1_O1", "M2", 3, 5),
    ("J1_O2", "M0", 5, 7),
    ("J2_O0", "M2", 0, 3),
    ("J2_O1", "M0", 3, 4),
    ("J2_O2", "M1", 5, 7),
)


def hand_schedule() -> Schedule:
    return Schedule(
        tuple(ScheduledOperation(oid, machine_id, start, end)
              for oid, machine_id, start, end in HAND_MADE)
    )


def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def main() -> None:
    instance = load_standard_jsp(DATA)
    schedule = hand_schedule()
    validate_schedule(instance, schedule)
    print(f"实例：{instance.meta['source']}，"
          f"{len(instance.jobs)} 订单 x {len(instance.machines)} 机器，"
          f"{instance.total_operation_count} 道工序")
    print(f"手算排程的 makespan = {makespan(instance, schedule)}")

    section("第 1 节：建图 —— 节点与四类弧")
    graph = build_graph(instance, schedule)
    print(f"工序节点数 = {len(graph.nodes)}"
          f"（虚拟源点与汇点不放进 nodes，只在弧的端点上出现），弧数 = {len(graph.arcs)}")
    kinds: dict[str, int] = {}
    for arc in graph.arcs:
        kinds[arc.kind] = kinds.get(arc.kind, 0) + 1
    for kind in ("source", "job", "machine", "sink"):
        print(f"  {kind:8s} 弧 {kinds.get(kind, 0):3d} 条")
    print("\n每台机器上的定向（这就是「析取弧选择了哪个方向」）：")
    for machine in instance.machines:
        sequence = graph.sequence_on(machine.id)
        print(f"  {machine.id}：{' -> '.join(sequence)}")
    print("\n源点出发的弧（权重 = 订单释放时间）：")
    for arc in graph.successors("__source__"):
        print(f"  {arc.tail} -> {arc.head}  权重 {arc.weight}")
    order = graph.topological_order()
    print(f"\n拓扑序长度 = {len(order)}"
          f"（= 工序节点 {len(graph.nodes)} + 源点 + 汇点），含环 = {graph.has_cycle()}")

    section("第 2 节：关键路径 = 最长路径")
    path = critical_path(instance, schedule)
    length = path_length(instance, schedule, path)
    print(f"关键路径（{len(path)} 道工序）：")
    for index, operation_id in enumerate(path):
        item = schedule.by_operation()[operation_id]
        prefix = "  " if index == 0 else "  ->"
        print(f"{prefix} {operation_id}  {item.machine_id} "
              f"[{item.start_time},{item.end_time})")
    print(f"\n路径长度（独立重算：首道工序所在订单的释放时间 + 沿途工时）= {length}")
    print(f"makespan = {makespan(instance, schedule)}")
    print(f"两者相等：{length == makespan(instance, schedule)}")
    print("\n逐条弧验证（关键路径上每对相邻工序之间必须真的有弧）：")
    for tail, head in zip(path, path[1:]):
        arc = graph.arc_between(tail, head)
        print(f"  {tail} -> {head}  弧类型 = {arc.kind if arc else '不存在'}")
    analysis = analyze(instance, schedule)
    print(f"\nanalyze：path_length = {analysis.path_length}，"
          f"graph_length = {analysis.graph_length}，makespan = {analysis.makespan}")
    print(f"check_critical_path 返回 = {check_critical_path(instance, schedule)}")

    section("第 3 节：关键块 —— 关键路径上同机器且相邻的极大段")
    item_of = schedule.by_operation()
    blocks = critical_blocks(instance, schedule)
    machines_of_block = critical_block_machines(instance, schedule)
    for block, machine_id in zip(blocks, machines_of_block):
        first, last = item_of[block[0]], item_of[block[-1]]
        print(f"  机器 {machine_id}：{list(block)}")
        print(f"        从 {first.start_time} 到 {last.end_time}，"
              f"共 {len(block)} 道工序，块内无空隙 = "
              f"{all(item_of[a].end_time == item_of[b].start_time
                     for a, b in zip(block, block[1:]))}")
    joined = tuple(operation_id for block in blocks for operation_id in block)
    print(f"\n块拼起来 = {list(joined)}")
    print(f"与关键路径完全相同：{joined == path}")

    section("第 4 节：定理的前提 —— 把 M2 的末道工序人工推迟")
    delayed_operations = tuple(
        replace(item, start_time=item.start_time + 3, end_time=item.end_time + 3)
        if item.operation_id == "J0_O2"
        else item
        for item in schedule.operations
    )
    delayed = Schedule(delayed_operations)
    validate_schedule(instance, delayed)  # 推迟 3 个单位后仍然可行
    analysis_delayed = analyze(instance, delayed)
    before_item = schedule.by_operation()["J0_O2"]
    after_item = delayed.by_operation()["J0_O2"]
    print(f"J0_O2 从 [{before_item.start_time},{before_item.end_time}) "
          f"推迟到 [{after_item.start_time},{after_item.end_time})")
    print("推迟后排程仍然可行：validate_schedule 未报错")
    print(f"推迟后 makespan = {makespan(instance, delayed)}")
    print(f"推迟后路径长度 = {analysis_delayed.path_length}")
    print(f"松弛工序（开工晚于最早可开工时刻的工序）= {list(analysis_delayed.slack)}")
    print(f"是否左移排程 = {analysis_delayed.is_left_shifted}")
    print(f"路径长度 == makespan = {analysis_delayed.matches_makespan}")
    try:
        check_critical_path(instance, delayed)
    except ValueError as error:
        print(f"check_critical_path 拒绝：{error}")

    section("第 5 节：左移排程把前提补回来")
    shifted = left_shift_schedule(instance, delayed)
    validate_schedule(instance, shifted)
    analysis_shifted = analyze(instance, shifted)
    print(f"左移后 makespan = {makespan(instance, shifted)}"
          f"（不高于推迟后的 {makespan(instance, delayed)}）")
    print(f"左移后是否左移排程 = {analysis_shifted.is_left_shifted}，"
          f"松弛 = {list(analysis_shifted.slack)}")
    print(f"左移后路径长度 = {analysis_shifted.path_length}，"
          f"重新等于 makespan = {analysis_shifted.matches_makespan}")
    print("\n左移前后的时间线对比：")
    before = {item.operation_id: (item.start_time, item.end_time) for item in delayed.operations}
    after = {item.operation_id: (item.start_time, item.end_time) for item in shifted.operations}
    for operation_id in sorted(before):
        mark = "" if before[operation_id] == after[operation_id] else "   <- 被前移"
        print(f"  {operation_id}  {before[operation_id]} -> {after[operation_id]}{mark}")

    section("对照：非延迟列表调度给出的排程")
    for rule in ("mwr", "spt"):
        result = jsp_priority(instance, {"objective": "makespan", "priority": rule})
        validate_schedule(instance, result.schedule)
        result_analysis = analyze(instance, result.schedule)
        print(f"  {rule:4s} Cmax = {result.objective:5.1f}  "
              f"关键路径长度 = {result_analysis.path_length}  "
              f"关键块 = {[list(block) for block in critical_blocks(instance, result.schedule)]}")

    section("当日结论")
    print("1. 析取图 = 路线弧（硬约束）+ 机器弧（由排程定向）+ 源弧/汇弧（权重=工时/释放时间）。")
    print("2. 左移排程上，最长路径长度恰好等于 makespan —— 一切基于关键路径的判断都以它为前提。")
    print("3. 关键块 = 关键路径上同机器且相邻的极大段；块内相邻工序必须首尾相接。")
    print("4. 非左移排程上等式失效，必须先归一化再谈关键路径 —— 检查函数会明确报错而不是硬算。")


if __name__ == "__main__":
    main()
