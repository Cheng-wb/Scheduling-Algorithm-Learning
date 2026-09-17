"""W4D2：hint / 目标上界割 / 前缀固定——三件事必须分开报告。

对应笔记 Week_4/Day2.md。它们经常被笼统地叫做「warm start」，但性质完全不同：

* ``set_hint``       只是**建议**，不改变可行域，也不保证被采纳 → 对质量无保证；
* ``objective_cutoff`` 加 ``obj <= UB``，UB 来自已验证可行的排程 → **有效不等式**，
  不切最优解，把「也许会变好」变成「不会比初解差」；
* ``fixed_prefix``   固定初解序列的前若干位置 → **改变可行域**，因此**会改变最优值**。
  它是邻域搜索，不是强化。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_common.bridge import M2_OBJECTIVES, edd, generate_instance, spt, wspt
from opt_models.strengthening import solve_single_machine


def main() -> None:
    inst = generate_instance(81, jobs=10, machines=1)
    objective = "total_tardiness"
    spec = {"objective": objective, "time_limit": 10.0, "seed": 0}

    print("== 1. 初解从哪来：M1 规则 ==")
    seeds = {}
    for name, rule in (("spt", spt), ("edd", edd), ("wspt", wspt)):
        schedule = rule(inst)
        value = float(M2_OBJECTIVES[objective](inst, schedule))
        seeds[name] = (schedule, value)
        print(f"  {name:6} 初解目标 = {value:.0f}")
    best_rule = min(seeds, key=lambda k: seeds[k][1])
    seed_schedule, seed_value = seeds[best_rule]
    print(f"  取最好的规则：{best_rule}（{seed_value:.0f}）作为初解")

    print()
    print("== 2. 三件事的正交组合（同一实例、同一预算）==")
    print(f"  {'配置':34} {'状态':9} {'目标':>7} {'相对初解':>9} {'冲突':>7} {'耗时(s)':>8}")
    configs = [
        ("不做任何事（基准）", dict(set_hint=False, objective_cutoff=False, fixed_prefix=0)),
        ("只给 hint", dict(set_hint=True, objective_cutoff=False, fixed_prefix=0)),
        ("只加目标上界割", dict(set_hint=False, objective_cutoff=True, fixed_prefix=0)),
        ("hint + 上界割", dict(set_hint=True, objective_cutoff=True, fixed_prefix=0)),
        ("固定前 3 个位置", dict(set_hint=False, objective_cutoff=False, fixed_prefix=3)),
        ("固定全部 10 个位置", dict(set_hint=False, objective_cutoff=False, fixed_prefix=10)),
    ]
    results = []
    for label, flags in configs:
        r = solve_single_machine(
            inst, spec, hint_schedule=seed_schedule if flags["set_hint"] else None, method=label, **flags
        )
        results.append((label, r))
        rel = "—" if r.objective is None else f"{r.objective - seed_value:+.0f}"
        print(
            f"  {label:34} {r.status:9} {r.objective:>7.0f} {rel:>9} "
            f"{str(r.iterations):>7} {r.wall_time:>8.3f}"
        )

    by_label = dict(results)
    cutoff = by_label["只加目标上界割"].objective
    hint_only = by_label["只给 hint"].objective
    base = by_label["不做任何事（基准）"].objective
    fixed_all = by_label["固定全部 10 个位置"].objective
    prefix3 = by_label["固定前 3 个位置"].objective

    print()
    print("== 3. 三条结论（都可证伪，不是口号）==")
    assert base == cutoff, "上界割不应该改变最优值"
    print(f"  ① 上界割是最优值不变的：基准 {base:.0f} == 加割 {cutoff:.0f}  →  它是有效不等式")
    print(f"  ② hint 不提供任何质量保证：只给 hint 得 {hint_only:.0f}，"
          f"与基准 {base:.0f} 的关系取决于求解器是否采纳建议")
    assert fixed_all == seed_value, "固定全部位置必须复现初解本身"
    print(f"  ③ 固定全部位置 = 复现初解：{fixed_all:.0f} == 初解 {seed_value:.0f}  →  "
          f"这不是强化，是把解空间缩到一个点")
    print(f"     固定前 3 个位置得 {prefix3:.0f}：它是初解的**邻域**里的最优，"
          f"k 越大越接近初解")

    print()
    print("全部断言通过。")


if __name__ == "__main__":
    main()
