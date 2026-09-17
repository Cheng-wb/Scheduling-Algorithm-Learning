"""Week 2 验收：三个 MILP formulation 的手算对拍、枚举等价性与不可行路径。

这些测试的共同纪律：

1. **期望值一律手工推导**，不由被测模型生成（例如 3 job 实例的 ``ΣTj = 1``）；
2. **每个返回的排程都过 M1 的独立验证器**（``validate_schedule``），
   求解器自称 ``OPTIMAL`` 不作为可行性证据；
3. **Big-M 的合法性用不等式验**：枚举小实例的全部可行排程，逐对检查
   「被松弛掉的那一侧」的界确实够大 —— 一个 Big-M 只有在从不切掉可行解时
   才叫合法；
4. **枚举等价性**用 M1 的 ``exhaustive_optimum`` 对拍（独立穷举，不依赖求解器）。
"""

from __future__ import annotations

from itertools import permutations

import pytest

from opt_common.bridge import (
    M2_OBJECTIVES,
    Instance,
    Job,
    Machine,
    Operation,
    schedule_errors,
    validate_schedule,
)
from opt_models.milp_scheduling import (
    FORMULATIONS,
    loose_big_m,
    pair_big_m,
    time_horizon,
    trivial_lower_bound,
)
from opt_solvers.registry import get
from opt_solvers.result import STATUSES
from scheduling_algorithms.search import OBJECTIVES as ORACLE_OBJECTIVES


# --------------------------------------------------------------------------
# 测试实例（全部固定、可手算）
# --------------------------------------------------------------------------
def hand3() -> Instance:
    """3 job 单机实例：A(p=3,d=4)、B(p=2,d=2)、C(p=4,r=5,d=10)。

    手算：B(0-2) → A(2-5) → C(5-9)，
    ``ΣTj = 0 + 1 + 0 = 1``，``Cmax = 9``（总加工 9，机器可以不停）。
    """
    return Instance(
        (
            Job("A", ("OA",), 0, 4),
            Job("B", ("OB",), 0, 2),
            Job("C", ("OC",), 5, 10),
        ),
        (
            Operation("OA", "A", 3, ("M0",)),
            Operation("OB", "B", 2, ("M0",)),
            Operation("OC", "C", 4, ("M0",)),
        ),
        (Machine("M0", "M0"),),
    )


