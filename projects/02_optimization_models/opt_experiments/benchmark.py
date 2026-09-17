"""M2 可复现批次：同实例、同时间预算下比较 MILP / CP-SAT / 启发式。

    python -m opt_experiments.benchmark --config configs/month2.json --output artifacts/month2

与 M1 批次的设计保持一致（配置驱动、先落盘输入、失败留痕、不覆盖非空目录），
并针对精确方法补三件事：

1. **时间预算显式记录**：求解器是有终止条件的，``time_limit`` 必须进结果行，
   否则「谁更快」无从谈起。
2. **独立验证**：每个返回的排程都过 M1 的 ``schedule_errors``，结果落在
   ``validation`` 列。求解器自称 ``OPTIMAL`` 不等于解可行。
3. **bound 与 gap 如实留空**：启发式没有 bound，写空值而不是 0。

源码指纹同时覆盖 M2 的四个包与 M1 的四个包——M2 的结果依赖 M1 的验证器与
目标函数，只 hash M2 是不完整的。
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

from opt_common.bridge import M1_ROOT, M2_ROOT, generate_instance, save_json_instance
from opt_solvers.registry import available, describe, describe_missing, get, load_week_modules
from opt_solvers.result import SolveResult, validate_result

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
SOURCE_PACKAGES = (
    ("opt_common", "opt_solvers", "opt_models", "opt_experiments"),
    ("scheduling_core", "scheduling_algorithms", "scheduling_io"),
)


def write_json(path: Path, data: Any) -> None:
    """写出 JSON；``None`` 保留为 null，禁止 NaN/Infinity。"""
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """写出 CSV。列取所有行键的并集（保持首次出现顺序），缺的键写空。

    不用 ``rows[0]`` 的键：失败行与成功行的字段不完全相同，按第一行定列会
    在遇到多出来的键时抛 ``ValueError``，把一条记录问题升级成整批失败。
    """
    import csv

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


def _hash_tree(root: Path, packages: tuple[str, ...]) -> list[str]:
    chunks: list[str] = []
    for package in packages:
        base = root / package
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            chunks.append(relative)
            chunks.append(hashlib.sha256(path.read_bytes()).hexdigest())
    return chunks


def source_hash() -> str:
    """M2 四个包 + M1 三个包的联合指纹（顺序稳定）。"""
    digest = hashlib.sha256()
    for chunk in _hash_tree(M2_ROOT, SOURCE_PACKAGES[0]):
        digest.update(chunk.encode())
    for chunk in _hash_tree(M1_ROOT, SOURCE_PACKAGES[1]):
        digest.update(chunk.encode())
    return digest.hexdigest()


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
        )
        return out.stdout.strip()
    except OSError:
        return ""


def build_instance(spec: dict[str, Any]):
    """从配置构造实例。目前支持 ``kind="scheduling"``（走 M1 生成器）。"""
    kind = spec.get("kind", "scheduling")
    if kind != "scheduling":
        raise ValueError(f"unsupported instance kind: {kind}")
    return generate_instance(**spec["generator"])


def run(config_path: Path, output: Path) -> list[dict[str, Any]]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output must be empty (preserve previous experiments): {output}")

    # 版本状态必须在**创建输出目录之前**捕获。否则刚写进去的 config.json
    # 就会被 git 视为未跟踪文件，working_tree_dirty 永远为 True —— 那样这个
    # 标记就失去了全部意义（M1 的批次就栽在这上面）。
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
            "budget_unit": "one solver call under a shared wall-clock time limit",
            "registered_methods": available(),
        },
    )

    # --- 输入先落盘：同一实例的所有方法共享逐字节相同的输入 -----------------
    instances: dict[str, Any] = {}
    instance_hashes: dict[str, str] = {}
    for spec in config["instances"]:
        name = spec["name"]
        if not name.replace("_", "").isalnum():
            raise ValueError("instance name must be alphanumeric/underscore")
        instance = build_instance(spec)
        path = output / "instances" / f"{name}.json"
        save_json_instance(instance, path)
        instances[name] = instance
        instance_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()

    # --- 求解 --------------------------------------------------------------
    rows: list[dict[str, Any]] = []
    for spec in config["instances"]:
        name = spec["name"]
        instance = instances[name]
        objective_name = spec.get("objective", "makespan")
        for group, method, params in _variants(config, spec):
            if not _has_method(method):
                rows.append(
                    _failed_row(
                        name,
                        instance_hashes[name],
                        group,
                        method,
                        objective_name,
                        time_limit,
                        f"method not registered: {method}",
                    )
                )
                continue
            for seed in config.get("seeds", [0]):
                run_id = f"{name}__{group}__{method}__{seed}"
                call_spec = {
                    "objective": objective_name,
                    "time_limit": time_limit,
                    "seed": seed,
                    **params,
                }
                effective_limit = float(call_spec["time_limit"])
                row: dict[str, Any] = {
                    "run_id": run_id,
                    "instance": name,
                    "input_sha256": instance_hashes[name],
                    "group": group,
                    "method": method,
                    "seed": seed,
                    "objective_name": objective_name,
                    "time_limit": effective_limit,
                }
                try:
                    result = get(method)(instance, call_spec)
                except Exception as exc:  # 求解失败不能中断整批
                    row.update(
                        _failed_row(
                            name,
                            instance_hashes[name],
                            group,
                            method,
                            objective_name,
                            effective_limit,
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
                    # 求解器给了不可行的解：这是比 FAILED 更严重的问题，
                    # 必须让它在结果表里显眼，而不是悄悄算进均值。
                    row["status"] = "INVALID_SOLUTION"
                    row["failure_reason"] = (
                        f"independent validator rejected returned schedule: {diagnostics[:3]}"
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
                                    }
                                    for item in result.schedule.operations
                                ]
                            }
                        ),
                    },
                )

    _attach_references(rows, instances, config)
    write_csv(output / "results.csv", rows)
    failures = [
        row
        for row in rows
        if row["status"] in ("FAILED", "INVALID_SOLUTION", "MODEL_INVALID", "NOT_SOLVED")
    ]
    write_json(output / "failures.json", failures)
    _summarize(rows, output)
    return rows


def _reference_for(instance, rows: list[dict[str, Any]], objective_name: str):
    """给一个实例定参考值，并说明它是**哪一种**参考。

    三档，优先级从高到低——这正是 M1 反复强调的「参考值有强弱之分」：

    ``optimum``            独立枚举算出的真正最优（不依赖任何被测求解器）
    ``proven_by_solver``   某个求解器在预算内证明了最优（可信，但依赖求解器正确）
    ``best-known``         本批次见过的最好可行解（只是下界估计，不是证明）
    """
    from opt_common.bridge import M2_OBJECTIVES

    solved = [r for r in rows if r["objective"] is not None]
    if not solved:
        return "none", None

    # 档 1：独立枚举（只对单工序小实例可行，与求解器无关）
    # 枚举器会因多种原因拒绝：多工序、组合数超限、目标不在 M1 的 OBJECTIVES 里。
    # 任何拒绝都只是「这一档不适用」，绝不能让它中断整批。
    try:
        from scheduling_algorithms.oracle import exhaustive_optimum

        value, _, _ = exhaustive_optimum(instance, objective_name, limit=100_000)
        return "optimum", float(value)
    except Exception:  # noqa: BLE001 - 见上：不适用的原因很多，一律降级到下一档
        pass

    # 档 2：求解器证明的最优
    proven = [float(r["objective"]) for r in solved if r["status"] == "OPTIMAL"]
    if proven:
        return "proven_by_solver", min(proven)

    # 档 3：本批最好可行解
    return "best-known", min(float(r["objective"]) for r in solved)


def _attach_references(
    rows: list[dict[str, Any]], instances: dict[str, Any], config: dict[str, Any]
) -> None:
    """按实例补 ``reference_type`` / ``reference`` / ``gap_to_reference``。"""
    by_instance: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_instance.setdefault(row["instance"], []).append(row)

    for name, selected in by_instance.items():
        objective_name = selected[0]["objective_name"]
        kind, reference = _reference_for(instances[name], selected, objective_name)
        for row in selected:
            row["reference_type"] = kind
            row["reference"] = reference
            if reference is None or row["objective"] is None:
                row["gap_to_reference"] = None
            else:
                row["gap_to_reference"] = (float(row["objective"]) - reference) / max(
                    1.0, abs(reference)
                )
        if kind == "optimum":
            # 独立枚举已经定出最优，那么任何 bound 都不可能比它更低；
            # 这是对求解器 best_bound 的一次交叉检查。
            for row in selected:
                bound = row.get("best_bound")
                if bound is not None and bound > reference + 1e-6:
                    row["failure_reason"] = (
                        f"{row['failure_reason']} | best_bound {bound} > independently "
                        f"enumerated optimum {reference}"
                    ).strip(" |")


def _has_method(method: str) -> bool:
    try:
        get(method)
        return True
    except KeyError:
        return False


def _variants(
    config: dict[str, Any], spec: dict[str, Any]
) -> list[tuple[str, str, dict[str, Any]]]:
    """展开成 (group, method, params) 三元组：主实验 + 敏感性实验。

    实例可以用 ``"methods"`` 覆盖全局方法表。这不是为了「让结果好看」，
    而是因为单机规则本来就不适用于并行机实例：把它列上去只会产生一条
    无信息量的 ``FAILED``。
    """
    out: list[tuple[str, str, dict[str, Any]]] = []
    for method in spec.get("methods", config.get("methods", [])):
        out.append(("main", method, {}))
    if spec.get("sensitivity", True):
        for item in config.get("sensitivity", []):
            params = dict(item)
            method = params.pop("method")
            label = params.pop("label", method)
            if method not in spec.get("methods", config.get("methods", [])):
                continue
            out.append((label, method, params))
    return out


def _failed_row(
    name: str,
    input_sha256: str,
    group: str,
    method: str,
    objective_name: str,
    time_limit: float,
    reason: str,
) -> dict[str, Any]:
    return {
        "run_id": f"{name}__{group}__{method}",
        "instance": name,
        "input_sha256": input_sha256,
        "group": group,
        "method": method,
        "seed": None,
        "objective_name": objective_name,
        "time_limit": time_limit,
        "status": "FAILED",
        "objective": None,
        "best_bound": None,
        "gap": None,
        "iterations": None,
        "build_time": None,
        "solve_time": None,
        "wall_time": None,
        "validation": "",
        "failure_reason": reason,
        "reference_type": None,
        "reference": None,
        "gap_to_reference": None,
    }


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
        iters = [int(r["iterations"]) for r in solved if r["iterations"] is not None]
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
                "mean_iterations": round(statistics.mean(iters), 2) if iters else None,
            }
        )
    write_csv(output / "summary.csv", summary)
    _report(summary, output)


def _report(summary: list[dict[str, Any]], output: Path) -> None:
    references = {
        (row["instance"], row["reference_type"], row["reference"]) for row in summary
    }
    lines = [
        "# M2 实验汇总（脚本生成）",
        "",
        "`gap`=(objective−best_bound)/max(1,|objective|)：相对**求解器自己的界**。",
        "`gap_to_reference`=(objective−reference)/max(1,|reference|)：相对**该实例的参考值**。",
        "启发式没有 bound，两者都为空，**不能当作 0**。",
        "",
        "## 实例参考值",
        "",
        "| 实例 | 参考类型 | 参考值 |",
        "|---|---|---:|",
    ]
    seen: set[str] = set()
    for instance, kind, value in sorted(references):
        if instance in seen:
            continue
        seen.add(instance)
        shown = "—" if value is None else f"{value:g}"
        lines.append(f"| {instance} | `{kind}` | {shown} |")
    lines += [
        "",
        "`optimum` 来自独立枚举，`proven_by_solver` 来自某个求解器在预算内的证明，",
        "`best-known` 只是本批见过的最好可行解——**不是最优性证书**。",
        "",
        "## 逐方法汇总",
        "",
        "| 实例 | 组 | 方法 | 成功/失败 | 已证明最优 | 均值 | 平均 gap | 平均 ref gap | 平均耗时(s) | 平均迭代 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        def fmt(value: Any, digits: int = 3) -> str:
            return "—" if value is None else f"{value:.{digits}f}"

        lines.append(
            f"| {row['instance']} | {row['group']} | {row['method']} | "
            f"{row['successful']}/{row['failed']} | {row['optimal_count']} | "
            f"{fmt(row['mean_objective'])} | {fmt(row['mean_gap'], 4)} | "
            f"{fmt(row['mean_gap_to_reference'], 4)} | "
            f"{fmt(row['mean_wall_time'], 3)} | {fmt(row['mean_iterations'], 1)} |"
        )
    lines += [
        "",
        "同一实例跨方法汇总。时间预算相同不代表实际耗时相同；",
        "`OPTIMAL` 只说明求解器证明了自己的模型最优，排程可行性另由独立验证器判定。",
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "month2.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "month2")
    args = parser.parse_args()
    rows = run(args.config, args.output)
    failed = sum(1 for r in rows if r["status"] in ("FAILED", "INVALID_SOLUTION"))
    print(f"runs={len(rows)}, failed={failed}, output={args.output.resolve()}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
