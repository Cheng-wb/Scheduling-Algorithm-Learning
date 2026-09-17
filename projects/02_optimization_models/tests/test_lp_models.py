"""Week 1 LP 模型的验收测试。

**expected 全部来自手算，不由被测函数生成。** 每个手算值旁边都写了它是怎么算出来的：
顶点枚举、对偶方程组、或者互补松弛的逐对检查。求解器给出的数字只用来**对照**这些
手算值，不用来定义它们——这与 M1「expected 不由被测算法生成」是同一条纪律。

两类断言刻意分开写：

* ``== 手算值``：模型写对了没有；
* ``<= 容差``：数值对拍（可行性残差、rc 恒等式、互补松弛、对偶可行）过没过。

第二类断言**不检查具体数值**，只检查不变量。这样即使某个版本的求解器换了一个
同样最优的基（退化时会发生），测试也不会误报。
"""

from __future__ import annotations

from fractions import Fraction
from itertools import permutations

import pytest

from opt_models.lp_models import (
    ASSIGNMENT_BASE,
    PRODUCTION_2D,
    PRODUCTION_BASE,
    PRODUCTION_INFEASIBLE,
    TRANSPORT_BASE,
    AssignmentData,
    TransportData,
    build_assignment_lp,
    build_dual,
    build_production_lp,
    build_transportation_lp,
    complementarity_rows,
    dual_feasibility_violation,
    duality_gap,
    enumerate_vertices_2d,
    max_complementarity_violation,
    max_reduced_cost_identity_error,
    max_primal_nonnegativity_violation,
    production_capacity_grid,
    solve_model,
)

#: 事后对拍容差。GLOP 自身的可行性容差在 1e-8 量级，所以这里只检查「是不是
#: 数值尘埃」；实测最大残差在 1e-13 以下（见 artifacts/month2_w1/report.md）。
TOL = 1e-9


# ---------------------------------------------------------------------------
# 1. 手算生产 LP：两变量两约束
# ---------------------------------------------------------------------------


def test_production_2d_hand_computed_optimum():
    """手算：max 40x1 + 30x2, 2x1+x2<=100, x1+2x2<=80。

    四个顶点由两条直线求交得到：
        (0,0) 与 x1 轴、x2 轴 -> 0
        (50,0) 2x1 = 100        -> 2000
        (0,40) 2x2 = 80         -> 1200
        (40,20) 联立两条产能约束 -> 40*40 + 30*20 = 2200
    最大值 2200，在两约束同时取等的顶点 (40,20) 上取到。
    """
    solution = solve_model(build_production_lp(PRODUCTION_2D))

    assert solution.status == "OPTIMAL"
    assert solution.objective == pytest.approx(2200.0, abs=TOL)
    assert solution.primal["x_P1"] == pytest.approx(40.0, abs=TOL)
    assert solution.primal["x_P2"] == pytest.approx(20.0, abs=TOL)
    # 两条产能约束都取等 -> slack 都为 0
    assert solution.slack["cap_M"] == pytest.approx(0.0, abs=TOL)
    assert solution.slack["cap_L"] == pytest.approx(0.0, abs=TOL)


def test_production_2d_hand_computed_shadow_prices():
    """手算对偶：两个变量都取正 -> 两条对偶约束都取等。

        2y_M + y_L = 40
        y_M + 2y_L = 30
    解得 y_M = 50/3, y_L = 20/3；对偶目标 100*(50/3) + 80*(20/3) = 6600/3 = 2200。
    """
    solution = solve_model(build_production_lp(PRODUCTION_2D))

    assert solution.dual["cap_M"] == pytest.approx(50.0 / 3.0, abs=TOL)
    assert solution.dual["cap_L"] == pytest.approx(20.0 / 3.0, abs=TOL)
    # 手算的对偶目标：100*(50/3) + 80*(20/3) = 6600/3 = 2200，用 Fraction 保证精确
    hand_dual_objective = 100 * Fraction(50, 3) + 80 * Fraction(20, 3)
    assert hand_dual_objective == Fraction(6600, 3)
    assert solution.objective == pytest.approx(float(hand_dual_objective), abs=TOL)


