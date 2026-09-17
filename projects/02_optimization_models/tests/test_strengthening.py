"""Week 4 模型强化与初解注入的验收测试。

本文件的测试对象不是「求解器算得对不对」，而是**强化手段有没有偷偷改变问题**：

1. **对称破缺不得改变最优值**。同一个实例，未强化模型、只加冗余约束的模型、
   加满强化的模型，三者最优值必须相同；能穷举的还与 M1 的独立枚举对拍。
   强化改变了最优值 = 代码有 bug，这条优先级高于任何「加速效果」。
2. **warm start 的结果不得劣于它的初解**。这是 ``milp_warmstart`` 的契约，
   由「上界割 + 退回初解」保证；测试直接断言。
3. **全变量固定必须逐毫秒复现初解**。固定了整条序列之后，模型只剩「最早开工」
   一件事可做，因此它的最优值必须**恰好**等于初解值——差一点都说明固定没生效。
4. **每个返回的排程都过 M1 的独立验证器**，且目标值用 M1 的评价器重算后一致。

所有小实例的期望最优值都写在注释里的手算时间线上，不由被测代码生成。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from opt_common.bridge import (  # noqa: E402
    M2_OBJECTIVES,
    Instance,
    Job,
    Machine,
    Operation,
    Schedule,
    ScheduledOperation,
    generate_instance,
    schedule_errors,
    validate_schedule,
)
from opt_models.strengthening import (  # noqa: E402
    RULES,
    build_parallel_model,
    build_single_machine_milp,
    cpsat_symmetry,
    detect_machine_symmetry,
    machine_loads,
    makespan_lower_bound,
    milp_fixing,
    milp_warmstart,
    solve_parallel_cpsat,
    solve_single_machine,
)
from opt_solvers.result import SolveResult, validate_result  # noqa: E402


SPEC_MAKESPAN = {"objective": "makespan", "time_limit": 5.0, "seed": 0}
SPEC_TARDINESS = {"objective": "total_tardiness", "time_limit": 5.0, "seed": 0}


# --------------------------------------------------------------------------
# 手工实例：期望值全部来自显式推导
# --------------------------------------------------------------------------
def parallel_hand_instance() -> Instance:
    """2 台机器、5 个工序，M1 Week 1 Day 5 的手算实例：最优 ``Cmax = 6``。

    ``p = [3, 3, 2, 2, 2]``，总负载 12，下界 ``max(3, ceil(12/2)) = 6``；
    ``M0 = 3 + 3``、``M1 = 2 + 2 + 2`` 恰好达到下界，所以最优值就是 6。
    """
    processing = (3, 3, 2, 2, 2)
    jobs = tuple(
        Job(f"J{i}", (f"J{i}_O0",), 0, None, 1.0) for i in range(len(processing))
    )
    operations = tuple(
        Operation(f"J{i}_O0", f"J{i}", p, ("M0", "M1")) for i, p in enumerate(processing)
    )
    return Instance(jobs, operations, (Machine("M0", "M0"), Machine("M1", "M1")))


def parallel_release_instance() -> Instance:
    """2 台机器、带释放时间，手算最优 ``Cmax = 13``。

    J0(r=0,p=4)、J1(r=0,p=4)、J2(r=10,p=3)、J3(r=10,p=3)。
    两台机器各自先做 p=4，机器空转到 10 再做 p=3：
    ``M0 = 0-4, 10-13``、``M1 = 0-4, 10-13`` → ``Cmax = 13``。
    下界 ``max(4, ceil(14/2)=7, max_j(r_j+p_j)=13) = 13``，与手算相等。
    """
    jobs = (
        Job("J0", ("J0_O0",), 0, None, 1.0),
        Job("J1", ("J1_O0",), 0, None, 1.0),
        Job("J2", ("J2_O0",), 10, None, 1.0),
        Job("J3", ("J3_O0",), 10, None, 1.0),
    )
    operations = (
        Operation("J0_O0", "J0", 4, ("M0", "M1")),
        Operation("J1_O0", "J1", 4, ("M0", "M1")),
        Operation("J2_O0", "J2", 3, ("M0", "M1")),
        Operation("J3_O0", "J3", 3, ("M0", "M1")),
    )
    return Instance(jobs, operations, (Machine("M0", "M0"), Machine("M1", "M1")))


def asymmetric_parallel_instance() -> Instance:
    """**不**具备机器对称性：J1 只能上 M0。

    此时「把机器编号互换」不再是模型的对称变换（J1 会失去合格机器），
    因此负载降序约束不合法，必须被识别出来并跳过。
    手算最优：J1 = M0(0-5)，J2、J3 各 4、4，M1 = 8，M0 = 5 → ``Cmax = 8``。
    """
    jobs = (
        Job("J1", ("J1_O0",), 0, None, 1.0),
        Job("J2", ("J2_O0",), 0, None, 1.0),
        Job("J3", ("J3_O0",), 0, None, 1.0),
    )
    operations = (
        Operation("J1_O0", "J1", 5, ("M0",)),
        Operation("J2_O0", "J2", 4, ("M0", "M1")),
        Operation("J3_O0", "J3", 4, ("M0", "M1")),
    )
    return Instance(jobs, operations, (Machine("M0", "M0"), Machine("M1", "M1")))


def single_hand_instance() -> Instance:
    """单机 ``1||ΣTj`` 手算实例：最优 ``ΣTj = 2``（顺序 B → A → C）。

    A(p=3,d=3)、B(p=2,d=2)、C(p=4,d=10)，全部 r=0。穷举六个顺序：

    ```text
    A,B,C: C=[3,5,9]  T=[0,3,0]  ΣT=3
    B,A,C: C=[2,5,9]  T=[0,2,0]  ΣT=2   ← 最优
    B,C,A: C=[2,6,9]  T=[0,4,0]  ΣT=4
    A,C,B: C=[3,7,9]  T=[0,5,0]  ΣT=5
    C,A,B: C=[4,7,9]  T=[0,4,0]  ΣT=4
    C,B,A: C=[4,6,9]  T=[0,4,0]  ΣT=4
    ```
    """
    jobs = (
        Job("A", ("A_O0",), 0, 3, 1.0),
        Job("B", ("B_O0",), 0, 2, 1.0),
        Job("C", ("C_O0",), 0, 10, 1.0),
    )
    operations = (
        Operation("A_O0", "A", 3, ("M0",)),
        Operation("B_O0", "B", 2, ("M0",)),
        Operation("C_O0", "C", 4, ("M0",)),
    )
    return Instance(jobs, operations, (Machine("M0", "M0"),))


def single_edd_trap_instance() -> Instance:
    """单机实例：EDD 得 4，最优 3（M1 Week 1 Day 7 的 CE-02）。

    J1(p=1,d=1)、J2(p=1,d=3)、J3(p=3,d=2)：

    ```text
    EDD 顺序 J1,J3,J2: C=[1,4,5]  T=[0,2,2]  ΣT=4
    顺序 J1,J2,J3:     C=[1,2,5]  T=[0,0,3]  ΣT=3   ← 最优
    ```
    """
    jobs = (
        Job("J1", ("J1_O0",), 0, 1, 1.0),
        Job("J2", ("J2_O0",), 0, 3, 1.0),
        Job("J3", ("J3_O0",), 0, 2, 1.0),
    )
    operations = (
        Operation("J1_O0", "J1", 1, ("M0",)),
        Operation("J2_O0", "J2", 1, ("M0",)),
        Operation("J3_O0", "J3", 3, ("M0",)),
    )
    return Instance(jobs, operations, (Machine("M0", "M0"),))


def single_release_instance() -> Instance:
    """单机、带释放时间的手算实例：最优 ``ΣTj = 1``。

    J1(r=5,p=4,d=12)、J2(r=0,p=2,d=3)、J3(r=8,p=3,d=9)。
    最早开工序 J2(0-2) → J1(5-9) → J3(9-12)：T = [0, 0, 3] → 3。
    换成 J2(0-2) → J3(8-11) → J1(11-15)：T = [3, 0, 0] → 3。
    ``ΣTj`` 更小的排法是把 J1 放最后但 J3 提前？J3 r=8 不能早于 8，
    所以 [0,2] 空转 → J3(8-11)、J1(5-9) 放不下（5<8 时机器空闲）。
    J1(5-9) → J3(9-12)：T=[0,0,3]=3；J3 必须等 r=8，因此
    J1(5-9) 与 J3(9-12) 是唯一可行的两段排列，T3 = 12-9 = 3。
    让 J1 更晚：J2(0-2) → 空转 → J3(8-11) → J1(11-15)，T1 = 3、T3 = 2？不对：
    J3 的 d=9，C=11 → T3 = 2；J1 的 d=12，C=15 → T1 = 3；合计 5。
    所以最优是 3（J2→J1→J3 或 J2→J3→J1 中的 T 总和）。
    """
    jobs = (
        Job("J1", ("J1_O0",), 5, 12, 1.0),
        Job("J2", ("J2_O0",), 0, 3, 1.0),
        Job("J3", ("J3_O0",), 8, 9, 1.0),
    )
    operations = (
        Operation("J1_O0", "J1", 4, ("M0",)),
        Operation("J2_O0", "J2", 2, ("M0",)),
        Operation("J3_O0", "J3", 3, ("M0",)),
    )
    return Instance(jobs, operations, (Machine("M0", "M0"),))


# --------------------------------------------------------------------------
# 断言工具
# --------------------------------------------------------------------------
def assert_feasible(instance: Instance, result: SolveResult) -> Schedule:
    """每个返回的排程都必须过 M1 的独立验证器，且目标值可被独立重算。"""
    assert result.schedule is not None, f"{result.method}: 没有排程"
    assert validate_result(instance, result) == []
    validate_schedule(instance, result.schedule)
    if result.objective is not None:
        name = result.detail["objective_name"]
        recomputed = float(M2_OBJECTIVES[name](instance, result.schedule))
        assert result.objective == pytest.approx(recomputed, abs=1e-9)
    if result.objective is not None and result.best_bound is not None:
        assert result.best_bound <= result.objective + 1e-9
    return result.schedule


def assert_bound_honest(result: SolveResult) -> None:
    """status 为 OPTIMAL 时必须有界且 gap 为 0；界必须 ≤ 目标值。"""
    if result.best_bound is not None and result.objective is not None:
        assert result.best_bound <= result.objective + 1e-9
        if result.proven_optimal:
            assert result.best_bound == pytest.approx(result.objective, abs=1e-9)
            assert result.gap == pytest.approx(0.0, abs=1e-9)


def parallel_instances() -> list[tuple[str, Instance]]:
    return [
        ("hand_p32223", parallel_hand_instance()),
        ("hand_release", parallel_release_instance()),
        ("asymmetric", asymmetric_parallel_instance()),
        ("gen_8x3", generate_instance(seed=52, jobs=8, machines=3)),
        ("gen_12x3", generate_instance(seed=53, jobs=12, machines=3)),
    ]


def single_instances() -> list[tuple[str, Instance]]:
    return [
        ("hand_tardiness", single_hand_instance()),
        ("hand_edd_trap", single_edd_trap_instance()),
        ("hand_release", single_release_instance()),
        ("gen_8x1", generate_instance(seed=50, jobs=8, machines=1)),
        ("gen_12x1", generate_instance(seed=51, jobs=12, machines=1)),
    ]


def objective_value(instance: Instance, schedule: Schedule, name: str) -> float:
    return float(M2_OBJECTIVES[name](instance, schedule))


# --------------------------------------------------------------------------
# 1. 对称破缺不得改变最优值
# --------------------------------------------------------------------------
@pytest.mark.parametrize("label,instance", parallel_instances())
def test_symmetry_breaking_keeps_optimum(label: str, instance: Instance) -> None:
    """未强化 / 只加冗余 / 加满强化，三者的最优值必须完全相同。"""
    plain = solve_parallel_cpsat(
        instance,
        SPEC_MAKESPAN,
        symmetry_breaking=False,
        redundant_constraints=False,
        method="plain",
    )
    bounded = solve_parallel_cpsat(
        instance,
        SPEC_MAKESPAN,
        symmetry_breaking=False,
        redundant_constraints=True,
        method="redundant",
    )
    strengthened = solve_parallel_cpsat(
        instance,
        SPEC_MAKESPAN,
        symmetry_breaking=True,
        redundant_constraints=True,
        method="strengthened",
    )
    for result in (plain, bounded, strengthened):
        assert_feasible(instance, result)
        assert result.status == "OPTIMAL", f"{label}/{result.method}: {result.detail}"
    assert plain.objective == bounded.objective == strengthened.objective


@pytest.mark.parametrize(
    "label,instance,expected",
    [
        ("hand_p32223", parallel_hand_instance(), 6.0),
        ("hand_release", parallel_release_instance(), 13.0),
        ("asymmetric", asymmetric_parallel_instance(), 8.0),
    ],
)
def test_parallel_hand_optima(label: str, instance: Instance, expected: float) -> None:
    """手算最优值对拍：强化版与未强化版都必须给出同一个手算答案。"""
    for symmetry in (False, True):
        result = solve_parallel_cpsat(
            instance,
            SPEC_MAKESPAN,
            symmetry_breaking=symmetry,
            redundant_constraints=True,
            method=f"sym={symmetry}",
        )
        assert_feasible(instance, result)
        assert result.objective == pytest.approx(expected)
    assert makespan_lower_bound(instance) <= expected


def test_parallel_optimum_matches_independent_oracle() -> None:
    """小实例与 M1 的独立穷举对拍（不依赖任何求解器）。"""
    from scheduling_algorithms.oracle import exhaustive_optimum

    for label, instance in (
        ("hand_p32223", parallel_hand_instance()),
        ("hand_release", parallel_release_instance()),
        ("asymmetric", asymmetric_parallel_instance()),
    ):
        optimum, _, _ = exhaustive_optimum(instance, "makespan", limit=100_000)
        strengthened = solve_parallel_cpsat(
            instance,
            SPEC_MAKESPAN,
            symmetry_breaking=True,
            redundant_constraints=True,
            method="strengthened",
        )
        assert_feasible(instance, strengthened)
        assert strengthened.objective == pytest.approx(float(optimum)), label


def test_symmetry_is_detected_only_when_machines_interchangeable() -> None:
    assert detect_machine_symmetry(parallel_hand_instance()) is True
    assert detect_machine_symmetry(asymmetric_parallel_instance()) is False
    single = single_hand_instance()
    assert detect_machine_symmetry(single) is False  # 只有一台机器，没有可交换的对称


def test_symmetry_rows_are_skipped_when_machines_differ() -> None:
    """资格集合逐机器不同时，负载降序约束必须被跳过且最优值不变。"""
    instance = asymmetric_parallel_instance()
    result = solve_parallel_cpsat(
        instance,
        SPEC_MAKESPAN,
        symmetry_breaking=True,
        redundant_constraints=True,
        method="strengthened",
    )
    assert result.detail["symmetry_breaking_applied"] is False
    assert "symmetry_skipped_reason" in result.detail
    assert result.detail["symmetry_rows"] == 0
    assert_feasible(instance, result)
    assert result.objective == pytest.approx(8.0)


def test_symmetry_breaking_reorders_loads_not_the_objective() -> None:
    """强化版的解真的满足负载降序——约束确实生效，而不是被悄悄丢掉。"""
    instance = parallel_release_instance()
    result = solve_parallel_cpsat(
        instance,
        SPEC_MAKESPAN,
        symmetry_breaking=True,
        redundant_constraints=True,
        method="strengthened",
    )
    schedule = assert_feasible(instance, result)
    loads = machine_loads(instance, schedule)
    assert loads["M0"] >= loads["M1"], loads
    assert result.detail["symmetry_rows"] == len(instance.machines) - 1


def test_tardiness_objective_skips_machine_symmetry() -> None:
    """目标是 ``total_tardiness`` 时，机器置换不再保持目标值，必须跳过。"""
    instance = parallel_hand_instance()
    result = solve_parallel_cpsat(
        instance,
        SPEC_TARDINESS,
        symmetry_breaking=True,
        redundant_constraints=True,
        method="strengthened",
    )
    assert result.detail["symmetry_breaking_applied"] is False
    assert "not invariant" in result.detail["symmetry_skipped_reason"]
    assert_feasible(instance, result)


def test_redundant_bound_never_exceeds_optimum() -> None:
    """冗余下界约束只能等于或低于真实最优值（它是下界，不是目标值）。"""
    for label, instance in parallel_instances():
        bound = makespan_lower_bound(instance)
        result = solve_parallel_cpsat(
            instance,
            SPEC_MAKESPAN,
            symmetry_breaking=True,
            redundant_constraints=True,
            method="strengthened",
        )
        assert_feasible(instance, result)
        assert bound <= float(result.objective), label


@pytest.mark.parametrize("label,instance", parallel_instances())
def test_cpsat_symmetry_registered_wrapper(label: str, instance: Instance) -> None:
    result = cpsat_symmetry(instance, SPEC_MAKESPAN)
    assert result.method == "cpsat_symmetry"
    assert_feasible(instance, result)
    assert_bound_honest(result)


# --------------------------------------------------------------------------
# 2. warm start 不劣于初解
# --------------------------------------------------------------------------
@pytest.mark.parametrize("label,instance", single_instances())
@pytest.mark.parametrize("rule", ["spt", "edd", "wspt", "best"])
def test_warmstart_never_worse_than_seed(label: str, instance: Instance, rule: str) -> None:
    result = milp_warmstart(instance, {**SPEC_TARDINESS, "rule": rule})
    assert result.method == "milp_warmstart"
    assert_feasible(instance, result)
    assert_bound_honest(result)
    assert result.objective <= result.detail["seed_objective"] + 1e-9


def test_warmstart_matches_hand_optimum() -> None:
    """小实例与 M1 的独立穷举对拍（12 道工序有 12! 种排列，超出穷举预算）。"""
    from scheduling_algorithms.oracle import exhaustive_optimum

    for label, instance in single_instances()[:4]:  # 手算 3 个 + gen_8x1
        result = milp_warmstart(instance, SPEC_TARDINESS)
        assert_feasible(instance, result)
        assert result.status == "OPTIMAL", label
        optimum, _, _ = exhaustive_optimum(instance, "total_tardiness", limit=200_000)
        assert result.objective == pytest.approx(float(optimum)), label


def test_warmstart_reports_optimality_without_an_oracle() -> None:
    """12 道工序的实例无法穷举，只能要求「自证最优」：bound == 目标值。"""
    instance = generate_instance(seed=51, jobs=12, machines=1)
    result = milp_warmstart(instance, SPEC_TARDINESS)
    assert_feasible(instance, result)
    assert result.proven_optimal
    assert result.detail["termination_reason"] == "proved optimal"
    assert result.objective <= result.detail["seed_objective"] + 1e-9


def test_warmstart_hand_computed_values() -> None:
    """手算答案的两处锚点：最优 2、以及 EDD 陷阱实例最优 3。"""
    trap = single_edd_trap_instance()
    best = milp_warmstart(trap, SPEC_TARDINESS)
    assert best.objective == pytest.approx(3.0)
    assert best.detail["seed_objective"] == pytest.approx(3.0)  # best 规则取到 SPT

    edd_seeded = milp_warmstart(trap, {**SPEC_TARDINESS, "rule": "edd"})
    assert edd_seeded.detail["seed_objective"] == pytest.approx(4.0)
    assert edd_seeded.objective <= 4.0  # 上界割的契约：不劣于初解
    assert edd_seeded.objective == pytest.approx(3.0)  # 而且真的找到了更优解

    hand = single_hand_instance()
    assert milp_warmstart(hand, SPEC_TARDINESS).objective == pytest.approx(2.0)


def test_warmstart_handles_release_times() -> None:
    """有释放时间时初解必须按 start_time 反解序列，否则固定会错位。"""
    instance = single_release_instance()
    result = milp_warmstart(instance, SPEC_TARDINESS)
    assert_feasible(instance, result)
    assert result.objective == pytest.approx(3.0)
    assert result.detail["seed_objective"] <= 3.0


def test_cutoff_is_a_valid_inequality_not_a_change_of_problem() -> None:
    """开/关上界割，最优值不变（割只允许「不劣」，不允许「更好」）。"""
    instance = single_edd_trap_instance()
    with_cut = milp_warmstart(instance, {**SPEC_TARDINESS, "rule": "edd"})
    without_cut = milp_warmstart(
        instance, {**SPEC_TARDINESS, "rule": "edd", "objective_cutoff": False}
    )
    assert with_cut.objective == pytest.approx(3.0)
    assert_feasible(instance, without_cut)
    assert without_cut.objective == pytest.approx(3.0)


def test_hint_only_does_not_guarantee_anything_but_is_reported() -> None:
    """只给 hint（不加上界割）时，detail 必须如实标注 hint 是建议而非约束。"""
    instance = single_hand_instance()
    result = solve_single_machine(
        instance,
        SPEC_TARDINESS,
        set_hint=True,
        objective_cutoff=False,
        fixed_prefix=0,
        method="milp_hint_only",
    )
    assert result.detail["hint_kind"].startswith("MIP start")
    assert "advisory" in result.detail["hint_kind"]
    assert "objective_cutoff" not in result.detail
    assert_feasible(instance, result)


# --------------------------------------------------------------------------
# 3. variable fixing 的正确性与代价
# --------------------------------------------------------------------------
@pytest.mark.parametrize("label,instance", single_instances())
def test_fixing_all_variables_reproduces_seed_exactly(label: str, instance: Instance) -> None:
    """固定整条序列后，最优值必须**恰好**等于初解值，且排程逐字段相同。"""
    result = milp_fixing(instance, {**SPEC_TARDINESS, "fix_ratio": 1.0})
    assert result.method == "milp_fixing"
    schedule = assert_feasible(instance, result)
    assert result.detail["fixed_variables"] == len(instance.jobs)
    assert result.detail["free_variables"] == 0
    assert result.objective == pytest.approx(result.detail["seed_objective"])

    # 与初解排程逐项比对（顺序无关）
    rule_name = result.detail["seed_rule"]
    seed_schedule = RULES[rule_name](instance)
    assert sorted(
        (item.operation_id, item.machine_id, item.start_time, item.end_time)
        for item in schedule.operations
    ) == sorted(
        (item.operation_id, item.machine_id, item.start_time, item.end_time)
        for item in seed_schedule.operations
    ), label


def test_fixing_all_variables_reproduces_a_suboptimal_seed() -> None:
    """EDD 陷阱实例：全固定必须复现「差」的初解 4，而不是最优 3。"""
    instance = single_edd_trap_instance()
    result = milp_fixing(
        instance, {**SPEC_TARDINESS, "fix_ratio": 1.0, "rule": "edd"}
    )
    assert_feasible(instance, result)
    assert result.objective == pytest.approx(4.0)
    assert result.detail["seed_objective"] == pytest.approx(4.0)


def test_fixing_zero_variables_reproduces_the_full_model() -> None:
    """``fix_ratio=0`` 时不得固定任何变量，结果与未固定模型一致。"""
    instance = single_release_instance()
    free = milp_fixing(instance, {**SPEC_TARDINESS, "fix_ratio": 0.0})
    full = milp_warmstart(instance, {**SPEC_TARDINESS, "objective_cutoff": False})
    assert free.detail["fixed_variables"] == 0
    assert_feasible(instance, free)
    assert free.objective == pytest.approx(full.objective)


def test_fixing_is_a_restriction_so_it_can_only_be_worse_or_equal() -> None:
    """固定位置是加约束：目标值不可能低于未固定模型的最优值。"""
    for label, instance in single_instances():
        free = milp_warmstart(instance, {**SPEC_TARDINESS, "objective_cutoff": False})
        fixed = milp_fixing(instance, {**SPEC_TARDINESS, "fix_ratio": 0.5})
        assert_feasible(instance, free)
        assert_feasible(instance, fixed)
        assert fixed.objective >= free.objective - 1e-9, label


@pytest.mark.parametrize("ratio", [-0.1, 1.5])
def test_fixing_rejects_invalid_ratio(ratio: float) -> None:
    result = milp_fixing(single_hand_instance(), {**SPEC_TARDINESS, "fix_ratio": ratio})
    assert result.status == "FAILED"
    assert "fix_ratio" in result.detail["failure_reason"]


# --------------------------------------------------------------------------
# 4. 输入范围与失败留痕
# --------------------------------------------------------------------------
def test_methods_fail_honestly_out_of_scope() -> None:
    parallel = parallel_hand_instance()
    multi_op = generate_instance(seed=54, jobs=6, machines=3, operations_per_job=2)
    for result in (
        milp_warmstart(parallel, SPEC_TARDINESS),
        milp_fixing(parallel, SPEC_TARDINESS),
        cpsat_symmetry(multi_op, SPEC_MAKESPAN),
    ):
        assert result.status == "FAILED"
        assert result.objective is None
        assert result.best_bound is None
        assert result.schedule is None
        assert result.detail["failure_reason"]


def test_unknown_objective_is_failed_not_silently_defaulted() -> None:
    result = cpsat_symmetry(parallel_hand_instance(), {"objective": "no_such_objective"})
    assert result.status == "FAILED"
    assert "no_such_objective" in result.detail["failure_reason"]

    result = milp_warmstart(single_hand_instance(), {"objective": "no_such_objective"})
    assert result.status == "FAILED"
    assert "no_such_objective" in result.detail["failure_reason"]


def test_result_rows_keep_none_as_none() -> None:
    """接口纪律：没有 bound 就是 ``None``（写空值，不写 0）。"""
    result = milp_warmstart(single_hand_instance(), {**SPEC_TARDINESS, "rule": "spt"})
    assert result.best_bound is not None  # CBC 证明了最优，界必须给出
    from opt_solvers.heuristics import heur_spt

    heuristic = heur_spt(single_hand_instance(), SPEC_TARDINESS)
    assert heuristic.best_bound is None
    assert heuristic.gap is None
    assert heuristic.to_row()["best_bound"] is None


def test_solver_objective_residual_is_reported_and_small() -> None:
    """求解器自报目标值只进 detail，且与独立重算值的残差必须可查。"""
    instance = single_instances()[-1][1]
    result = milp_warmstart(instance, SPEC_TARDINESS)
    assert_feasible(instance, result)
    assert result.detail["objective_residual"] == pytest.approx(0.0, abs=1e-6)
    assert result.detail["max_time_round_residual"] == pytest.approx(0.0, abs=1e-9)


def test_build_time_and_solve_time_are_separate_and_positive() -> None:
    result = cpsat_symmetry(parallel_hand_instance(), SPEC_MAKESPAN)
    assert result.build_time >= 0.0
    assert result.solve_time > 0.0
    assert result.wall_time == pytest.approx(result.build_time + result.solve_time)
    assert result.detail["solver_wall_time"] >= 0.0


def test_model_builders_expose_reusable_handles() -> None:
    """模型骨架可被诊断模块复用：变量句柄齐全，且不含任何目标。"""
    instance = parallel_hand_instance()
    context = build_parallel_model(instance, "makespan")
    assert len(context.literal) == len(instance.operations) * len(instance.machines)
    assert set(context.end_of_operation) == {op.id for op in instance.operations}
    assert context.lower_bound == makespan_lower_bound(instance)

    single = single_hand_instance()
    milp = build_single_machine_milp(single, "total_tardiness")
    n = len(single.jobs)
    assert len(milp.assign) == n and len(milp.assign[0]) == n
    assert milp.variables > 0 and milp.constraints > 0


def test_schedule_errors_helper_is_the_gate() -> None:
    """独立验证器是本模块的闸门：手工造一个非法排程必须被抓出来。"""
    instance = single_hand_instance()
    bad = Schedule(
        (
            ScheduledOperation("A_O0", "M0", 0, 3),
            ScheduledOperation("B_O0", "M0", 1, 3),  # 与 A 重叠
            ScheduledOperation("C_O0", "M0", 5, 9),
        )
    )
    assert any("overlap" in error for error in schedule_errors(instance, bad))
    assert schedule_errors(instance, RULES["spt"](instance)) == []