def hand3_parallel() -> Instance:
    """2 台机器、3 个 job：p = [4, 3, 5]（同质并行取机全资格）。

    手算：``LB = max(5, ceil(12/2)) = 6``，但 6 无法达到（{5} 与 {4,3} 的差为 2），
    最优是 ``{5}`` 与 ``{4,3}`` 的划分，``Cmax = 7``。
    """
    return Instance(
        tuple(Job(f"J{i}", (f"O{i}",)) for i in range(3)),
        tuple(
            Operation(f"O{i}", f"J{i}", p, ("M0", "M1"))
            for i, p in enumerate([4, 3, 5])
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )


def four_jobs() -> Instance:
    """4 job 单机实例（带释放时间与交期），用于 Big-M 合法性的全枚举检验。"""
    return Instance(
        (
            Job("J0", ("O0",), 0, 6),
            Job("J1", ("O1",), 2, 9),
            Job("J2", ("O2",), 5, 20),
            Job("J3", ("O3",), 1, 12),
        ),
        (
            Operation("O0", "J0", 3, ("M0",)),
            Operation("O1", "J1", 4, ("M0",)),
            Operation("O2", "J2", 2, ("M0",)),
            Operation("O3", "J3", 5, ("M0",)),
        ),
        (Machine("M0", "M0"),),
    )


def collective_infeasible() -> Instance:
    """3 个 r=0、p=4 的 job 放在一台机器上：总加工 12，任何 8 的截止都装不下。"""
    return Instance(
        tuple(Job(f"J{i}", (f"O{i}",), 0, 20) for i in range(3)),
        tuple(Operation(f"O{i}", f"J{i}", 4, ("M0",)) for i in range(3)),
        (Machine("M0", "M0"),),
    )


def two_job_two_ops() -> Instance:
    """单机、2 个 job 各 2 道工序：A(2→3)、B(4→1)，总加工 10。

    手算 ``ΣCj`` 最小 = ``A 先于 B`` 的形状：A1(0-2) A2(2-5) B1(5-9) B2(9-10)，
    ``C_A = 5``、``C_B = 10``，合计 15。
    """
    return Instance(
        (Job("A", ("A1", "A2")), Job("B", ("B1", "B2"))),
        (
            Operation("A1", "A", 2, ("M0",)),
            Operation("A2", "A", 3, ("M0",)),
            Operation("B1", "B", 4, ("M0",)),
            Operation("B2", "B", 1, ("M0",)),
        ),
        (Machine("M0", "M0"),),
    )


def spec(objective: str = "makespan", **extra) -> dict:
    return {"objective": objective, "time_limit": 10.0, "seed": 0, **extra}


def all_methods(instance: Instance, cfg: dict) -> dict[str, object]:
    return {name: get(name)(instance, cfg) for name in FORMULATIONS}


# --------------------------------------------------------------------------
# 1. 手算最优值
# --------------------------------------------------------------------------
def test_three_job_hand_computed_tardiness() -> None:
    """3 job 实例的 ΣTj 最优是手算值 1，三个 formulation 都必须给出来。"""
    instance = hand3()
    for name, result in all_methods(instance, spec("total_tardiness")).items():
        assert result.status == "OPTIMAL", (name, result.status)
        assert result.objective == 1.0, name
        validate_schedule(instance, result.schedule)


def test_three_job_hand_computed_makespan() -> None:
    """同一实例的 Cmax 最优是 9（总加工 9，机器不必空转）。"""
    instance = hand3()
    for name, result in all_methods(instance, spec("makespan")).items():
        assert result.status == "OPTIMAL", (name, result.status)
        assert result.objective == 9.0, name
        validate_schedule(instance, result.schedule)


def test_parallel_hand_computed_makespan() -> None:
    """2 机 3 job：最优 Cmax = 7，且严格大于平凡下界 6。

    并行实例只有 ``milp_alt`` 能接（sequence 模型只定义单机），
    所以这里单独调它 —— 另外两个模型在并行实例上的 ``FAILED`` 另有测试。
    """
    instance = hand3_parallel()
    result = get("milp_alt")(instance, spec("makespan"))
    assert result.status == "OPTIMAL", result.detail
    assert result.objective == 7.0
    validate_schedule(instance, result.schedule)
    assert trivial_lower_bound(instance, "makespan") == 6.0


def test_precedence_hand_computed_completion_time() -> None:
    """2 job × 2 工序的单机实例：ΣCj 最优 = 15（手算的 A 先 B 后形状）。"""
    instance = two_job_two_ops()
    result = get("milp_alt")(instance, spec("total_completion_time"))
    assert result.status == "OPTIMAL"
    assert result.objective == 15.0
    validate_schedule(instance, result.schedule)  # 独立验证器会检查 precedence


# --------------------------------------------------------------------------
# 2. 三个 formulation 互相一致
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "objective", sorted(M2_OBJECTIVES)
)
def test_three_formulations_agree(objective: str) -> None:
    """同一实例、同一目标：三个 formulation 的目标值必须一致（都要求最优）。"""
    instance = hand3()
    values = {
        name: result.objective
        for name, result in all_methods(instance, spec(objective)).items()
    }
    assert len(set(values.values())) == 1, values
    assert all(result.status == "OPTIMAL" for result in all_methods(instance, spec(objective)).values())


def test_loose_and_tight_agree_on_a_larger_instance() -> None:
    """8 job 单机实例上，只差 Big-M 取法的两个模型给出同一个最优值。"""
    from opt_common.bridge import generate_instance

    instance = generate_instance(seed=50, jobs=8, machines=1)
    cfg = spec("total_tardiness")
    tight = get("milp_tight")(instance, cfg)
    loose = get("milp_loose")(instance, cfg)
    assert tight.status == loose.status == "OPTIMAL"
    assert tight.objective == loose.objective
    assert tight.detail["big_m_max"] < loose.detail["big_m_max"]  # 确实换过 M


# --------------------------------------------------------------------------
# 3. 枚举等价性（Day 5 的最强证据）
# --------------------------------------------------------------------------
@pytest.mark.parametrize("objective", sorted(ORACLE_OBJECTIVES))
def test_enumeration_equivalence_single_machine(objective: str) -> None:
    """与 M1 的独立穷举 ``exhaustive_optimum`` 对拍：小实例上三方最优值必须相同。"""
    from scheduling_algorithms.oracle import exhaustive_optimum

    instance = hand3()
    expected, _, _ = exhaustive_optimum(instance, objective, limit=100_000)
    for name, result in all_methods(instance, spec(objective)).items():
        assert result.objective == pytest.approx(expected), (name, result.objective, expected)


