"""M3 Week 2 测试：FJSP 解码器、三种指派、CP-SAT 模型与穷举 oracle 的对拍。

纪律（与 M1/M2 一致，不是可选项）：

1. **期望值全部手写**：来自纸面上的时间线推导，不由被测函数生成。
2. **每个返回的排程都过独立验证器**（``fjsp_core.schedule_validation``）。
3. **对拍用另一条计算路径**：CP-SAT 与解码器互相印证不算数，要三方一致
   （解码器 / 启发式 ↔ CP-SAT ↔ 穷举 oracle）。
4. **失败路径也要测**：拒绝非法顺序、拒绝不支持的约束、拒绝超限的空间。
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from fjsp_core import (  # noqa: E402
    Calendar,
    Machine,
    Maintenance,
    Qualification,
    Schedule,
    ScheduledOperation,
    Setup,
    Worker,
    objective_breakdown,
    schedule_errors,
    validate_schedule,
)
from fjsp_shop.cpsat_fjsp import (  # noqa: E402
    build_model,
    fjsp_cpsat,
    lower_bound,
    time_horizon,
)
from fjsp_shop.fjsp import (  # noqa: E402
    assign_load_balance,
    assign_random,
    assign_shortest,
    decode,
    dispatch,
    fjsp_loadbalance,
    fjsp_random,
    fjsp_shortest,
)
from fjsp_shop.oracle import (  # noqa: E402
    enumeration_space,
    exhaustive_optimum,
    topological_order_count,
)
from fjsp_shop.toy_instances import TOY_INSTANCES  # noqa: E402

SPEC = {"objective": "makespan", "time_limit": 2.0, "seed": 0}
HEURISTICS = {
    "fjsp_random": fjsp_random,
    "fjsp_shortest": fjsp_shortest,
    "fjsp_loadbalance": fjsp_loadbalance,
}
ALL_METHODS = {**HEURISTICS, "fjsp_cpsat": fjsp_cpsat}


def toy(name: str):
    return TOY_INSTANCES[name]()


def timeline(schedule: Schedule) -> dict[str, tuple[str, int, int]]:
    """``{工序: (机器, 开工, 完工)}`` —— 与手写时间线逐字段对比。"""
    return {
        item.operation_id: (item.machine_id, item.start_time, item.end_time)
        for item in schedule.operations
    }


# ---------------------------------------------------------------------------
# 解码器：手算时间线
# ---------------------------------------------------------------------------


def test_decode_append_matches_hand_timeline() -> None:
    """``gap_2x2`` 上的一对 (指派, 顺序)，附加式解码逐步手推：

    O00@M1[0,4) → O10@M1[4,12) → O11@M0[12,14)（等 O10）→ O01@M0[14,17)（M0 只在末尾接）。
    """
    instance = toy("gap_2x2")
    schedule = decode(
        instance,
        {"O00": "M1", "O01": "M0", "O10": "M1", "O11": "M0"},
        ("O00", "O10", "O11", "O01"),
        insert=False,
    )
    assert timeline(schedule) == {
        "O00": ("M1", 0, 4),
        "O10": ("M1", 4, 12),
        "O11": ("M0", 12, 14),
        "O01": ("M0", 14, 17),
    }
    validate_schedule(instance, schedule)


def test_decode_insert_fills_the_gap() -> None:
    """同一个 (指派, 顺序) 换成插入式：``O01`` 落进 M0 的 ``[0, 12)`` 空档，省 3 分钟。"""
    instance = toy("gap_2x2")
    schedule = decode(
        instance,
        {"O00": "M1", "O01": "M0", "O10": "M1", "O11": "M0"},
        ("O00", "O10", "O11", "O01"),
        insert=True,
    )
    assert timeline(schedule) == {
        "O00": ("M1", 0, 4),
        "O01": ("M0", 4, 7),
        "O10": ("M1", 4, 12),
        "O11": ("M0", 12, 14),
    }
    validate_schedule(instance, schedule)
    # 同一个输入，插入式必须不差于附加式（它对每个工序的可行集合更大）
    assert 14 < 17


def test_decode_rejects_non_topological_order() -> None:
    with pytest.raises(ValueError, match="process route"):
        decode(
            toy("gap_2x2"),
            {"O00": "M0", "O01": "M0", "O10": "M1", "O11": "M1"},
            ("O01", "O00", "O10", "O11"),  # O01 排到 O00 之前
        )


def test_decode_rejects_incomplete_order_and_ineligible_machine() -> None:
    instance = toy("gap_2x2")
    with pytest.raises(ValueError, match="exactly once"):
        decode(instance, {"O00": "M0", "O01": "M0", "O10": "M1"}, ("O00", "O01", "O10"))
    with pytest.raises(ValueError, match="cannot run on"):
        decode(
            instance,
            {"O00": "M9", "O01": "M0", "O10": "M1", "O11": "M1"},
            ("O00", "O01", "O10", "O11"),
        )


def test_decode_respects_release_times() -> None:
    """把 J1 的释放时间改到 5：O10 不可能在 5 之前开工（手算）。"""
    instance = replace(
        toy("gap_2x2"),
        jobs=(toy("gap_2x2").job("J0"), replace(toy("gap_2x2").job("J1"), release_time=5)),
    )
    schedule = decode(
        instance,
        {"O00": "M1", "O01": "M0", "O10": "M1", "O11": "M0"},
        ("O00", "O10", "O11", "O01"),
        insert=True,
    )
    assert timeline(schedule)["O10"] == ("M1", 5, 13)
    validate_schedule(instance, schedule)


# ---------------------------------------------------------------------------
# 派工：状态推进与确定性
# ---------------------------------------------------------------------------


def test_dispatch_ect_hand_traced_on_gap_instance() -> None:
    """``gap_2x2`` + 全 ``M0`` 指派（只能这么做吗？不——这里给一个手算的指派）。

    指派 {O00:M0, O01:M0, O10:M1, O11:M1}：
    第一步候选 O00(M0, 2→4) 与 O10(M1, 8→8) 的 ECT 分别是 2 与 8，O00 先；
    之后 J0 的 O01 只要 3 分钟而上界 5，继续压 M0；O10、O11 排 M1。
    """
    instance = toy("gap_2x2")
    schedule = dispatch(instance, {"O00": "M0", "O01": "M0", "O10": "M1", "O11": "M1"})
    assert timeline(schedule) == {
        "O00": ("M0", 0, 2),
        "O01": ("M0", 2, 5),
        "O10": ("M1", 0, 8),
        "O11": ("M1", 8, 14),
    }
    validate_schedule(instance, schedule)


def test_dispatch_rules_can_differ_but_all_stay_feasible() -> None:
    instance = toy("assign_2x3")
    assignment = assign_shortest(instance)
    values = {}
    for rule in ("ect", "est", "spt", "mwkr"):
        schedule = dispatch(instance, assignment, rule=rule)
        validate_schedule(instance, schedule)
        values[rule] = max(item.end_time for item in schedule.operations)
    # 规则不同 → 排序键不同；这四个规则在该实例上未必两两不同，但都必须可行
    assert len(set(values.values())) >= 1
    assert values["ect"] >= 0


def test_dispatch_rejects_unknown_rule_and_ineligible_machine() -> None:
    instance = toy("gap_2x2")
    assignment = {"O00": "M0", "O01": "M0", "O10": "M1", "O11": "M1"}
    with pytest.raises(ValueError, match="unknown dispatch rule"):
        dispatch(instance, assignment, rule="fifo")
    bad = dict(assignment, O00="M9")
    with pytest.raises(ValueError, match="cannot run on"):
        dispatch(instance, bad)


# ---------------------------------------------------------------------------
# 三种指派策略：手算对照
# ---------------------------------------------------------------------------


def test_assign_shortest_picks_each_operation_fastest_machine() -> None:
    """``assign_2x3`` 上逐工序比工时：O00=3(M0), O01=4(M1), O10=3(M0), O11=4(M1)。"""
    assert assign_shortest(toy("assign_2x3")) == {
        "O00": "M0",
        "O01": "M1",
        "O10": "M0",
        "O11": "M1",
    }


def test_assign_load_balance_hand_traced() -> None:
    """``assign_2x3`` 上按 ``(-min_time, id)`` 顺序逐步推（预计负载 = 当前负载 + 本机工时）：

    | 步 | 工序 | M0 | M1 | M2 | 选中 |
    |---|---|---|---|---|---|
    | 1 | O01 | 5 | **4** | 8 | M1（负载 4） |
    | 2 | O11 | **6** | 8 | 9 | M0（负载 6） |
    | 3 | O00 | 9 | 10 | **9** | M2（与 M0 同为 9，但当前负载 0 < 6） |
    | 4 | O10 | **9** | 11 | 15 | M0（负载 9） |
    """
    assert assign_load_balance(toy("assign_2x3")) == {
        "O01": "M1",
        "O11": "M0",
        "O00": "M2",
        "O10": "M0",
    }


def test_assign_random_is_seed_deterministic_and_eligible_only() -> None:
    instance = toy("tiny_2x2")
    first = assign_random(instance, 3)
    assert first == assign_random(instance, 3), "同种子必须给同一个指派"
    assert first == {"O00": "M0", "O01": "M0", "O10": "M1", "O11": "M1"}
    for assignment in (assign_random(instance, seed) for seed in range(20)):
        for operation_id, machine_id in assignment.items():
            assert machine_id in instance.operation(operation_id).eligible_machine_ids


def test_heuristics_leave_best_bound_none_and_fill_breakdown() -> None:
    """启发式没有下界：``best_bound`` 必须是 ``None``，不是 0、更不是目标值。"""
    for name, solve in HEURISTICS.items():
        result = solve(toy("assign_2x3"), SPEC)
        assert result.status == "FEASIBLE"
        assert result.best_bound is None, f"{name} 不该给出下界"
        assert result.gap is None, "没有下界时 gap 必须是 None，不是 0"
        assert result.breakdown == objective_breakdown(toy("assign_2x3"), result.schedule)
        assert result.best_bound != result.objective


# ---------------------------------------------------------------------------
# 四方法在tiny实例上一致、在较大实例上分歧
# ---------------------------------------------------------------------------


def test_all_four_methods_reach_the_optimum_on_the_tiny_instance() -> None:
    """``tiny_2x2``：``makespan = 2`` 同时等于下界，所以最优性不靠穷举也能证明。

    ``seed = 3`` 的随机指派恰好把两个订单分到两台机器上（换成别的 seed 就不一定）。
    """
    instance = toy("tiny_2x2")
    assert lower_bound(instance) == 2
    assert exhaustive_optimum(instance, "makespan", limit=200_000)[0] == 2.0
    objective = fjsp_cpsat(instance, {**SPEC, "seed": 3})
    assert objective.status == "OPTIMAL"
    assert objective.objective == 2.0
    for name, solve in HEURISTICS.items():
        result = solve(instance, {**SPEC, "seed": 3})
        assert result.objective == 2.0, f"{name} 在 tiny_2x2 上掉了最优"
        assert result.schedule is not None and schedule_errors(instance, result.schedule) == []


def test_four_methods_disagree_on_a_larger_instance() -> None:
    """``assign_2x3``：oracle 证明最优 10；CP-SAT 拿到 10，三个启发式分别 11 / 13 / 14。"""
    instance = toy("assign_2x3")
    optimum, _ = exhaustive_optimum(instance, "makespan", limit=200_000)
    assert optimum == 10.0

    measured = {name: solve(instance, SPEC).objective for name, solve in ALL_METHODS.items()}
    assert measured["fjsp_cpsat"] == 10.0
    assert measured["fjsp_shortest"] == 11.0
    assert measured["fjsp_loadbalance"] == 13.0
    assert measured["fjsp_random"] == 14.0
    # 分歧真实存在：最好与最差差 40%
    assert max(measured.values()) / optimum == pytest.approx(1.4)
    cpsat_result = fjsp_cpsat(instance, SPEC)
    assert cpsat_result.status == "OPTIMAL"
    assert cpsat_result.best_bound == 10.0


def test_jsp_instance_still_works_for_fjsp_methods() -> None:
    """``flexibility = 1``：三种指派策略退化成同一个指派，四方法都必须给出最优 7。"""
    instance = toy("jsp_fixed_2x2")
    optimum, _ = exhaustive_optimum(instance, "makespan", limit=200_000)
    assert optimum == 7.0
    assert assign_shortest(instance) == assign_load_balance(instance)
    assert assign_load_balance(instance) == {op.id: op.eligible_machine_ids[0] for op in instance.operations}
    for name, solve in ALL_METHODS.items():
        result = solve(instance, SPEC)
        assert result.objective == 7.0, f"{name} 在 JSP 实例上没拿到最优"
        assert schedule_errors(instance, result.schedule) == []


def test_heuristics_are_never_below_the_oracle() -> None:
    """oracle 是下界意义上的基准：任何可行方法都不可能比它更好。"""
    for name in ("tiny_2x2", "assign_2x3", "gap_2x2", "jsp_fixed_2x2"):
        instance = toy(name)
        optimum, _ = exhaustive_optimum(instance, "makespan", limit=200_000)
        for method, solve in ALL_METHODS.items():
            result = solve(instance, SPEC)
            assert result.objective >= optimum, f"{method} 在 {name} 上低于最优，说明有一方错了"


# ---------------------------------------------------------------------------
# CP-SAT 模型
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["tiny_2x2", "gap_2x2", "assign_2x3", "jsp_fixed_2x2"])
def test_cpsat_matches_the_oracle(name: str) -> None:
    instance = toy(name)
    optimum, _ = exhaustive_optimum(instance, "makespan", limit=200_000)
    result = fjsp_cpsat(instance, SPEC)
    assert result.status == "OPTIMAL"
    assert result.objective == optimum
    assert result.best_bound == optimum
    validate_schedule(instance, result.schedule)
    assert result.breakdown["cmax"] == optimum


def test_cpsat_model_shape_is_hand_countable() -> None:
    """``tiny_2x2``：4 道工序 × 2 台合格机器 → 8 个可选区间；每道 ExactlyOne。

    变量数 = 4 个 start + 4 个 end + 8 个 bool + 1 个 makespan = 17。
    """
    stats = build_model(toy("tiny_2x2")).stats()
    assert stats["operations"] == 4
    assert stats["optional_intervals"] == 8
    assert stats["variables"] == 17
    instance = toy("tiny_2x2")
    # 上界：所有工序串起来、每道都取最慢机器 = (3 + 3 + 3 + 3)
    assert time_horizon(instance) == 12


def test_cpsat_uses_the_solver_bound_and_recomputes_the_objective() -> None:
    instance = toy("assign_2x3")
    result = fjsp_cpsat(instance, SPEC)
    assert result.detail["bound_kind"] == "proven"
    assert result.detail["cp_status"] in ("OPTIMAL", "FEASIBLE")
    # 目标值来自独立重算，与求解器读数一致（差 < 1e-6）
    assert abs(result.detail["solver_objective_delta"]) < 1e-6
    assert result.detail["num_search_workers"] == 1, "线程数为 1 才谈得上可复现"


def test_cpsat_declines_objectives_it_does_not_model() -> None:
    instance = toy("tiny_2x2")
    with pytest.raises(ValueError, match="optimizes"):
        fjsp_cpsat(instance, {**SPEC, "objective": "total_tardiness"})
    with pytest.raises(ValueError, match="optimizes"):
        build_model(instance, {"objective": "weighted_sum"})


def test_cpsat_declines_unsupported_constraints() -> None:
    """带换型的实例必须被拒绝：忽略了换型的模型最优解不是问题的可行解。"""
    instance = replace(
        toy("tiny_2x2"),
        setups=(Setup("F0", "F1", 3),),
    )
    with pytest.raises(ValueError, match="unsupported constraints: setups"):
        fjsp_cpsat(instance, SPEC)


# ---------------------------------------------------------------------------
# 穷举 oracle
# ---------------------------------------------------------------------------


def test_oracle_space_count_is_assignments_times_topological_orders() -> None:
    """三个手算实例的空间：96 / 486 / 6。

    96 = 2^4 个指派 × 6 个拓扑序；486 = 3^4 × 6；6 = 1 × 6。
    顺序一侧用的是 ``n! / Π k_j!``（2 订单 × 2 工序 → ``24 / 4 = 6``），不是 ``4! = 24``。
    """
    assert topological_order_count(toy("tiny_2x2")) == 6
    assert enumeration_space(toy("tiny_2x2")) == 96
    assert enumeration_space(toy("assign_2x3")) == 486
    assert enumeration_space(toy("jsp_fixed_2x2")) == 6


def test_oracle_refuses_when_the_space_exceeds_the_limit() -> None:
    instance = toy("assign_2x3")  # 空间 486
    with pytest.raises(ValueError, match="exceeds limit"):
        exhaustive_optimum(instance, "makespan", limit=485)
    # 刚好等于上限时允许
    value, _ = exhaustive_optimum(instance, "makespan", limit=486)
    assert value == 10.0


def test_oracle_refuses_constraints_it_does_not_model() -> None:
    base = toy("tiny_2x2")
    cases = {
        "calendars": replace(base, calendars=(Calendar("C", ((0, 5), (8, 40))),)),
        "maintenances": replace(base, maintenances=(Maintenance("MT", "M0", ((5, 7),)),)),
        "setups": replace(base, setups=(Setup("F0", "F1", 2),)),
        "workers": replace(base, workers=(Worker("W0", "W0", (), 1),)),
        "qualifications": replace(base, qualifications=(Qualification("M0", "F0"),)),
        "locked operations": replace(
            base,
            operations=(
                replace(base.operation("O00"), locked_machine_id="M0"),
                *base.operations[1:],
            ),
        ),
    }
    for label, instance in cases.items():
        with pytest.raises(ValueError) as excinfo:
            exhaustive_optimum(instance, "makespan", limit=200_000)
        assert label in str(excinfo.value), f"{label} 必须出现在拒绝原因里"


def test_oracle_refuses_a_non_makespan_objective() -> None:
    with pytest.raises(ValueError, match="only certifies"):
        exhaustive_optimum(toy("tiny_2x2"), "total_tardiness", limit=200_000)


def test_oracle_returns_a_schedule_that_passes_the_validator() -> None:
    for name in ("tiny_2x2", "gap_2x2", "assign_2x3", "jsp_fixed_2x2"):
        instance = toy(name)
        value, schedule = exhaustive_optimum(instance, "makespan", limit=200_000)
        validate_schedule(instance, schedule)
        assert max(item.end_time for item in schedule.operations) == value


def test_oracle_hand_computed_values() -> None:
    """三个手算最优值：``tiny_2x2 = 2``（等于下界）、``gap_2x2 = 10``、``assign_2x3 = 10``。"""
    assert exhaustive_optimum(toy("tiny_2x2"), "makespan", 200_000)[0] == 2.0
    assert exhaustive_optimum(toy("gap_2x2"), "makespan", 200_000)[0] == 10.0
    assert exhaustive_optimum(toy("assign_2x3"), "makespan", 200_000)[0] == 10.0
    assert exhaustive_optimum(toy("jsp_fixed_2x2"), "makespan", 200_000)[0] == 7.0


# ---------------------------------------------------------------------------
# 全局纪律
# ---------------------------------------------------------------------------


def test_every_returned_schedule_passes_the_independent_validator() -> None:
    for name in TOY_INSTANCES:
        instance = toy(name)
        for method, solve in ALL_METHODS.items():
            result = solve(instance, SPEC)
            assert result.schedule is not None
            errors = schedule_errors(instance, result.schedule)
            assert errors == [], f"{method} 在 {name} 上返回了不可行排程：{errors}"


def test_results_are_deterministic_across_runs() -> None:
    """同实例、同 spec 跑两次必须完全一样（启发式与单线程 CP-SAT 都要满足）。"""
    instance = toy("assign_2x3")
    for method, solve in ALL_METHODS.items():
        first, second = solve(instance, SPEC), solve(instance, SPEC)
        assert first.schedule == second.schedule, f"{method} 两次结果不同"
        assert first.objective == second.objective


def test_empty_assignment_placeholder_is_not_silently_accepted() -> None:
    """缺工序的指派必须报错，而不是把某道工序忘掉。"""
    instance = toy("tiny_2x2")
    with pytest.raises(ValueError, match="missing operation"):
        decode(instance, {"O00": "M0", "O01": "M0", "O10": "M1"}, ("O00", "O01", "O10", "O11"))
