"""W4D5：统一结果接口——为什么三种方法能说同一种话。

对应笔记 Week_4/Day5.md。这个接口是 M2 的共享地基（``opt_solvers/result.py``），
本脚本**不重新实现**它，而是用它跑三类方法，然后逐条检验那几条纪律：

1. 启发式没有 bound → ``best_bound`` 必须是 ``None``，``gap`` 也必须是 ``None``；
2. ``build_time`` 与 ``solve_time`` 分开记；
3. 求解器说 ``OPTIMAL`` 不等于解可行 → 每个返回排程过 M1 的独立验证器；
4. 缺 bound 时**写空**，绝不写 0。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_common.bridge import generate_instance
from opt_solvers.registry import available, get, load_week_modules
from opt_solvers.result import STATUSES, SolveResult, validate_result


def main() -> None:
    load_week_modules()

    print("== 1. 状态词表：一次说清所有可能的结局 ==")
    print(f"  {len(STATUSES)} 个状态：{', '.join(STATUSES)}")
    print("  前五个是 CP-SAT 的原生语义；FAILED / NOT_SOLVED 是工程包装；")
    print("  FEASIBLE_OR_UNKNOWN 是「只找可行解」模式下的原生状态。")

    print()
    print("== 2. 三类方法进同一个接口 ==")
    inst = generate_instance(51, jobs=12, machines=1)
    spec = {"objective": "total_tardiness", "time_limit": 10.0, "seed": 0}
    methods = ["heur_spt", "milp_tight"]
    print(f"  {'方法':22} {'状态':9} {'目标':>7} {'bound':>9} {'gap':>8} {'建模(s)':>8} {'求解(s)':>8} {'验证':>6}")
    rows: dict[str, SolveResult] = {}
    for name in methods:
        r = get(name)(inst, spec)
        diagnostics = validate_result(inst, r)
        rows[name] = r
        gap = "None" if r.gap is None else f"{r.gap:.4f}"
        bound = "None" if r.best_bound is None else f"{r.best_bound:.1f}"
        print(
            f"  {name:22} {r.status:9} {r.objective:>7.0f} {bound:>9} {gap:>8} "
            f"{r.build_time:>8.3f} {r.solve_time:>8.3f} {'通过' if not diagnostics else '拒绝':>6}"
        )

    print()
    print("== 3. 纪律一：启发式必须写 None，不能写 0 ==")
    heur = rows["heur_spt"]
    assert heur.best_bound is None, "启发式没有下界，best_bound 必须是 None"
    assert heur.gap is None, "没有 bound 就没有 gap"
    print(f"  heur_spt: best_bound={heur.best_bound!r}  gap={heur.gap!r}")
    print("  如果把 best_bound 填成目标值，gap 会恒为 0，看起来「已证明最优」——")
    print("  这是求解器实验里最严重的伪证据，接口层直接禁止这种填法。")

    print()
    print("== 4. 纪律二：建模时间与求解时间是两个问题 ==")
    for name, r in rows.items():
        share = r.build_time / r.wall_time * 100 if r.wall_time else 0.0
        print(f"  {name:22} 建模 {r.build_time:.4f}s / 总计 {r.wall_time:.4f}s（占 {share:5.1f}%）")

    print()
    print("== 5. 纪律三：OPTIMAL 不等于解可行 ==")
    milp = rows["milp_tight"]
    if milp.proven_optimal:
        claim = "求解器证明了自己的**模型**最优"
    else:
        claim = "求解器未证明最优，只给出一个可行解"
    print(f"  milp_tight 状态 = {milp.status} —— {claim}")
    diagnostics = validate_result(inst, milp)
    print(f"  独立验证器对返回排程的诊断 = {diagnostics or '无（可行）'}")
    print("  两件事必须分开：前者是求解器对**模型**的声明（而且本例里它并没有做出")
    print("  「最优」的声明），后者是 M1 的 schedule_errors 对**时间轴是否真的合法**的判断。")
    print("  无论状态是 OPTIMAL 还是 FEASIBLE，排程都必须过独立验证器——")
    print("  求解器的声明不构成可行性的证据。")

    print()
    print("== 6. 落表时 None 保持为空 ==")
    row = heur.to_row()
    print(f"  heur_spt.to_row() = {row}")
    assert row["best_bound"] is None and row["gap"] is None
    print("  写进 CSV 后是空单元格，不是 0——读表的人一眼能看出「这项没有」，")
    print("  而 0 会被误读成「测出来是 0」。")

    print()
    print("== 7. 当前注册的方法总览 ==")
    for name in available():
        print(f"  {name}")

    print()
    print("全部断言通过。")


if __name__ == "__main__":
    main()