@pytest.mark.parametrize("objective", sorted(ORACLE_OBJECTIVES))
def test_enumeration_equivalence_parallel(objective: str) -> None:
    """并行机上同样与穷举对拍：``milp_alt`` 的选机决策必须落到真最优。"""
    from scheduling_algorithms.oracle import exhaustive_optimum

    instance = hand3_parallel()
    expected, _, _ = exhaustive_optimum(instance, objective, limit=100_000)
    result = get("milp_alt")(instance, spec(objective))
    assert result.objective == pytest.approx(expected), (result.objective, expected)


def test_enumeration_equivalence_four_jobs_with_release_dates() -> None:
    """4 job 带释放时间：``milp_tight`` 与穷举在 ΣTj 上一致（4! = 24 次枚举）。"""
    from scheduling_algorithms.oracle import exhaustive_optimum

    instance = four_jobs()
    expected, _, count = exhaustive_optimum(instance, "total_tardiness", limit=100_000)
    assert count == 24
    result = get("milp_tight")(instance, spec("total_tardiness"))
    assert result.objective == pytest.approx(expected)
    validate_schedule(instance, result.schedule)


# --------------------------------------------------------------------------
# 4. Big-M 的合法性（不是「紧不紧」，而是「会不会切掉解」）
# --------------------------------------------------------------------------
def test_big_m_never_cuts_off_feasible_schedules() -> None:
    """逐个枚举可行排程，验证两种 Big-M 都满足「被松弛的那一侧」的不等式。

    对每一对 ``(j, k)``，当 j 排在 k 之前（``x_jk = 1``）时，第二条约束
    ``s_j >= s_k + p_k - M_kj * x_jk`` 退化成需要 ``M_kj >= C_k - s_j``；
    只要该式对**所有**可行排程成立，M 就不会切掉可行解。
    """
    instance = four_jobs()
    horizon = time_horizon(instance)
    tight = pair_big_m(instance, horizon)
    loose = loose_big_m(instance, horizon)
    op_by_job = {job.id: job.operation_ids[0] for job in instance.jobs}
    op_by_id = {op.id: op for op in instance.operations}
    jobs = {job.id: job for job in instance.jobs}

    checked = 0
    for order in permutations(job.id for job in instance.jobs):
        clock = 0
        starts: dict[str, int] = {}
        ends: dict[str, int] = {}
        for job_id in order:
            op = op_by_id[op_by_job[job_id]]
            start = max(clock, jobs[job_id].release_time)
            starts[job_id] = start
            ends[job_id] = start + op.processing_time
            clock = ends[job_id]
        for index, first in enumerate(order):
            for second in order[index + 1 :]:
                # first 先于 second ⇒ x = 1 ⇒ 第二条约束需要 M_second,first 足够大。
                required = ends[second] - starts[first]
                assert tight[(second, first)] >= required
                assert loose >= required
                checked += 1
    assert checked == 24 * 6  # 24 个排程，每个排程 6 对


def test_big_m_matches_the_proved_time_bounds() -> None:
    """``M_jk = H - r_k`` 的逐对界必须落在 ``[max p, H]`` 内，且 loose 大于它。"""
    instance = four_jobs()
    horizon = time_horizon(instance)
    tight = pair_big_m(instance, horizon)
    release = {job.id: job.release_time for job in instance.jobs}
    for (first, second), value in tight.items():
        assert value == horizon - release[second]
    assert min(tight.values()) > 0
    assert loose_big_m(instance, horizon) >= max(tight.values())


# --------------------------------------------------------------------------
# 5. LP relaxation 与下界
# --------------------------------------------------------------------------
@pytest.mark.parametrize("method", FORMULATIONS)
@pytest.mark.parametrize("objective", ["total_tardiness", "makespan", "total_completion_time"])
def test_root_lp_bound_not_above_integer_optimum(method: str, objective: str) -> None:
    """LP relaxation 是有效下界：root bound ≤ 整数最优值。"""
    instance = hand3()
    lp = get(method)(instance, spec(objective, root_lp=True))
    mip = get(method)(instance, spec(objective))
    assert lp.best_bound is not None
    assert mip.objective is not None
    assert lp.best_bound <= mip.objective + 1e-6


def test_root_lp_reports_bound_without_a_schedule() -> None:
    """只解 LP 时没有可行排程可交：``objective`` 必须留空，下界不许冒充可行解。"""
    from opt_common.bridge import generate_instance

    instance = generate_instance(seed=50, jobs=8, machines=1)
    result = get("milp_tight")(instance, spec("total_tardiness", root_lp=True))
    assert result.status == "UNKNOWN"
    assert result.objective is None
    assert result.schedule is None
    assert result.best_bound is not None


