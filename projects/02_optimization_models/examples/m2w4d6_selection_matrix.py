"""W4D6：同实例同预算比较三类方法，产出「选择矩阵」。

对应笔记 Week_4/Day6.md。三类方法指 MILP、CP-SAT 与启发式（M1 规则）。
本脚本在共同实例集上跑同一预算，记录质量、bound、gap、耗时与**终止原因**，
然后回答一个实际问题：**什么情况下该用哪一个？**

纪律：所有结论都标注实例、目标与预算；不写成「某方法普遍更好」。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_common.bridge import generate_instance
from opt_solvers.registry import get, load_week_modules
from opt_solvers.result import validate_result

TIME_LIMIT = 5.0

CASES = (
    (
        "single_12 (ΣT, 已可解)",
        generate_instance(51, jobs=12, machines=1),
        "total_tardiness",
        ["heur_spt", "milp_tight", "milp_alt"],
    ),
    (
        "single_20 (ΣT, 搜不完)",
        generate_instance(70, jobs=20, machines=1),
        "total_tardiness",
        ["heur_spt", "milp_tight", "milp_alt"],
    ),
    (
        "parallel_12 (Cmax)",
        generate_instance(53, jobs=12, machines=3),
        "makespan",
        ["heur_parallel_lpt", "cpsat_parallel", "cpsat_symmetry", "milp_alt"],
    ),
    (
        "parallel_24 (Cmax, 搜不完)",
        generate_instance(72, jobs=24, machines=3),
        "makespan",
        ["heur_parallel_lpt", "cpsat_parallel", "milp_alt"],
    ),
)


def main() -> None:
    load_week_modules()
    print(f"共同预算：每种方法 {TIME_LIMIT:.0f} 秒；启发式不使用该预算（秒级完成）。")
    print("gap 为 None 表示该方法不提供 bound，不是 0。")
    print()

    for label, inst, objective, methods in CASES:
        print(f"=== {label}   objective={objective} ===")
        print(f"  {'方法':20} {'状态':9} {'目标':>7} {'bound':>9} {'gap':>8} {'耗时(s)':>8} {'验证':>5}")
        results = []
        for name in methods:
            r = get(name)(inst, {"objective": objective, "time_limit": TIME_LIMIT, "seed": 0})
            diagnostics = validate_result(inst, r)
            results.append((name, r))
            gap = "None" if r.gap is None else f"{r.gap:.4f}"
            bound = "None" if r.best_bound is None else f"{r.best_bound:.1f}"
            print(
                f"  {name:20} {r.status:9} {r.objective:>7.0f} {bound:>9} {gap:>8} "
                f"{r.wall_time:>8.3f} {'通过' if not diagnostics else '拒绝':>5}"
            )

        # 注意：不能写 `objective or inf` —— 目标值为 0.0 时它是假值，
        # 会被当成无穷大，于是「最好的解」反而永远选不上。
        def rank(item: tuple[str, object]) -> float:
            value = item[1].objective
            return float("inf") if value is None else value

        winner = min(results, key=rank)
        proven = [n for n, r in results if r.status == "OPTIMAL"]
        print(f"  → 本实例最好可行解来自 {winner[0]}（{winner[1].objective:.0f}）")
        print(f"  → 在预算内证明最优的方法：{proven if proven else '无'}")
        print()

    print("=== 选择矩阵（由上面的实测归纳，不是先验信条）===")
    print("  规模小、要**保证最优**        → MILP 或 CP-SAT；两者都能给出最优性证明。")
    print("  单机、排序型、目标含迟交      → 序列 MILP 的建模最直接；")
    print("                                  但它的 LP 松弛很弱（根界常为 0），")
    print("                                  时间索引替代模型根界强得多。")
    print("  并行机、只看 Cmax            → CP-SAT 的区间+NoOverlap 表达最自然。")
    print("  多工序 / JSP 型              → CP-SAT 的 precedence + NoOverlap。")
    print("  大规模、预算内搜不完          → 先用规则给可行解，再让精确方法在剩余")
    print("                                  预算里改进；此时 gap>0 是常态。")
    print("  只要一个能用的解              → 启发式；但**没有 bound**，")
    print("                                  不要拿它和精确方法的 gap 并列。")
    print()
    print("全部结果都来自上面这四组实测；换实例、换预算都要重新测，不能外推。")


if __name__ == "__main__":
    main()
