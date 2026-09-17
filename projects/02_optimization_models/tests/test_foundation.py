"""M2 共享地基的测试：M1 桥接、统一结果接口、方法注册表、批次辅助函数。

这些是**跨周**的约定。周模块各自的模型测试在 ``test_lp_models.py`` /
``test_milp_scheduling.py`` / ``test_cpsat_models.py`` / ``test_strengthening.py``，
本文件只守住「四周都必须遵守」的那几条纪律。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from opt_common.bridge import (  # noqa: E402
    M1_ROOT,
    M2_OBJECTIVES,
    Instance,
    Schedule,
    ScheduledOperation,
    generate_instance,
    makespan,
    spt,
    validate_schedule,
)
from opt_experiments.benchmark import source_hash, write_csv, write_json  # noqa: E402
from opt_solvers import heuristics  # noqa: F401,E402  (导入即注册基线)
from opt_solvers.registry import (  # noqa: E402
    available,
    describe_missing,
    get,
    register,
)
from opt_solvers.result import (  # noqa: E402
    STATUSES,
    SolveResult,
    require_feasible,
    validate_result,
)


# --- M1 桥接 -------------------------------------------------------------


def test_bridge_exposes_m1_domain_model() -> None:
    assert M1_ROOT.is_dir()
    instance = generate_instance(1, jobs=3, machines=1)
    assert isinstance(instance, Instance)
    assert len(instance.jobs) == 3


def test_bridge_reuses_m1_rules_and_objectives() -> None:
    instance = generate_instance(2, jobs=4, machines=1)
    schedule = spt(instance)
    assert isinstance(schedule, Schedule)
    # 目标函数必须是 M1 的同一套（M2 不重新实现指标）
    assert makespan(instance, schedule) > 0
    validate_schedule(instance, schedule)
    for name in ("makespan", "total_tardiness", "weighted_completion_time"):
        assert name in M2_OBJECTIVES


# --- 统一结果接口 --------------------------------------------------------


def test_missing_bound_is_none_not_zero() -> None:
    """M2 最重要的一条纪律：启发式没有下界，gap 必须是 None。"""
    result = SolveResult(method="heur", status="FEASIBLE", objective=42.0, best_bound=None)
    assert result.best_bound is None
    assert result.gap is None, "无 bound 时 gap 必须为 None，写成 0 会伪造「已证明最优」"
    assert result.proven_optimal is False
    assert result.to_row()["gap"] is None


def test_proven_optimal_has_zero_gap() -> None:
    result = SolveResult(method="m", status="OPTIMAL", objective=10.0, best_bound=10.0)
    assert result.gap == 0.0
    assert result.proven_optimal is True


def test_gap_uses_objective_scale() -> None:
    result = SolveResult(method="m", status="FEASIBLE", objective=100.0, best_bound=90.0)
    assert result.gap == pytest.approx(0.1)


def test_bound_above_objective_is_rejected() -> None:
    """下界高于可行解说明包装层搞错了方向，必须当场失败。"""
    with pytest.raises(ValueError, match="best_bound > objective"):
        SolveResult(method="m", status="FEASIBLE", objective=5.0, best_bound=9.0)


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown status"):
        SolveResult(method="m", status="DONE")


def test_status_vocabulary_covers_cp_sat_semantics() -> None:
    for status in ("OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"):
        assert status in STATUSES


def test_wall_time_is_build_plus_solve() -> None:
    result = SolveResult(method="m", status="OPTIMAL", build_time=0.25, solve_time=1.75)
    assert result.wall_time == pytest.approx(2.0)


# --- 独立验证 ------------------------------------------------------------


def test_validate_result_rejects_infeasible_schedule() -> None:
    """求解器自称可行不算数：M1 的独立验证器说了才算。"""
    instance = generate_instance(3, jobs=3, machines=1)
    good = spt(instance)
    first = good.operations[0]
    # 把第一道工序的结束时刻改坏（duration 与实际工时不符）
    broken = Schedule(
        (
            ScheduledOperation(
                first.operation_id, first.machine_id, first.start_time, first.end_time + 5
            ),
            *good.operations[1:],
        )
    )
    result = SolveResult(method="liar", status="OPTIMAL", objective=1.0, schedule=broken)
    diagnostics = validate_result(instance, result)
    assert diagnostics, "被破坏的排程必须被独立验证器发现"
    with pytest.raises(ValueError):
        require_feasible(instance, result)


def test_validate_result_accepts_feasible_schedule() -> None:
    instance = generate_instance(4, jobs=3, machines=1)
    result = SolveResult(
        method="m", status="FEASIBLE", objective=1.0, schedule=spt(instance)
    )
    assert validate_result(instance, result) == []
    require_feasible(instance, result)


def test_validate_result_without_schedule_is_vacuous() -> None:
    """纯参数模型（LP）没有排程，视为无约束可查，不是通过验证。"""
    result = SolveResult(method="lp", status="OPTIMAL", objective=1.0)
    assert validate_result(generate_instance(5, jobs=2, machines=1), result) == []
    with pytest.raises(ValueError):
        require_feasible(generate_instance(5, jobs=2, machines=1), result)


# --- 方法注册表 ----------------------------------------------------------


def test_m1_baselines_are_registered() -> None:
    for name in ("heur_spt", "heur_edd", "heur_wspt", "heur_lpt", "heur_parallel_lpt"):
        assert name in available()


def test_duplicate_registration_is_rejected() -> None:
    with pytest.raises(ValueError, match="already registered"):
        register("heur_spt")(lambda instance, spec: None)


def test_unknown_method_is_reported_not_raised() -> None:
    assert describe_missing(["heur_spt", "no_such_method"]) == ["no_such_method"]
    with pytest.raises(KeyError):
        get("no_such_method")


@pytest.mark.parametrize("rule", ["heur_spt", "heur_edd", "heur_wspt", "heur_lpt"])
def test_rule_baseline_has_no_bound_and_is_not_optimal(rule: str) -> None:
    """规则基线是 FEASIBLE，不是 OPTIMAL —— 即使经典结论说它在特定目标下最优。"""
    instance = generate_instance(6, jobs=5, machines=1)
    result = get(rule)(instance, {"objective": "total_tardiness"})
    assert result.status == "FEASIBLE"
    assert result.best_bound is None
    assert result.gap is None
    validate_schedule(instance, result.schedule)


def test_rule_baseline_fails_gracefully_when_inapplicable() -> None:
    """单机规则用在并行机实例上：记 FAILED 并给出原因，不抛异常中断整批。"""
    instance = generate_instance(7, jobs=4, machines=3)
    result = get("heur_spt")(instance, {"objective": "makespan"})
    assert result.status == "FAILED"
    assert "single-machine" in result.detail["failure_reason"]


def test_rule_baseline_rejects_unknown_objective() -> None:
    instance = generate_instance(8, jobs=3, machines=1)
    result = get("heur_spt")(instance, {"objective": "not_an_objective"})
    assert result.status == "FAILED"
    assert "unknown objective" in result.detail["failure_reason"]


# --- 批次辅助函数 --------------------------------------------------------


def test_write_csv_takes_union_of_keys(tmp_path: Path) -> None:
    """失败行与成功行字段不同时，按第一行定列会抛异常、把记录问题升级成整批失败。"""
    rows = [
        {"a": 1, "b": 2},
        {"a": 3, "c": 4},
    ]
    path = tmp_path / "r.csv"
    write_csv(path, rows)
    text = path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "a,b,c"


def test_write_csv_and_json_handle_empty(tmp_path: Path) -> None:
    write_csv(tmp_path / "empty.csv", [])
    assert not (tmp_path / "empty.csv").exists()
    write_json(tmp_path / "e.json", {"x": None})
    assert "null" in (tmp_path / "e.json").read_text(encoding="utf-8")


def test_write_json_forbids_nan(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_json(tmp_path / "bad.json", {"x": float("nan")})


def test_source_hash_is_stable_and_covers_both_projects() -> None:
    first = source_hash()
    assert first == source_hash(), "源码指纹必须稳定"
    assert len(first) == 64