def test_time_indexed_relaxation_is_strictly_stronger_here() -> None:
    """实测发现：time-indexed 的 root bound 严格高于 sequence 模型（同一实例）。"""
    from opt_common.bridge import generate_instance

    instance = generate_instance(seed=50, jobs=8, machines=1)
    cfg = spec("total_tardiness")
    sequence = get("milp_tight")(instance, {**cfg, "root_lp": True})
    alternative = get("milp_alt")(instance, {**cfg, "root_lp": True})
    assert alternative.best_bound > sequence.best_bound + 1.0


# --------------------------------------------------------------------------
# 6. 不可行路径
# --------------------------------------------------------------------------
@pytest.mark.parametrize("method", FORMULATIONS)
def test_infeasible_deadline_returns_infeasible(method: str) -> None:
    """总加工 12 却要求 8 前完工：每个 job 单独可行、整体不可行 → INFEASIBLE。"""
    instance = collective_infeasible()
    infeasible = get(method)(instance, spec("makespan", deadline=8))
    assert infeasible.status == "INFEASIBLE"
    assert infeasible.objective is None and infeasible.schedule is None
    assert infeasible.best_bound is None  # 不可行时没有可比下界
    # 同一个实例把截止放宽到 12 就可行，说明上面不是「模型坏了」而是「真的不可行」。
    feasible = get(method)(instance, spec("makespan", deadline=12))
    assert feasible.status == "OPTIMAL"
    assert feasible.objective == 12.0
    validate_schedule(instance, feasible.schedule)


@pytest.mark.parametrize("method", ["milp_tight", "milp_loose", "milp_alt"])
def test_deadline_below_processing_time_is_certified_at_build_time(method: str) -> None:
    """``r + p > deadline`` 时模型在建模阶段就给出不可行证明，不必等求解器。"""
    instance = hand3()  # C: r=5, p=4
    result = get(method)(instance, spec("makespan", deadline=5))
    assert result.status == "INFEASIBLE"
    assert "infeasibility_certificate" in result.detail
    assert result.solve_time == 0.0  # 没有调用求解器


def test_sequence_model_declines_parallel_instances() -> None:
    """``milp_tight`` / ``milp_loose`` 只支持单机：并行实例如实记 FAILED 并说明原因。"""
    instance = hand3_parallel()
    for name in ("milp_tight", "milp_loose"):
        result = get(name)(instance, spec("makespan"))
        assert result.status == "FAILED"
        assert "单机" in result.detail["failure_reason"]


def test_unknown_objective_is_failed() -> None:
    instance = hand3()
    for name in FORMULATIONS:
        result = get(name)(instance, spec("no_such_objective"))
        assert result.status == "FAILED"
        assert "unknown objective" in result.detail["failure_reason"]


# --------------------------------------------------------------------------
# 7. 统一结果接口的纪律
# --------------------------------------------------------------------------
def test_statuses_and_timings_are_well_formed() -> None:
    """状态词表合法、建模与求解分开计时、bound 与 schedule 的伴随关系成立。"""
    instance = hand3()
    for name, result in all_methods(instance, spec("total_tardiness")).items():
        assert result.status in STATUSES
        assert result.build_time >= 0.0 and result.solve_time >= 0.0
        assert result.objective == pytest.approx(
            float(M2_OBJECTIVES["total_tardiness"](instance, result.schedule))
        )
        assert result.best_bound is not None and result.gap == 0.0
        assert result.detail["iterations_kind"] == "branch_and_bound"


def test_every_returned_schedule_passes_independent_validator() -> None:
    """跨实例 × 跨目标 × 三个模型的全体返回排程，逐个过 M1 的独立验证器。"""
    instances = {
        "hand3": hand3(),
        "hand3_parallel": hand3_parallel(),
        "four_jobs": four_jobs(),
        "two_ops": two_job_two_ops(),
    }
    checked = 0
    for name, instance in instances.items():
        for objective in sorted(M2_OBJECTIVES):
            cfg = spec(objective)
            for method in FORMULATIONS:
                result = get(method)(instance, cfg)
                if result.schedule is None:
                    continue
                assert schedule_errors(instance, result.schedule) == [], (name, method, objective)
                validate_schedule(instance, result.schedule)
                checked += 1
    assert checked >= len(instances) * len(M2_OBJECTIVES) * 2


def test_solver_objective_matches_recomputed_objective() -> None:
    """求解器自己的目标值与 M1 重算的目标值一致（模型编码没错位）。"""
    instance = four_jobs()
    for method in FORMULATIONS:
        result = get(method)(instance, spec("total_tardiness"))
        assert result.detail["solver_objective"] == pytest.approx(result.objective)
