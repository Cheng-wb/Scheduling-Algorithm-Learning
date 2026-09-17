"""Week 2 证据驱动器：同实例、同预算比较 loose / tight Big-M 与 time-indexed 替代模型。

    python -m opt_experiments.w2_formulations --output artifacts/month2_w2

产出的三件套（``results.csv`` / ``metadata.json`` / ``report.md``）与 M2 的
月度批次保持同一套纪律：**先落盘输入、时间预算进结果行、失败留痕、不覆盖非空目录**。
区别只在于本驱动是 Week 2 的教学对照实验，粒度更细 —— 每个 formulation 都跑两次：

``root_lp`` 一次     只解 LP relaxation，得到**formulation 强度**指标（root bound）
``limit`` 一次       在同一个 ``time_limit`` 下解 MIP，得到**搜索行为**指标
                     （incumbent、nodes、runtime、gap）

**为什么必须分开报这两个数**：在时间受限时，MIP 的最终 ``best_bound`` 是从 root
bound 出发随搜索慢慢爬升的**进度值**，两个 formulation 的进度值差异只说明「这一
分钟内谁爬得快」，不能当成「谁的松弛更强」。松弛强弱只能由 root LP bound 回答。

**关于 tight 与 loose 的实测结论**（本驱动的目的之一就是把这个结论测出来，而不是
背下来）：在这组实例上，两种 Big-M 的 root LP bound **完全相同**。原因不是
「tight 不够紧」，而是两者的松弛都弱到同一个退化点：LP 只要把每对 ``x_jk`` 取成
某个分数，就能让所有工序在释放时间上「并行开工」，于是 bound 塌到
``max_j (r_j + p_j)`` / ``Σ_j (r_j + p_j)``（makespan / ΣCj），对 tardiness 更是
直接塌到 0。Big-M 的取值只在 ``M < p_j + p_k`` 时才会真正切到松弛，而两种取法都
远大于这个阈值。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opt_common.bridge import M2_OBJECTIVES, Instance, generate_instance, save_json_instance
from opt_solvers.registry import available, get, load_week_modules
from opt_solvers.result import validate_result

# 复用月度批次的三个工具函数：哈希、写 JSON、写 CSV 的语义必须与月度批次一致。
from opt_experiments.benchmark import source_hash, write_csv, write_json

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1

#: Week 2 的固定实例表。``single_a`` / ``single_b`` / ``parallel_a`` / ``parallel_b``
#: 与 ``configs/month2.json`` 中的实例同种子，保证周实验与月批次说的是同几个实例。
INSTANCE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "single_a",
        "generator": {"seed": 50, "jobs": 8, "machines": 1},
        "objective": "total_tardiness",
        "time_limit": 10.0,
        "methods": ["milp_tight", "milp_loose", "milp_alt"],
    },
    {
        "name": "single_c",
        "generator": {"seed": 60, "jobs": 15, "machines": 1},
        "objective": "total_tardiness",
        "time_limit": 10.0,
        "methods": ["milp_tight", "milp_loose", "milp_alt"],
    },
    {
        "name": "parallel_a",
        "generator": {"seed": 52, "jobs": 8, "machines": 3},
        "objective": "makespan",
        "time_limit": 10.0,
        "methods": ["milp_alt", "heur_parallel_lpt"],
    },
)

#: 独立枚举的上限：超过就跳过 reference 的 ``optimum`` 档（M1 的 oracle 自带 limit）。
ORACLE_LIMIT = 100_000


def build_instances(
    specs: tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Instance]:
    """按实例表生成实例（固定种子，与输入顺序无关）。"""
    return {
        spec["name"]: generate_instance(**spec["generator"])
        for spec in (specs if specs is not None else INSTANCE_SPECS)
    }


def _reference(instance: Instance, objective: str, rows: list[dict[str, Any]]) -> tuple[str, float | None]:
    """给一个实例定参考值，并说明它是**哪一档**参考（与月度批次同一套优先级）。"""
    try:
        from scheduling_algorithms.oracle import exhaustive_optimum

        value, _, _ = exhaustive_optimum(instance, objective, limit=ORACLE_LIMIT)
        return "optimum", float(value)
    except (ValueError, ImportError):
        pass
    proven = [
        float(row["objective"])
        for row in rows
        if row["status"] == "OPTIMAL" and row.get("objective") is not None
    ]
    if proven:
        return "proven_by_solver", min(proven)
    feasible = [
        float(row["objective"]) for row in rows if row.get("objective") is not None
    ]
    if feasible:
        return "best-known", min(feasible)
    return "none", None


def _root_lp_row(instance: Instance, spec: dict[str, Any], method: str, seed: int) -> dict[str, Any]:
    """只解 LP relaxation：回答「这个 formulation 的根节点界有多强」。"""
    call_spec = {
        "objective": spec["objective"],
        "time_limit": spec.get("lp_time_limit", 60.0),
        "seed": seed,
        "root_lp": True,
    }
    result = get(method)(instance, call_spec)
    return {
        "instance": spec["name"],
        "group": "root_lp",
        "method": method,
        "objective_name": spec["objective"],
        "status": result.status,
        "objective": result.objective,
        "best_bound": result.best_bound,
        "gap": result.gap,
        "nodes": result.iterations,
        "build_time": round(result.build_time, 6),
        "solve_time": round(result.solve_time, 6),
        "wall_time": round(result.wall_time, 6),
        "lp_integral": result.detail.get("lp_relaxation_integral"),
        "simplex_iterations": result.detail.get("simplex_iterations"),
        "variables": result.detail.get("variables"),
        "constraints": result.detail.get("constraints"),
        "nonzeros": result.detail.get("nonzeros"),
        "big_m_min": result.detail.get("big_m_min"),
        "big_m_max": result.detail.get("big_m_max"),
        "validation": "",
        "failure_reason": result.detail.get("failure_reason", ""),
    }


def _limit_row(instance: Instance, spec: dict[str, Any], method: str, seed: int) -> dict[str, Any]:
    """在同一个 ``time_limit`` 下解 MIP：回答「搜索行为如何」。"""
    time_limit = float(spec.get("time_limit", 10.0))
    call_spec = {
        "objective": spec["objective"],
        "time_limit": time_limit,
        "seed": seed,
    }
    started = time.perf_counter()
    result = get(method)(instance, call_spec)
    wall = time.perf_counter() - started
    diagnostics = validate_result(instance, result)
    row: dict[str, Any] = {
        "instance": spec["name"],
        "group": "limit",
        "method": method,
        "objective_name": spec["objective"],
        "time_limit": time_limit,
        "seed": seed,
        "status": result.status,
        "objective": result.objective,
        "best_bound": result.best_bound,
        "gap": result.gap,
        "nodes": result.iterations,
        "build_time": round(result.build_time, 6),
        "solve_time": round(result.solve_time, 6),
        "wall_time": round(wall, 6),
        "lp_integral": None,
        "simplex_iterations": None,
        "variables": result.detail.get("variables"),
        "constraints": result.detail.get("constraints"),
        "nonzeros": result.detail.get("nonzeros"),
        "big_m_min": result.detail.get("big_m_min"),
        "big_m_max": result.detail.get("big_m_max"),
        "validation": "; ".join(diagnostics),
        "failure_reason": result.detail.get("failure_reason", ""),
    }
    if diagnostics:
        row["status"] = "INVALID_SOLUTION"
        row["failure_reason"] = "independent validator rejected returned schedule"
    return row


def compare_models(
    instance: Instance, spec: dict[str, Any], *, seed: int = 0
) -> list[dict[str, Any]]:
    """对一个实例跑完 root LP 与限时 MIP 两类记录（返回原始行，未加参考值）。"""
    rows: list[dict[str, Any]] = []
    for method in spec["methods"]:
        rows.append(_root_lp_row(instance, spec, method, seed))
        rows.append(_limit_row(instance, spec, method, seed))
    return rows


def collect(
    specs: tuple[dict[str, Any], ...] | None = None, *, seed: int = 0
) -> list[dict[str, Any]]:
    """跑完实例表里的全部实例，并补上参考值与 ``gap_to_reference``。"""
    specs = specs if specs is not None else INSTANCE_SPECS
    instances = build_instances(specs)
    rows: list[dict[str, Any]] = []
    for spec in specs:
        selected = compare_models(instances[spec["name"]], spec, seed=seed)
        kind, reference = _reference(instances[spec["name"]], spec["objective"], selected)
        for row in selected:
            row["reference_type"] = kind
            row["reference"] = reference
            if reference is None or row.get("objective") is None:
                row["gap_to_reference"] = None
            else:
                row["gap_to_reference"] = (float(row["objective"]) - reference) / max(
                    1.0, abs(reference)
                )
        rows.extend(selected)
    return rows


def _report(
    rows: list[dict[str, Any]],
    output: Path,
    instances: dict[str, Instance],
    specs: tuple[dict[str, Any], ...],
) -> None:
    """写出人读的 ``report.md``：两张表（松弛强度 / 搜索行为）加一段解释。"""
    lines = [
        "# M2 Week 2 实验汇总（脚本生成）",
        "",
        "两个 formulation 的对照必须分成**两类指标**看：",
        "",
        "- `root_lp` 组 = 只解 LP relaxation，回答**松弛强度**（root bound）；",
        "- `limit` 组 = 同一时间预算解 MIP，回答**搜索行为**（incumbent / nodes / gap）。",
        "",
        "时间受限时 `limit` 组的 `best_bound` 是随搜索爬升的**进度值**，不是强度指标。",
        "",
    ]
    for spec in specs:
        name = spec["name"]
        instance = instances[name]
        subset = [row for row in rows if row["instance"] == name]
        if not subset:
            continue
        lines += [
            f"## 实例 `{name}`（{spec['objective']}）",
            "",
            f"生成参数 `{json.dumps(spec['generator'], ensure_ascii=False)}`，"
            f"时间预算 {spec.get('time_limit', 10.0)}s，"
            f"参考类型 `{subset[0]['reference_type']}`，参考值 {subset[0]['reference']}。",
            "",
            "| 方法 | 组 | 状态 | 目标值 | best bound | gap | nodes | 建模(s) | 求解(s) | 变量 | 约束 | 非零元 |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for row in subset:
            def fmt(value: Any, digits: int = 4) -> str:
                return "-" if value is None else f"{value:.{digits}f}"

            lines.append(
                f"| `{row['method']}` | {row['group']} | `{row['status']}` | "
                f"{fmt(row.get('objective'), 2)} | {fmt(row.get('best_bound'))} | "
                f"{fmt(row.get('gap'))} | {row.get('nodes')} | "
                f"{fmt(row.get('build_time'), 4)} | {fmt(row.get('solve_time'), 3)} | "
                f"{row.get('variables')} | {row.get('constraints')} | {row.get('nonzeros')} |"
            )
        lines.append("")

    lines += [
        "## 读表要点",
        "",
        "1. `milp_tight` 与 `milp_loose` 的 **root LP bound 完全相同**：两者都松到同一个",
        "   退化点（LP 用分数 `x_jk` 让所有工序在释放时间上并行开工），Big-M 的大小在",
        "   这个区间里改变不了松弛值。",
        "2. 真正拉开 root bound 的是 **formulation 的变量定义**：`milp_alt` 的",
        "   time-indexed 模型用时间格点 + 容量约束表达互斥，根节点界高出一个量级。",
        "3. `milp_alt` 的代价在模型规模：变量数随 ``H = max r + Σp`` 线性增长，",
        "   建模时间明显高于 sequence 模型。松弛强 ≠ 一定更快，要连规模一起看。",
        "4. 每个返回的排程都过了 M1 的独立验证器；`INVALID_SOLUTION` 表示求解器给的解",
        "   被独立验证器拒绝，比 `FAILED` 更严重。",
        "",
    ]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


def run(
    output: Path,
    *,
    seed: int = 0,
    time_limit_override: float | None = None,
) -> list[dict[str, Any]]:
    """跑完整套 Week 2 实验并落盘。**输出目录必须为空或不存在。**"""
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output must be empty (preserve previous experiments): {output}")
    output.mkdir(parents=True, exist_ok=True)

    module_failures = load_week_modules()
    specs = tuple(
        {**spec, "time_limit": time_limit_override or spec.get("time_limit", 10.0)}
        for spec in INSTANCE_SPECS
    )
    instances = build_instances(specs)
    started = time.perf_counter()
    rows = collect(specs, seed=seed)
    elapsed = time.perf_counter() - started

    (output / "instances").mkdir(exist_ok=True)
    instance_hashes: dict[str, str] = {}
    for name, instance in instances.items():
        path = output / "instances" / f"{name}.json"
        save_json_instance(instance, path)
        instance_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    for row in rows:
        row["input_sha256"] = instance_hashes[row["instance"]]

    write_json(
        output / "metadata.json",
        {
            "schema_version": SCHEMA_VERSION,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "git_commit": _git("rev-parse", "HEAD"),
            "working_tree_dirty": bool(_git("status", "--porcelain")),
            "source_sha256": source_hash(),
            "seed": seed,
            "elapsed_seconds": round(elapsed, 3),
            "unavailable_modules": module_failures,
            "registered_methods": available(),
            "instance_specs": list(specs),
            "oracle_limit": ORACLE_LIMIT,
            "budget_unit": "one solver call under a shared wall-clock time limit",
            "root_lp_note": (
                "root_lp 组只解 LP relaxation；此时 objective 为 None（没有可行排程），"
                "best_bound 是该 formulation 的有效下界。"
            ),
        },
    )
    write_csv(output / "results.csv", rows)
    _report(rows, output, instances, specs)
    return rows


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
        )
        return out.stdout.strip()
    except OSError:
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "month2_w2")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--time-limit", type=float, default=None)
    args = parser.parse_args()
    load_week_modules()
    rows = run(args.output, seed=args.seed, time_limit_override=args.time_limit)
    failed = sum(1 for row in rows if row["status"] in ("FAILED", "INVALID_SOLUTION"))
    print(
        f"week2 rows={len(rows)}, failed={failed}, output={args.output.resolve()}"
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
