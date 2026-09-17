"""把 M1 的规则基线接入 M2 的统一结果接口。

这五个方法的全部价值在于**给出参照点**，以及演示统一接口里最关键的一条纪律：

    ``best_bound = None``

启发式没有下界。规则给出的是一个**可行解**，不是「距离最优还差多少」的证明。
状态因此是 ``FEASIBLE`` 而**不是** ``OPTIMAL``——即使在 SPT 对 ``1||ΣCj``
最优这种经典结论成立的问题上，那也是**对特定 α|β|γ 的理论结论**，不是本方法
在任意目标下都能自称最优的理由。把 ``best_bound`` 填成目标值会让 gap 恒为 0，
看起来像「已证明最优」，这正是 M2 要防的伪证据。
"""

from __future__ import annotations

import time
from typing import Any

from opt_common.bridge import (
    M2_OBJECTIVES,
    Instance,
    Schedule,
    edd,
    lpt,
    parallel_lpt,
    spt,
    wspt,
)
from opt_solvers.registry import register
from opt_solvers.result import SolveResult


def _run_rule(instance: Instance, spec: dict[str, Any], rule_name: str, fn) -> SolveResult:
    """统一包装：计时、算目标、把规则异常记成 FAILED。"""
    objective_name = spec.get("objective", "makespan")
    if objective_name not in M2_OBJECTIVES:
        return SolveResult(
            method=f"heur_{rule_name}",
            status="FAILED",
            detail={"failure_reason": f"unknown objective: {objective_name}"},
        )
    started = time.perf_counter()
    try:
        schedule: Schedule = fn(instance)
    except (ValueError, IndexError, KeyError) as exc:
        # 规则只支持单工序 / 单机等窄范围，不适用时如实记为 FAILED。
        return SolveResult(
            method=f"heur_{rule_name}",
            status="FAILED",
            solve_time=time.perf_counter() - started,
            detail={"failure_reason": f"{type(exc).__name__}: {exc}"},
        )
    solve_time = time.perf_counter() - started
    return SolveResult(
        method=f"heur_{rule_name}",
        status="FEASIBLE",  # 可行，但没有最优性证明
        objective=float(M2_OBJECTIVES[objective_name](instance, schedule)),
        best_bound=None,  # 启发式没有下界：必须为空
        schedule=schedule,
        build_time=0.0,
        solve_time=solve_time,
        detail={"rule": rule_name, "bound_kind": "none"},
    )


@register("heur_spt", "M1 SPT 规则基线（无 bound）")
def heur_spt(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    return _run_rule(instance, spec, "spt", spt)


@register("heur_edd", "M1 EDD 规则基线（无 bound）")
def heur_edd(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    return _run_rule(instance, spec, "edd", edd)


@register("heur_wspt", "M1 WSPT 规则基线（无 bound）")
def heur_wspt(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    return _run_rule(instance, spec, "wspt", wspt)


@register("heur_lpt", "M1 LPT 规则基线（无 bound）")
def heur_lpt(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    return _run_rule(instance, spec, "lpt", lpt)


@register("heur_parallel_lpt", "M1 并行机 LPT 列表基线（无 bound）")
def heur_parallel_lpt(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    return _run_rule(instance, spec, "parallel_lpt", parallel_lpt)