def test_vertices_of_production_2d_are_hand_enumerated():
    """极点枚举给出且仅给出四个手算顶点，目标值也逐一对应。"""
    model = build_production_lp(PRODUCTION_2D)
    vertices = enumerate_vertices_2d(model)

    observed = {
        (int(v.point[0]), int(v.point[1])): (int(v.objective), v.tight_rows)
        for v in vertices
    }
    assert observed == {
        (0, 0): (0, ()),
        (0, 40): (1200, ("cap_L",)),
        (40, 20): (2200, ("cap_M", "cap_L")),
        (50, 0): (2000, ("cap_M",)),
    }
    # 极点上的最优值等于 LP 最优值：两变量时基本定理可以直接看出来
    best = max(item.objective for item in vertices)
    assert best == 2200
    assert solve_model(model).objective == pytest.approx(float(best), abs=TOL)


# ---------------------------------------------------------------------------
# 2. 手算生产 LP：三产品两资源（本周主算例）
# ---------------------------------------------------------------------------


def test_production_base_hand_computed_solution():
    """手算：P3 的单位资源利润最高，最优基是 {P1, P3}。

    两条产能约束取等：2x1 + x3 = 100、x1 + x3 = 80 -> x1 = 20, x3 = 60。
    目标 40*20 + 25*60 = 800 + 1500 = 2300。P2 不生产。
    """
    solution = solve_model(build_production_lp(PRODUCTION_BASE))

    assert solution.status == "OPTIMAL"
    assert solution.objective == pytest.approx(2300.0, abs=TOL)
    assert solution.primal == {
        "x_P1": pytest.approx(20.0, abs=TOL),
        "x_P2": pytest.approx(0.0, abs=TOL),
        "x_P3": pytest.approx(60.0, abs=TOL),
    }
    # 松弛量手算：cap 行取等 -> 0；需求行分别为 40-20、50-0、80-60
    assert solution.slack == {
        "cap_M": pytest.approx(0.0, abs=TOL),
        "cap_L": pytest.approx(0.0, abs=TOL),
        "demand_P1": pytest.approx(20.0, abs=TOL),
        "demand_P2": pytest.approx(50.0, abs=TOL),
        "demand_P3": pytest.approx(20.0, abs=TOL),
    }


def test_production_base_hand_computed_duals_and_reduced_cost():
    """手算对偶：x_P1、x_P3 取正 -> 它们的两条对偶约束取等。

        P1: 2y_M + y_L + y_D1 = 40
        P3:  y_M + y_L + y_D3 = 25
    两条需求上限都没顶住 -> y_D1 = y_D3 = 0，于是 2y_M + y_L = 40、y_M + y_L = 25，
    相减得 y_M = 15、y_L = 10。

    P2 不生产，其 reduced cost 手算为
        30 - (y_M + 2y_L) = 30 - (15 + 20) = -5。
    """
    solution = solve_model(build_production_lp(PRODUCTION_BASE))

    assert solution.dual == {
        "cap_M": pytest.approx(15.0, abs=TOL),
        "cap_L": pytest.approx(10.0, abs=TOL),
        "demand_P1": pytest.approx(0.0, abs=TOL),
        "demand_P2": pytest.approx(0.0, abs=TOL),
        "demand_P3": pytest.approx(0.0, abs=TOL),
    }
    # 基变量的 reduced cost 必为 0
    assert solution.reduced_cost["x_P1"] == pytest.approx(0.0, abs=TOL)
    assert solution.reduced_cost["x_P3"] == pytest.approx(0.0, abs=TOL)
    assert solution.reduced_cost["x_P2"] == pytest.approx(-5.0, abs=TOL)


def test_shadow_price_equals_hand_computed_objective_difference():
    """影子价格的含义由手算验证：产能 M 从 100 加到 110，目标增加 15*10 = 150。

    2300 + 150 = 2450，与直接求解扰动后的模型一致。
    """
    base = solve_model(build_production_lp(PRODUCTION_BASE))
    perturbed_data = PRODUCTION_BASE.with_capacity("M", 110.0)
    perturbed = solve_model(build_production_lp(perturbed_data))

    hand_delta = 15.0 * 10.0
    assert perturbed.objective - base.objective == pytest.approx(hand_delta, abs=TOL)
    assert perturbed.objective == pytest.approx(2450.0, abs=TOL)


