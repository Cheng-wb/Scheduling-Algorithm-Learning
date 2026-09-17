"""Day 1：LP 标准型、可行域、极点与 slack。

两变量算例的价值在于**整张可行域可以画出来**：极点是两条约束直线的交点，
可以用精确有理数枚举，于是「最优解一定在极点取到」不是一句口号，而是一张
可以逐行核对的表。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fractions import Fraction

from opt_models.lp_models import (
    PRODUCTION_2D,
    build_production_lp,
    enumerate_vertices_2d,
    row_slack,
    solve_model,
)


def describe(data) -> None:
    """按「集合 -> 参数 -> 变量 -> 目标 -> 约束」的顺序打印模型。"""
    print("== 1. 集合 ==")
    print(f"产品集合 P = {list(data.products)}")
    print(f"资源集合 R = {list(data.resources)}")
    print()
    print("== 2. 参数（全部写在集合之后，单位统一）==")
    print(f"单位利润 profit   = {dict(zip(data.products, data.profit))}")
    for index, resource in enumerate(data.resources):
        print(
            f"单位消耗 usage[{resource}] = "
            f"{dict(zip(data.products, data.usage[index]))}"
        )
    print(f"可用产能 capacity = {dict(zip(data.resources, data.capacity))}")
    print()


def print_model(model) -> None:
    print("== 3. 变量与目标（标准型：max c'x, Ax <= b, x >= 0）==")
    terms = " + ".join(
        f"{coefficient:g}*{name}"
        for name, coefficient in zip(model.var_names, model.objective_coeffs)
    )
    print(f"变量  x >= 0，共 {model.num_variables} 个：{list(model.var_names)}")
    print(f"目标  max {terms}")
    print(f"约束  共 {model.num_rows} 条：")
    for row in model.rows:
        body = " + ".join(f"{coefficient:g}*{name}" for name, coefficient in row.terms)
        print(f"        {row.name:8s} {body} {row.sense} {row.rhs:g}")
    print()


def print_vertices(model) -> None:
    print("== 4. 极点（两条直线求交，用 Fraction 精确算）==")
    print("  极点坐标    目标值   使该点成为极点的紧约束")
    for vertex in enumerate_vertices_2d(model):
        point = f"({vertex.point[0]}, {vertex.point[1]})"
        tight = ", ".join(vertex.tight_rows) if vertex.tight_rows else "(无：原点)"
        print(f"  {point:11s} {str(vertex.objective):>7s}   {tight}")
    print()
    print("两条直线平行时无交点、交点越界时不是可行点，都被枚举排除。")
    print("原点没有非负约束之外的紧约束，所以紧约束列为空。")
    print()


def print_slack_table(model) -> None:
    print("== 5. slack：约束「还剩多少余量」 ==")
    probes = {
        "(0, 0) 原点": {"x_P1": 0.0, "x_P2": 0.0},
        "(50, 0) 只做 P1": {"x_P1": 50.0, "x_P2": 0.0},
        "(0, 40) 只做 P2": {"x_P1": 0.0, "x_P2": 40.0},
        "(40, 20) 最优极点": {"x_P1": 40.0, "x_P2": 20.0},
        "(20, 20) 内点": {"x_P1": 20.0, "x_P2": 20.0},
    }
    header = "  点              目标值    " + "".join(f"{row.name:>12s}" for row in model.rows)
    print(header)
    for label, values in probes.items():
        activity = {row.name: row.activity(values) for row in model.rows}
        objective = sum(
            coefficient * values[name]
            for name, coefficient in zip(model.var_names, model.objective_coeffs)
        )
        slacks = "".join(
            f"{row_slack(row, activity[row.name]):>12.4g}" for row in model.rows
        )
        print(f"  {label:14s} {objective:>7.4g}   {slacks}")
    print()
    print("紧约束处 slack = 0；内点的 slack 全部大于 0——这就是「极点 vs 内点」的区别。")
    print()


def print_solver_check(model) -> None:
    solution = solve_model(model)
    print("== 6. 求解器核对 ==")
    print(f"状态 {solution.status}，最优目标 {solution.objective:g}")
    print(f"最优解 {solution.primal}")
    print(f"影子价格 {solution.dual}")
    hand = Fraction(40) * Fraction(40) + Fraction(30) * Fraction(20)
    print(f"手算顶点 (40, 20) 的目标：40*40 + 30*20 = {hand}")
    assert solution.objective is not None
    assert abs(solution.objective - float(hand)) < 1e-9
    print("极点枚举的最优值 = 求解器最优值，断言通过。")


def main() -> None:
    data = PRODUCTION_2D
    model = build_production_lp(data)
    describe(data)
    print_model(model)
    print_vertices(model)
    print_slack_table(model)
    print_solver_check(model)


if __name__ == "__main__":
    main()
