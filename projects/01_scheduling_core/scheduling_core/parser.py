"""把外部 JSON 数据解析成调度输入模型（Instance）。

只负责读取、结构、类型转换与缺失字段的默认值；
业务上的合法性判断（唯一性、引用完整性等）在 validation.py。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Instance, Job, Machine, Operation


def load_json_instance(path: str | Path) -> Instance:
    """从 JSON 文件读取并构造 Instance。"""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return _parse_instance(data)


def _parse_instance(data: dict[str, Any]) -> Instance:
    machines = tuple(
        Machine(id=item["id"], name=item["name"])
        for item in data["machines"]
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
            processing_time=int(item["processing_time"]),
            eligible_machine_ids=tuple(item["eligible_machine_ids"]),
        )
        for item in data["operations"]
    )

    return Instance(jobs=jobs, operations=operations, machines=machines)