def test_shadow_price_is_only_locally_valid():
    """影子价格只在基不变的区间内有效——区间外「预测」必须失效。

    手算区间：x_P1 = cap_M - 80 >= 0 且 x_P1 <= 40（P1 的需求上限）
    -> cap_M 在 [80, 120] 内 y_M 才是 15。网格数据实测：
        cap_M = 90/100/110  -> y_M = 15
        cap_M = 60/70       -> y_M = 20（另一个基）
        cap_M = 130/140     -> y_M = 0 （P1 顶住需求上限，M 还有余量）
    """
    grid = {int(d.capacity[0]): solve_model(build_production_lp(d)) for d in production_capacity_grid("M")}

    for value in (90, 100, 110):
        assert grid[value].dual["cap_M"] == pytest.approx(15.0, abs=TOL)
    for value in (60, 70):
        assert grid[value].dual["cap_M"] == pytest.approx(20.0, abs=TOL)
    for value in (130, 140):
        assert grid[value].dual["cap_M"] == pytest.approx(0.0, abs=TOL)

    # 区间外线性外推失败：2300 + 15*(130-100) = 2750，实测只有 2600
    assert grid[130].objective == pytest.approx(2600.0, abs=TOL)
    assert grid[130].objective != pytest.approx(2750.0, abs=TOL)


def test_reduced_cost_is_a_break_even_price_not_a_slope():
    """reduced cost 的定价含义：P2 的单位利润从 30 涨到 35 才进入基。

    手算：rc = -5 -> 利润提高 5 时 rc 归零，P2 恰好保本；再高才值得生产。
    """
    at_35 = solve_model(build_production_lp(PRODUCTION_BASE.with_profit("P2", 35.0)))
    assert at_35.reduced_cost["x_P2"] == pytest.approx(0.0, abs=TOL)
    assert at_35.objective == pytest.approx(2300.0, abs=TOL)  # 保本点上目标不变

    at_40 = solve_model(build_production_lp(PRODUCTION_BASE.with_profit("P2", 40.0)))
    assert at_40.objective == pytest.approx(2400.0, abs=TOL)
    assert at_40.primal["x_P2"] == pytest.approx(20.0, abs=TOL)


# ---------------------------------------------------------------------------
# 3. 手算运输 LP
# ---------------------------------------------------------------------------


def test_transportation_hand_computed_solution():
    """手算：S1 供 D1(15) 与 D2(5)，S2 供 D2(15) 与 D3(10)。

    费用 4*15 + 6*5 + 4*15 + 3*10 = 60 + 30 + 60 + 30 = 180。
    基本变量 4 个（m+n-1 = 2+3-1 = 4），全为正 -> 该基非退化。
    """
    solution = solve_model(build_transportation_lp(TRANSPORT_BASE))

    assert solution.status == "OPTIMAL"
    assert solution.objective == pytest.approx(180.0, abs=TOL)
    assert solution.primal == {
        "x_S1_D1": pytest.approx(15.0, abs=TOL),
        "x_S1_D2": pytest.approx(5.0, abs=TOL),
        "x_S1_D3": pytest.approx(0.0, abs=TOL),
        "x_S2_D1": pytest.approx(0.0, abs=TOL),
        "x_S2_D2": pytest.approx(15.0, abs=TOL),
        "x_S2_D3": pytest.approx(10.0, abs=TOL),
    }


