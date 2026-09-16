"""串行追加解码器的三条手推轨迹与 append-only 行为。

对应 Week 2 Day 2。脚本只打印，不写任何文件，输出确定。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_algorithms.decoder import decode
from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.schedule import Schedule
from scheduling_core.schedule_validation import validate_schedule
from scheduling_core.solution import Candidate


def route_instance() -> Instance:
    """J0 = A(p=3, r=2) -> B(p=2)；J1 = C(p=1, r=0)。A 只能上 M0。"""
    return Instance(
        (Job("J0", ("A", "B"), 2), Job("J1", ("C",))),
        (
            Operation("A", "J0", 3, ("M0",)),
            Operation("B", "J0", 2, ("M0", "M1")),
            Operation("C", "J1", 1, ("M0", "M1")),
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )


def quadruple(schedule: Schedule) -> list[tuple[str, str, int, int]]:
    return [
        (item.operation_id, item.machine_id, item.start_time, item.end_time)
        for item in schedule.operations
    ]


def machine_lines(schedule: Schedule) -> None:
    """按机器打印已排区间，并标出仍旧空闲的时段。"""
    for machine_id in ("M0", "M1"):
        items = sorted(
            (item for item in schedule.operations if item.machine_id == machine_id),
            key=lambda item: item.start_time,
        )
        ranges = "".join(
            f" {item.operation_id}[{item.start_time},{item.end_time})"
            for item in items
        )
        idle = []
        frontier = 0
        for item in items:
            if item.start_time > frontier:
                idle.append(f"[{frontier},{item.start_time})")
            frontier = item.end_time
        idle_text = "空闲 " + " ".join(idle) if idle else "无空闲"
        print(f"    {machine_id}:{ranges}   （{idle_text}）")


def main() -> None:
    instance = route_instance()
    print("instance：J0 = A(p=3, r=2) -> B(p=2)，J1 = C(p=1, r=0)")
    print("A 的资格 =", instance.operations[0].eligible_machine_ids,
          " B 的资格 =", instance.operations[1].eligible_machine_ids,
          " C 的资格 =", instance.operations[2].eligible_machine_ids)

    cases = (
        (
            ("A", "B", "C"),
            ("M0", "M1", "M0"),
            [("A", "M0", 2, 5), ("B", "M1", 5, 7), ("C", "M0", 5, 6)],
        ),
        (
            ("B", "C", "A"),
            ("M0", "M1", "M0"),
            [("C", "M0", 0, 1), ("A", "M0", 2, 5), ("B", "M1", 5, 7)],
        ),
        (
            ("B", "C", "A"),
            ("M0", "M0", "M1"),
            [("C", "M1", 0, 1), ("A", "M0", 2, 5), ("B", "M0", 5, 7)],
        ),
    )

    for index, (order, assignments, expected) in enumerate(cases, start=1):
        candidate = Candidate(order, assignments)
        schedule = decode(instance, candidate)
        validate_schedule(instance, schedule)
        assert quadruple(schedule) == expected, quadruple(schedule)
        assert decode(instance, candidate) == schedule

        order_text = ",".join(order)
        assignment_text = ",".join(assignments)
        print()
        print(f"[轨迹 {index}] order={order_text}  assignments={assignment_text}")
        print("  扫描顺序（= Schedule.operations 的构造顺序）:",
              " -> ".join(item.operation_id for item in schedule.operations))
        for item in schedule.operations:
            print(f"    {item.operation_id}: {item.machine_id}"
                  f"[{item.start_time},{item.end_time})")
        machine_lines(schedule)
        print("  与手算轨迹一致，且重复解码得到相同 Schedule。")

    print()
    print("[append-only] 不向机器已有空隙插入工序")
    first = decode(instance, Candidate(("A", "B", "C"), ("M0", "M1", "M0")))
    c_start = next(
        item.start_time for item in first.operations if item.operation_id == "C"
    )
    print("  轨迹 1 中 A 的释放时间 r=2，M0 的 [0,2) 一直空闲。")
    print(f"  但 C 虽然指派在 M0，start = {c_start}，落在 A 之后，没有回填 [0,2)。")
    print("  原因：decoder 只做 start = max(machine_ready, 前驱完工, 释放时间)，")
    print("        machine_ready 只增不减，机器一旦推进就不会退回填空隙。")

    print()
    print("[输出顺序] Schedule.operations 是构造顺序，不按 start_time 排序")
    shifted = decode(instance, Candidate(("A", "C", "B"), ("M0", "M0", "M1")))
    validate_schedule(instance, shifted)
    print("  order=A,C,B  assignments=M0,M0,M1  ->")
    print("    构造顺序 =", [item.operation_id for item in shifted.operations])
    print("    各自 start =", [item.start_time for item in shifted.operations])
    print("  C 的 start 最小却排在 A 之后，说明输出元组只反映构造顺序。")


if __name__ == "__main__":
    main()
