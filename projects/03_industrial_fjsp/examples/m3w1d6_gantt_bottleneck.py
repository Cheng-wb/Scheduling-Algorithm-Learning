"""M3 Week 1 Day 6：读标准格式实例，导出甘特与瓶颈分析。

四节：

```text
1. 读文件   tests/data/tiny3x3.jsp 是手写的标准格式（第一行「订单数 机器数」）
2. 甘特行   六个字段、按 (machine_id, start_time, operation_id) 排序
3. 瓶颈     机器负载汇总：忙时、跨度、利用率、负载占比；瓶颈 = 忙时最大的那台
4. 落盘     调用驱动 fjsp_experiments.week1_gantt，把四个实例的甘特 CSV 写进
            artifacts/month3_w1/，再读回来验证六个字段没丢
```

**甘特是展示模型，不是领域模型**：领域里的排程是 ``Schedule``
（工序 -> 机器 + 起止时刻），甘特行只是把它摊平成「一行一道工序」的表格，
多出来的 ``job_id`` 与 ``duration`` 都是可以从 ``Schedule`` 反推出来的冗余字段。
两者分开，才能让「换一种展示」不牵动调度逻辑。

运行：``python examples/m3w1d6_gantt_bottleneck.py``
"""

import csv
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.models import FJSPInstance
from fjsp_core.objective import makespan
from fjsp_core.result import validate_result
from fjsp_core.schedule_validation import validate_schedule
from fjsp_io.standard import format_standard_jsp, load_standard_jsp
from fjsp_shop.gantt import (
    GANTT_FIELDS,
    machine_load_summary,
    render_ascii_gantt,
    to_gantt_rows,
)
from fjsp_shop.jsp import jsp_cpsat

PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "tests" / "data" / "tiny3x3.jsp"
ARTIFACTS = PROJECT / "artifacts" / "month3_w1"


def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def print_instance(instance: FJSPInstance) -> None:
    print(f"来源文件 = {instance.meta['source']}，格式 = {instance.meta['format']}，"
          f"机器号 0 基 = {instance.meta['machine_id_base'] == 0}")
    for job in instance.jobs:
        route = " -> ".join(
            f"{instance.operation(oid).machine_times[0][0]}"
            f"({instance.operation(oid).machine_times[0][1]})"
            for oid in job.operation_ids
        )
        print(f"  {job.id}：{route}")


def main() -> None:
    section("第 1 节：读标准格式文件")
    instance = load_standard_jsp(DATA)
    print_instance(instance)
    print(f"\n往返写回（机器 id 必须是 M0..M{len(instance.machines) - 1} 且每道工序一台机器）：")
    print(format_standard_jsp(instance).rstrip())

    section("第 2 节：甘特行 —— 六个字段")
    result = jsp_cpsat(instance, {"objective": "makespan", "time_limit": 10.0, "seed": 0})
    validate_schedule(instance, result.schedule)
    validate_result(instance, result)
    rows = to_gantt_rows(instance, result.schedule)
    print(f"字段顺序 = {GANTT_FIELDS}")
    print(f"行数 = {len(rows)}，"
          f"排序键 = (machine_id, start_time, operation_id) 且已排序 = "
          f"{rows == sorted(rows, key=lambda row: (row['machine_id'], row['start_time'], row['operation_id']))}")
    print("\nmachine_id | job_id | operation_id | start | end | duration")
    for row in rows:
        print(f"{row['machine_id']:>10s} | {row['job_id']:>6s} | {row['operation_id']:>9s} | "
              f"{row['start_time']:5d} | {row['end_time']:3d} | {row['duration']:8d}")
    print(f"\n从甘特行独立复核：最大完工时刻 = "
          f"{max(row['end_time'] for row in rows)}，makespan() = "
          f"{makespan(instance, result.schedule)}")

    print("\nASCII 甘特（数字是订单在 jobs 里的下标，点表示空闲）：")
    for line in render_ascii_gantt(instance, result.schedule, width=24):
        print("  " + line)

    section("第 3 节：机器负载与瓶颈")
    summary = machine_load_summary(instance, result.schedule)
    print("machine_id | 工序数 | 忙时 | 跨度 | 跨度内空闲 | 利用率 | 负载占比")
    for item in summary:
        print(f"{item['machine_id']:>10s} | {item['operation_count']:6d} | "
              f"{item['busy_time']:4d} | {item['span']:4d} | {item['idle_in_span']:10d} | "
              f"{item['utilization']:6.3f} | {item['load_share']:8.3f}")
    total_busy = sum(item["busy_time"] for item in summary)
    print(f"\n总忙时 = {total_busy}（= 所有工序工时之和），"
          f"负载占比之和 = {sum(item['load_share'] for item in summary):.3f}")
    bottleneck = summary[0]
    print(f"瓶颈机器 = {bottleneck['machine_id']}"
          f"（忙时 {bottleneck['busy_time']}，利用率 {bottleneck['utilization']:.3f}）")
    print(f"机器上的顺序：{' -> '.join(bottleneck['sequence'])}")
    print(f"瓶颈机器的忙时 {bottleneck['busy_time']} 与 makespan "
          f"{makespan(instance, result.schedule)} 的关系："
          f"{'相等（本实例瓶颈机器一路不停）' if bottleneck['busy_time'] == makespan(instance, result.schedule) else '小于（瓶颈机器也有空闲）'}")

    section("第 4 节：落盘与读回")
    from fjsp_experiments.week1_gantt import run as run_week1

    print(f"输出目录 = {ARTIFACTS}")
    try:
        exported = run_week1(output=ARTIFACTS)
    except ValueError as error:
        exported = None
        print(f"跳过写盘：{error}")
        print("（Week 1 的规矩是保留上一次的实验结果，要重跑请先清空该目录）")
    if exported is not None:
        for name, block in exported["instances"].items():
            for row in block["runs"]:
                bound = "-" if row["best_bound"] is None else f"{row['best_bound']:.0f}"
                objective = "-" if row["objective"] is None else f"{row['objective']:.0f}"
                print(f"  {name:10s} {row['method']:14s} {row['status']:9s} "
                      f"目标值 {objective:>6s} 界 {bound:>6s} "
                      f"瓶颈机 {row.get('bottleneck_machine', '-')}")

    csv_path = ARTIFACTS / "gantt_flow_5x3.csv"
    if csv_path.exists():
        with csv_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            read_back = list(reader)
        print(f"\n读回 {csv_path.name}：表头 = {reader.fieldnames}")
        print(f"行数 = {len(read_back)}，六列齐全 = "
              f"{list(reader.fieldnames) == list(GANTT_FIELDS)}")
        print("前 3 行：")
        for row in read_back[:3]:
            print("  " + " | ".join(f"{row[key]}" for key in GANTT_FIELDS))
        print(f"最后一行：{' | '.join(read_back[-1][key] for key in GANTT_FIELDS)}")
    else:
        print(f"\n{csv_path} 不存在（本次没写盘，也没有上一次的结果）")

    section("当日结论")
    print("1. 标准格式只有两样东西：头行的「订单数 机器数」与每订单一行的「机器号 工时」对，")
    print("   机器号 0 基。解析器只用手写样例验证过，没有用 OR-Library 原始文件验证。")
    print("2. 甘特行是展示模型：六列、按 (机器, 开工, 工序号) 排序，全部字段都能从 Schedule 反推。")
    print("3. 瓶颈 = 忙时最大的机器；它的忙时是 makespan 的下界，本实例上两者相等。")
    print("4. 落盘走驱动 fjsp_experiments/week1_gantt.py，版本状态在创建目录之前捕获。")


if __name__ == "__main__":
    main()