def test_transportation_hand_computed_duals():
    """手算对偶：u_i + v_j = c_ij 在基本格上取等。

        u1 + v1 = 4, u1 + v2 = 6, u2 + v2 = 4, u2 + v3 = 3
    取 u1 = 0 -> v1 = 4, v2 = 6, u2 = -2, v3 = 5。
    非基本格检查：u1 + v3 = 5 <= 8（rc = 3），u2 + v1 = 2 <= 6（rc = 4）。
    对偶目标 20*0 + 25*(-2) + 15*4 + 20*6 + 10*5 = 180，与原始目标相等。
    """
    solution = solve_model(build_transportation_lp(TRANSPORT_BASE))

    assert solution.dual == {
        "supply_S1": pytest.approx(0.0, abs=TOL),
        "supply_S2": pytest.approx(-2.0, abs=TOL),
        "demand_D1": pytest.approx(4.0, abs=TOL),
        "demand_D2": pytest.approx(6.0, abs=TOL),
        "demand_D3": pytest.approx(5.0, abs=TOL),
    }
    assert solution.reduced_cost["x_S1_D3"] == pytest.approx(3.0, abs=TOL)
    assert solution.reduced_cost["x_S2_D1"] == pytest.approx(4.0, abs=TOL)
    # 非负约束之外，等式行的对偶变量是自由的：u2 = -2 < 0 完全正常
    assert solution.dual["supply_S2"] < 0


def test_transportation_rejects_unbalanced_instance():
    """产销不平衡需要先加虚拟源或汇；builder 不做这个决定，直接报错。"""
    unbalanced = TransportData(
        name="unbalanced",
        sources=("S1",),
        destinations=("D1",),
        supply=(10.0,),
        demand=(12.0,),
        cost=((1.0,),),
    )
    with pytest.raises(ValueError, match="balanced"):
        build_transportation_lp(unbalanced)


# ---------------------------------------------------------------------------
# 4. 手算指派 LP
# ---------------------------------------------------------------------------


def test_assignment_matches_brute_force_permutations():
    """手算：3x3 全部 6 个排列的目标值。

        (W1,W2,W3) -> 9+4+1 = 14      (W1,W3,W2) -> 9+3+8 = 20
        (W2,W1,W3) -> 2+6+1 =  9      (W2,W3,W1) -> 2+3+5 = 10
        (W3,W1,W2) -> 7+6+8 = 21      (W3,W2,W1) -> 7+4+5 = 16
    最小 9，唯一指派 J1->W2、J2->W1、J3->W3。
    """
    costs = ASSIGNMENT_BASE.cost
    best = min(
        sum(costs[i][order[i]] for i in range(3)) for order in permutations(range(3))
    )
    assert best == 9

    solution = solve_model(build_assignment_lp(ASSIGNMENT_BASE))
    assert solution.status == "OPTIMAL"
    assert solution.objective == pytest.approx(float(best), abs=TOL)
    assert solution.primal["x_J1_W2"] == pytest.approx(1.0, abs=TOL)
    assert solution.primal["x_J2_W1"] == pytest.approx(1.0, abs=TOL)
    assert solution.primal["x_J3_W3"] == pytest.approx(1.0, abs=TOL)
    # LP relaxation 给出整数解：这是指派多面体的整性，不是四舍五入的结果
    assert all(
        value == pytest.approx(round(value), abs=TOL) for value in solution.primal.values()
    )


def test_assignment_dual_is_not_unique_but_satisfies_hand_checks():
    """指派 LP 是退化的（最优解只有 3 个非零分量，而基有 2n-1 = 5 个位置），
    所以对偶最优解**不唯一**——这里不比对某个具体向量，只检查手算能验证的不变量：

    * ``u_i + v_j <= c_ij`` 对全部 9 个格成立（对偶可行）；
    * ``u_i + v_j = c_ij`` 在指派的 3 个格上成立（互补松弛）；
    * ``Σu + Σv = 9``（强对偶）。
    """
    solution = solve_model(build_assignment_lp(ASSIGNMENT_BASE))

    dual_of_agent = {agent: solution.dual[f"agent_{agent}"] for agent in ASSIGNMENT_BASE.agents}
    dual_of_task = {task: solution.dual[f"task_{task}"] for task in ASSIGNMENT_BASE.tasks}

    for i, agent in enumerate(ASSIGNMENT_BASE.agents):
        for j, task in enumerate(ASSIGNMENT_BASE.tasks):
            assert dual_of_agent[agent] + dual_of_task[task] <= ASSIGNMENT_BASE.cost[i][j] + TOL

    for agent, task, cost in (("J1", "W2", 2.0), ("J2", "W1", 6.0), ("J3", "W3", 1.0)):
        assert dual_of_agent[agent] + dual_of_task[task] == pytest.approx(cost, abs=TOL)

    total = sum(dual_of_agent.values()) + sum(dual_of_task.values())
    assert total == pytest.approx(9.0, abs=TOL)


