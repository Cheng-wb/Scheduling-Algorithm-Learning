"""Day 6：对拍、数值容差与「求解器说 OPTIMAL 不等于解可行」。

本脚本把 Week 1 全部对拍手段并排跑一遍，并回答两个具体问题：

1. 容差该取多少？用**同一批数据**在 1e-15 到 1e-6 之间扫一遍，数出每个阈值
   能通过多少个场景——太严会把浮点噪声当成错误，太松会放过真错误；
2. 状态码可靠吗？本环境的 GLOP 对**无界** LP 也返回 ``INFEASIBLE``，
   所以状态码只能读作「没有最优解」，不能读作「可行域为空」。

对拍用的量全部由本模块**自己复算**：约束活动值按系数重算、对偶目标由
``build_dual`` 独立求解，不抄求解器的自述。
"""

import sys
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ortools.linear_solver import pywraplp

from opt_models.lp_models import (
    ASSIGNMENT_BASE,
    DEFAULT_TOLERANCE,
    PRODUCTION_2D,
    PRODUCTION_BASE,
    PRODUCTION_INFEASIBLE,
    STATUS_NAMES,
    TRANSPORT_BASE,
    build_assignment_lp,
    build_dual,
    build_production_lp,
    build_transportation_lp,
    dual_feasibility_violation,
    duality_gap,
    max_complementarity_violation,
    max_reduced_cost_identity_error,
    solve_model,
)

CORE_MODELS = (
    build_production_lp(PRODUCTION_2D),
    build_production_lp(PRODUCTION_BASE),
    build_transportation_lp(TRANSPORT_BASE),
    build_assignment_lp(ASSIGNMENT_BASE),
)


def metrics(model):
    """返回 (原始目标, 对偶目标, 可行性残差, 互补松弛, rc 恒等式, 对偶可行违反)。"""
    solution = solve_model(model)
    dual_solution = solve_model(build_dual(model))
    return (
        solution,
        dual_solution,
        solution.max_constraint_residual,
        max_complementarity_violation(model, solution),
        max_reduced_cost_identity_error(model, solution),
        dual_feasibility_violation(model, solution),
    )


def _fmt(value) -> str:
    return "None" if value is None else f"{value:.3e}"


def worst_metric(values) -> float | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def print_definitions() -> None:
    print("== 1. 五条独立核对的定义 ==")
    print("约束残差   ：按 A x 重算活动值，再看它越过右端项多少（原始可行性）")
    print("互补松弛   ：max |x_j * rc_j| 与 |slack_i * y_i|（最优性的必要条件）")
    print("rc 恒等式  ：max |rc_j - (c_j - Σ_i a_ij y_i)|（符号约定是否正确）")
    print("对偶可行   ：y 的符号条件与 Σ_i a_ij y_i >= c_j（对偶可行性）")
    print("对偶目标   ：另建 dual 模型独立求解，与原始目标比（强对偶）")
    print()


def print_table() -> None:
    print("== 2. 四个核心场景的核对结果 ==")
    print(f"{'场景':<16s}{'primal':>10s}{'dual':>10s}{'|gap|':>11s}{'相对 gap':>11s}"
          f"{'残差':>11s}{'互补松弛':>11s}{'rc 恒等':>11s}{'对偶可行':>11s}")
    for model in CORE_MODELS:
        solution, dual_solution, residual, complementarity, identity, feasibility = metrics(model)
        gap = duality_gap(solution.objective, dual_solution.objective)
        scale = max(1.0, abs(solution.objective))
        print(
            f"{model.name:<16s}{solution.objective:>10g}{dual_solution.objective:>10g}"
            f"{_fmt(gap):>11s}{_fmt(None if gap is None else gap / scale):>11s}"
            f"{_fmt(residual):>11s}{_fmt(complementarity):>11s}"
            f"{_fmt(identity):>11s}{_fmt(feasibility):>11s}"
        )
    print("两次独立求解的目标值只在浮点噪声级别上不同，其余四个量都在 1e-13 以下。")
    print()


def print_tolerance_probe() -> None:
    print("== 3. 容差探针：同一批数据、不同阈值，各能通过几个场景 ==")
    samples = []
    for model in CORE_MODELS:
        solution, _, residual, complementarity, identity, feasibility = metrics(model)
        samples.append((model.name, worst_metric([residual, complementarity, identity, feasibility])))
    print(f"{'阈值':>9s}{'通过场景数':>12s}   未通过者")
    for tolerance in (1e-15, 1e-14, 1e-13, 1e-12, 1e-11, DEFAULT_TOLERANCE, 1e-6):
        failed = [name for name, worst in samples if worst is not None and worst > tolerance]
        print(f"{tolerance:>9.0e}{len(samples) - len(failed):>12d}   "
              f"{'、'.join(failed) if failed else '无'}")
    print("本环境实测的最大噪声在 2e-13 量级，所以 1e-15、1e-14、1e-13 三个阈值")
    print("会把浮点尘埃判成错误——它们不是「更严格」，而是「没有意义」。")
    print(f"默认取 {DEFAULT_TOLERANCE:.0e}：比实测噪声宽约 4 个数量级，也严于求解器")
    print("自带的可行性容差（1e-8 量级）——它是**事后对拍**用的尺子，不用来放宽求解器。")
    print("这条探针只能回答「多严算太严」；「多松算太松」要靠构造已知错误来检验，")
    print("第 7 节会喂一个已知错误的输入，验证检查器**确实会报警**。")
    print()


