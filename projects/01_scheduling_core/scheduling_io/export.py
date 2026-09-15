"""把 Schedule 导出为适合 Gantt 图的结构化数据与 CSV。

Gantt rows 是「展示/导出格式」，与领域结果 Schedule 分离：
Schedule 只存 machine_id / operation_id / start / end，job_id 由 instance 反查。
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from scheduling_core.models import Instance
from scheduling_core.schedule import Schedule

GANTT_FIELDS = (
    "machine_id",
    "job_id",
    "operation_id",
    "start_time",
    "end_time",
    "duration",
)


def to_gantt_rows(
    instance: Instance,
    schedule: Schedule,
) -> list[dict[str, Any]]:
    """把 Schedule 转成六字段 Gantt 行，按 (machine_id, start_time, operation_id) 排序。

    排序让输出确定且便于人工查看与 diff，而不是依赖算法内部的决策顺序。
    """
    operation_by_id = {op.id: op for op in instance.operations}

    rows: list[dict[str, Any]] = []

    for item in schedule.operations:
        operation = operation_by_id[item.operation_id]

        rows.append(
            {
                "machine_id": item.machine_id,
                "job_id": operation.job_id,
                "operation_id": item.operation_id,
                "start_time": item.start_time,
                "end_time": item.end_time,
                "duration": item.end_time - item.start_time,
            }
        )

    return sorted(
        rows,
        key=lambda row: (
            row["machine_id"],
            row["start_time"],
            row["operation_id"],
        ),
    )


def write_gantt_csv(
    rows: list[dict[str, Any]],
    path: str | Path,
) -> None:
    """把 Gantt 行写成 CSV，列顺序固定为 GANTT_FIELDS。"""
    path = Path(path)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=GANTT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