def test_assignment_rejects_non_square_instance():
    rectangular = AssignmentData(
        name="rect",
        agents=("J1", "J2"),
        tasks=("W1", "W2", "W3"),
        cost=((1.0, 2.0, 3.0), (4.0, 5.0, 6.0)),
    )
    with pytest.raises(ValueError, match="square"):
        build_assignment_lp(rectangular)


# ---------------------------------------------------------------------------
# 5. 互补松弛：逐对手算
# ---------------------------------------------------------------------------


def test_complementary_slackness_hand_pairs_on_production_base():
    """手算三对互补松弛，全部乘积为 0：

    * 变量 ``x_P1``：取正 -> reduced cost 必须是 0；
    * 变量 ``x_P2``：reduced cost = -5 < 0 -> ``x_P2`` 必须是 0；
    * 约束 ``demand_P1``：松弛量 20 > 0 -> 影子价格必须是 0。
    """
    model = build_production_lp(PRODUCTION_BASE)
    solution = solve_model(model)

    assert solution.primal["x_P1"] * solution.reduced_cost["x_P1"] == pytest.approx(0.0, abs=TOL)
    assert solution.reduced_cost["x_P1"] == pytest.approx(0.0, abs=TOL)
    assert solution.reduced_cost["x_P2"] == pytest.approx(-5.0, abs=TOL)
    assert solution.primal["x_P2"] == pytest.approx(0.0, abs=TOL)
    assert solution.slack["demand_P1"] == pytest.approx(20.0, abs=TOL)
    assert solution.dual["demand_P1"] == pytest.approx(0.0, abs=TOL)

    # 明细表里每一对的乘积也都要是 0（等式行不在表里：它的 slack 恒为 0）
    items = complementarity_rows(model, solution)
    assert items, "optimal solution must produce complementarity pairs"
    assert all(item["product"] <= TOL for item in items)
    assert {item["kind"] for item in items} == {"variable", "inequality_row"}
    # 5 个不等式行（2 产能 + 3 需求）都在表里，3 个变量也在
    assert len(items) == 3 + 5


@pytest.mark.parametrize(
    "name, model",
    [
        ("prod_2d", build_production_lp(PRODUCTION_2D)),
        ("prod_base", build_production_lp(PRODUCTION_BASE)),
        ("transport_base", build_transportation_lp(TRANSPORT_BASE)),
        ("assign_base", build_assignment_lp(ASSIGNMENT_BASE)),
    ],
)
def test_numerical_invariants_on_every_model(name, model):
    """不变量检查（不比对具体数值，只比对关系）。

    四个模型上都要求：原始可行、``rc_j = c_j - Σ a_ij y_i`` 的符号约定成立、
    互补松弛成立、对偶可行、且**对偶目标 = 原始目标**。
    """
    solution = solve_model(model)

    assert solution.status == "OPTIMAL", name
    assert solution.max_constraint_residual <= TOL, name
    assert max_primal_nonnegativity_violation(solution) <= TOL, name
    assert max_reduced_cost_identity_error(model, solution) <= TOL, name
    assert max_complementarity_violation(model, solution) <= TOL, name
    assert dual_feasibility_violation(model, solution) <= TOL, name

    dual_solution = solve_model(build_dual(model))
    assert dual_solution.status == "OPTIMAL", name
    assert duality_gap(solution.objective, dual_solution.objective) <= TOL, name


