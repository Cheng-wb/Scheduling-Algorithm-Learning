"""M3 可复现批次：同实例、同时间预算下比较 Flow Shop 启发式 / JSP / FJSP 各类方法。

    python -m fjsp_experiments.benchmark --config configs/month3.json --output artifacts/month3

沿用 M2 批次的设计，并保留 M2 自查出来的那条关键顺序纪律：

**版本状态必须在创建输出目录之前捕获。** 否则刚写进输出目录的 ``config.json``
会被 git 当成未跟踪文件，``working_tree_dirty`` 恒为 True、这个标记就废了
（M1 的批次正是栽在这里；M2 修正后 source hash 才真正可核对）。

M3 额外记录 ``cmax / total_tardiness / setup`` 三个分量，因为 Week 3 的目标是
加权和，只看一个数会让分量取舍完全不可见。
"""

from __future__ import annotations

import argparse
import csv
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

from fjsp_core.models import FJSPInstance
from fjsp_core.objective import OBJECTIVES
from fjsp_core.result import ShopResult, validate_result
from fjsp_io.parser import save_json_instance
from fjsp_shop.registry import available, describe_missing, get, load_week_modules

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
PACKAGES = ("fjsp_core", "fjsp_shop", "fjsp_io", "fjsp_experiments")


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """列取所有行键的并集（保持首次出现顺序），缺的写空。"""
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def source_hash() -> str:
    digest = hashlib.sha256()
    for package in PACKAGES:
        base = ROOT / package
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
    return digest.hexdigest()


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
        )
        return out.stdout.strip()
    except OSError:
        return ""


def build_instance(spec: dict[str, Any]) -> FJSPInstance:
    from fjsp_io.generator import generate_instance

    if spec.get("kind", "fjsp") != "fjsp":
        raise ValueError(f"unsupported instance kind: {spec.get('kind')!r}")
    return generate_instance(**spec["generator"])


def _variants(config: dict[str, Any], spec: dict[str, Any]) -> list[tuple[str, str, dict]]:
    """(group, method, params) 三元组：主实验 + 敏感性实验，支持实例级覆盖。"""
    out: list[tuple[str, str, dict]] = []
    methods = spec.get("methods", config.get("methods", []))
    for method in methods:
        out.append(("main", method, {}))
    if spec.get("sensitivity", True):
        for item in config.get("sensitivity", []):
            params = dict(item)
            method = params.pop("method")
            label = params.pop("label", method)
            if method not in methods:
                continue
            out.append((label, method, params))
    return out


def _failed_row(
    name: str, digest: str, group: str, method: str, objective: str, reason: str
) -> dict[str, Any]:
    return {
        "run_id": f"{name}__{group}__{method}",
        "instance": name,
        "input_sha256": digest,
        "group": group,
        "method": method,
        "objective_name": objective,
        "status": "FAILED",
        "objective": None,
        "best_bound": None,
        "gap": None,
        "iterations": None,
        "build_time": None,
        "solve_time": None,
        "wall_time": None,
        "cmax": None,
        "total_tardiness": None,
        "setup": None,
        "validation": "",
        "failure_reason": reason,
        "reference_type": None,
        "reference": None,
        "gap_to_reference": None,
    }


