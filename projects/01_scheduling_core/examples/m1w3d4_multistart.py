"""Multi-start 的分段预算账本：重启条件、逐评价 trace 与两个极端设置。

用 `restart_interval=7` 强制短分段，把每一次评价属于哪一段、哪一次是随机重启、
全局 best 有没有被清空全部打印出来；再对比 `restart_interval=1`（逼近连续随机重启）
与 `restart_interval` 大于总预算（逼近单起点 First）两个极端。

只读取结果并打印，不写入 artifacts/；固定 seed，可重复。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_algorithms.search import SearchConfig, solve
from scheduling_io.generator import generate_instance

BUDGET = 30
INTERVAL = 7
SEED = 9


def segment_of(evaluation: int, interval: int) -> int:
    """分段编号：当 interval 每次都被触发时，分段起点恰为 1, 1+interval, 1+2*interval, ..."""
    return (evaluation - 1) // interval + 1


def restart_evaluations(trace, interval: int) -> list[int]:
    starts = [k for k in range(1, len(trace) + 1) if (k - 1) % interval == 0]
    for k in starts[1:]:
        # 每个分段起点都必须是随机重启记录，而重启记录一定是 accepted=True。
        assert trace[k - 1].accepted, f"第 {k} 次评价不是重启点，分段假设不成立"
    return starts


def print_trace(title: str, result, interval: int) -> None:
    print()
    print(title)
    print(f"objective={result.objective:.1f}  evaluations={result.evaluations}  status={result.status}")
    starts = restart_evaluations(result.trace, interval)
    print(f"检测到的分段起点（评价编号）: {starts} → 共 {len(starts)} 段，重启 {len(starts) - 1} 次")
    print("evaluation,segment,proposed,current,best,accepted,note")
    for point in result.trace:
        k = point.evaluation
        if k == 1:
            note = "初始评价，属于第 1 段"
        elif k in starts:
            note = "随机重启：新段的第 1 项，本身消耗 1 次评价"
        elif point.accepted:
            note = "扫描发现严格改善并移动"
        else:
            note = "扫描候选，未改善"
        print(
            f"{k},{segment_of(k, interval)},{point.proposed:.1f},{point.current:.1f},"
            f"{point.best:.1f},{point.accepted},{note}"
        )
    bests = [p.best for p in result.trace]
    print(
        "全局 best 单调不增?",
        bests == sorted(bests, reverse=True),
        f"（首值 {bests[0]:.1f} → 末值 {bests[-1]:.1f}）",
    )


def main() -> None:
    instance = generate_instance(40, jobs=6, machines=2, operations_per_job=2)
    print("instance = generate_instance(40, jobs=6, machines=2, operations_per_job=2)")
    print(f"总预算 budget={BUDGET}，分段上限 restart_interval={INTERVAL}，seed={SEED}")
    print(f"预算账本：总预算 {BUDGET} 次评价是整个搜索的全部额度，")
    print(f"绝不是「每次重启额外获得 {BUDGET} 次」；重启只从这 {BUDGET} 次里再花掉 1 次。")

    main_result = solve(
        instance,
        SearchConfig(
            algorithm="multistart", budget=BUDGET, seed=SEED, restart_interval=INTERVAL
        ),
    )
    print_trace(f"=== 主实验：multistart, restart_interval={INTERVAL} ===", main_result, INTERVAL)

    trace = main_result.trace
    rises = [
        (trace[k - 1].evaluation, trace[k - 1].current, trace[k].current)
        for k in range(1, len(trace))
        if trace[k].current > trace[k - 1].current
    ]
    print()
    print("随机重启可以比当前解更差的直接证据（current 上升）：")
    for before, old, new in rises:
        print(f"  #{before} → #{before + 1}: current {old:.1f} → {new:.1f}（变差了，但仍然成为当前解）")
    if rises:
        after = rises[0][0] + 1
        print(f"  同一次评价里 best 仍为 {trace[after - 1].best:.1f}：全局 best 从不在重启时清空。")
    print("反过来说，First 的移动只接受严格改善，current 永远不会上升。")

    print()
    print(
        f"分段长度：每段最多 {INTERVAL} 次评价，其中第 1 次是重启（第 1 段是初始评价），"
        f"剩下 {INTERVAL - 1} 次留给局部搜索；"
        f"本运行共 {main_result.evaluations} 次评价，恰好用完 budget={BUDGET}。"
    )

    nonstop = solve(
        instance,
        SearchConfig(algorithm="multistart", budget=BUDGET, seed=SEED, restart_interval=1),
    )
    print()
    print("=== 极端 1：restart_interval=1 → 每段只剩 1 次评价，全部是随机重启 ===")
    print(
        f"objective={nonstop.objective:.1f}  evaluations={nonstop.evaluations}  "
        f"status={nonstop.status}  accepted=True 的评价数="
        f"{sum(1 for p in nonstop.trace if p.accepted)}"
    )
    print("分段上限为 1 时，扫描循环在每次评价前就因「本段额度已用完」而退出，")
    print("所以每一段都没有任何扫描评价，整轮运行退化成连续随机重启。")
    print("current 列:", [f"{p.current:.0f}" for p in nonstop.trace])

    big_interval = BUDGET * 10
    big = solve(
        instance,
        SearchConfig(
            algorithm="multistart", budget=BUDGET, seed=SEED, restart_interval=big_interval
        ),
    )
    first_result = solve(
        instance, SearchConfig(algorithm="first", budget=BUDGET, seed=SEED)
    )
    print()
    print(f"=== 极端 2：restart_interval={big_interval} 远大于 budget={BUDGET} ===")
    print(
        f"objective={big.objective:.1f}  evaluations={big.evaluations}  "
        f"status={big.status}  accepted=True 的评价数="
        f"{sum(1 for p in big.trace if p.accepted)}"
    )
    print("与单起点 First 的逐点对比：")
    print(f"  逐评价 trace 完全相同? {big.trace == first_result.trace}")
    print(f"  multistart: objective={big.objective:.1f} evaluations={big.evaluations} status={big.status}")
    print(f"  first     : objective={first_result.objective:.1f} evaluations={first_result.evaluations} status={first_result.status}")
    print("  本运行里每一轮扫描都被总预算打断，没有一轮真正扫完整个邻域（确认局部最优），")
    print("  所以多起点从未被触发；若某一轮提前确认局部最优，multistart 仍会重启，")
    print("  这一点与 first 立即以 LOCAL_OPTIMUM 结束不同。")

    print()
    print(
        f"对照：restart_interval={INTERVAL} 得到 {main_result.objective:.1f}，"
        f"restart_interval=1 得到 {nonstop.objective:.1f}，"
        f"接近单起点 First 得到 {first_result.objective:.1f}"
    )
    print("两个极端都不是普遍最优：分段太短无法深入改善，太长则可能只在同一个 basin 里打转。")


if __name__ == "__main__":
    main()
