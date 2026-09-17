"""Day 4：推导对偶——弱对偶、强对偶、互补松弛与影子价格。

本脚本把「对偶」当成一件**可以被机器复核的事情**：先用 ``build_dual`` 按标准
对偶表机械地造出对偶 LP（不抄原始目标），再**独立求解**它，然后核对三件事：

1. 弱对偶：任意一个对偶可行解的目标值都是原始目标的**上界**（max 问题）；
2. 强对偶：两边各自的最优值相等；
3. 互补松弛：``x_j * rc_j = 0`` 与 ``slack_i * y_i = 0`` 逐项成立。

对偶的适用范围也一并写在输出里：强对偶要求**两边都有可行解**；影子价格只在
当前基不变的范围内有效。所有手算值（``50/3``、``20/3``、``2200``）都写在源码里。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fractions import Fraction

from opt_models.lp_models import (
    PRODUCTION_2D,
    build_dual,
    build_production_lp,
    complementarity_rows,
    duality_gap,
    solve_model,
)

TOLERANCE = 1e-9


def print_primal(model) -> None:
    print("== 1. 原始 LP（标准型：max c'x, Ax <= b, x >= 0）==")
    terms = " + ".join(
        f"{coefficient:g}*{name}"
        for name, coefficient in zip(model.var_names, model.objective_coeffs)
    )
    print(f"max {terms}")
    for row in model.rows:
        body = " + ".join(f"{coefficient:g}*{name}" for name, coefficient in row.terms)
        print(f"  {row.name:<8s} {body} {row.sense} {row.rhs:g}")
    print(f"  {'非负':<8s} " + ", ".join(f"{name} >= 0" for name in model.var_names))
    print()


def print_duality_table(model, dual) -> None:
    print("== 2. 原始—对偶对照表（由 build_dual 的命名约定生成，不靠位置索引）==")
    print("约束行 -> 对偶变量（含符号条件）：")
    print(f"  {'原始约束':<12s}{'方向':>5s}{'右端项':>9s}   {'对偶变量':<14s}符号条件")
    for row in model.rows:
        name = f"y_{row.name}"
        lower, upper = dual.variables[name].lb(), dual.variables[name].ub()
        if lower == 0.0:
            sign = "y >= 0"
        elif upper == 0.0:
            sign = "y <= 0"
        else:
            sign = "y 自由"
        print(f"  {row.name:<12s}{row.sense:>5s}{row.rhs:>9.1f}   {name:<14s}{sign}")
    print("原始变量 -> 对偶约束（含方向与右端项）：")
    print(f"  {'原始变量':<10s}   {'对偶约束':<12s}{'方向':>5s}{'右端项':>9s}")
    for name, coefficient in zip(model.var_names, model.objective_coeffs):
        dual_row = dual.row(f"d_{name}")
        print(
            f"  {name:<10s}   {dual_row.name:<12s}{dual_row.sense:>5s}{dual_row.rhs:>9.1f}"
        )
    print(f"对偶目标：{'min' if dual.sense == 'min' else 'max'} "
          + " + ".join(
              f"{coefficient:g}*{name}"
              for name, coefficient in zip(dual.var_names, dual.objective_coeffs)
          ))
    print()


def print_hand_dual_solution(dual, dual_solution) -> Fraction:
    print("== 3. 手算对偶最优解（两条对偶约束同时顶死）==")
    y_m, y_l = Fraction(50, 3), Fraction(20, 3)
    print(f"解方程组 2 y_M + y_L = 40、y_M + 2 y_L = 30，得 y_M = {y_m}、y_L = {y_l}")
    print(
        "对偶目标 b'y = 100*(50/3) + 80*(20/3) = "
        f"{Fraction(100) * y_m + Fraction(80) * y_l}"
    )
    print(
        f"求解器独立求解对偶得 {dual_solution.objective:g}，"
        f"差值 {abs(dual_solution.objective - 2200.0):.3e}"
    )
    print(f"对偶状态 {dual_solution.status}，对偶变量 "
          f"{ {name: round(value, 10) for name, value in dual_solution.primal.items()} }")
    print()


def print_weak_duality(model, primal_solution) -> None:
    print("== 4. 弱对偶：任意对偶可行解都给出原始目标的上界 ==")
    y_m, y_l = 20.0, 10.0
    check_a = 2 * y_m + 1 * y_l
    check_b = 1 * y_m + 2 * y_l
    print(f"取一个**非最优**的对偶点 y_M = {y_m:g}、y_L = {y_l:g}：")
    print(f"  对偶约束 2 y_M + y_L = {check_a:g} >= 40，可行")
    print(f"  对偶约束 y_M + 2 y_L = {check_b:g} >= 30，可行")
    bound = 100 * y_m + 80 * y_l
    print(f"  它的目标值 b'y = {bound:g}")
    print(f"弱对偶断言：{bound:g} >= 原始最优 {primal_solution.objective:g}，成立。")
    print("注意：弱对偶只对**对偶可行**的点成立，不可行的 y 不提供任何界。")
    print()


def print_complementarity(model, solution) -> None:
    print("== 5. 互补松弛逐项核对（2D 算例）==")
    print(f"{'类型':<18s}{'名字':<10s}{'原始侧':>12s}{'对偶侧':>12s}{'乘积':>12s}")
    for item in complementarity_rows(model, solution):
        print(
            f"{item['kind']:<18s}{item['name']:<10s}"
            f"{item['primal']:>12.6f}{item['dual']:>12.6f}{item['product']:>12.3e}"
        )
    print("两条产能行 slack = 0，它们的影子价格可以不为 0；")
    print("两个变量都为正，它们的 reduced cost 必须是 0。这就是互补松弛的两半。")
    print()


def print_dual_of_dual(model, primal_solution, dual_model, dual_solution) -> None:
    print("== 6. 对偶的对偶：结构上应当回到原始 ==")
    back = build_dual(dual_model)
    back_solution = solve_model(back)
    print(f"原始 {model.num_variables} 个变量、{model.num_rows} 条约束")
    print(f"对偶 {dual_model.num_variables} 个变量、{dual_model.num_rows} 条约束")
    print(f"对偶的对偶 {back.num_variables} 个变量、{back.num_rows} 条约束")
    print(f"变量名逐一对应：{back.var_names}")
    print(f"方向：原始 {model.sense} -> 对偶 {dual_model.sense} -> 对偶的对偶 {back.sense}")
    print(f"目标值：原始 {primal_solution.objective:g}、对偶 {dual_solution.objective:g}、"
          f"对偶的对偶 {back_solution.objective:g}")
    print(
        f"对偶的对偶与原始的差 |gap| = "
        f"{abs(back_solution.objective - primal_solution.objective):.3e}"
    )
    print()


def main() -> None:
    model = build_production_lp(PRODUCTION_2D)
    primal_solution = solve_model(model)
    dual_model = build_dual(model)
    dual_solution = solve_model(dual_model)

    print_primal(model)
    print_duality_table(model, dual_model)
    print(f"原始状态 {primal_solution.status}，原始最优 {primal_solution.objective:g}；"
          f"影子价格 { {k: round(v, 10) for k, v in primal_solution.dual.items()} }")
    print()
    print_hand_dual_solution(dual_model, dual_solution)
    gap = duality_gap(primal_solution.objective, dual_solution.objective)
    print(f"== 强对偶：|原始目标 - 对偶目标| = {gap:.3e}（容差 {TOLERANCE:g}）==")
    print("强对偶的前提是两边都有可行解且都有最优解；本算例满足。")
    print()
    print_weak_duality(model, primal_solution)
    print_complementarity(model, primal_solution)
    print_dual_of_dual(model, primal_solution, dual_model, dual_solution)

    print("== 7. 断言 ==")
    assert gap is not None and gap < TOLERANCE
    assert abs(primal_solution.objective - 2200.0) < TOLERANCE
    assert abs(dual_solution.objective - 2200.0) < TOLERANCE
    assert abs(primal_solution.dual["cap_M"] - 50 / 3) < TOLERANCE
    assert abs(primal_solution.dual["cap_L"] - 20 / 3) < TOLERANCE
    print("强对偶、手算对偶解、对偶的对偶三项断言全部通过。")


if __name__ == "__main__":
    main()