def run(config_path: Path, output: Path) -> list[dict[str, Any]]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output must be empty (preserve previous experiments): {output}")

    # --- 版本状态：必须在创建输出目录之前 -------------------------------
    frozen_commit = _git("rev-parse", "HEAD")
    frozen_dirty = bool(_git("status", "--porcelain"))
    frozen_source = source_hash()

    output.mkdir(parents=True, exist_ok=True)
    (output / "instances").mkdir(exist_ok=True)
    (output / "runs").mkdir(exist_ok=True)
    (output / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    module_failures = load_week_modules()
    time_limit = float(config.get("time_limit_seconds", 30.0))
    write_json(
        output / "metadata.json",
        {
            "schema_version": SCHEMA_VERSION,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "git_commit": frozen_commit,
            "working_tree_dirty": frozen_dirty,
            "source_sha256": frozen_source,
            "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
            "time_limit_seconds": time_limit,
            "unavailable_modules": module_failures,
            "registered_methods": available(),
            "budget_unit": "one solver call under a shared wall-clock time limit",
        },
    )

    # --- 输入先落盘 --------------------------------------------------------
    instances: dict[str, FJSPInstance] = {}
    digests: dict[str, str] = {}
    for spec in config["instances"]:
        name = spec["name"]
        if not name.replace("_", "").isalnum():
            raise ValueError("instance name must be alphanumeric/underscore")
        instance = build_instance(spec)
        path = output / "instances" / f"{name}.json"
        save_json_instance(instance, path)
        instances[name] = instance
        digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()

    # --- 求解 --------------------------------------------------------------
    rows: list[dict[str, Any]] = []
    for spec in config["instances"]:
        name = spec["name"]
        instance = instances[name]
        objective = spec.get("objective", "makespan")
        if objective not in OBJECTIVES:
            raise ValueError(f"instance {name!r} has unknown objective {objective!r}")
        for group, method, params in _variants(config, spec):
            try:
                solve_fn = get(method)
            except KeyError:
                row = _failed_row(
                    name, digests[name], group, method, objective,
                    f"method not registered: {method}",
                )
                rows.append(row)
                continue
            for seed in config.get("seeds", [0]):
                run_id = f"{name}__{group}__{method}__{seed}"
                call_spec = {
                    "objective": objective,
                    "time_limit": float(params.get("time_limit", time_limit)),
                    "seed": seed,
                    **params,
                }
                row: dict[str, Any] = {
                    "run_id": run_id,
                    "instance": name,
                    "input_sha256": digests[name],
                    "group": group,
                    "method": method,
                    "objective_name": objective,
                }
                try:
                    result = solve_fn(instance, call_spec)
                except Exception as exc:  # 单次求解失败不能中断整批
                    row.update(
                        _failed_row(
                            name, digests[name], group, method, objective,
                            f"{type(exc).__name__}: {exc}",
                        )
                    )
                    row["run_id"] = run_id
                    row["failure_traceback"] = traceback.format_exc()[-400:]
                    rows.append(row)
                    continue

                diagnostics = validate_result(instance, result)
                row.update(result.to_row())
                row["validation"] = "; ".join(diagnostics)
                row["failure_reason"] = ""
                if diagnostics:
                    # 求解器给了不可行的解：比 FAILED 更严重，必须显眼
                    row["status"] = "INVALID_SOLUTION"
                    row["failure_reason"] = (
                        f"independent validator rejected the schedule: {diagnostics[:3]}"
                    )
                rows.append(row)
                write_json(
                    output / "runs" / f"{run_id}.json",
                    {
                        "run_id": run_id,
                        "spec": call_spec,
                        "result": result.to_row(),
                        "detail": result.detail,
                        "validation": diagnostics,
                        "schedule": (
                            None
                            if result.schedule is None
                            else {
                                "operations": [
                                    {
                                        "operation_id": item.operation_id,
                                        "machine_id": item.machine_id,
                                        "start_time": item.start_time,
                                        "end_time": item.end_time,
                                        "worker_id": item.worker_id,
                                    }
                                    for item in result.schedule.operations
                                ]
                            }
                        ),
                    },
                )

    _attach_references(rows, instances)
    write_csv(output / "results.csv", rows)
    failures = [
        row
        for row in rows
        if row["status"] in ("FAILED", "INVALID_SOLUTION", "MODEL_INVALID", "NOT_SOLVED")
    ]
    write_json(output / "failures.json", failures)
    _summarize(rows, output)
    return rows


def _reference_for(instance: FJSPInstance, rows: list[dict[str, Any]], objective: str):
    """三档参考值：独立枚举 / 求解器证明 / 本批最好可行解。"""
    solved = [r for r in rows if r["objective"] is not None]
    if not solved:
        return "none", None
    try:
        from fjsp_shop.oracle import exhaustive_optimum

        value, _ = exhaustive_optimum(instance, objective, limit=200_000)
        return "optimum", float(value)
    except Exception:
        # 枚举器不存在 / 实例太大 / 目标不支持 —— 都只是「这一档不适用」
        pass
    proven = [float(r["objective"]) for r in solved if r["status"] == "OPTIMAL"]
    if proven:
        return "proven_by_solver", min(proven)
    return "best-known", min(float(r["objective"]) for r in solved)


def _attach_references(
    rows: list[dict[str, Any]], instances: dict[str, FJSPInstance]
) -> None:
    by_instance: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_instance.setdefault(row["instance"], []).append(row)
    for name, selected in by_instance.items():
        objective = selected[0]["objective_name"]
        kind, reference = _reference_for(instances[name], selected, objective)
        for row in selected:
            row["reference_type"] = kind
            row["reference"] = reference
            if reference is None or row["objective"] is None:
                row["gap_to_reference"] = None
            else:
                row["gap_to_reference"] = (float(row["objective"]) - reference) / max(
                    1.0, abs(reference)
                )


def _summarize(rows: list[dict[str, Any]], output: Path) -> None:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["instance"], row["group"], row["method"]), []).append(row)

    summary: list[dict[str, Any]] = []
    for (instance, group, method), selected in sorted(groups.items()):
        solved = [r for r in selected if r["objective"] is not None]
        objectives = [float(r["objective"]) for r in solved]
        gaps = [float(r["gap"]) for r in solved if r["gap"] is not None]
        ref_gaps = [
            float(r["gap_to_reference"])
            for r in solved
            if r.get("gap_to_reference") is not None
        ]
        walls = [float(r["wall_time"]) for r in solved if r["wall_time"] is not None]
        summary.append(
            {
                "instance": instance,
                "group": group,
                "method": method,
                "successful": len(solved),
                "failed": len(selected) - len(solved),
                "optimal_count": sum(1 for r in solved if r["status"] == "OPTIMAL"),
                "reference_type": selected[0].get("reference_type"),
                "reference": selected[0].get("reference"),
                "mean_objective": round(statistics.mean(objectives), 6) if objectives else None,
                "best_objective": min(objectives) if objectives else None,
                "mean_gap": round(statistics.mean(gaps), 6) if gaps else None,
                "mean_gap_to_reference": (
                    round(statistics.mean(ref_gaps), 6) if ref_gaps else None
                ),
                "mean_wall_time": round(statistics.mean(walls), 6) if walls else None,
            }
        )
    write_csv(output / "summary.csv", summary)
    _report(summary, output)


