"""W4 实验记录：强化手段消融、时间预算扫描、不可行诊断，落盘到 artifacts/month2_w4/。

    python -m opt_experiments.w4_engineering --output artifacts/month2_w4

纪律与月末批次一致：不覆盖非空目录、失败留痕、`None` 不写成 0。
刻意保持**小规模 + 短预算**：``diagnose_infeasibility`` 的删除过滤会多次重解，
在大会话实例上会安静地跑很久。
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from opt_common.bridge import generate_instance
from opt_experiments.benchmark import source_hash, write_csv, write_json
from opt_models.diagnostics import (
    deadlines_with_slack,
    diagnose_infeasibility,
    scaling_report,
)
from opt_models.strengthening import solve_parallel_cpsat, solve_single_machine
from opt_solvers.registry import get, load_week_modules

ROOT = Path(__file__).resolve().parents[1]

#: 只在这些实例上做强化消融：规模刻意偏小，保证每次求解都在秒级完成。
PARALLEL_CASES = (
    ("par_6x3", dict(seed=80, jobs=6, machines=3)),
    ("par_10x3", dict(seed=83, jobs=10, machines=3)),
)
SINGLE_CASES = (
    ("sgl_8x1", dict(seed=50, jobs=8, machines=1)),
    ("sgl_12x1", dict(seed=51, jobs=12, machines=1)),
    # seed=81 上 SPT 初解不是最优（283 > 271），这样前缀固定的「限制解空间」
    # 才看得出来；前两个实例的规则初解恰好等于最优，四档会并列，
    # 那种情况下 fix_all 虽然正确，却证明不了它**限制了**什么。
    ("sgl_10x1_seed_suboptimal", dict(seed=81, jobs=10, machines=1)),
)
TIME_LIMITS = (1.0, 3.0, 10.0)


def _strengthening_rows() -> list[dict[str, Any]]:
    """对称破缺 × 冗余约束的 2×2 消融。核心断言：最优值必须不变。"""
    rows: list[dict[str, Any]] = []
    for name, params in PARALLEL_CASES:
        instance = generate_instance(**params)
        spec = {"objective": "makespan", "time_limit": 10.0, "seed": 0}
        for symmetry in (False, True):
            for redundant in (False, True):
                label = f"sym={int(symmetry)}_red={int(redundant)}"
                result = solve_parallel_cpsat(
                    instance,
                    spec,
                    symmetry_breaking=symmetry,
                    redundant_constraints=redundant,
                    method=f"cpsat_{label}",
                )
                row = {
                    "instance": name,
                    "group": "strengthening_ablation",
                    "variant": label,
                    "symmetry_breaking": symmetry,
                    "redundant_constraints": redundant,
                    **result.to_row(),
                }
                rows.append(row)
    return rows


def _warmstart_rows() -> list[dict[str, Any]]:
    """hint / 目标上界割 / 前缀固定 三条正交开关。"""
    rows: list[dict[str, Any]] = []
    for name, params in SINGLE_CASES:
        instance = generate_instance(**params)
        spec = {"objective": "total_tardiness", "time_limit": 10.0, "seed": 0}
        from opt_common.bridge import M2_OBJECTIVES, spt

        seed_schedule = spt(instance)
        seed_value = float(M2_OBJECTIVES["total_tardiness"](instance, seed_schedule))
        total = len(instance.jobs)
        variants = (
            ("hint_only", dict(set_hint=True, objective_cutoff=False, fixed_prefix=0)),
            ("cutoff_only", dict(set_hint=False, objective_cutoff=True, fixed_prefix=0)),
            ("cutoff_and_hint", dict(set_hint=True, objective_cutoff=True, fixed_prefix=0)),
            ("fix_prefix_3", dict(set_hint=False, objective_cutoff=False, fixed_prefix=3)),
            ("fix_all", dict(set_hint=False, objective_cutoff=False, fixed_prefix=total)),
        )
        for label, flags in variants:
            result = solve_single_machine(
                instance,
                spec,
                hint_schedule=seed_schedule if flags["set_hint"] else None,
                method=f"milp_{label}",
                **flags,
            )
            rows.append(
                {
                    "instance": name,
                    "group": "warmstart_ablation",
                    "variant": label,
                    "seed_value": seed_value,
                    **result.to_row(),
                }
            )
    return rows


def _time_limit_rows() -> list[dict[str, Any]]:
    """同一实例扫时间预算，记录终止原因。"""
    rows: list[dict[str, Any]] = []
    instance = generate_instance(70, jobs=20, machines=1)
    for limit in TIME_LIMITS:
        result = get("milp_tight")(
            instance, {"objective": "total_tardiness", "time_limit": limit, "seed": 0}
        )
        rows.append(
            {
                "instance": "sgl_20x1",
                "group": "time_limit_scan",
                "variant": f"limit_{limit:g}s",
                "time_limit": limit,
                **result.to_row(),
            }
        )
    return rows


def _diagnostics_rows() -> list[dict[str, Any]]:
    """不可行诊断：slack 作为可控旋钮。"""
    rows: list[dict[str, Any]] = []
    instance = generate_instance(82, jobs=6, machines=1)
    for slack in (0.5, 1.0, 2.0):
        deadlines = deadlines_with_slack(instance, slack)
        started = time.perf_counter()
        report = diagnose_infeasibility(instance, deadlines, time_limit=3.0)
        elapsed = time.perf_counter() - started
        rows.append(
            {
                "instance": "sgl_6x1",
                "group": "infeasibility_diagnosis",
                "variant": f"slack_{slack:g}",
                "status": report.status,
                "objective": None,
                "best_bound": None,
                "gap": None,
                "iterations": report.solves,
                "build_time": 0.0,
                "solve_time": round(elapsed, 6),
                "wall_time": round(elapsed, 6),
                "reported_conflict": "|".join(report.reported_conflict),
                "minimal_conflict": "|".join(report.minimal_conflict),
                "reduction_steps": report.reduction_steps,
            }
        )
    return rows


def run(output: Path) -> list[dict[str, Any]]:
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output must be empty (preserve previous experiments): {output}")
    output.mkdir(parents=True, exist_ok=True)

    load_week_modules()
    rows = _strengthening_rows() + _warmstart_rows() + _time_limit_rows() + _diagnostics_rows()

    write_json(
        output / "metadata.json",
        {
            "schema_version": 1,
            "source_sha256": source_hash(),
            "budget_unit": "one solver call under an explicit time limit",
            "time_limits_seconds": list(TIME_LIMITS),
            "note": "强化消融与 warm start 消融都用小实例；诊断用 3s 预算限制删除过滤的代价",
        },
    )
    write_json(
        output / "scaling.json",
        asdict(scaling_report(generate_instance(82, jobs=6, machines=1))),
    )
    write_csv(output / "results.csv", rows)
    _report(rows, output)
    return rows


def _report(rows: list[dict[str, Any]], output: Path) -> None:
    def fmt(value: Any, digits: int = 3) -> str:
        return "—" if value is None else f"{value:.{digits}f}"

    lines = [
        "# M2 Week 4 实验汇总（脚本生成）",
        "",
        "空值表示**该方法不提供**这个量，不是 0。",
        "",
        "## 1. 强化消融（同质并行机，Cmax）",
        "",
        "| 实例 | 变体 | 状态 | 目标 | 界 | 冲突 | 耗时(s) |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        if row["group"] != "strengthening_ablation":
            continue
        lines.append(
            f"| {row['instance']} | `{row['variant']}` | {row['status']} | "
            f"{fmt(row['objective'], 0)} | {fmt(row['best_bound'], 0)} | "
            f"{fmt(row['iterations'], 0)} | {fmt(row['wall_time'])} |"
        )
    lines += [
        "",
        "**判据**：同一实例的四个变体目标值必须完全相同。不同即说明强化改变了最优值，",
        "那是建模错误，不是性能差异。",
        "",
        "## 2. warm start 消融（单机，ΣT）",
        "",
        "| 实例 | 变体 | 状态 | 目标 | 相对规则初解 | 耗时(s) |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in rows:
        if row["group"] != "warmstart_ablation":
            continue
        delta = (
            "—"
            if row["objective"] is None
            else f"{row['objective'] - row['seed_value']:+.0f}"
        )
        lines.append(
            f"| {row['instance']} | `{row['variant']}` | {row['status']} | "
            f"{fmt(row['objective'], 0)} | {delta} | {fmt(row['wall_time'])} |"
        )
    lines += [
        "",
        "`fix_all` 必然等于规则初解本身——它是把解空间缩到一个点，不是强化。",
        "",
        "## 3. 时间预算扫描（20 作业单机，ΣT）",
        "",
        "| 预算(s) | 状态 | 目标 | 界 | gap | 节点 | 建模(s) | 求解(s) |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        if row["group"] != "time_limit_scan":
            continue
        lines.append(
            f"| {row['time_limit']:g} | {row['status']} | {fmt(row['objective'], 0)} | "
            f"{fmt(row['best_bound'])} | {fmt(row['gap'], 4)} | {fmt(row['iterations'], 0)} | "
            f"{fmt(row['build_time'])} | {fmt(row['solve_time'])} |"
        )
    lines += [
        "",
        "## 4. 不可行诊断（slack 作为旋钮）",
        "",
        "| slack | 状态 | 求解次数 | 极小冲突集 | 删除过滤步数 |",
        "|---|---|---:|---|---:|",
    ]
    for row in rows:
        if row["group"] != "infeasibility_diagnosis":
            continue
        lines.append(
            f"| {row['variant'].split('_')[1]} | {row['status']} | {row['iterations']} | "
            f"`{row['minimal_conflict']}` | {row['reduction_steps']} |"
        )
    lines += [
        "",
        "冲突集是**相对这组假设**的极小集：slack 变化后，能各自达标的作业变了，",
        "冲突集也跟着变。所以「冲突」不能脱离「相对哪组假设」单独讲。",
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "month2_w4")
    args = parser.parse_args()
    rows = run(args.output)
    failed = sum(1 for r in rows if r.get("status") in ("FAILED", "INVALID_SOLUTION"))
    print(f"rows={len(rows)}, failed={failed}, output={args.output.resolve()}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
