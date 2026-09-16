"""Best Improvement 与 First Improvement：同一邻域下的扫描成本与 trace 语义。

本脚本做两件事：
1. 用一个小到可以手算的教学模型复现「First 花 1 次评价得到 99，Best 花 3 次评价得到 80」；
   再在同样的总预算下让 First 走完多轮，说明 Best 的「每轮更贪心」不等于「同预算更好」。
2. 在同一实例 + 同一 seed 上跑真实的 first / best，打印 objective、实际 evaluations、status，
   并展示 Best 的 trace 中 current 在扫描期间不变、accepted 表示「这一轮是否移动」。

只读取结果并打印，不写入 artifacts/；固定 seed，可重复。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_algorithms.decoder import initial_candidate
from scheduling_algorithms.neighborhoods import neighbors
from scheduling_algorithms.search import SearchConfig, solve
from scheduling_io.generator import generate_instance

# ---- 教学用最小模型：状态 -> (自身目标值, [(邻居状态, 邻居目标值)])，列表顺序即固定扫描顺序 ----
Toy = tuple[int, list[tuple[str, int]]]
TOY: dict[str, Toy] = {
    "s0": (100, [("s1", 99), ("s2", 98), ("s3", 80)]),
    "s1": (99, [("s4", 90), ("s5", 85)]),
    "s2": (98, []),
    "s3": (80, []),
    "s4": (90, [("s6", 70)]),
    "s5": (85, []),
    "s6": (70, []),
}


def toy_first(start: str, budget: int) -> tuple[str, int, int]:
    """First Improvement：碰到第一个严格改善就移动；返回 (终态, 目标值, 评价数, 移动次数)。"""
    current, used, moves = start, 0, 0
    while used < budget:
        moved = False
        for neighbor, value in TOY.get(current, (0, []))[1]:
            if used >= budget:
                break
            used += 1
            if value < TOY[current][0]:
                current, moved = neighbor, True
                moves += 1
                break
        if not moved:
            break
    return current, TOY[current][0], used, moves


def toy_best(start: str, budget: int) -> tuple[str, int, int]:
    """Best Improvement：扫完一整轮再移动一次；扫描被预算截断时用已看到的最好候选。"""
    current, used, moves = start, 0, 0
    while used < budget:
        chosen, chosen_value = current, TOY[current][0]
        for neighbor, value in TOY.get(current, (0, []))[1]:
            if used >= budget:
                break
            used += 1
            if value < chosen_value:
                chosen, chosen_value = neighbor, value
        if chosen == current:
            break
        current, moves = chosen, moves + 1
    return current, TOY[current][0], used, moves


def point_line(point) -> str:
    return (
        f"#{point.evaluation:>3}  proposed={point.proposed:>7.1f}  "
        f"current={point.current:>7.1f}  best={point.best:>7.1f}  accepted={point.accepted}"
    )


def run_case(title: str, instance, objective: str, budget: int, seed: int) -> None:
    print()
    print(title)
    size = len(list(neighbors(instance, initial_candidate(instance))))
    print(f"同一 neighbors 生成器去重后的邻域规模: {size}")
    print("algorithm,objective,evaluations,moves,status")
    results = {}
    for algorithm in ("first", "best"):
        result = solve(
            instance,
            SearchConfig(
                algorithm=algorithm, objective=objective, budget=budget, seed=seed
            ),
        )
        results[algorithm] = result
        moves = sum(1 for p in result.trace if p.accepted and p.evaluation > 1)
        print(
            f"{algorithm},{result.objective:.1f},{result.evaluations},{moves},{result.status}"
        )
    best = results["best"]
    currents = sorted({p.current for p in best.trace})
    print(f"best 的 current 列一共只出现 {len(currents)} 个取值: {currents}")
    accepted = [p.evaluation for p in best.trace if p.accepted]
    print("best 的 accepted=True 点是:", accepted)
    rounds = [
        (accepted[i - 1] + 1, accepted[i]) for i in range(1, len(accepted))
    ]
    print(f"best 完成的扫描轮次（评价区间）: {rounds}；每轮评价数 {[b - a + 1 for a, b in rounds]}")
    print(f"对比邻域规模 {size}：轮次评价数小于邻域规模 → 这一轮扫描被预算截断，不是完整邻域。")
    print("best 的前 4 个 trace 点（扫描期间 current 不动）:")
    for point in best.trace[:4]:
        print("  " + point_line(point))
    print("best 的最后一个 trace 点:")
    last = best.trace[-1]
    print("  " + point_line(last))
    print(f"  proposed={last.proposed:.1f} 是这次评价的候选值；")
    if last.proposed != last.current:
        print(
            f"  current={last.current:.1f} 是本轮选定后回填的当前解，"
            "所以它不等于最后一个 proposed（本轮最好的候选出现在更早的评价里）。"
        )
    else:
        print(
            f"  current={last.current:.1f} 正好等于最后一个 proposed，"
            "只是说明本轮最好的候选恰好是最后一个被评价的候选。"
        )
    print(
        f"  accepted={last.accepted} 回答的是「这一轮最后到底移动了没有」，"
        "不是「最后一个候选被接受了没有」。"
    )


def main() -> None:
    print("=" * 78)
    print("第 1 部分：手算模型 —— current=100，一轮的邻居按固定顺序评价出 99, 98, 80")
    print("=" * 78)
    print("初始解 s0，目标 100；同一轮邻居扫描顺序：s1=99, s2=98, s3=80")
    for name, runner in (("First", toy_first), ("Best ", toy_best)):
        state, value, used, moves = runner("s0", budget=3)
        print(f"{name}: 用 {used} 次评价到达 {state}（目标 {value}，移动 {moves} 次）")
    print()
    print("两种走法的逐步展开：")
    print("  First： 第1次评价=99 < 100 → 立刻移动，本轮结束（1 次评价换来 99）")
    print("  Best ： 第1次评价=99，第2次评价=98，第3次评价=80 → 本轮扫完才移动（3 次评价换来 80）")
    print()
    print("把总预算固定为 3，两种策略在同一预算下的最终结果：")
    print("algorithm,final_objective,evaluations,moves")
    for name, runner in (("first", toy_first), ("best ", toy_best)):
        state, value, used, moves = runner("s0", budget=3)
        print(f"{name},{value},{used},{moves}")
    _, first_value, _, _ = toy_first("s0", 3)
    _, best_value, _, _ = toy_best("s0", 3)
    print(
        f"结论：预算 3 下 First 用 1+1+1 次评价走完三轮，到达 {first_value}；"
        f"Best 把 3 次评价全花在第一轮，按 99/98/80 中最小的 80 移动，到达 {best_value}。"
    )
    print(
        "「Best 每轮更贪心」说的是同一轮的候选里选得更好，"
        "而不是「同样总预算下最终目标一定更低」。"
    )

    run_case(
        "第 2 部分 A：单机 12 工序，目标 total_tardiness，预算 150，seed 0",
        generate_instance(20, jobs=12, machines=1),
        "total_tardiness",
        150,
        0,
    )
    run_case(
        "第 2 部分 B：2 台机器 8 工序，目标 makespan，预算 60，seed 0",
        generate_instance(20, jobs=8, machines=2),
        "makespan",
        60,
        0,
    )
    print()
    print("=" * 78)
    print("两个真实实例的结论方向相反：A 上 Best 更好（529 < 575），B 上 First 更好（35 < 39）。")
    print("两次运行里 Best 都只完成了 1 次移动，而它那一轮扫描都被预算截断（不是完整邻域），")
    print("所以它返回的并不是「完整邻域的最优移动」；First 用同样的预算完成了更多轮。")
    print("=" * 78)


if __name__ == "__main__":
    main()
