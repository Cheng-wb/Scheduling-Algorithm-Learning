"""Day 7：Week 1 复盘——把一周的工具串成一条流水线，并写下它的边界。

复盘不是把七天的话再说一遍，而是回答三个问题：

1. 一条 LP 从「业务问题」走到「可执行结论」要经过哪些**可检查**的步骤？
2. 对偶的四个读数量（``shadow price``、``reduced cost``、``slack``、``gap``）
   分别能回答什么业务问题？
3. 这套工具在哪里会给出**看起来对、其实错**的结论？——三条局限各配一个
   本周已经出现过的反例。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_models.lp_models import (
    ASSIGNMENT_BASE,
    PRODUCTION_2D,
    PRODUCTION_BASE,
    PRODUCTION_INFEASIBLE,
    TRANSPORT_BASE,
    build_assignment_lp,
    build_dual,
    build_production_lp,
    build_transportation_lp,
    duality_gap,
    max_complementarity_violation,
    solve_model,
)

TOLERANCE = 1e-9

STEPS = (
    ("1. 写集合", "产品、资源、源、汇、人、任务——先把索引集合写死，型号顺序后面全靠它"),
    ("2. 写参数", "利润、消耗、产能、需求、运费、成本——每个参数都带单位，且与集合对齐"),
    ("3. 写变量", "先声明取值范围（>= 0 / 自由 / 整数），再谈它的含义"),
    ("4. 写目标", "max 或 min，写明它是「单位量 x 数量」的求和，不许有常数项"),
    ("5. 写约束", "每条约束一句话：谁被谁限制；上界写成行，不写成变量界"),
    ("6. 求解", "读状态；状态不是 OPTIMAL 时先别解释目标值"),
    ("7. 读解", "primal、slack、reduced cost、shadow price 四个量一起读"),
    ("8. 对拍", "c'x 与 b'y 互相印证；互补松弛与 rc 恒等式做结构性核对"),
    ("9. 解释", "把数字翻译回业务语言，并标出它成立的**区间**"),
)


def print_pipeline() -> None:
    print("== 1. 建模九步（前五步写模型，后四步读模型）==")
    for name, description in STEPS:
        print(f"  {name:<10s} {description}")
    print()


def print_summary() -> None:
    print("== 2. 本周五个算例的总账 ==")
    models = (
        build_production_lp(PRODUCTION_2D),
        build_production_lp(PRODUCTION_BASE),
        build_production_lp(PRODUCTION_INFEASIBLE),
        build_transportation_lp(TRANSPORT_BASE),
        build_assignment_lp(ASSIGNMENT_BASE),
    )
    print(f"{'场景':<18s}{'类型':<15s}{'规模':>9s}{'状态':>11s}{'primal':>10s}"
          f"{'dual':>10s}{'|gap|':>10s}{'互补松弛':>11s}")
    for model in models:
        solution = solve_model(model)
        scale = f"{model.num_variables}x{model.num_rows}"
        if not solution.has_solution:
            print(
                f"{model.name:<18s}{model.meta['kind']:<15s}{scale:>9s}{solution.status:>11s}"
                f"{'None':>10s}{'None':>10s}{'None':>10s}{'None':>11s}"
            )
            continue
        dual_solution = solve_model(build_dual(model))
        gap = duality_gap(solution.objective, dual_solution.objective)
        complementarity = max_complementarity_violation(model, solution)
        print(
            f"{model.name:<18s}{model.meta['kind']:<15s}{scale:>9s}{solution.status:>11s}"
            f"{solution.objective:>10g}{dual_solution.objective:>10g}{gap:>10.2e}"
            f"{complementarity:>11.2e}"
        )
    print("前两个是生产计划、第三个故意不可行、后两个是网络结构的 LP。")
    print("不可行行的四个量都写 None：没有解的时候不能拿 0 冒充结果。")
    print()


def print_dual_reading() -> None:
    model = build_production_lp(PRODUCTION_BASE)
    solution = solve_model(model)
    print("== 3. 对偶的四个读数量各回答什么问题（prod_base）==")
    print(f"{'约束行':<12s}{'slack':>10s}{'shadow price':>14s}   业务读法")
    readings = {
        "cap_M": "M 产能多 1 单位，利润 +15；少于 15 元/单位就别扩",
        "cap_L": "L 产能多 1 单位，利润 +10；同理",
        "demand_P1": "需求上限放松 1 单位不改变利润——它现在没顶住",
        "demand_P2": "同上；P2 的需求上限根本用不上",
        "demand_P3": "同上；P3 还有 20 单位余量",
    }
    for row in model.rows:
        print(
            f"{row.name:<12s}{solution.slack[row.name]:>10.4f}"
            f"{solution.dual[row.name]:>14.4f}   {readings[row.name]}"
        )
    print()
    print(f"{'变量':<8s}{'x':>9s}{'reduced cost':>15s}   业务读法")
    for name in model.var_names:
        value = solution.primal[name]
        reduced = solution.reduced_cost[name]
        if value > TOLERANCE:
            note = "已投产，rc = 0；它是基变量，没有额外信息"
        else:
            note = f"不投产；P2 的单位利润要涨到 {30 - reduced:g} 才值得开工"
        print(f"{name:<8s}{value:>9.4f}{reduced:>15.4f}   {note}")
    print("注意 x_P2 那一行：reduced cost 是**盈亏平衡价**，不是「涨 5 元就多赚 5 元」。")
    print()


def print_limits() -> None:
    print("== 4. 三条局限（每条都有本周的反例）==")
    print("局限一：状态码不等于可行性结论。")
    print("  prod_infeasible 返回 INFEASIBLE，但本环境 GLOP 对无界 LP 也返回同一个码；")
    print("  「真的不可行」是手算 x_P2 <= 50 与 x_P2 >= 60 冲突得到的。")
    print("局限二：shadow price 只在基不变的区间内有效。")
    print("  cap_M 的影子价格在 [80, 120] 上是 15；到 130 时目标停在 2600，")
    print("  线性预测会给出 2750，多算了 150。")
    print("局限三：对偶解可能不唯一，别把打印出来的那一组当成唯一真理。")
    print("  assign_base 的对偶有 6 个变量，取等的对偶约束却只有 5 条")
    print("  （其中 2 条来自退化的零分量），于是最优对偶解有一维自由度；")
    print("  能核验的是不变量（u_i + v_j <= c_ij、u + v 在配对上取等、Σu + Σv = 9）。")
    print()


def main() -> None:
    print_pipeline()
    print_summary()
    print_dual_reading()
    print_limits()

    print("== 5. 断言 ==")
    base = solve_model(build_production_lp(PRODUCTION_BASE))
    assert abs(base.objective - 2300.0) < TOLERANCE
    assert abs(base.dual["cap_M"] - 15.0) < TOLERANCE
    assert abs(base.reduced_cost["x_P2"] - (-5.0)) < TOLERANCE
    assert abs(base.primal["x_P2"]) < TOLERANCE
    far = solve_model(build_production_lp(PRODUCTION_BASE.with_capacity("M", 130.0)))
    assert abs(far.objective - 2600.0) < TOLERANCE
    assert abs(far.objective - (2300.0 + 15.0 * 30.0)) > 100.0
    print("复盘用到的六个数字全部来自本周脚本与手算，断言通过。")


if __name__ == "__main__":
    main()
