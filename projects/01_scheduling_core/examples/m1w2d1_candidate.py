"""Candidate 表示：order 是优先级列表、assignments 对齐 instance.operations。

对应 Week 2 Day 1。脚本只打印，不写任何文件，输出确定。
"""

import sys
from itertools import permutations, product
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_algorithms.decoder import decode
from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.schedule_validation import validate_schedule
from scheduling_core.solution import Candidate, validate_candidate


def route_instance() -> Instance:
    """两作业三工序：J0 = A(p=3, r=2) -> B(p=2)；J1 = C(p=1, r=0)。"""
    return Instance(
        (Job("J0", ("A", "B"), 2), Job("J1", ("C",))),
        (
            Operation("A", "J0", 3, ("M0",)),
            Operation("B", "J0", 2, ("M0", "M1")),
            Operation("C", "J1", 1, ("M0", "M1")),
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )


def show(instance: Instance, candidate: Candidate) -> None:
    validate_candidate(instance, candidate)
    schedule = decode(instance, candidate)
    validate_schedule(instance, schedule)
    order_text = ",".join(candidate.order)
    assignment_text = ",".join(candidate.assignments)
    print(f"  order={order_text:<6} assignments={assignment_text}")
    print(f"    构造顺序 = {[item.operation_id for item in schedule.operations]}")
    for item in schedule.operations:
        print(
            f"    {item.operation_id}: {item.machine_id}"
            f"[{item.start_time},{item.end_time})"
        )


def main() -> None:
    instance = route_instance()
    print("instance.operations 顺序 =", tuple(op.id for op in instance.operations))
    print("A 的资格 =", instance.operations[0].eligible_machine_ids,
          " B 的资格 =", instance.operations[1].eligible_machine_ids,
          " C 的资格 =", instance.operations[2].eligible_machine_ids)

    print()
    print("[1] 三个编码例子")
    entries = (
        (Candidate(("A", "B", "C"), ("M0", "M1", "M0")), "A->M0, B->M1, C->M0"),
        (Candidate(("B", "C", "A"), ("M0", "M1", "M0")), "只改优先级，指派不变"),
        (Candidate(("B", "C", "A"), ("M0", "M0", "M1")), "B 改到 M0、C 改到 M1"),
    )
    for candidate, note in entries:
        print(f"- {note}")
        show(instance, candidate)

    print()
    print("[2] order 是优先级列表，不是拓扑序")
    out_of_order = Candidate(("B", "C", "A"), ("M0", "M1", "M0"))
    print("  B 的前驱 A 排在 B 之后，order =", out_of_order.order)
    schedule = decode(instance, out_of_order)
    validate_schedule(instance, schedule)
    print("  decode 仍产出可行排程，构造顺序 =",
          [item.operation_id for item in schedule.operations])
    print("  B 排在第一位，但 A 未排定前不会被选中，B 的 start =",
          next(item.start_time for item in schedule.operations
               if item.operation_id == "B"))

    print()
    print("[3] 表示冗余：不同 order 得到同一个 Schedule")
    first = decode(instance, Candidate(("A", "B", "C"), ("M0", "M1", "M0")))
    second = decode(instance, Candidate(("B", "A", "C"), ("M0", "M1", "M0")))
    print("  (A,B,C)/(M0,M1,M0) == (B,A,C)/(M0,M1,M0) ?", first == second)
    print("  原因：B 的优先级再高也排在 A 之后，两者构造顺序都是 A,B,C")

    third = decode(instance, Candidate(("B", "C", "A"), ("M0", "M1", "M0")))
    fourth = decode(instance, Candidate(("C", "A", "B"), ("M0", "M1", "M0")))
    print("  (B,C,A)/(M0,M1,M0) == (C,A,B)/(M0,M1,M0) ?", third == fourth)

    seen = {}
    for order in permutations(("A", "B", "C")):
        for assignment in product(("M0",), ("M0", "M1"), ("M0", "M1")):
            candidate = Candidate(order, assignment)
            schedule = decode(instance, candidate)
            seen.setdefault(schedule, []).append(candidate)
    print("  合法候选解 =", sum(len(group) for group in seen.values()),
          " 不同 Schedule =", len(seen))

    print()
    print("[4] assignments 对齐 instance.operations，不随 order 重排")
    candidate = Candidate(("C", "A", "B"), ("M0", "M0", "M1"))
    print("  order         =", candidate.order)
    print("  assignments   =", candidate.assignments)
    for op, machine in zip(instance.operations, candidate.assignments):
        print(f"    {op.id} -> {machine}   （第 {instance.operations.index(op) + 1} 位）")

    print()
    print("[5] validate_candidate 的拒绝边界")
    bad = (
        ("缺失工序", Candidate(("A", "B", "A"), ("M0", "M1", "M0"))),
        ("指派长度不符", Candidate(("A", "B", "C"), ("M0", "M1"))),
        ("不合格机器", Candidate(("A", "B", "C"), ("M1", "M0", "M0"))),
    )
    for name, candidate in bad:
        try:
            validate_candidate(instance, candidate)
        except ValueError as error:
            print(f"  {name:<8} -> ValueError: {error}")


if __name__ == "__main__":
    main()
