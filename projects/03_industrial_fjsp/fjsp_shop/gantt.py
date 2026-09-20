"""甘特图导出：把排程翻译成**展示模型**，与领域模型严格分开。

**为什么要有这一层？** ``Schedule`` 是领域模型：不可变、最小、只含结果字段
（``operation_id`` / ``machine_id`` / ``start_time`` / ``end_time``）。它故意不存
``job_id``、不存 ``duration``、不保证任何顺序 —— 那些都是「给人和报表看」的信息。
甘特图要的正好是这些派生字段，所以单独定义一个宽表：

```text
机器轴    machine_id
订单轴    job_id        —— 由 operation_id 反查 instance.operations 得到
工序      operation_id
时间      start_time / end_time
长度      duration = end_time - start_time
```

三条设计约定：

1. **六字段固定**，顺序即 ``GANTT_FIELDS``；``duration`` 是派生值，不是新信息；
2. **按 ``(machine_id, start_time, operation_id)`` 排序**：算法内部的决策顺序与展示顺序
   无关，排序让输出确定、便于人工查看与 diff（与 M1 的 ``to_gantt_rows`` 同一条约定）；
3. **``Schedule`` 负责「正确」，甘特行负责「好看」**：两者不互相污染 ——
   往 ``Schedule`` 里塞 ``job_id`` 会让它不再是最小结果表示，
   让甘特行参与求解则会把它变成第二份会被改坏的状态。

模块里还带一个 ASCII 时间轴（``render_ascii_gantt``）与一个机器负载表
（``machine_load_summary``）—— 后者是 Week 1 Day 6「瓶颈分析」的数据来源。
ASCII 输出只用数字与 ``.``，不含任何非 GBK 字符。
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from fjsp_core.models import FJSPInstance, Schedule

#: 甘特行的固定六字段。顺序就是 CSV 的列顺序。
GANTT_FIELDS = ("machine_id", "job_id", "operation_id", "start_time", "end_time", "duration")

#: 排序键：机器 → 开工时刻 → 工序 id。三项齐全才保证全序、可 diff。
GANTT_SORT_KEYS = ("machine_id", "start_time", "operation_id")


def to_gantt_rows(instance: FJSPInstance, schedule: Schedule) -> list[dict[str, Any]]:
    """排程 → 六字段甘特行（已排序）。``job_id`` 由 ``operation_id`` 反查。"""
    job_of = {operation.id: operation.job_id for operation in instance.operations}
    rows: list[dict[str, Any]] = []
    for item in schedule.operations:
        if item.operation_id not in job_of:
            raise ValueError(f"未知工序，无法反查 job_id：{item.operation_id!r}")
        rows.append(
            {
                "machine_id": item.machine_id,
                "job_id": job_of[item.operation_id],
                "operation_id": item.operation_id,
                "start_time": int(item.start_time),
                "end_time": int(item.end_time),
                "duration": int(item.end_time) - int(item.start_time),
            }
        )
    rows.sort(key=lambda row: tuple(row[key] for key in GANTT_SORT_KEYS))
    return rows


def write_gantt_csv(rows: list[dict[str, Any]], path: str | Path) -> None:
    """按固定六列写出 CSV。``newline=""`` 避免 Windows 下的空行，``utf-8`` 保证中文可读。"""
    target = Path(path)
    if target.parent and not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(GANTT_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in GANTT_FIELDS})


def machine_load_summary(instance: FJSPInstance, schedule: Schedule) -> list[dict[str, Any]]:
    """每台机器的负载画像 —— 瓶颈分析的第一张表。

    ``utilization`` 的分母是该排程的 makespan（不是机器自己的 span）：
    「这台机器占用了整段工期里的百分之多少」。``load_share`` 的分母是所有机器的
    忙碌时间之和，回答「瓶颈是不是被某一台机器独占」。
    """
    makespan = max((item.end_time for item in schedule.operations), default=0)
    total_busy = sum(item.end_time - item.start_time for item in schedule.operations) or 1
    summary: list[dict[str, Any]] = []
    for machine in instance.machines:
        items = sorted(
            (item for item in schedule.operations if item.machine_id == machine.id),
            key=lambda item: (item.start_time, item.operation_id),
        )
        busy = sum(item.end_time - item.start_time for item in items)
        first = items[0].start_time if items else 0
        last = items[-1].end_time if items else 0
        span = last - first
        summary.append(
            {
                "machine_id": machine.id,
                "operation_count": len(items),
                "busy_time": busy,
                "span": span,
                "idle_in_span": span - busy,
                "utilization": round(busy / makespan, 4) if makespan else 0.0,
                "load_share": round(busy / total_busy, 4),
                "sequence": [item.operation_id for item in items],
            }
        )
    summary.sort(key=lambda row: (-row["busy_time"], row["machine_id"]))
    return summary


def render_ascii_gantt(
    instance: FJSPInstance, schedule: Schedule, *, width: int = 60
) -> list[str]:
    """把排程画成文本时间轴：一个字符 = 一个时间格，数字是订单序号，``.`` 是空闲。

    只用 ASCII（数字 / ``.`` / ``|`` / ``-``），不引入任何可能超出 GBK 的字符 ——
    这是本仓库「脚本 stdout 不设编码护栏」的配套约定。
    """
    makespan = max((item.end_time for item in schedule.operations), default=0)
    if makespan <= 0:
        return ["（空排程）"]
    scale = max(1, -(-makespan // width))  # 向上取整
    symbols = {job.id: str(index % 10) for index, job in enumerate(instance.jobs)}
    job_of = {operation.id: operation.job_id for operation in instance.operations}
    columns = -(-makespan // scale)

    lines = [f"时间轴：1 格 = {scale} 个时间单位，总长 {makespan}，共 {columns} 格"]
    for machine in instance.machines:
        bar = ["."] * columns
        for item in schedule.operations:
            if item.machine_id != machine.id:
                continue
            symbol = symbols[job_of[item.operation_id]]
            for slot in range(item.start_time // scale, -(-item.end_time // scale)):
                if 0 <= slot < columns:
                    bar[slot] = symbol
        lines.append(f"{machine.id:>4} |{''.join(bar)}|")
    legend = "  ".join(f"{symbols[job.id]}={job.id}" for job in instance.jobs)
    lines.append(f"图例：{legend}")
    return lines
