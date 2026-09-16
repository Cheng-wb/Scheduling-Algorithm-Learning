"""M1W3D2 First Improvement：邻域扫描顺序、逐步接受与停止条件。"""

import sys
from itertools import permutations
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.objective import weighted_completion_time
from scheduling_core.schedule_validation import validate_schedule
from scheduling_core.solution import Candidate
from scheduling_algorithms.decoder import decode
from scheduling_algorithms.neighborhoods import neighbors
from scheduling_algorithms.search import SearchConfig, solve


def one_machine(p: list[int]) -> Instance:
    """单机、每个 Job 一道工序、w=1，工序 ID 依次为 A,B,C..."""
    names = [chr(ord("A") + i) for i in range(len(p))]
    return Instance(
        tuple(Job(name, (name,), 0, None, 1.0) for name in names),
        tuple(
            Operation(name, name, value, ("M0",))
            for name, value in zip(names, p, strict=True)
        ),
        (Machine("M0", "M0"),),
    )


def decode_order(instance: Instance, order: tuple[str, ...]):
    """按给定优先级顺序解码并验证，返回可信排程。"""
    schedule = decode(instance, Candidate(order, ("M0",) * len(order)))
    validate_schedule(instance, schedule)
    return schedule


def timeline(schedule) -> str:
    return "  ".join(
        f"{item.operation_id}:{item.start_time}->{item.end_time}"
        for item in schedule.operations
    )


def main() -> None:
    instance = one_machine([3, 1, 2])
    objective = weighted_completion_time

    print("== 1. 输入：单机 p=[3,1,2]，w=1，目标 ΣwC ==")
    print("  Job  A  B  C")
    print("  p    3  1  2")
    print("  w    1  1  1")
    print(f"  Σp = {sum(op.processing_time for op in instance.operations)}，单机 Cmax 恒为 6")

    print("\n== 2. 初始解 ABC ==")
    initial = Candidate(("A", "B", "C"), ("M0", "M0", "M0"))
    initial_schedule = decode_order(instance, initial.order)
    value = objective(instance, initial_schedule)
    ends = [item.end_time for item in initial_schedule.operations]
    print(f"  {timeline(initial_schedule)}  →  ΣC = {'+'.join(str(end) for end in ends)} = {value}")
    assert value == 13

    print("\n== 3. 邻域扫描顺序（neighbors 的固定产出顺序）==")
    for order in (("A", "B", "C"), ("B", "C", "A")):
        current = Candidate(order, ("M0",) * 3)
        items = [
            (moved.order, objective(instance, decode(instance, moved)))
            for moved in neighbors(instance, current)
        ]
        print(f"  从 {''.join(order)} 出发: " + "  ".join(
            f"{''.join(item_order)}({item_value:.0f})" for item_order, item_value in items
        ))
    print("  邻域 = 5 个去重排列（单资格机器，reassign 只会得到自身）")

    print("\n== 4. First Improvement 逐评价轨迹（budget=12, 显式传入初始解）==")
    result = solve(
        instance,
        SearchConfig(
            algorithm="first",
            objective="weighted_completion_time",
            budget=12,
            seed=0,
        ),
        initial,
    )
    print("  evaluation  proposed  current  best  accepted")
    for item in result.trace:
        print(
            f"  {item.evaluation:>10}  {item.proposed:>8}  {item.current:>7}  "
            f"{item.best:>4}  {item.accepted}"
        )
    print(f"  最终 order={result.candidate.order}  objective={result.objective}  status={result.status}")
    assert result.objective == 10 and result.status == "LOCAL_OPTIMUM"
    assert result.evaluations == 11 and result.evaluations < 12
    print("  第 2 次评价就接受 BAC(11)，随后在 BCA(10) 处停下：完整扫描 5 个邻居无严格改善")

    print("\n== 5. 预算截断 vs 完整扫描 ==")
    truncated = solve(
        instance,
        SearchConfig(
            algorithm="first",
            objective="weighted_completion_time",
            budget=9,
            seed=0,
        ),
        initial,
    )
    print(
        f"  budget=9 : evaluations={truncated.evaluations} "
        f"objective={truncated.objective} status={truncated.status}"
    )
    print(
        f"  budget=12: evaluations={result.evaluations} "
        f"objective={result.objective} status={result.status}"
    )
    assert truncated.objective == result.objective == 10
    assert truncated.status == "BUDGET" and result.status == "LOCAL_OPTIMUM"
    print("  两者目标值相同，但只有完整扫描过全部 5 个邻居才能声称 LOCAL_OPTIMUM")

    print("\n== 6. 独立枚举：本实例的全局最优 ==")
    best = min(
        (
            objective(instance, decode(instance, Candidate(order, ("M0",) * 3))),
            order,
        )
        for order in permutations(("A", "B", "C"))
    )
    print(f"  6 个排列的最小 ΣwC = {best[0]:.0f}，对应 order={best[1]}")
    assert best[0] == result.objective == 10
    print("  单机 w=1 时 SPT 对 ΣCj 最优，所以 BCA 在本实例上也是全局最优")

    print("\n全部断言通过：扫描顺序、逐步接受、BUDGET/LOCAL_OPTIMUM 与枚举对拍均已验证。")


if __name__ == "__main__":
    main()
