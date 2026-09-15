"""把外部 JSON 数据解析成调度输入模型（Instance）。

只负责读取、结构、类型转换与缺失字段的默认值；
业务上的合法性判断（唯一性、引用完整性等）在 validation.py。
"""

from __future__ import annotations

import json
import csv
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scheduling_core.models import Instance, Job, Machine, Operation


def load_json_instance(path: str | Path) -> Instance:
    """从 JSON 文件读取并构造 Instance。"""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return _parse_instance(data)


def _parse_instance(data: dict[str, Any]) -> Instance:
    machines = tuple(
        Machine(id=item["id"], name=item["name"]) for item in data["machines"]
    )

    jobs = tuple(
        Job(
            id=item["id"],
            operation_ids=tuple(item["operation_ids"]),
            release_time=item.get("release_time", 0),
            due_date=item.get("due_date"),
            weight=float(item.get("weight", 1.0)),
        )
        for item in data["jobs"]
    )

    operations = tuple(
        Operation(
            id=item["id"],
            job_id=item["job_id"],
            processing_time=item["processing_time"],
            eligible_machine_ids=tuple(item["eligible_machine_ids"]),
        )
        for item in data["operations"]
    )

    return Instance(jobs=jobs, operations=operations, machines=machines)


def save_json_instance(instance: Instance, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(asdict(instance), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_csv_instance(directory: str | Path) -> Instance:
    """读取 machines/jobs/operations.csv；列表列使用 |，空交期为 None。"""
    root = Path(directory)

    def rows(name: str) -> list[dict[str, Any]]:
        with (root / name).open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    jobs = rows("jobs.csv")
    operations = rows("operations.csv")
    for job in jobs:
        job["operation_ids"] = job["operation_ids"].split("|")
        job["release_time"] = int(job.get("release_time") or 0)
        job["due_date"] = int(job["due_date"]) if job.get("due_date") else None
        job["weight"] = float(job.get("weight") or 1)
    for op in operations:
        op["eligible_machine_ids"] = op["eligible_machine_ids"].split("|")
        op["processing_time"] = int(op["processing_time"])
    return _parse_instance(
        {"machines": rows("machines.csv"), "jobs": jobs, "operations": operations}
    )
