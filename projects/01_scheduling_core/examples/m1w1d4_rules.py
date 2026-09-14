"""Day 4 实验：单机 SPT/EDD/WSPT/LPT 规则与释放时间处理。

对应学习笔记：Month_01_基础系统与框架设计/Week_1/Day4.md。

运行方式（在 projects/01_scheduling_core 目录下）：
    python -m examples.m1w1d4_rules
或直接运行本文件：
    python examples/m1w1d4_rules.py
直接运行时自动定位项目目录，无需安装包或手动设置环境变量。

实验内容：
- 实例 A：Day1 连续性的 5 job 单机实例（带释放时间），演示释放时间处理。
- 实例 B：4 job 无释放时间实例，演示四条规则顺序不同、且各自在其目标上最优。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.objective import (
    makespan,
    max_lateness,
    total_completion_time,
    total_tardiness,
    weighted_completion_time,
)
from scheduling_core.rules import edd, lpt, spt, wspt


def single_machine_instance(jobs_spec) -> Instance:
    """由 (id, p, r, d, w) 列表构造单机实例。"""
    m1 = Machine(id="M1", name="Machine 1")

    operations = []
    jobs = []

    for jid, p, r, d, w in jobs_spec:
        oid = f"O_{jid}"
        operations.append(
            Operation(id=oid, job_id=jid, processing_time=p, eligible_machine_ids=("M1",))
        )
        jobs.append(
            Job(id=jid, operation_ids=(oid,), release_time=r, due_date=d, weight=w)
        )

    return Instance(jobs=tuple(jobs), operations=tuple(operations), machines=(m1,))


def job_order(instance: Instance, schedule) -> list[str]:
    """从 Schedule 提取按开始时间排序的 job id 序列。"""
    op_by_id = {op.id: op for op in instance.operations}
    ordered = sorted(schedule.operations, key=lambda s: s.start_time)
    return [op_by_id[s.operation_id].job_id for s in ordered]


def report(instance: Instance, title: str) -> None:
    """在一个实例上跑四条规则，打印对比表。"""
    print(f"\n=== {title} ===")
    print(f"machines: {[m.id for m in instance.machines]}")
    print(
        f"jobs: "
        + ", ".join(
            f"{j.id}(p={op.processing_time}, r={j.release_time}, "
            f"d={j.due_date}, w={j.weight})"
            for j, op in zip(instance.jobs, instance.operations)
        )
    )

    print(f"{'rule':6} {'order':22} {'Cmax':>5} {'ΣCj':>5} {'ΣTj':>5} {'ΣwjCj':>7} {'Lmax':>5}")
    print("-" * 60)

    for name, rule in [("SPT", spt), ("EDD", edd), ("WSPT", wspt), ("LPT", lpt)]:
        schedule = rule(instance)
        order = job_order(instance, schedule)
        print(
            f"{name:6} {','.join(order):22} "
            f"{makespan(instance, schedule):>5} "
            f"{total_completion_time(instance, schedule):>5} "
            f"{total_tardiness(instance, schedule):>5} "
            f"{weighted_completion_time(instance, schedule):>7} "
            f"{max_lateness(instance, schedule):>5}"
        )


def instance_a() -> Instance:
    """带释放时间的 5 job 实例（延续 Day1 第 14 节的数据）。"""
    return single_machine_instance(
        [
            ("J1", 6, 0, 12, 1.0),
            ("J2", 2, 0, 8, 3.0),
            ("J3", 4, 3, 15, 1.0),
            ("J4", 3, 5, 10, 2.0),
            ("J5", 7, 0, 20, 1.0),
        ]
    )


def instance_b() -> Instance:
    """无释放时间的 4 job 实例，四条规则顺序明显不同。"""
    return single_machine_instance(
        [
            ("J1", 4, 0, 6, 1.0),
            ("J2", 1, 0, 12, 5.0),
            ("J3", 3, 0, 8, 2.0),
            ("J4", 2, 0, 3, 1.0),
        ]
    )


def main() -> None:
    report(instance_a(), "实例 A：带释放时间（演示释放时间处理）")
    report(instance_b(), "实例 B：无释放时间（演示规则差异与各自最优目标）")

    print("\n解读：")
    print("- 实例 B 中 SPT 的 ΣCj 最小（20），符合 1||ΣCj 最优。")
    print("- 实例 B 中 WSPT 的 ΣwjCj 最小（29），符合 1||ΣwjCj 最优。")
    print("- 实例 B 中 EDD 的 Lmax 最小（1），符合 1||Lmax 最优。")
    print("- LPT 在单机上对 ΣCj/ΣTj/ΣwjCj 均较差，它是为 P||Cmax 并行机设计的基线。")
    print("- 实例 A 里 SPT/EDD/WSPT 恰好同序，是因为本组数据使然，不代表一般成立。")


if __name__ == "__main__":
    main()
