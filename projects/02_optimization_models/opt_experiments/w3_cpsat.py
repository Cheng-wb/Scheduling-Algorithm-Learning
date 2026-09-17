"""Week 3 实验驱动：把 CP-SAT 区间模型的证据写进 ``artifacts/month2_w3/``。

    python -m opt_experiments.w3_cpsat --output artifacts/month2_w3

与月末批次（:mod:`opt_experiments.benchmark`）保持同一套纪律，但范围收窄到本周：

* 先落盘实例（``instances/*.json``），同一实例的所有方法共享逐字节相同的输入；
* 每一行都带 ``time_limit``——求解器有终止条件，离开预算就谈不上「谁更快」；
* 每个返回的排程都过 M1 的独立验证器，诊断落在 ``validation`` 列；
* ``best_bound`` 没有就留空，失败留痕，不覆盖非空输出目录。

与月末批次的两点不同：

1. **参考值来自手算**。本周的实例要么是我手推出来的（写在 ``HAND_COMPUTED``
   里，附推导要点），要么标成 ``proven_by_solver`` / ``best-known``。
   没有任何一个参考值是由被测方法自己生成的。
2. **MILP 对照是自动探测的**。第 6 天要求「在共同支持的实例集上比较 MILP 与
   CP-SAT」。Week 2 的 ``opt_models/milp_scheduling.py`` 尚未落在代码树里时，
   本驱动**如实记录 MILP 不可用**，只用 CP-SAT 与 M1 启发式做同预算对照——
   绝不用别的东西冒充 MILP 的数字。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opt_common.bridge import (
    M2_OBJECTIVES,
    Instance,
    Job,
    Machine,
    Operation,
    generate_instance,
    save_json_instance,
)
from opt_experiments.benchmark import source_hash, write_csv, write_json
from opt_solvers.registry import available, describe, get, load_week_modules
from opt_solvers.result import validate_result

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1

#: 月末批次里与本周共用的实例（同 seed、同机器数），保证日后能直接对齐。
SHARED_WITH_MONTH = ("w3_parallel_8", "w3_parallel_12", "w3_routes_6")

#: 第 6 天要对照的 MILP 方法名。Week 2 未落地时这些名字取不到。
MILP_METHODS = ("milp_tight", "milp_loose", "milp_alt")


def _eval(instance: Instance, schedule, name: str) -> float:
    return float(M2_OBJECTIVES[name](instance, schedule))


def build_instances() -> dict[str, tuple[Instance, str, float | None, str]]:
    """本周的实例表：``名字 -> (实例, 目标, 手算参考值或 None, 参考值来源说明)``。"""
    catalog: dict[str, tuple[Instance, str, float | None, str]] = {}

    # --- 手算实例：并行机 LPT 反例（M1 Week 1 Day 5 的原例） -----------------
    parallel_small = Instance(
        tuple(Job(f"J{i}", (f"J{i}_O0",)) for i in range(5)),
        tuple(
            Operation(f"J{i}_O0", f"J{i}", p, ("M0", "M1"))
            for i, p in enumerate([3, 3, 2, 2, 2])
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )
    # 手算：LPT 得 7（M1 = 3+2+2 = 7），最优 6（M0 = 3+3、M1 = 2+2+2）
    catalog["w3_parallel_small"] = (parallel_small, "makespan", 6.0, "hand_computed")

    # --- 手算实例：下界紧的并行机 -----------------------------------------
    parallel_tight = Instance(
        tuple(Job(f"J{i}", (f"J{i}_O0",)) for i in range(4)),
        tuple(
            Operation(f"J{i}_O0", f"J{i}", p, ("M0", "M1"))
            for i, p in enumerate([8, 7, 6, 5])
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )
    # 手算：LB = max(8, ceil(26/2)) = 13；M0 = 8+5、M1 = 7+6 达到下界
    catalog["w3_parallel_tight"] = (parallel_tight, "makespan", 13.0, "hand_computed")

    # --- 手算实例：2x2 固定路由 JSP ---------------------------------------
    jsp = Instance(
        tuple(Job(f"J{i}", (f"J{i}_O0", f"J{i}_O1")) for i in range(2)),
        (
            Operation("J0_O0", "J0", 3, ("M0",)),
            Operation("J0_O1", "J0", 2, ("M1",)),
            Operation("J1_O0", "J1", 2, ("M1",)),
            Operation("J1_O1", "J1", 4, ("M0",)),
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )
    # 手算：M0 必须加工 3 + 4 = 7，故 Cmax >= 7；M0: J0_O0 0-3 / J1_O1 3-7，
    # M1: J1_O0 0-2 / J0_O1 3-5 达到 7
    catalog["w3_jsp_2x2"] = (jsp, "makespan", 7.0, "hand_computed")

    # --- 手算实例：Cumulative 容量收紧 ------------------------------------
    cumulative = Instance(
        tuple(Job(f"J{i}", (f"J{i}_O0",)) for i in range(3)),
        tuple(
            Operation(f"J{i}_O0", f"J{i}", 5, ("M0", "M1")) for i in range(3)
        ),
        (Machine("M0", "M0"), Machine("M1", "M1")),
    )
    # 手算：只有 NoOverlap → 两台机器并行 → 10；容量 1 时三道工序串行 → 15。
    # 参考值随容量设置而变，所以实例级参考留空，由 plan() 逐行给出。
    catalog["w3_cumulative_small"] = (cumulative, "makespan", None, "per_group")

    # --- 与月末批次共用的生成实例 -----------------------------------------
    # 生成参数与 configs/month2.json 的 single_8 / single_12 / parallel_8 /
    # parallel_12 / routes_6 逐项一致，只是换了名字前缀，结果可以逐行对齐。
    catalog["w3_single_8"] = (
        generate_instance(50, jobs=8, machines=1),
        "total_tardiness",
        None,
        "cross_checked",
    )
    catalog["w3_single_12"] = (
        generate_instance(51, jobs=12, machines=1),
        "total_tardiness",
        None,
        "cross_checked",
    )
    catalog["w3_parallel_8"] = (
        generate_instance(52, jobs=8, machines=3),
        "makespan",
        None,
        "cross_checked",
    )
    catalog["w3_parallel_12"] = (
        generate_instance(53, jobs=12, machines=3),
        "makespan",
        None,
        "cross_checked",
    )
    catalog["w3_routes_6"] = (
        generate_instance(54, jobs=6, machines=3, operations_per_job=2),
        "makespan",
        None,
        "cross_checked",
    )
    return catalog


def plan() -> list[dict[str, Any]]:
    """本周的 (实例, 方法, 参数, 标签) 运行表。参数写死，保证可复现。"""
    base = {"time_limit": 5.0, "seed": 0}
    return [
        # --- 并行机：模型本身 + 时间缩放敏感性 -------------------------
        {
            "instance": "w3_parallel_small",
            "method": "cpsat_parallel",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_parallel_small",
            "method": "cpsat_parallel",
            "label": "scale_4",
            "params": {**base, "time_scale": 4},
        },
        {
            "instance": "w3_parallel_tight",
            "method": "cpsat_parallel",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_parallel_tight",
            "method": "heur_parallel_lpt",
            "label": "main",
            "params": {**base},
        },
        # --- 共用实例：单机，MILP 三种 formulation × CP-SAT 两种模型（第 6 天）---
        # milp_tight / milp_loose 是单机 disjunctive 模型，与 cpsat_jsp 的
        # 「一工序一区间 + NoOverlap」是同一件事的两种说法。
        {
            "instance": "w3_single_8",
            "method": "milp_tight",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_single_8",
            "method": "milp_loose",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_single_8",
            "method": "milp_alt",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_single_8",
            "method": "cpsat_jsp",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_single_8",
            "method": "cpsat_parallel",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_single_8",
            "method": "heur_edd",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_single_12",
            "method": "milp_tight",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_single_12",
            "method": "milp_loose",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_single_12",
            "method": "milp_alt",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_single_12",
            "method": "cpsat_jsp",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_single_12",
            "method": "cpsat_parallel",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_single_12",
            "method": "heur_edd",
            "label": "main",
            "params": {**base},
        },
        # --- 共用实例：并行机，time-indexed MILP × CP-SAT 区间模型 --------
        {
            "instance": "w3_parallel_8",
            "method": "milp_alt",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_parallel_8",
            "method": "cpsat_parallel",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_parallel_8",
            "method": "heur_parallel_lpt",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_parallel_12",
            "method": "milp_alt",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_parallel_12",
            "method": "cpsat_parallel",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_parallel_12",
            "method": "heur_parallel_lpt",
            "label": "main",
            "params": {**base},
        },
        # --- JSP 与柔性路由 -------------------------------------------
        {
            "instance": "w3_jsp_2x2",
            "method": "cpsat_jsp",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_routes_6",
            "method": "cpsat_jsp",
            "label": "main",
            "params": {**base},
        },
        {
            "instance": "w3_routes_6",
            "method": "cpsat_parallel",
            "label": "main",
            "params": {**base},
        },
        # --- Cumulative：容量对照 -------------------------------------
        {
            "instance": "w3_cumulative_small",
            "method": "cpsat_parallel",
            "label": "no_capacity",
            "params": {**base},
            "reference": 10.0,
        },
        {
            "instance": "w3_cumulative_small",
            "method": "cpsat_cumulative",
            "label": "cap_1",
            "params": {**base, "resource_capacity": 1, "resource_demand": 1},
            "reference": 15.0,
        },
        {
            "instance": "w3_cumulative_small",
            "method": "cpsat_cumulative",
            "label": "cap_2",
            "params": {**base, "resource_capacity": 2, "resource_demand": 1},
            "reference": 10.0,
        },
        {
            "instance": "w3_cumulative_small",
            "method": "cpsat_cumulative",
            "label": "infeasible_demand_2",
            "params": {**base, "resource_capacity": 1, "resource_demand": 2},
            "reference": None,
        },
    ]


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
        )
        return out.stdout.strip()
    except OSError:
        return ""


def _milp_note(present: list[str], missing: list[str]) -> str:
    """如实记录 Week 2 的 MILP 对照在这台机器上到底可不可用。"""
    if present and not missing:
        return (
            "Week 2 的 opt_models/milp_scheduling.py 已落地，"
            f"MILP 对照方法 {present} 全部可用，本批次的跨范式比较是实测值。"
        )
    if present:
        return (
            f"Week 2 的 MILP 方法只找到 {present}，缺少 {missing}；"
            "缺失的方法在结果里表示为缺行，未用任何其它数字替代。"
        )
    return (
        "Week 2 的 opt_models/milp_scheduling.py 尚未落地，"
        "MILP 对照列在本批次中为不可用；未用任何其它数字替代。"
    )


def run(output: Path, time_limit: float = 5.0) -> list[dict[str, Any]]:
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output must be empty (preserve previous experiments): {output}")

    output.mkdir(parents=True, exist_ok=True)
    (output / "instances").mkdir(exist_ok=True)

    module_failures = load_week_modules()
    milp_present = [name for name in MILP_METHODS if name in available()]
    milp_missing = [name for name in MILP_METHODS if name not in available()]

    catalog = build_instances()

    # --- 输入先落盘 -------------------------------------------------------
    instance_hashes: dict[str, str] = {}
    objectives: dict[str, str] = {}
    references: dict[str, tuple[float | None, str]] = {}
    for name, (instance, objective_name, reference, reference_kind) in catalog.items():
        path = output / "instances" / f"{name}.json"
        save_json_instance(instance, path)
        instance_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        objectives[name] = objective_name
        references[name] = (reference, reference_kind)

    write_json(
        output / "metadata.json",
        {
            "schema_version": SCHEMA_VERSION,
            "week": "M2-W3 CP-SAT 区间模型",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "git_commit": _git("rev-parse", "HEAD"),
            "working_tree_dirty": bool(_git("status", "--porcelain")),
            "source_sha256": source_hash(),
            "budget_unit": "one solver call under a shared wall-clock time limit",
            "time_limit_seconds": time_limit,
            "unavailable_modules": module_failures,
            "registered_methods": available(),
            "milp_available": bool(milp_present),
            "milp_methods_present": milp_present,
            "milp_methods_missing": milp_missing,
            "milp_note": _milp_note(milp_present, milp_missing),
            "instance_hashes": instance_hashes,
            "references": {
                name: {"value": value, "kind": kind, "objective": objectives[name]}
                for name, (value, kind) in references.items()
            },
        },
    )

    # --- 求解 -------------------------------------------------------------
    rows: list[dict[str, Any]] = []
    for item in plan():
        name = item["instance"]
        instance, _, _, _ = catalog[name]
        method = item["method"]
        label = item["label"]
        params = {**item["params"], "time_limit": item["params"].get("time_limit", time_limit)}
        call_spec = {"objective": objectives[name], **params}
        run_id = f"{name}__{method}__{label}"
        # 参考值优先取运行表里逐行给的（Cumulative 组参考值随容量而变），
        # 否则回落到实例级参考。
        reference = item.get("reference", references[name][0])
        reference_kind = item.get("reference_kind", references[name][1])
        row: dict[str, Any] = {
            "run_id": run_id,
            "instance": name,
            "input_sha256": instance_hashes[name],
            "group": label,
            "method": method,
            "objective_name": objectives[name],
            "time_limit": call_spec["time_limit"],
            "seed": call_spec["seed"],
            "time_scale": call_spec.get("time_scale"),
            "resource_capacity": call_spec.get("resource_capacity"),
            "resource_demand": call_spec.get("resource_demand"),
            "reference": reference,
            "reference_kind": reference_kind,
        }
        if method not in available():
            row.update(_empty_row(f"method not registered: {method}"))
            rows.append(row)
            continue
        try:
            result = get(method)(instance, call_spec)
        except Exception as exc:  # 求解失败不能中断整批
            row.update(_empty_row(f"{type(exc).__name__}: {exc}"))
            row["failure_traceback"] = traceback.format_exc()[-400:]
            rows.append(row)
            continue

        diagnostics = validate_result(instance, result)
        row.update(result.to_row())
        row["validation"] = "; ".join(diagnostics)
        row["peak_resource"] = _peak(instance, result, call_spec.get("resource_demand", 1))
        if diagnostics:
            row["status"] = "INVALID_SOLUTION"
            row["failure_reason"] = f"validator rejected schedule: {diagnostics[:3]}"
        if row["reference"] is not None and row["objective"] is not None:
            row["gap_to_reference"] = (
                float(row["objective"]) - float(row["reference"])
            ) / max(1.0, abs(float(row["reference"])))
        rows.append(row)

    # 批次参考值：只由**本批已证明最优**的目标值算出来，第二档退到最好可行解。
    # 它不是证书——`best-known` 只是「本批见过的最好解」。
    batch_reference = _batch_references(rows)
    for row in rows:
        kind, value = batch_reference.get(row["instance"], (None, None))
        row["batch_reference_kind"] = kind
        row["batch_reference"] = value
        if value is None or row["objective"] is None:
            row["gap_to_batch_reference"] = None
        else:
            row["gap_to_batch_reference"] = (
                float(row["objective"]) - float(value)
            ) / max(1.0, abs(float(value)))

    write_csv(output / "results.csv", rows)
    write_json(
        output / "failures.json",
        [
            row
            for row in rows
            if row["status"] in ("FAILED", "INVALID_SOLUTION", "MODEL_INVALID", "NOT_SOLVED")
        ],
    )
    _write_report(rows, output, milp_present, milp_missing, batch_reference, time_limit)
    return rows


def _batch_references(rows: list[dict[str, Any]]) -> dict[str, tuple[str, float]]:
    """按实例算批次参考值：优先「本批已证明最优的最小值」，否则「本批最好可行解」。"""
    by_instance: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["objective"] is None:
            continue
        by_instance.setdefault(row["instance"], []).append(row)

    out: dict[str, tuple[str, float]] = {}
    for name, selected in by_instance.items():
        proven = [float(r["objective"]) for r in selected if r["status"] == "OPTIMAL"]
        if proven:
            out[name] = ("proven_by_solver", min(proven))
        else:
            out[name] = ("best-known", min(float(r["objective"]) for r in selected))
    return out


def _peak(instance: Instance, result, demand: int) -> int | None:
    """独立复核容量约束（M1 验证器不覆盖 Cumulative 语义）。"""
    if result.schedule is None:
        return None
    from opt_models.cpsat_models import cumulative_profile

    return cumulative_profile(instance, result.schedule, demand)[0]


def _empty_row(reason: str) -> dict[str, Any]:
    return {
        "status": "FAILED",
        "objective": None,
        "best_bound": None,
        "gap": None,
        "iterations": None,
        "build_time": None,
        "solve_time": None,
        "wall_time": None,
        "validation": "",
        "peak_resource": None,
        "gap_to_reference": None,
        "failure_reason": reason,
    }


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return str(value)


def _write_report(
    rows: list[dict[str, Any]],
    output: Path,
    milp_present: list[str],
    milp_missing: list[str],
    batch_reference: dict[str, tuple[str, float]],
    time_limit: float,
) -> None:
    lines = [
        "# M2 Week 3：CP-SAT 区间模型实验（脚本生成）",
        "",
        f"统一时间预算：每次求解 `{time_limit:g}` 秒，`num_search_workers=1`、`random_seed=0`。",
        "`gap`=(objective−best_bound)/max(1,|objective|)，`gap_to_reference` 相对该实例的参考值。",
        "参考值分两档：`hand_computed` 是手算时间线推出的最优；`solver_proven` 是另一组同语义设置给出的可证最优。",
        "启发式没有 bound，`gap` 一律留空——**空不是 0**。",
        "",
        "## 1. 实例与参考值",
        "",
        "| 实例 | 组 | 目标 | 参考类型 | 参考值 |",
        "|---|---|---|---|---:|",
    ]
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row["instance"], row["group"])
        if key in seen:
            continue
        seen.add(key)
        shown = "—" if row.get("reference") is None else f"{row['reference']:g}"
        lines.append(
            f"| {row['instance']} | `{row['group']}` | `{row['objective_name']}` | "
            f"`{row['reference_kind']}` | {shown} |"
        )

    lines += [
        "",
        "## 2. 逐次运行",
        "",
        "| run | 状态 | 目标 | bound | gap | 参考 | ref gap | 建模(s) | 求解(s) | 分支 | 峰值资源 | 独立校验 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {run} | `{status}` | {obj} | {bound} | {gap} | {ref} | {refgap} | "
            "{build} | {solve} | {it} | {peak} | {val} |".format(
                run=row["run_id"].replace("__", " / "),
                status=row["status"],
                obj=_fmt(row["objective"]),
                bound=_fmt(row["best_bound"]),
                gap=_fmt(row["gap"], 4),
                ref=_fmt(row.get("reference")),
                refgap=_fmt(row.get("gap_to_reference"), 4),
                build=_fmt(row.get("build_time"), 4),
                solve=_fmt(row.get("solve_time"), 4),
                it=_fmt(row.get("iterations"), 0),
                peak=_fmt(row.get("peak_resource"), 0),
                val=row.get("validation") or "通过",
            )
        )

    lines += ["", "## 3. 第 6 天：同实例集、同预算的 MILP × CP-SAT 对照", ""]
    if milp_present:
        lines.append(
            "MILP 方法可用：" + ", ".join(f"`{n}`" for n in milp_present) + "。"
        )
    else:
        lines += [
            "**MILP 对照列在本批次中不可用。** 注册表里取不到 "
            + ", ".join(f"`{n}`" for n in milp_missing)
            + "，",
            "本表因此只对照 CP-SAT 与 M1 启发式基线——**不在此处填报任何估计值**。",
        ]
    lines += [
        "",
        "同一实例、同一时间预算、同一独立验证器。`参考` 一列是该实例在**本批次**里",
        "已经证明最优的最小目标值（`proven_by_solver`），不是独立枚举的证书。",
        "",
        "| 实例 | 目标 | 方法 | 状态 | 目标值 | bound | gap | 建模(s) | 求解(s) | 相对参考 |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    shared_names = (
        "w3_single_8",
        "w3_single_12",
        "w3_parallel_8",
        "w3_parallel_12",
        "w3_routes_6",
    )
    shared = [row for row in rows if row["instance"] in shared_names]
    for name in shared_names:
        for row in shared:
            if row["instance"] != name:
                continue
            lines.append(
                f"| {row['instance']} | `{row['objective_name']}` | `{row['method']}` | "
                f"`{row['status']}` | {_fmt(row['objective'])} | {_fmt(row['best_bound'])} | "
                f"{_fmt(row['gap'], 4)} | {_fmt(row.get('build_time'), 4)} | "
                f"{_fmt(row.get('solve_time'), 4)} | {_fmt(row.get('gap_to_batch_reference'), 4)} |"
            )

    lines += ["", "### 3.1 交叉核对：两条独立技术路线给出同一个最优值", ""]
    lines += [
        "| 实例 | MILP 证明的最优 | CP-SAT 证明的最优 | 是否一致 |",
        "|---|---:|---:|---|",
    ]
    for name in shared_names:
        milp_values = [
            float(row["objective"])
            for row in shared
            if row["instance"] == name
            and row["method"] in MILP_METHODS
            and row["status"] == "OPTIMAL"
            and row["objective"] is not None
        ]
        cpsat_values = [
            float(row["objective"])
            for row in shared
            if row["instance"] == name
            and row["method"].startswith("cpsat_")
            and row["status"] == "OPTIMAL"
            and row["objective"] is not None
        ]
        if not milp_values or not cpsat_values:
            shown_milp = "—" if not milp_values else f"{min(milp_values):g}"
            shown_cpsat = "—" if not cpsat_values else f"{min(cpsat_values):g}"
            lines.append(
                f"| {name} | {shown_milp} | {shown_cpsat} | 无双方同时证明最优的记录 |"
            )
            continue
        agree = min(milp_values) == min(cpsat_values)
        lines.append(
            f"| {name} | {min(milp_values):g} | {min(cpsat_values):g} | "
            f"{'一致' if agree else '**不一致，需排查**'} |"
        )

    lines += ["", "## 4. Cumulative 与 NoOverlap 的语义对照", ""]
    cumulative_rows = [row for row in rows if row["instance"] == "w3_cumulative_small"]
    lines += [
        "同一实例（2 台机器 × 3 个 p=5 的工序）在不同容量设置下的结果：",
        "",
        "| 组 | 方法 | 容量 | 需求 | 状态 | Cmax | 峰值占用 |",
        "|---|---|---:|---:|---|---:|---:|",
    ]
    for row in cumulative_rows:
        lines.append(
            f"| `{row['group']}` | `{row['method']}` | {_fmt(row.get('resource_capacity'), 0)} | "
            f"{_fmt(row.get('resource_demand'), 0)} | `{row['status']}` | "
            f"{_fmt(row['objective'])} | {_fmt(row.get('peak_resource'), 0)} |"
        )

    lines += [
        "",
        "## 5. 状态分布",
        "",
        "| 状态 | 次数 |",
        "|---|---:|",
    ]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    for status, count in sorted(counts.items()):
        lines.append(f"| `{status}` | {count} |")

    means = [float(r["solve_time"]) for r in rows if r.get("solve_time") is not None]
    if means:
        lines += [
            "",
            f"平均求解耗时 {statistics.mean(means):.4f} s（{len(means)} 次成功求解）。",
        ]

    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "month2_w3")
    parser.add_argument("--time-limit", type=float, default=5.0)
    args = parser.parse_args()
    rows = run(args.output, time_limit=args.time_limit)
    failed = sum(1 for r in rows if r["status"] in ("FAILED", "INVALID_SOLUTION"))
    print(f"runs={len(rows)}, failed={failed}, output={args.output.resolve()}")
    print("methods:", ", ".join(describe(name) for name in ("cpsat_parallel", "cpsat_jsp", "cpsat_cumulative")))
    print("available:", ", ".join(available()))


if __name__ == "__main__":
    main()
