"""W4D1：同质机器对称性、对称破缺与冗余约束——强化不得改变最优值。

对应笔记 Week_4/Day1.md。核心断言：**加对称破缺前后，最优值必须完全相同。**
如果最优值变了，那不是强化，是改题。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_common.bridge import generate_instance
from opt_models.strengthening import (
    add_load_ordering,
    add_redundant_bounds,
    build_parallel_model,
    detect_machine_symmetry,
    makespan_lower_bound,
    solve_parallel_cpsat,
)


def main() -> None:
    print("== 1. 对称性检测：哪些实例是同质并行机 ==")
    for label, inst in (
        ("5j/3m 同质", generate_instance(80, jobs=5, machines=3)),
        ("5j/1m 单机", generate_instance(80, jobs=5, machines=1)),
    ):
        print(f"  {label:12} detect_machine_symmetry = {detect_machine_symmetry(inst)}")
    print("  说明：单机只有一台机器，没有可交换的对象，对称破缺无从谈起。")

    inst = generate_instance(80, jobs=6, machines=3)
    spec = {"objective": "makespan", "time_limit": 10.0, "seed": 0}
    base = solve_parallel_cpsat(
        inst, spec, symmetry_breaking=False, redundant_constraints=False, method="baseline"
    )
    sym = solve_parallel_cpsat(
        inst, spec, symmetry_breaking=True, redundant_constraints=False, method="symmetry"
    )
    both = solve_parallel_cpsat(
        inst, spec, symmetry_breaking=True, redundant_constraints=True, method="symmetry+redundant"
    )

    print()
    print("== 2. 消融：强化手段逐项开关（同一实例、同一预算）==")
    print(f"  {'配置':22} {'状态':9} {'目标':>6} {'界':>6} {'冲突':>7} {'耗时(s)':>8}")
    for r in (base, sym, both):
        print(
            f"  {r.method:22} {r.status:9} {r.objective:>6.0f} {r.best_bound:>6.0f} "
            f"{str(r.iterations):>7} {r.wall_time:>8.3f}"
        )

    print()
    print("== 3. 最优值必须不变（强化 ≠ 改题）==")
    values = {r.objective for r in (base, sym, both)}
    assert len(values) == 1, f"强化改变了最优值：{values}"
    print(f"  三种配置的最优值全部 = {base.objective:.0f}  →  强化成立")

    lower = makespan_lower_bound(inst)
    verdict = "紧：已证明最优" if lower == base.objective else "松：不足以证明最优"
    print(f"  独立下界 makespan_lower_bound = {lower}  →  与最优值 {base.objective:.0f} 相比：{verdict}")
    if lower != base.objective:
        print("  注意：下界不等于最优值时，'OPTIMAL' 是求解器自己搜完得到的结论，")
        print("        不是这个解析下界给的。两者是独立的证据，不要混为一谈。")

    print()
    print("== 3b. 公平起见：强化也可能是负收益 ==")
    print("  迭代数（conflicts）：", ", ".join(f"{r.method}={r.iterations}" for r in (base, sym, both)))
    if both.iterations and base.iterations and both.iterations > base.iterations:
        print("  本例中对称破缺**增加**了冲突数：这些实例本来就小，")
        print("  额外约束的开销没有被搜索空间的缩小抵消。如实记录，不粉饰。")

    print()
    print("== 4. 冗余约束到底加了多少条 ==")
    context = build_parallel_model(inst, "makespan")
    print(f"  变量数（对称破缺前）: {len(context.model.Proto().variables)}")
    added = add_redundant_bounds(context)
    print(f"  add_redundant_bounds 追加约束数 = {added}")
    order = add_load_ordering(context)
    print(f"  add_load_ordering   追加约束数 = {order}")

    print()
    print("全部断言通过。")


if __name__ == "__main__":
    main()
