"""W4D4：时间限制、workers、种子——记录终止原因，而不只是目标值。

对应笔记 Week_4/Day4.md。求解器是有**终止条件**的，「谁更快」离开预算就无从
谈起。本脚本在同一个较难实例上扫描时间预算，观察：

* 终止状态怎么变（OPTIMAL → FEASIBLE）；
* gap 怎么随预算收缩；
* 建模时间与求解时间分别是多少（两者是不同的问题）。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_common.bridge import generate_instance
from opt_solvers.registry import get, load_week_modules


def main() -> None:
    load_week_modules()
    # 20 个作业的单机总迟交：NP-hard，10 秒预算下大概率搜不完
    inst = generate_instance(70, jobs=20, machines=1)
    objective = "total_tardiness"

    print("== 1. 时间预算扫描（同一实例、同一 seed）==")
    print(f"  {'预算(s)':>8} {'状态':9} {'目标':>8} {'界':>10} {'gap':>8} {'节点':>6} {'建模(s)':>8} {'求解(s)':>8}")
    rows = []
    for limit in (1.0, 3.0, 10.0, 30.0):
        r = get("milp_tight")(inst, {"objective": objective, "time_limit": limit, "seed": 0})
        rows.append((limit, r))
        gap = "—" if r.gap is None else f"{r.gap:.4f}"
        print(
            f"  {limit:>8.1f} {r.status:9} {r.objective:>8.0f} {r.best_bound:>10.4f} "
            f"{gap:>8} {str(r.iterations):>6} {r.build_time:>8.3f} {r.solve_time:>8.3f}"
        )

    print()
    print("== 2. 预算不是装饰：它改变了终止原因 ==")
    statuses = [r.status for _, r in rows]
    print(f"  状态序列 = {statuses}")
    if "OPTIMAL" in statuses and "FEASIBLE" in statuses:
        print("  同一实例在不同预算下既有 OPTIMAL 也有 FEASIBLE ——")
        print("  所以「某方法解出 X」这句话，不带上预算就是不完整的。")
    else:
        print("  本实例在各档预算下都没有搜完；目标值随预算改善，但都未证明最优。")

    print()
    print("== 3. 界是单调的，目标值不一定单调 ==")
    bounds = [r.best_bound for _, r in rows]
    print(f"  界序列 = {[f'{b:.2f}' for b in bounds]}")
    assert all(b2 >= b1 - 1e-6 for b1, b2 in zip(bounds, bounds[1:])), "界必须随预算单调不降"
    print("  界随预算单调不降（这是分支定界的基本性质）；")
    print("  而目标值只保证「不劣于上一档的最好解」，中间可能因搜索路径不同而波动。")

    print()
    print("== 4. 建模时间与求解时间是两个问题 ==")
    for limit, r in rows:
        share = r.build_time / r.wall_time * 100 if r.wall_time else 0.0
        print(f"  预算={limit:>5.1f}s  建模 {r.build_time:.4f}s 占 {share:5.1f}%   求解 {r.solve_time:.4f}s")
    print("  建模时间基本不随预算变化；报告里只写一个总耗时，就无法归因。")

    print()
    print("== 5. workers 与种子：会影响数值吗 ==")
    for workers in (1, 4):
        r = get("cpsat_parallel")(
            generate_instance(72, jobs=24, machines=3),
            {"objective": "makespan", "time_limit": 5.0, "seed": 0, "workers": workers},
        )
        print(f"  workers={workers}: status={r.status} obj={r.objective:.0f} "
              f"bound={r.best_bound:.0f} wall={r.wall_time:.2f}s")
    print("  多 worker 会改变搜索路径，因此同一 seed 不保证同一中间轨迹；")
    print("  要严格复现就固定 workers=1。")

    print()
    print("全部断言通过。")


if __name__ == "__main__":
    main()
