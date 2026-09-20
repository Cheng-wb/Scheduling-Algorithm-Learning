"""M3 Week 3 Day 1：释放时间与交期如何在单机实例上咬人。

四道工序挤在一台机器上，其中一道要到第 8 个时间单位才允许开工，另有两道交期极紧。

    python examples/m3w3d1_release_and_due.py

脚本做四件事：

1. 用 `fjsp_cpsat_multiobj`（`alpha = 1`，等价于最小化 `Cmax`）求出最优排程，
   打印逐工序时间线；
2. 把「释放时间造成的空闲」手算出来与求解器对照——空闲长度不是求解器的习惯，
   而是 `release_time` 减去它之前能塞进去的工时；
3. 手工构造两个反例排程：一个让晚到工序提前开工（触发 `release` 诊断），
   一个虽然合法却把紧交期的订单拖晚（手算 `ΣT`）。反例是手写的，不是求解器的输出；
4. 逐订单列出 `C_j`、`d_j`、`T_j = max(0, C_j - d_j)`。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core import (
    FJSPInstance,
    Job,
    Machine,
    Operation,
    Schedule,
    ScheduledOperation,
    job_completion_times,
    schedule_errors,
    total_tardiness,
)
from fjsp_shop.registry import get, load_week_modules

#: 单机实例 D1。总工时 9，其中 `A` 的释放时间 8 大于其余三道的工时和 5，
#: 所以机器在 `A` 之前**必须**空转至少 3 个时间单位——这条空闲是约束逼出来的。
INSTANCE = FJSPInstance(
    jobs=(
        Job("J0", ("A",), release_time=8, due_date=14),
        Job("J1", ("B",), release_time=0, due_date=3),
        Job("J2", ("C",), release_time=0, due_date=20),
        Job("J3", ("E",), release_time=0, due_date=1),
    ),
    operations=(
        Operation("A", "J0", 0, (("M0", 4),)),
        Operation("B", "J1", 0, (("M0", 2),)),
        Operation("C", "J2", 0, (("M0", 2),)),
        Operation("E", "J3", 0, (("M0", 1),)),
    ),
    machines=(Machine("M0", "M0"),),
)

#: 反例一（不合法）：`A` 在 0 点开工，早于它的释放时间 8。
ILLEGAL_EARLY = Schedule(
    operations=(
        ScheduledOperation("A", "M0", 0, 4),
        ScheduledOperation("E", "M0", 4, 5),
        ScheduledOperation("B", "M0", 5, 7),
        ScheduledOperation("C", "M0", 7, 9),
    )
)

#: 手写排程二（合法）：把紧交期的小工序 `E` 放到最前面。
#: 手算：`E` 完工 1、`B` 完工 3、`C` 完工 5、`A` 完工 12
#: -> ΣT = max(0,1-1) + max(0,3-3) + max(0,5-20) + max(0,12-14) = 0
#: 它的 `Cmax` 与求解器那条**相同**（都是 12）——只优化 `Cmax` 时这两条并列最优。
HAND_TIGHT_FIRST = Schedule(
    operations=(
        ScheduledOperation("E", "M0", 0, 1),
        ScheduledOperation("B", "M0", 1, 3),
        ScheduledOperation("C", "M0", 3, 5),
        ScheduledOperation("A", "M0", 8, 12),
    )
)

#: 手写排程三（合法但很差）：把 `E` 一路推到最后。
#: 手算：`C` 完工 2、`B` 完工 4、`A` 完工 12、`E` 完工 13
#: -> ΣT = max(0,2-20) + max(0,4-3) + max(0,12-14) + max(0,13-1) = 0 + 1 + 0 + 12 = 13
ILLEGAL_LATE = Schedule(
    operations=(
        ScheduledOperation("C", "M0", 0, 2),
        ScheduledOperation("B", "M0", 2, 4),
        ScheduledOperation("A", "M0", 8, 12),
        ScheduledOperation("E", "M0", 12, 13),
    )
)

SPEC = {
    "objective": "weighted_sum",
    "time_limit": 5.0,
    "seed": 0,
    "weights": {"alpha": 1.0, "beta": 0.0, "gamma": 0.0},
    "normalization": {"mode": "none"},
}


def main() -> None:
    load_week_modules()

    print("== 实例 D1（单机 M0） ==")
    print(f"{'工序':<6}{'订单':<6}{'工时':>6}{'释放':>6}{'交期':>6}")
    for job in INSTANCE.jobs:
        for op_id in job.operation_ids:
            op = INSTANCE.operation(op_id)
            print(
                f"{op.id:<6}{job.id:<6}{op.time_on('M0'):>6}"
                f"{job.release_time:>6}{job.due_date:>6}"
            )
    total_work = sum(
        INSTANCE.operation(op_id).time_on("M0")
        for job in INSTANCE.jobs
        for op_id in job.operation_ids
    )
    print(f"总工时 {total_work}；A 的释放时间 8 > 其余三道工序的工时和 5 -> 机器必然空转")

    result = get("fjsp_cpsat_multiobj")(INSTANCE, SPEC)
    print()
    print("== 最优排程（fjsp_cpsat_multiobj, alpha=1） ==")
    print(
        f"status={result.status}  best_bound={result.best_bound}  "
        f"objective={result.objective:g}  solve_time={result.solve_time:.4f}s"
    )
    print(f"breakdown={result.breakdown}")
    print(f"独立验证器：{schedule_errors(INSTANCE, result.schedule) or '通过'}")

    ordered = sorted(result.schedule.operations, key=lambda item: item.start_time)
    print()
    print("时间线（每格 1 个时间单位，'.' = 空闲）：")
    print("  M0 " + _bars(ordered))

    print()
    print("机器空闲段：", _idle_gaps(ordered) or "无")
    for lo, hi in _idle_gaps(ordered):
        print(
            f"  空闲 [{lo},{hi}) 长度 {hi - lo}"
            f" = A 的释放时间 {INSTANCE.job('J0').release_time} - 之前已排的 {lo} 个时间单位"
        )

    print()
    print("== 反例一：让 A 在 0 点开工（早于释放时间 8） ==")
    print("  排程：" + _render(ILLEGAL_EARLY))
    _show(ILLEGAL_EARLY)

    print()
    print("== 手写排程二：同样的 Cmax，ΣT 却完全不同 ==")
    print("  排程：" + _render(HAND_TIGHT_FIRST))
    _show(HAND_TIGHT_FIRST)
    print("  手算 ΣT = (1-1)^+ + (3-3)^+ + (5-20)^+ + (12-14)^+ = 0")
    print(f"  求解器复算 ΣT = {total_tardiness(INSTANCE, HAND_TIGHT_FIRST)}")
    print("  这两条排程的 Cmax 都是 12：只写 Cmax 的目标函数对交期完全无感。")

    print()
    print("== 手写排程三：合法但把紧交期工序一路推到最后 ==")
    print("  排程：" + _render(ILLEGAL_LATE))
    _show(ILLEGAL_LATE)
    print("  手算 ΣT = (2-20)^+ + (4-3)^+ + (12-14)^+ + (13-1)^+ = 0 + 1 + 0 + 12 = 13")
    print(f"  求解器复算 ΣT = {total_tardiness(INSTANCE, ILLEGAL_LATE)}")

    print()
    print("== 逐订单完成时间与迟交（最优排程） ==")
    completion = job_completion_times(INSTANCE, result.schedule)
    print(f"{'订单':<6}{'工序':>6}{'C_j':>6}{'d_j':>6}{'T_j':>6}")
    for job in INSTANCE.jobs:
        done = completion.get(job.id, 0)
        print(
            f"{job.id:<6}{','.join(job.operation_ids):>6}{done:>6}"
            f"{job.due_date:>6}{max(0, done - job.due_date):>6}"
        )
    print(f"合计 ΣT = {total_tardiness(INSTANCE, result.schedule)}")


def _render(schedule: Schedule) -> str:
    return "  ".join(
        f"{item.operation_id}[{item.start_time},{item.end_time})"
        for item in sorted(schedule.operations, key=lambda item: item.start_time)
    )


def _show(schedule: Schedule) -> None:
    diagnostics = schedule_errors(INSTANCE, schedule)
    if not diagnostics:
        print("  验证器诊断：通过（没有任何约束被违反）")
        return
    print(f"  验证器诊断（{len(diagnostics)} 条）：")
    for line in diagnostics:
        print(f"    {line}")


def _bars(ordered: list[ScheduledOperation]) -> str:
    """把排程画成一行方框：工序用首字母，空闲用 `.`。"""
    end = max((item.end_time for item in ordered), default=0)
    cells = ["." for _ in range(end)]
    for item in ordered:
        for tick in range(item.start_time, item.end_time):
            cells[tick] = item.operation_id[0]
    return "".join(cells) + f"   (0 -> {end})"


def _idle_gaps(ordered: list[ScheduledOperation]) -> list[tuple[int, int]]:
    """机器上没排工序的时间段。**只看机器**，不看订单之间的先后。"""
    gaps: list[tuple[int, int]] = []
    cursor = 0
    for item in ordered:
        if cursor < item.start_time:
            gaps.append((cursor, item.start_time))
        cursor = max(cursor, item.end_time)
    return gaps


if __name__ == "__main__":
    main()