def _report(summary: list[dict[str, Any]], output: Path) -> None:
    def fmt(value: Any, digits: int = 3) -> str:
        return "—" if value is None else f"{value:.{digits}f}"

    references = sorted(
        {(r["instance"], r["reference_type"], r["reference"]) for r in summary}
    )
    lines = [
        "# M3 实验汇总（脚本生成）",
        "",
        "`gap` 相对**求解器自己的界**；`gap_to_reference` 相对**该实例的参考值**。",
        "启发式没有 bound，两者都为空，**不能当作 0**。",
        "",
        "## 实例参考值",
        "",
        "| 实例 | 参考类型 | 参考值 |",
        "|---|---|---:|",
    ]
    seen: set[str] = set()
    for instance, kind, value in references:
        if instance in seen:
            continue
        seen.add(instance)
        lines.append(f"| {instance} | `{kind}` | {'—' if value is None else f'{value:g}'} |")
    lines += [
        "",
        "`optimum` 来自独立枚举，`proven_by_solver` 来自某个求解器在预算内的证明，",
        "`best-known` 只是本批见过的最好可行解——**不是最优性证书**。",
        "",
        "## 逐方法汇总",
        "",
        "| 实例 | 组 | 方法 | 成功/失败 | 已证明最优 | 均值 | 平均 gap | 平均 ref gap | 平均耗时(s) |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['instance']} | {row['group']} | {row['method']} | "
            f"{row['successful']}/{row['failed']} | {row['optimal_count']} | "
            f"{fmt(row['mean_objective'])} | {fmt(row['mean_gap'], 4)} | "
            f"{fmt(row['mean_gap_to_reference'], 4)} | {fmt(row['mean_wall_time'], 3)} |"
        )
    lines += [
        "",
        "同一实例跨方法汇总。时间预算相同不代表实际耗时相同；",
        "`OPTIMAL` 只说明求解器证明了自己的**模型**最优，排程可行性另由独立验证器判定。",
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "month3.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "month3")
    args = parser.parse_args()
    rows = run(args.config, args.output)
    failed = sum(1 for r in rows if r["status"] in ("FAILED", "INVALID_SOLUTION"))
    print(f"runs={len(rows)}, failed={failed}, output={args.output.resolve()}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
