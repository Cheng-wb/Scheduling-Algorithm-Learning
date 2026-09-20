"""M3 Week 1 的甘特/瓶颈驱动：把四个实例的排程导出成 CSV 与控制台报表。

    python -m fjsp_experiments.week1_gantt --output artifacts/month3_w1

为什么需要这个驱动：Day 6 的实验脚本要**落盘**甘特 CSV，而示例脚本本身只打印不写盘
（Week 1 的规矩）。写盘这件事集中在这里，并且沿用 M2 批次的那条顺序纪律：

**版本状态必须在创建输出目录之前捕获。** 否则写进输出目录的文件会被 git 当成
未跟踪文件，``working_tree_dirty`` 就恒为 True、这个标记也就废了。

输出的三个东西：

```text
metadata.json        创建时间、python/平台、git 提交、工作区是否干净、源码哈希
gantt_<实例>.csv     六列：machine_id, job_id, operation_id, start_time, end_time, duration
summary.json         每个实例的方法、状态、目标值、界、机器负载与瓶颈机器
```

输出目录默认是 ``artifacts/month3_w1``（Week 1 自己的目录）。
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

from fjsp_core.models import FJSPInstance
from fjsp_core.result import validate_result
from fjsp_io.generator import generate_instance
from fjsp_shop.gantt import machine_load_summary, to_gantt_rows, write_gantt_csv
from fjsp_shop.jsp import jsp_cpsat, jsp_priority
from fjsp_shop.flowshop import flow_johnson, flow_neh

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts" / "month3_w1"
TIME_LIMIT = 30.0

# configs/month3.json 里 Week 1 关注的四个实例（与 Day 5 用同一套参数）
INSTANCES = (
    ("flow_5x3", dict(seed=100, jobs=5, machines=3, operations_per_job=3,
                      flow_shop=True, flexibility=1),
     ("flow_johnson", "flow_neh", "jsp_priority", "jsp_cpsat")),
    ("flow_8x4", dict(seed=101, jobs=8, machines=4, operations_per_job=4,
                      flow_shop=True, flexibility=1),
     ("flow_johnson", "flow_neh", "jsp_priority", "jsp_cpsat")),
    ("jsp_6x4", dict(seed=102, jobs=6, machines=4, operations_per_job=3, flexibility=1),
     ("jsp_priority", "jsp_cpsat")),
    ("jsp_8x5", dict(seed=103, jobs=8, machines=5, operations_per_job=4, flexibility=1),
     ("jsp_priority", "jsp_cpsat")),
)

METHODS = {
    "flow_johnson": lambda instance: flow_johnson(instance, {"objective": "makespan"}),
    "flow_neh": lambda instance: flow_neh(instance, {"objective": "makespan"}),
    "jsp_priority": lambda instance: jsp_priority(
        instance, {"objective": "makespan", "priority": "mwr"}
    ),
    "jsp_cpsat": lambda instance: jsp_cpsat(
        instance, {"objective": "makespan", "time_limit": TIME_LIMIT, "seed": 0}
    ),
}


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
        )
        return out.stdout.strip()
    except OSError:
        return ""


def git_state() -> dict[str, Any]:
    """必须在创建输出目录之前调用 —— 否则 dirty 标记会被自己写出的文件污染。"""
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "working_tree_dirty": bool(_git("status", "--porcelain")),
    }


def source_hash() -> str:
    """``fjsp_core`` / ``fjsp_shop`` / ``fjsp_io`` 三个包的全部 .py 内容哈希。"""
    digest = hashlib.sha256()
    for package in ("fjsp_core", "fjsp_shop", "fjsp_io"):
        base = ROOT / package
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
    return digest.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )


def solve_one(instance: FJSPInstance, method_name: str) -> dict[str, Any]:
    """跑一个方法并把结果压成一行可落盘的记录。"""
    started = time.perf_counter()
    result = METHODS[method_name](instance)
    wall = time.perf_counter() - started
    row: dict[str, Any] = {
        "method": method_name,
        "status": result.status,
        "objective": result.objective,
        "best_bound": result.best_bound,
        "gap": result.gap,
        "solve_time": result.solve_time,
        "wall_time": wall,
        "failure_reason": result.detail.get("failure_reason"),
    }
    if result.schedule is None:
        row["validation"] = "no schedule"
        return row

    validate_result(instance, result)
    loads = machine_load_summary(instance, result.schedule)
    bottleneck = loads[0]
    row.update(
        {
            "validation": "ok",
            "breakdown": dict(result.breakdown),
            "bottleneck_machine": bottleneck["machine_id"],
            "bottleneck_busy_time": bottleneck["busy_time"],
            "bottleneck_utilization": bottleneck["utilization"],
            "machine_loads": [
                {
                    "machine_id": item["machine_id"],
                    "operation_count": item["operation_count"],
                    "busy_time": item["busy_time"],
                    "utilization": item["utilization"],
                    "sequence": list(item["sequence"]),
                }
                for item in loads
            ],
            "gantt_rows": [dict(item) for item in to_gantt_rows(instance, result.schedule)],
        }
    )
    return row


def run(output: Path | None = None) -> dict[str, Any]:
    """跑四个实例，落盘甘特 CSV 与汇总，返回汇总字典。"""
    target = Path(output) if output is not None else DEFAULT_OUTPUT
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"输出目录必须是空的（保留上一次实验）：{target}")

    # --- 版本状态：必须在创建输出目录之前 --------------------------------
    state = git_state()
    digest = source_hash()

    target.mkdir(parents=True, exist_ok=True)
    write_json(
        target / "metadata.json",
        {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            **state,
            "source_sha256": digest,
            "time_limit_seconds": TIME_LIMIT,
            "instances": [name for name, _, _ in INSTANCES],
        },
    )

    summary: dict[str, Any] = {"instances": {}}
    for name, spec, method_names in INSTANCES:
        instance = generate_instance(**spec)
        rows = [solve_one(instance, method_name) for method_name in method_names]
        summary["instances"][name] = {"generator": spec, "runs": rows}
        # 甘特 CSV 只用最优的那个来源：CP-SAT 结果（保证与其他方法同实例可比）
        best = next((row for row in rows if row["method"] == "jsp_cpsat"), rows[-1])
        if best.get("gantt_rows"):
            write_gantt_csv(
                best["gantt_rows"], target / f"gantt_{name}.csv"
            )
    write_json(target / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Week 1 甘特与瓶颈导出")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = run(args.output)
    print(f"输出目录：{args.output}")
    for name, block in summary["instances"].items():
        for row in block["runs"]:
            bound = "-" if row["best_bound"] is None else f"{row['best_bound']:.0f}"
            objective = "-" if row["objective"] is None else f"{row['objective']:.0f}"
            print(f"  {name:10s} {row['method']:14s} {row['status']:9s} "
                  f"目标值 {objective:>6s} 界 {bound:>6s} "
                  f"瓶颈机 {row.get('bottleneck_machine', '-')}")


if __name__ == "__main__":
    main()