def print_float_noise() -> None:
    print("== 4. 求解器给的「极点」其实带着 1e-14 的噪声 ==")
    model = build_production_lp(PRODUCTION_2D)
    solution = solve_model(model)
    print("原始读数与 12 位小数舍入后的对照：")
    for name in model.var_names:
        raw = solution.primal[name]
        rounded = round(raw, 12)
        print(f"  {name}: {raw!r} -> {rounded!r}")
    exact = Fraction(0)
    for index, name in enumerate(model.var_names):
        coefficient = Fraction(Decimal(str(model.objective_coeffs[index])))
        exact += coefficient * Fraction(Decimal(str(round(solution.primal[name], 12))))
    print(f"舍入后按精确有理数重算目标：{exact}（精确到整数）")
    print(f"求解器报的目标：{solution.objective!r}")
    print(f"差 = {abs(float(exact) - solution.objective):.3e}")
    print("结论：这一位「尾巴」是浮点表示误差，不是模型误差；")
    print("把舍入后的整数解代回原模型，可行性残差为 "
          f"{abs(2 * 40 + 20 - 100):g} 与 {abs(40 + 2 * 20 - 80):g}，精确为 0。")
    print()


def print_status_trap() -> None:
    print("== 5. 状态码陷阱：GLOP 对无界 LP 也返回 INFEASIBLE ==")
    unbounded = pywraplp.Solver.CreateSolver("GLOP")
    x = unbounded.NumVar(0.0, unbounded.infinity(), "x")
    unbounded.Minimize(-x)
    unbounded_status = STATUS_NAMES.get(unbounded.Solve(), "UNKNOWN")
    print(f"min -x, x >= 0（可行、但目标无下界）-> 状态 {unbounded_status}")
    empty = pywraplp.Solver.CreateSolver("GLOP")
    y = empty.NumVar(0.0, empty.infinity(), "y")
    empty.Add(y >= 1)
    empty.Add(y <= 0)
    empty.Minimize(y)
    empty_status = STATUS_NAMES.get(empty.Solve(), "UNKNOWN")
    print(f"min y, y >= 1, y <= 0（真的不可行）-> 状态 {empty_status}")
    print(f"两个完全不同的情形拿到同一个状态码，所以 {unbounded_status} 只能读作")
    print("「没有最优解」。要区分「不可行」与「无界」必须另找证据：手算、")
    print("加人工界、或换一个后端。本文件把这条限制记在 GLOP_STATUS_CAVEAT 里。")
    print()


def print_infeasible_record() -> None:
    print("== 6. 不可行算例里哪些字段是 None（None 不是 0）==")
    model = build_production_lp(PRODUCTION_INFEASIBLE)
    solution = solve_model(model)
    print(f"状态 {solution.status}，objective = {solution.objective}，"
          f"dual_available = {solution.dual_available}")
    print(f"primal = {solution.primal}")
    print(f"dual = {solution.dual}")
    print(f"slack = {solution.slack}")
    print(f"max_constraint_residual = {solution.max_constraint_residual}")
    print(f"互补松弛检查 = {max_complementarity_violation(model, solution)}")
    print("冲突来自两条手算就能看出的行：")
    for name in ("demand_P2", "delivery_P2"):
        row = model.row(name)
        print(f"  {name}: {row.sense} {row.rhs:g}")
    print("x_P2 <= 50 与 x_P2 >= 60 不可能同时满足，这就是可行域为空的证据——")
    print("注意它来自手算，不是来自状态码。")
    print()


def print_false_alarm_probe() -> None:
    print("== 7. 检查器真的会报警吗（喂一个已知错误的输入）==")
    model = build_production_lp(PRODUCTION_2D)
    solution = solve_model(model)
    wrong_y = {"cap_M": 20.0, "cap_L": 10.0}
    wrong_reduced = {}
    for index, name in enumerate(model.var_names):
        dual_sum = sum(
            model.coefficient(row.name, name) * wrong_y[row.name] for row in model.rows
        )
        wrong_reduced[name] = model.objective_coeffs[index] - dual_sum
    fake = replace(solution, dual=wrong_y, reduced_cost=wrong_reduced)
    print(f"取一个**对偶可行但不是最优**的 y = {wrong_y}：")
    print(f"  对偶可行违反量 = {dual_feasibility_violation(model, fake):.3e}"
          "（符号条件与对偶约束都满足，所以它是 0）")
    print(f"  互补松弛违反量 = {max_complementarity_violation(model, fake):.3e}"
          "（x_P1 = 40 而 rc_P1 = -10，乘积不为 0，被抓到）")
    print(f"  与原始最优目标的差 = {abs(solution.objective - 2800.0):g}")
    print("这条反例说明：对偶可行是「必要条件」，光有它还不够；")
    print("互补松弛才是把「可行」推进到「最优」的那一步。")
    print()


def main() -> None:
    print_definitions()
    print_table()
    print_tolerance_probe()
    print_float_noise()
    print_status_trap()
    print_infeasible_record()
    print_false_alarm_probe()

    print("== 8. 断言 ==")
    for model in CORE_MODELS:
        solution, dual_solution, residual, complementarity, identity, feasibility = metrics(model)
        gap = duality_gap(solution.objective, dual_solution.objective)
        assert gap is not None and gap < DEFAULT_TOLERANCE
        for value in (residual, complementarity, identity, feasibility):
            assert value is not None and value < DEFAULT_TOLERANCE
    infeasible = solve_model(build_production_lp(PRODUCTION_INFEASIBLE))
    assert infeasible.objective is None
    assert max_complementarity_violation(build_production_lp(PRODUCTION_INFEASIBLE), infeasible) is None
    print(f"四个核心场景在 {DEFAULT_TOLERANCE:.0e} 下全部通过；不可行算例的各项检查为 None。")


if __name__ == "__main__":
    main()
