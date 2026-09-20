"""JSON 输入输出：实例 ↔ 文件。

**为什么保存实例而不是只保存种子？** 种子只能复现「当时的生成器实现」。生成器
一改，同一个种子就指向另一个实例，而旧实验记录会静默地失去意义。保存实例本身
（并记录它的 SHA-256）才是可审计的证据——M1/M2 的同一条纪律。

读回时**逐字段重建 dataclass**，把 JSON 的 list 还原成 tuple，否则
``frozen=True`` 的不可变契约会被悄悄破坏（list 是可变对象）。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fjsp_core.models import (
    Calendar,
    FJSPInstance,
    Job,
    Machine,
    Maintenance,
    Operation,
    Qualification,
    Schedule,
    ScheduledOperation,
    Setup,
    Worker,
)


def _instance_from_dict(data: dict[str, Any]) -> FJSPInstance:
    def pairs(values: list[list[Any]]) -> tuple[tuple[str, int], ...]:
        return tuple((str(machine), int(minutes)) for machine, minutes in values)

    def windows(values: list[list[int]]) -> tuple[tuple[int, int], ...]:
        return tuple((int(start), int(end)) for start, end in values)

    return FJSPInstance(
        jobs=tuple(
            Job(
                id=item["id"],
                operation_ids=tuple(item["operation_ids"]),
                release_time=int(item.get("release_time", 0)),
                due_date=None if item.get("due_date") is None else int(item["due_date"]),
                weight=float(item.get("weight", 1.0)),
                priority=int(item.get("priority", 0)),
            )
            for item in data["jobs"]
        ),
        operations=tuple(
            Operation(
                id=item["id"],
                job_id=item["job_id"],
                position=int(item["position"]),
                machine_times=pairs(item["machine_times"]),
                family=item.get("family"),
                locked_machine_id=item.get("locked_machine_id"),
                locked_start=(
                    None if item.get("locked_start") is None else int(item["locked_start"])
                ),
            )
            for item in data["operations"]
        ),
        machines=tuple(
            Machine(
                id=item["id"],
                name=item["name"],
                calendar_id=item.get("calendar_id"),
                group=item.get("group"),
            )
            for item in data["machines"]
        ),
        calendars=tuple(
            Calendar(id=item["id"], windows=windows(item.get("windows", [])))
            for item in data.get("calendars", [])
        ),
        maintenances=tuple(
            Maintenance(
                id=item["id"],
                machine_id=item["machine_id"],
                windows=windows(item["windows"]),
            )
            for item in data.get("maintenances", [])
        ),
        qualifications=tuple(
            Qualification(machine_id=item["machine_id"], family=item["family"])
            for item in data.get("qualifications", [])
        ),
        workers=tuple(
            Worker(
                id=item["id"],
                name=item["name"],
                machine_ids=tuple(item.get("machine_ids", [])),
                capacity=int(item.get("capacity", 1)),
            )
            for item in data.get("workers", [])
        ),
        setups=tuple(
            Setup(
                from_family=item["from_family"],
                to_family=item["to_family"],
                minutes=int(item["minutes"]),
            )
            for item in data.get("setups", [])
        ),
        meta=dict(data.get("meta", {})),
    )


def load_json_instance(path: str | Path) -> FJSPInstance:
    """从 JSON 文件读取并构造 :class:`FJSPInstance`。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return _instance_from_dict(data)


def save_json_instance(instance: FJSPInstance, path: str | Path) -> None:
    """写出实例。``ensure_ascii=False`` 让中文机器名不被转义，``indent=2`` 便于 diff。"""
    Path(path).write_text(
        json.dumps(asdict(instance), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def schedule_to_dict(schedule: Schedule) -> dict[str, Any]:
    return {
        "operations": [
            {
                "operation_id": item.operation_id,
                "machine_id": item.machine_id,
                "start_time": item.start_time,
                "end_time": item.end_time,
                "worker_id": item.worker_id,
            }
            for item in schedule.operations
        ]
    }


def schedule_from_dict(data: dict[str, Any]) -> Schedule:
    return Schedule(
        tuple(
            ScheduledOperation(
                operation_id=item["operation_id"],
                machine_id=item["machine_id"],
                start_time=int(item["start_time"]),
                end_time=int(item["end_time"]),
                worker_id=item.get("worker_id"),
            )
            for item in data["operations"]
        )
    )
