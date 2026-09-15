"""python -m scheduling_experiments.benchmark --config configs/month1.json。"""

import argparse
import csv
import hashlib
import json
import platform
import statistics
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scheduling_io.generator import generate_instance
from scheduling_algorithms.oracle import exhaustive_optimum
from scheduling_io.parser import save_json_instance
from scheduling_algorithms.search import ALGORITHMS, SearchConfig, solve

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def source_hash() -> str:
    digest = hashlib.sha256()
    for package in (
        "scheduling_core",
        "scheduling_algorithms",
        "scheduling_io",
        "scheduling_experiments",
    ):
        for path in sorted((ROOT / package).rglob("*.py")):
            digest.update(path.relative_to(ROOT).as_posix().encode())
            # Normalize line endings across Windows/Linux checkouts.
            digest.update(path.read_text(encoding="utf-8").encode("utf-8"))
    return digest.hexdigest()


def run(config_path: Path, output: Path) -> list[dict[str, Any]]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if output.exists() and any(output.iterdir()):
        raise ValueError(
            f"output must be empty (preserve previous experiments): {output}"
        )
    output.mkdir(parents=True, exist_ok=True)
    (output / "instances").mkdir()
    (output / "runs").mkdir()
    write_json(output / "config.json", config)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    write_json(
        output / "metadata.json",
        {
            "schema_version": 1,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "git_commit": commit.stdout.strip(),
            "working_tree_dirty": bool(dirty.stdout.strip()),
            "source_sha256": source_hash(),
            "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
            "budget_unit": "full decode + validate + objective, including initialization and rejection",
        },
    )
    rows = []
    trajectories = {}
    for spec in config["instances"]:
        name = spec["name"]
        if not name.replace("_", "").isalnum():
            raise ValueError("instance name must be alphanumeric/underscore")
        instance = generate_instance(**spec["generator"])
        path = output / "instances" / f"{name}.json"
        save_json_instance(instance, path)
        input_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        optimum = (
            exhaustive_optimum(instance, spec["objective"])[0]
            if spec.get("exact", False)
            else None
        )
        variants: list[tuple[str, str, dict[str, Any]]] = [
            ("main", algorithm, {})
            for algorithm in config.get("algorithms", ALGORITHMS)
        ]
        variants += [
            (f"sa_t{item['temperature']}_c{item['cooling']}", "sa", item)
            for item in config.get("sensitivity", [])
        ]
        for group, algorithm, parameters in variants:
            for seed in config["seeds"]:
                run_id = f"{name}__{group}__{algorithm}__{seed}"
                settings = SearchConfig(
                    algorithm=algorithm,
                    objective=spec["objective"],
                    seed=seed,
                    **(config["search"] | parameters),
                )
                row = {
                    "run_id": run_id,
                    "instance": name,
                    "input_sha256": input_hash,
                    "group": group,
                    "algorithm": algorithm,
                    "seed": seed,
                    "objective_name": settings.objective,
                    "budget": settings.budget,
                    "temperature": settings.temperature,
                    "cooling": settings.cooling,
                    "status": "FAILED",
                    "objective": None,
                    "evaluations": 0,
                    "elapsed_seconds": None,
                    "reference_type": (
                        "optimum" if optimum is not None else "best-known"
                    ),
                    "reference": optimum,
                    "gap": None,
                    "failure_reason": "",
                }
                try:
                    result = solve(instance, settings)
                    row.update(
                        status=result.status,
                        objective=result.objective,
                        evaluations=result.evaluations,
                        elapsed_seconds=result.elapsed_seconds,
                    )
                    write_json(
                        output / "runs" / f"{run_id}.json",
                        {
                            "config": asdict(settings),
                            "candidate": asdict(result.candidate),
                            "schedule": asdict(result.schedule),
                        },
                    )
                    write_csv(
                        output / "runs" / f"{run_id}.trace.csv",
                        [asdict(point) for point in result.trace],
                    )
                    trajectories[run_id] = result.trace
                except Exception as exc:  # 单次失败留痕，批次继续；CLI 最终非零退出。
                    row["failure_reason"] = f"{type(exc).__name__}: {exc}"
                rows.append(row)
    for row in rows:
        if row["reference"] is None:
            scores = [
                other["objective"]
                for other in rows
                if other["instance"] == row["instance"]
                and other["objective"] is not None
            ]
            row["reference"] = min(scores) if scores else None
        reference = row["reference"]
        if reference is not None and row["objective"] is not None:
            row["gap"] = (row["objective"] - reference) / max(1.0, abs(reference))
    write_csv(output / "results.csv", rows)
    write_json(
        output / "failures.json", [row for row in rows if row["status"] == "FAILED"]
    )
    summarize(rows, output, trajectories)
    return rows


