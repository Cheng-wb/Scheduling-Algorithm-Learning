"""M1W2D4 独立排程验证器：九类破坏的诊断输出与 [start,end) 相接约定。

本脚本只做三件事：
1. 手工构造 Day 2 实例的一条可行排程，确认 schedule_errors 返回空列表；
2. 依次注入九类破坏，打印 schedule_errors 的诊断并确认 validate_schedule 抛异常；
3. 演示区间相接合法、单个坏排程可产生多条诊断，以及 frontier 能识别长区间包住短区间。
验证器不调用 decoder，因此这里构造的每一条排程都是字面量，不来自任何算法。
"""

import sys
from dataclasses import replace
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.schedule import Schedule, ScheduledOperation
from scheduling_core.schedule_validation import schedule_errors, validate_schedule


def route_instance() -> Instance:
    """两作业三工序实例：J0 = A -> B（A 只能上 M0），J1 = C（释放时刻 2）。"""
    return Instance(
        (Job("J0", ("A", "B"), 2), Job("J1", ("C",))),
        (
            Operation("A", "J0", 3, ("M0",)),
            Operation("B", "J0", 2, ("M0", "M1")),
            Operation("C", "J1", 1, ("M0", "M1")),
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )


def feasible_items() -> list[ScheduledOperation]:
    """一条可行排程：A 在 M0[2,5)，B 在 M1[5,7)，C 在 M0[5,6)。"""
    return [
        ScheduledOperation("A", "M0", 2, 5),
        ScheduledOperation("B", "M1", 5, 7),
        ScheduledOperation("C", "M0", 5, 6),
    ]


def corrupt(kind: str, items: list[ScheduledOperation]) -> list[ScheduledOperation]:
    """按类型注入一处破坏；每条分支都只改一项，便于对照诊断。"""
    items = list(items)
    if kind == "precedence":
        items[1] = replace(items[1], start_time=2, end_time=4)
    elif kind == "overlap":
        items[2] = replace(items[2], start_time=3, end_time=4)
    elif kind == "illegal assignment":
        items[0] = replace(items[0], machine_id="M1")
    elif kind == "missing":
        items.pop()
    elif kind == "duplicate":
        items.append(items[0])
    elif kind == "release":
        items[0] = replace(items[0], start_time=0, end_time=3)
    elif kind == "duration":
        items[0] = replace(items[0], end_time=6)
    elif kind == "unknown operation":
        items[0] = replace(items[0], operation_id="X")
    elif kind == "invalid time type":
        items[0] = replace(items[0], start_time=float("nan"))
    else:
        raise ValueError(f"unknown corruption kind: {kind}")
    return items


CORRUPTIONS = (
    "precedence",
    "overlap",
    "illegal assignment",
    "missing",
    "duplicate",
    "release",
    "duration",
    "unknown operation",
    "invalid time type",
)


def touching_case() -> tuple[str, list[str]]:
    """[0,3) 与 [3,5) 相接：start 不早于 frontier 即合法，不要求 start > frontier。"""
    instance = Instance(
        (Job("J0", ("A", "B")),),
        (Operation("A", "J0", 3, ("M0",)), Operation("B", "J0", 2, ("M0",))),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )
    touching = Schedule(
        (
            ScheduledOperation("A", "M0", 0, 3),
            ScheduledOperation("B", "M0", 3, 5),
        )
    )
    return instance.jobs[0].id, schedule_errors(instance, touching)


def enclosing_case() -> list[str]:
    """M0 上 [0,10) 包住 [1,2) 与 [4,5)：frontier 保持 10，两条都被识别。"""
    instance = Instance(
        (Job("J0", ("A",)), Job("J1", ("B",)), Job("J2", ("C",))),
        (
            Operation("A", "J0", 10, ("M0",)),
            Operation("B", "J1", 1, ("M0",)),
            Operation("C", "J2", 1, ("M0",)),
        ),
        (Machine("M0", "M0"),),
    )
    nested = Schedule(
        (
            ScheduledOperation("A", "M0", 0, 10),
            ScheduledOperation("B", "M0", 1, 2),
            ScheduledOperation("C", "M0", 4, 5),
        )
    )
    return schedule_errors(instance, nested)


def main() -> None:
    instance = route_instance()

    print("== 1. 可行排程（手工构造，不经过 decoder）==")
    base = feasible_items()
    for item in base:
        print(
            f"  {item.operation_id} on {item.machine_id} "
            f"[{item.start_time},{item.end_time})"
        )
    base_errors = schedule_errors(instance, Schedule(tuple(base)))
    validate_schedule(instance, Schedule(tuple(base)))
    print(f"  schedule_errors -> {base_errors}；validate_schedule 未抛异常")

    print("\n== 2. 九类破坏的诊断 ==")
    for kind in CORRUPTIONS:
        errors = schedule_errors(instance, Schedule(tuple(corrupt(kind, base))))
        raised = "未抛出"
        try:
            validate_schedule(instance, Schedule(tuple(corrupt(kind, base))))
        except ValueError as exc:
            raised = str(exc)
        print(f"  [{kind}] {len(errors)} 条诊断")
        for error in errors:
            print(f"      {error}")
        print(f"      validate_schedule -> ValueError: {raised}")

    print("\n== 3. [start,end) 相接是合法的 ==")
    job_id, errors = touching_case()
    print(f"  {job_id}: A M0[0,3) 与 B M0[3,5) 相接 -> {errors}")
    assert errors == []

    print("\n== 4. 一个坏排程可以有多条诊断 ==")
    duration_errors = schedule_errors(
        instance, Schedule(tuple(corrupt("duration", base)))
    )
    print(f"  duration 类共 {len(duration_errors)} 条：{duration_errors}")
    assert len(duration_errors) == 3

    print("\n== 5. frontier 识别长区间包住短区间 ==")
    nested_errors = enclosing_case()
    for error in nested_errors:
        print(f"  {error}")
    assert len(nested_errors) == 2

    print("\n全部断言通过。")


if __name__ == "__main__":
    main()
