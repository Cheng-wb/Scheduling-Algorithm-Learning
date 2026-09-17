"""Day 2：用 LP 求解器实现生产计划，读 primal / slack / reduced cost。

求解器给出的是一条最优解，不是一份决策建议。要把它翻译成决策语言，需要四个
读数：变量取值、约束余量 ``slack``、变量的 ``reduced cost``、约束的
``shadow price``。本脚本先把三产品算例的约束矩阵原样打印出来，再逐行给出
这四个读数，最后用两条**手算**恒等式核对：``c'x = b'y``（强对偶）与
``rc_j = c_j - Σ_i a_ij y_i``（符号约定）。手算值写在源码里、不取自求解器，
否则核对就退化成把求解器的话抄一遍。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fractions import Fraction

from opt_models.lp_models import (
    PRODUCTION_BASE,
    build_production_lp,
    max_reduced_cost_identity_error,
    solve_model,
)

#: 手算最优解：两条产能约束顶死，解方程组 2 x_P1 + x_P3 = 100、x_P1 + x_P3 = 80。
HAND_X = {"x_P1": Fraction(20), "x_P2": Fraction(0), "x_P3": Fraction(60)}

#: 手算影子价格：由互补松弛把三条松弛的需求行剔掉，剩下 2x2 方程组
#: 2 y_M + y_L = 40、y_M + y_L = 25，解得 y_M = 15、y_L = 10。
HAND_Y = {
    "cap_M": Fraction(15),
    "cap_L": Fraction(10),
    "demand_P1": Fraction(0),
    "demand_P2": Fraction(0),
    "demand_P3": Fraction(0),
}

TOLERANCE = 1e-9


def print_parameters(data) -> None:
    print("== 1. 算例参数（先集合、后数值）==")
    print(f"产品集合 P = {list(data.products)}")
    print(f"资源集合 R = {list(data.resources)}")
    print(f"单位利润 profit = {dict(zip(data.products, data.profit))}")
    print(f"产能 capacity   = {dict(zip(data.resources, data.capacity))}")
    print(f"需求上限 max_demand = {dict(zip(data.products, data.max_demand))}")
    print()


def print_matrix(model) -> None:
    print("== 2. 约束矩阵（行是约束、列是变量）==")
    header = f"{'行名':<12s}" + "".join(f"{name:>9s}" for name in model.var_names)
    print(header + f"{'方向':>6s}{'右端项':>10s}")
    for row in model.rows:
        body = "".join(
            f"{model.coefficient(row.name, name):>9.1f}" for name in model.var_names
        )
        print(f"{row.name:<12s}{body}{row.sense:>6s}{row.rhs:>10.1f}")
    print(f"规模：{model.num_variables} 个变量、{model.num_rows} 条约束。")
    print()


def print_primal_table(model, solution) -> None:
    print("== 3. primal 解与 reduced cost ==")
    print(f"{'变量':<9s}{'x':>10s}{'reduced cost':>15s}   解释")
    for index, name in enumerate(model.var_names):
        value = solution.primal[name]
        reduced = solution.reduced_cost[name]
        hand = HAND_X[name]
        if hand > 0:
            note = "手算 > 0，投产；rc = 0，它是基变量"
        else:
            note = "手算 = 0，不投产；rc < 0 表示要它开工得先补贴"
        print(f"{name:<9s}{value:>10.4f}{reduced:>15.6f}   {note}")
    print()


def print_row_table(model, solution) -> None:
    print("== 4. 每行的 activity / slack / shadow price ==")
    print(f"{'行名':<12s}{'方向':>5s}{'右端项':>9s}{'activity':>11s}{'slack':>10s}{'y':>9s}   解释")
    for row in model.rows:
        activity = solution.activity[row.name]
        slack = solution.slack[row.name]
        dual = solution.dual[row.name]
        if abs(slack) < TOLERANCE:
            note = "顶死；放松 1 单位目标 +" + f"{dual:g}"
        else:
            note = f"还有 {slack:g} 单位余量，所以 y = 0"
        print(
            f"{row.name:<12s}{row.sense:>5s}{row.rhs:>9.1f}"
            f"{activity:>11.4f}{slack:>10.4f}{dual:>9.4f}   {note}"
        )
    print()


def print_hand_checks(model, solution) -> None:
    print("== 5. 手算核对 ==")
    objective = sum(
        Fraction(str(model.objective_coeffs[index])) * HAND_X[name]
        for index, name in enumerate(model.var_names)
    )
    primal_terms = " + ".join(
        f"{model.objective_coeffs[index]:g}*{HAND_X[name]}"
        for index, name in enumerate(model.var_names)
    )
    print(f"primal 手算：c'x = {primal_terms} = {objective}")
    dual_terms = " + ".join(
        f"{row.rhs:g}*{HAND_Y[row.name]}" for row in model.rows
    )
    dual_objective = sum(
        Fraction(str(row.rhs)) * HAND_Y[row.name] for row in model.rows
    )
    print(f"dual   手算：b'y = {dual_terms} = {dual_objective}")
    print(f"两者相等，正是强对偶；求解器给的目标值是 {solution.objective:g}。")
    print()
    print("== 6. reduced cost 的符号约定逐项核对 ==")
    for index, name in enumerate(model.var_names):
        dual_sum = sum(
            Fraction(str(model.coefficient(row.name, name))) * HAND_Y[row.name]
            for row in model.rows
        )
        expected = Fraction(str(model.objective_coeffs[index])) - dual_sum
        print(
            f"rc({name}) = c_j - Σ a_ij y_i = {model.objective_coeffs[index]:g} - "
            f"{dual_sum} = {expected}；求解器报 {solution.reduced_cost[name]:.6f}"
        )
    print(f"全模型最大恒等式误差 = {max_reduced_cost_identity_error(model, solution):.3e}")
    print()
    print("== 7. 断言 ==")
    assert solution.objective is not None
    assert abs(solution.objective - float(objective)) < TOLERANCE
    assert abs(float(objective) - float(dual_objective)) < TOLERANCE
    for name in model.var_names:
        assert abs(solution.primal[name] - float(HAND_X[name])) < TOLERANCE
        hand_rc = Fraction(str(model.objective_coeffs[model.var_names.index(name)])) - sum(
            Fraction(str(model.coefficient(row.name, name))) * HAND_Y[row.name]
            for row in model.rows
        )
        assert abs(solution.reduced_cost[name] - float(hand_rc)) < TOLERANCE
    for row in model.rows:
        assert abs(solution.dual[row.name] - float(HAND_Y[row.name])) < TOLERANCE
    print("primal、dual、reduced cost 三项手算值全部与求解器一致（容差 1e-9）。")


def main() -> None:
    model = build_production_lp(PRODUCTION_BASE)
    solution = solve_model(model)
    print_parameters(PRODUCTION_BASE)
    print_matrix(model)
    print(f"求解状态 {solution.status}，目标值 {solution.objective:g}")
    print()
    print_primal_table(model, solution)
    print_row_table(model, solution)
    print_hand_checks(model, solution)


if __name__ == "__main__":
    main()
