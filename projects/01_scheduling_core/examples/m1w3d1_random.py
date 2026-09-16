"""M1W3D1 搜索契约：SearchConfig/SearchResult、预算单位与 Random Search 轨迹。"""

import sys
from dataclasses import fields
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.objective import total_tardiness
from scheduling_core.schedule_validation import validate_schedule
from scheduling_algorithms.decoder import decode, initial_candidate
from scheduling_algorithms.oracle import exhaustive_optimum
from scheduling_algorithms.search import (
    ALGORITHMS,
    OBJECTIVES,
    SearchConfig,
    SearchResult,
    solve,
)


def demo_instance() -> Instance:
    """单机 4 工序小实例：目标 total_tardiness，LPT 初始解不是最优。"""
    return Instance(
        tuple(
            Job(f"J{i}", (f"O{i}",), 0, due, 1.0)
            for i, due in enumerate([3, 6, 12, 20])
        ),
        tuple(
            Operation(f"O{i}", f"J{i}", p, ("M0",))
            for i, p in enumerate([9, 7, 5, 3])
        ),
        (Machine("M0", "M0"),),
    )


def singleton_instance() -> Instance:
    """单工序、单机器：随机搜索只能反复提出同一个候选。"""
    return Instance(
        (Job("J0", ("O0",), 0, 5, 1.0),),
        (Operation("O0", "J0", 3, ("M0",)),),
        (Machine("M0", "M0"),),
    )


def main() -> None:
    instance = demo_instance()

    print("== 1. 搜索契约 ==")
    print("  solve(instance, config, initial=None) -> SearchResult")
    print(f"  ALGORITHMS = {ALGORITHMS}")
    print(f"  OBJECTIVES = {tuple(OBJECTIVES)}")
    print("  SearchConfig 字段与默认值：")
    for item in fields(SearchConfig):
        print(f"    {item.name:18} = {item.default!r}")
    print("  SearchResult 字段：")
    for item in fields(SearchResult):
        print(f"    {item.name:18} : {item.type}")
    print("  所有目标都是最小化；只有 OBJECTIVES 里的三个名字可以选")

    print("\n== 2. 默认初始解：LPT 优先级 + 贪心指派（只花 1 次评价）==")
    baseline = initial_candidate(instance)
    baseline_schedule = decode(instance, baseline)
    validate_schedule(instance, baseline_schedule)
    baseline_value = total_tardiness(instance, baseline_schedule)
    lpt_result = solve(
        instance, SearchConfig(algorithm="lpt", objective="total_tardiness")
    )
    print(f"  initial_candidate order={baseline.order} assign={baseline.assignments}")
    print(f"  初始值 = {baseline_value}")
    print(
        f"  algorithm=lpt: evaluations={lpt_result.evaluations} "
        f"status={lpt_result.status} objective={lpt_result.objective}"
    )
    assert lpt_result.evaluations == 1 and lpt_result.status == "BASELINE"
    assert lpt_result.objective == baseline_value
    print("  LPT 基线只用 1 次评价，不人为填满 budget=200")

    print("\n== 3. 预算单位：budget=1 只返回初始解 ==")
    one = solve(
        instance,
        SearchConfig(algorithm="random", objective="total_tardiness", budget=1),
    )
    point = one.trace[0]
    print(
        f"  evaluations={one.evaluations} status={one.status} objective={one.objective}"
    )
    print(
        f"  trace[0]: proposed={point.proposed} current={point.current} "
        f"best={point.best} accepted={point.accepted}"
    )
    assert one.evaluations == 1 and len(one.trace) == 1
    assert one.candidate == baseline and one.objective == baseline_value
    print("  一次评价 = 完整 decode + 独立 validate_schedule + objective，初始化即第 1 次")

    print("\n== 4. Random Search 逐评价轨迹（budget=10, seed=2）==")
    config = SearchConfig(
        algorithm="random", objective="total_tardiness", budget=10, seed=2
    )
    result = solve(instance, config)
    print("  evaluation  proposed  current  best  accepted")
    for item in result.trace:
        print(
            f"  {item.evaluation:>10}  {item.proposed:>8}  {item.current:>7}  "
            f"{item.best:>4}  {item.accepted}"
        )
    bests = [item.best for item in result.trace]
    assert bests == sorted(bests, reverse=True), "best 必须单调不增"
    assert result.evaluations == len(result.trace) <= config.budget
    assert result.objective == bests[-1] == total_tardiness(instance, result.schedule)
    validate_schedule(instance, result.schedule)
    rejected = sum(1 for item in result.trace if not item.accepted)
    print(f"  最终候选 order={result.candidate.order}")
    print(
        f"  evaluations={result.evaluations} status={result.status} "
        f"objective={result.objective}（含初始点共 {rejected} 条 accepted=False，全部计数）"
    )

    print("\n== 5. 重复的同一个候选也要计数 ==")
    tiny = singleton_instance()
    repeated = solve(
        tiny, SearchConfig(algorithm="random", objective="total_tardiness", budget=8)
    )
    print(f"  evaluations={repeated.evaluations} status={repeated.status}")
    print(f"  proposed 序列={[item.proposed for item in repeated.trace]}")
    assert repeated.evaluations == 8
    assert len(set(item.proposed for item in repeated.trace)) == 1
    print("  单工序单资格时每次随机都提出同一个候选，仍然消耗 8 次预算，不会死循环")

    print("\n== 6. 独立参照：oracle 确认这个实例的全局最优 ==")
    optimum, _, count = exhaustive_optimum(instance, objective="total_tardiness")
    print(f"  枚举 {count} 个组合（4! × 1），全局最优 = {optimum:.0f}")
    assert optimum == 22 and count == 24
    assert result.objective == optimum
    print("  搜索在第 2 次评价就碰到了这个值：这是运气，不是算法保证")

    print("\n全部断言通过：预算 1、逐评价轨迹、单调 best、重复计数与 oracle 对拍均已验证。")
    _ = SearchResult  # 保留 SearchResult 的类型引用，便于对照契约


if __name__ == "__main__":
    main()