def test_dual_of_dual_returns_the_primal_objective():
    """对偶的对偶 = 原问题（对四个模型逐一检查）。"""
    for model in (
        build_production_lp(PRODUCTION_2D),
        build_production_lp(PRODUCTION_BASE),
        build_transportation_lp(TRANSPORT_BASE),
        build_assignment_lp(ASSIGNMENT_BASE),
    ):
        primal = solve_model(model)
        back_model = build_dual(build_dual(model))
        back = solve_model(back_model)
        assert back.objective == pytest.approx(primal.objective, abs=1e-6), model.name
        # 转置两次回到原规模：变量数与约束数都对上，方向也回到原来的 min/max
        assert back_model.num_variables == model.num_variables, model.name
        assert back_model.num_rows == model.num_rows, model.name
        assert back_model.sense == model.sense, model.name


def test_build_dual_rejects_bounded_variables():
    """变量带有限上界时必须先在原始里写成行，否则对偶会漏项。"""
    model = build_assignment_lp(ASSIGNMENT_BASE)
    bounded = model.variables["x_J1_W1"]
    assert bounded.ub() == model.solver.infinity()  # builder 没给上界
    # 手工给一个上界，build_dual 必须拒绝
    bounded.SetBounds(0.0, 0.5)
    with pytest.raises(ValueError, match="bounded variables"):
        build_dual(model)


# ---------------------------------------------------------------------------
# 6. 不可行 LP
# ---------------------------------------------------------------------------


def test_infeasible_production_lp_is_detected():
    """手算不可行的理由：``demand_P2`` 要求 ``x_P2 <= 50``，
    ``delivery_P2`` 要求 ``x_P2 >= 60``，两行直接冲突。

    求解器报 ``INFEASIBLE``；但见 ``test_status_code_alone_is_not_a_proof``：
    这个状态码本身不构成「可行域为空」的证明。
    """
    model = build_production_lp(PRODUCTION_INFEASIBLE)
    solution = solve_model(model)

    assert solution.status == "INFEASIBLE"
    # 没有最优解 -> 没有目标值、没有影子价格、没有 reduced cost
    assert solution.objective is None
    assert solution.primal == {}
    assert solution.dual == {}
    assert solution.dual_available is False
    # 没有对偶解时互补松弛返回 None，而不是「0 = 通过」
    assert max_complementarity_violation(model, solution) is None
    assert max_reduced_cost_identity_error(model, solution) is None
    assert dual_feasibility_violation(model, solution) is None
    assert solution.max_constraint_residual is None
    # 手工核对冲突的那两行确实都在模型里
    senses = {row.name: (row.sense, row.rhs) for row in model.rows}
    assert senses["demand_P2"] == ("<=", 50.0)
    assert senses["delivery_P2"] == (">=", 60.0)


def test_status_code_alone_is_not_a_proof():
    """实测记录：本环境的 GLOP 后端对**无界** LP 也返回状态码 2（INFEASIBLE）。

    ``min -x, x >= 0`` 显然可行（取 x = 1 即可），只是没有最优解。这里刻意只
    断言稳健的部分——「没有最优解」——因为不同 ortools 版本可能把无界单独报成
    ``UNBOUNDED``（3）。结论：状态码 2 不能读作「可行域为空」。
    """
    from ortools.linear_solver import pywraplp

    solver = pywraplp.Solver.CreateSolver("GLOP")
    variable = solver.NumVar(0.0, solver.infinity(), "x")
    objective = solver.Objective()
    objective.SetMinimization()
    objective.SetCoefficient(variable, -1.0)

    statuses = {
        pywraplp.Solver.OPTIMAL: "OPTIMAL",
        pywraplp.Solver.FEASIBLE: "FEASIBLE",
        pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
    }
    status = statuses.get(solver.Solve(), "INFEASIBLE")
    assert status != "OPTIMAL"
    assert status != "FEASIBLE"
    # 可行点存在，所以状态码 2 不可能是「可行域为空」的证据
    assert 1.0 >= 0.0


# ---------------------------------------------------------------------------
# 7. 极点枚举的适用范围
# ---------------------------------------------------------------------------


def test_vertex_enumeration_rejects_models_with_more_than_two_variables():
    with pytest.raises(ValueError, match="2-variable"):
        enumerate_vertices_2d(build_production_lp(PRODUCTION_BASE))