def summarize(
    rows: list[dict[str, Any]], output: Path, trajectories: dict[str, Any]
) -> None:
    summaries = []
    for instance, group, algorithm in sorted(
        {(row["instance"], row["group"], row["algorithm"]) for row in rows}
    ):
        selected = [
            row
            for row in rows
            if (row["instance"], row["group"], row["algorithm"])
            == (instance, group, algorithm)
        ]
        good = [row for row in selected if row["objective"] is not None]
        scores = [row["objective"] for row in good]
        summaries.append(
            {
                "instance": instance,
                "group": group,
                "algorithm": algorithm,
                "successful": len(good),
                "failed": len(selected) - len(good),
                "mean": statistics.mean(scores) if scores else None,
                "median": statistics.median(scores) if scores else None,
                "stdev": statistics.stdev(scores) if len(scores) > 1 else 0.0,
                "best": min(scores) if scores else None,
                "mean_gap": (
                    statistics.mean(row["gap"] for row in good) if good else None
                ),
                "mean_evaluations": (
                    statistics.mean(row["evaluations"] for row in good)
                    if good
                    else None
                ),
                "mean_seconds": (
                    statistics.mean(row["elapsed_seconds"] for row in good)
                    if good
                    else None
                ),
            }
        )
    write_csv(output / "summary.csv", summaries)
    lines = [
        "# 实验汇总（脚本生成）",
        "",
        "gap=(value-reference)/max(1,abs(reference))；最小化。参考为零时是绝对差，不是百分比。",
        "",
        "| 实例 | 组 | 算法 | 成功/失败 | 均值 | 标准差 | 最好 | 平均 gap | 平均评价数 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in summaries:
        lines.append(
            f"| {item['instance']} | {item['group']} | {item['algorithm']} | {item['successful']}/{item['failed']} | {item['mean']} | {item['stdev']:.3f} | {item['best']} | {item['mean_gap']} | {item['mean_evaluations']} |"
        )
    lines += [
        "",
        "同一实例跨种子汇总；不把不同目标的原始值求平均。LPT 只评价一次，LS 可提前停机；预算是共同上限。",
        "",
        "图表：quality.png、convergence.png、gantt.png。敏感性结果单独按组列出，不算独立新算法。",
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    plot(rows, output, trajectories)


def plot(
    rows: list[dict[str, Any]], output: Path, trajectories: dict[str, Any]
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    main = [
        row for row in rows if row["group"] == "main" and row["objective"] is not None
    ]
    if not main:
        return
    fig, ax = plt.subplots(figsize=(9, 4))
    algorithms = sorted({row["algorithm"] for row in main})
    ax.boxplot(
        [
            [row["gap"] for row in main if row["algorithm"] == algorithm]
            for algorithm in algorithms
        ],
        tick_labels=algorithms,
    )
    ax.set(
        ylabel="Normalized reference gap",
        title="Mixed instances: descriptive distribution (not significance)",
    )
    fig.tight_layout()
    fig.savefig(output / "quality.png", dpi=140)
    plt.close(fig)
    selected_instance = main[-1]["instance"]
    seed = main[0]["seed"]
    fig, ax = plt.subplots(figsize=(9, 4))
    for row in main:
        if row["instance"] == selected_instance and row["seed"] == seed:
            trace = trajectories[row["run_id"]]
            ax.step(
                [point.evaluation for point in trace],
                [point.best for point in trace],
                where="post",
                marker="." if len(trace) == 1 else None,
                label=row["algorithm"],
            )
    ax.set(
        xlabel="Evaluations",
        ylabel="Best objective",
        title=f"{selected_instance}, seed={seed}",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "convergence.png", dpi=140)
    plt.close(fig)
    selected = min(
        (row for row in main if row["instance"] == selected_instance),
        key=lambda row: row["objective"],
    )
    schedule = json.loads(
        (output / "runs" / f"{selected['run_id']}.json").read_text(encoding="utf-8")
    )["schedule"]["operations"]
    machines = sorted({item["machine_id"] for item in schedule})
    job_ids = sorted({item["operation_id"].split("_")[0] for item in schedule})
    fig, ax = plt.subplots(figsize=(11, 4))
    for i, item in enumerate(schedule):
        y = machines.index(item["machine_id"])
        ax.barh(
            y,
            item["end_time"] - item["start_time"],
            left=item["start_time"],
            color=f"C{job_ids.index(item['operation_id'].split('_')[0]) % 10}",
            edgecolor="white",
        )
        ax.text(
            (item["start_time"] + item["end_time"]) / 2,
            y,
            item["operation_id"].replace("_", "\n"),
            ha="center",
            va="center",
            fontsize=6,
        )
    ax.set(
        yticks=range(len(machines)),
        yticklabels=machines,
        xlabel="Time",
        title=selected["run_id"],
    )
    fig.tight_layout()
    fig.savefig(output / "gantt.png", dpi=140)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "month1.json")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts" / "month1_refactored"
    )
    args = parser.parse_args()
    rows = run(args.config, args.output)
    failed = sum(row["status"] == "FAILED" for row in rows)
    print(f"runs={len(rows)}, failed={failed}, output={args.output.resolve()}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
