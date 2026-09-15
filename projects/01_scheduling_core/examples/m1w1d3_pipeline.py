"""Day 3 实验：跑通「JSON → Instance → 校验 → 手工排程 → 指标」数据流。

对应学习笔记：Month_01_基础系统与框架设计/Week_1/Day3.md。

运行方式（在 projects/01_scheduling_core 目录下）：
    python -m examples.m1w1d3_pipeline
或直接运行本文件：
    python examples/m1w1d3_pipeline.py
直接运行时自动定位项目目录，无需安装包或手动设置环境变量。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_core.objective import (
    makespan,
    total_completion_time,
    total_tardiness,
    weighted_completion_time,
)
from scheduling_io.parser import load_json_instance
from scheduling_core.schedule import Schedule, ScheduledOperation
from scheduling_core.validation import validate_instance


def build_hand_schedule() -> Schedule:
    """为 small_instance.json 手工构造一个简单可行排程。

    J1: O1(p=3, 可 M1/M2) → O2(p=2, 只能 M2)
    J2: O3(p=4, 只能 M1)
    排程：
      O1 放 M1：0-3
      O2 放 M2：3-5（须等 O1 完成）
      O3 放 M1：3-7（须等 O1 释放 M1）
    """
    return Schedule(
        operations=(
            ScheduledOperation(
                operation_id="O1", machine_id="M1", start_time=0, end_time=3
            ),
            ScheduledOperation(
                operation_id="O2", machine_id="M2", start_time=3, end_time=5
            ),
            ScheduledOperation(
                operation_id="O3", machine_id="M1", start_time=3, end_time=7
            ),
        )
    )


def main() -> None:
    json_path = Path(__file__).resolve().parent / "small_instance.json"

    instance = load_json_instance(json_path)
    validate_instance(instance)

    schedule = build_hand_schedule()

    print("jobs:", [job.id for job in instance.jobs])
    print("machines:", [machine.id for machine in instance.machines])
    print("makespan =", makespan(instance, schedule))
    print("total_completion_time =", total_completion_time(instance, schedule))
    print("total_tardiness =", total_tardiness(instance, schedule))
    print("weighted_completion_time =", weighted_completion_time(instance, schedule))


if __name__ == "__main__":
    main()
