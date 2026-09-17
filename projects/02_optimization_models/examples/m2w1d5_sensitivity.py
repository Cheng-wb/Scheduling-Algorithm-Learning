"""Day 5：扰动产能、需求与成本，核验影子价格的局部解释范围。

影子价格是一条**局部**斜率，不是全局导数。本脚本沿三条轴各扫一格：

* 产能轴：看 ``cap_M``、``cap_L`` 的影子价格在哪个区间保持不变；
* 成本轴（单位利润）：看 ``reduced cost`` 是「盈亏平衡价」而不是斜率；
* 需求轴：看一条**松弛**的约束如何在不改变影子价格的前提下产生一个折点。

每一行的「实测」都来自一次真实求解，「预测」按当天要检验的规则计算，
两者并列打印，让规则在哪里失效一眼可见。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_models.lp_models import (
    PRODUCTION_BASE,
    build_production_lp,
    production_capacity_grid,
    production_demand_grid,
    production_profit_grid,
    solve_model,
)

TOLERANCE = 1e-9


def solve(data):
    return solve_model(build_production_lp(data))


def print_baseline() -> None:
    solution = solve(PRODUCTION_BASE)
    print("== 1. 基准解与影子价格 ==")
    print(f"状态 {solution.status}，目标值 {solution.objective:g}")
    print(f"最优解 { {k: round(v, 6) for k, v in solution.primal.items()} }")
    for row in build_production_lp(PRODUCTION_BASE).rows:
        print(
            f"  {row.name:<12s} rhs {row.rhs:>6g}   slack {solution.slack[row.name]:>7.4f}"
            f"   影子价格 {solution.dual[row.name]:>8.4f}"
        )
    print("两条产能行的 slack 为 0、影子价格为正；三条需求行 slack 大于 0、影子价格为 0。")
    print()


def print_capacity_sweep(resource: str, section: int) -> None:
    grid = production_capacity_grid(resource)
    baseline = solve(PRODUCTION_BASE)
    shadow = baseline.dual[f"cap_{resource}"]
    base_value = dict(zip(PRODUCTION_BASE.resources, PRODUCTION_BASE.capacity))[resource]
    print(f"== {section}. 产能轴：沿 cap_{resource} 扫描（基准值 {base_value:g}，影子价格 {shadow:g}）==")
    print(f"{'取值':>7s}{'delta':>8s}{'状态':>10s}{'实测目标':>12s}{'预测目标':>12s}{'误差':>11s}{'该行影子价格':>14s}   预测成立")
    rows = []
    for data in grid:
        value = dict(zip(data.resources, data.capacity))[resource]
        solution = solve(data)
        delta = value - base_value
        predicted = baseline.objective + shadow * delta
        error = solution.objective - predicted
        ok = abs(error) < TOLERANCE
        rows.append((value, solution.objective, solution.dual[f"cap_{resource}"], ok))
        print(
            f"{value:>7g}{delta:>+8g}{solution.status:>10s}{solution.objective:>12g}"
            f"{predicted:>12g}{error:>11.3g}{solution.dual[f'cap_{resource}'] + 0.0:>14.4f}"
            f"   {'是' if ok else '否'}"
        )
    index = next(i for i, item in enumerate(rows) if abs(item[0] - base_value) < TOLERANCE)
    low = index
    while low - 1 >= 0 and rows[low - 1][3]:
        low -= 1
    high = index
    while high + 1 < len(rows) and rows[high + 1][3]:
        high += 1
    print(
        f"在这张网格上，线性预测成立的区间是 cap_{resource} ∈ "
        f"[{rows[low][0]:g}, {rows[high][0]:g}]。"
    )
    print("区间外预测立刻失效：目标值函数在折点处换了斜率，基准影子价格不再适用。")
    for position, side in ((low, "左"), (high, "右")):
        if position == 0 or position == len(rows) - 1:
            continue
        before, here, after = rows[position - 1], rows[position], rows[position + 1]
        left_slope = (here[1] - before[1]) / (here[0] - before[0])
        right_slope = (after[1] - here[1]) / (after[0] - here[0])
        print(
            f"  取值为 {here[0]:g}（区间{side}端点）时：左侧网格斜率 {left_slope:g}、"
            f"右侧网格斜率 {right_slope:g}，求解器报 {here[2] + 0.0:g}。"
        )
    print("折点上的对偶解不唯一：求解器报的那个数是众多次梯度之一，")
    print("用它做预测前先问清楚「往哪个方向扰动」。")
    print()


def print_profit_sweep(product: str, section: int) -> None:
    grid = production_profit_grid(product)
    baseline = solve(PRODUCTION_BASE)
    base_profit = dict(zip(PRODUCTION_BASE.products, PRODUCTION_BASE.profit))[product]
    reduced = baseline.reduced_cost[f"x_{product}"]
    break_even = base_profit - reduced
    print(f"== {section}. 成本轴：沿 {product} 的单位利润扫描 ==")
    print(f"基准单位利润 {base_profit:g}，基准 reduced cost {reduced:g}，"
          f"盈亏平衡价 = {base_profit:g} - ({reduced:g}) = {break_even:g}")
    print(f"{'单位利润':>9s}{'实测目标':>12s}{'x_' + product:>10s}{'reduced cost':>15s}   解释")
    for data in grid:
        value = dict(zip(data.products, data.profit))[product]
        solution = solve(data)
        primal = solution.primal[f"x_{product}"]
        rc = solution.reduced_cost[f"x_{product}"]
        if value < break_even - TOLERANCE:
            note = "低于盈亏平衡价：不投产，目标不变"
        elif abs(value - break_even) <= TOLERANCE:
            note = "正好等于盈亏平衡价：rc = 0，出现另一个同样好的顶点"
        else:
            note = "高于盈亏平衡价：开始投产，目标上升"
        print(f"{value:>9g}{solution.objective:>12g}{primal:>10.4f}{rc:>15.4f}   {note}")
    print("把 reduced cost 当斜率用会得出「单位利润越低越赚」的错结论；")
    print("它的正确读法是「要让这个变量进基，它的系数至少要提高多少」。")
    print()


def print_demand_sweep(product: str, section: int) -> None:
    grid = production_demand_grid(product)
    baseline = solve(PRODUCTION_BASE)
    shadow = baseline.dual[f"demand_{product}"]
    print(f"== {section}. 需求轴：沿 demand_{product} 扫描 ==")
    print(f"基准需求上限 {dict(zip(PRODUCTION_BASE.products, PRODUCTION_BASE.max_demand))[product]:g}，"
          f"该行影子价格 {shadow:g}")
    print(f"{'需求上限':>9s}{'实测目标':>12s}{'该行 slack':>12s}{'该行影子价格':>14s}{'x_' + product:>10s}   线性预测")
    for data in grid:
        value = dict(zip(data.products, data.max_demand))[product]
        solution = solve(data)
        predicted = baseline.objective + shadow * (value - dict(zip(PRODUCTION_BASE.products, PRODUCTION_BASE.max_demand))[product])
        error = solution.objective - predicted
        print(
            f"{value:>9g}{solution.objective:>12g}{solution.slack[f'demand_{product}']:>12.4f}"
            f"{solution.dual[f'demand_{product}']:>14.4f}{solution.primal[f'x_{product}']:>10.4f}"
            f"   {'成立' if abs(error) < TOLERANCE else f'失效（差 {error:g}）'}"
        )
    print("基准点上该行 slack = 20、影子价格 = 0，那是**右导数**；")
    print("把需求上限一路压到 20 时该行顶死，影子价格跳到 15——折点出现了。")
    print("于是同一个数字 0 只在「需求上限 >= 20」这一侧成立，另一侧要用 15。")
    print()


def main() -> None:
    print_baseline()
    print_capacity_sweep("M", 2)
    print_capacity_sweep("L", 3)
    print_profit_sweep("P2", 4)
    print_demand_sweep("P1", 5)

    print("== 6. 断言 ==")
    baseline = solve(PRODUCTION_BASE)
    assert abs(baseline.objective - 2300.0) < TOLERANCE
    assert abs(baseline.dual["cap_M"] - 15.0) < TOLERANCE
    assert abs(baseline.dual["cap_L"] - 10.0) < TOLERANCE
    assert abs(baseline.reduced_cost["x_P2"] - (-5.0)) < TOLERANCE
    at_80 = solve(PRODUCTION_BASE.with_capacity("M", 80.0))
    at_130 = solve(PRODUCTION_BASE.with_capacity("M", 130.0))
    assert abs(at_80.objective - (2300.0 + 15.0 * (80.0 - 100.0))) < TOLERANCE
    assert abs(at_130.objective - 2600.0) < TOLERANCE
    assert abs(at_130.objective - (2300.0 + 15.0 * 30.0)) > 100.0
    print("区间内预测成立（cap_M = 80）、区间外预测失效（cap_M = 130）两条断言均通过。")


if __name__ == "__main__":
    main()
