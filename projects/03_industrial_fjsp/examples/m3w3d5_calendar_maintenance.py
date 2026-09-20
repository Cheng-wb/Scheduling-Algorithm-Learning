"""M3 Week 3 Day 5：机器日历（`calendar`）与计划维护（`maintenance`）。

前面的约束都在描述「谁必须先做、谁不能和谁重叠」。日历不是：它说的是
**这台机器在哪些时刻根本不存在**——班次、周末、检修。工序区间 `[start, end)`
必须整体落在**某一个**可用区段内，不允许跨过停机段。

    python examples/m3w3d5_calendar_maintenance.py

三个实例、一张手排表，四件事：

1. `C1a`（日历窗 + 与窗重合的维护）：停机段怎么把时间线切成两截，
   排程只能在两截之间跳过去；
2. `C1b`（维护落在窗口**内部**）：维护不是日历的同义词——它是在日历之上
   再挖掉的洞。这一节同时打印 `fitting_windows` 的结果，说明「放不下」是
   几何计算判出来的，不是搜索失败；
3. 手工排出的四条时间线：验证器给的是 `calendar` 还是 `maintenance` 标签，
   以及为什么「贴着停机段结束」是合法的（半开区间 `[start, end)`）；
4. 两条日历编码（`split` / `blocker`）的规模与答案对照，以及一道
   **放不进任何窗**的工序：这种不可行在建模阶段就被判死，状态是 `INFEASIBLE`。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core import (
    Calendar,
    FJSPInstance,
    Job,
    Machine,
    Maintenance,
    Operation,
    Schedule,
    ScheduledOperation,
    objective_breakdown,
    schedule_errors,
)
from fjsp_shop.industrial import allowed_windows, fitting_windows, starting_domain
from fjsp_shop.registry import get, load_week_modules

#: C1a：`M0` 只有 `[0, 5)` 与 `[10, 20)` 两段可用，中间那段恰好是维护窗。
#: 手算：`X` 占 `[0, 4)`，`Y` 只能等第二段，`[10, 13)`，`Cmax = 13`。
C1A = FJSPInstance(
    jobs=(Job("J0", ("X",)), Job("J1", ("Y",))),
    operations=(
        Operation("X", "J0", 0, (("M0", 4),)),
        Operation("Y", "J1", 0, (("M0", 3),)),
    ),
    machines=(Machine("M0", "M0", calendar_id="CAL"),),
    calendars=(Calendar("CAL", ((0, 5), (10, 20))),),
    maintenances=(Maintenance("MT", "M0", ((5, 10),)),),
)

#: C1b：日历是**整段** `[0, 20)`，维护从里面挖掉 `(5, 10)`。
#: `Y` 要 6 分钟：`[0, 5)` 这一段只有 5 分钟长，塞不下，所以最早只能 `[10, 16)`。
#: 手算：`X[0, 4)` + 空 6 分钟 + `Y[10, 16)`，`Cmax = 16`。
C1B = FJSPInstance(
    jobs=(Job("J0", ("X",)), Job("J1", ("Y",))),
    operations=(
        Operation("X", "J0", 0, (("M0", 4),)),
        Operation("Y", "J1", 0, (("M0", 6),)),
    ),
    machines=(Machine("M0", "M0", calendar_id="CAL"),),
    calendars=(Calendar("CAL", ((0, 20),)),),
    maintenances=(Maintenance("MT", "M0", ((5, 10),)),),
)

#: C1c：唯一那道工序要 11 分钟，两段可用窗分别只有 5 与 10 分钟长。
C1C = FJSPInstance(
    jobs=(Job("J0", ("Z",)),),
    operations=(Operation("Z", "J0", 0, (("M0", 11),)),),
    machines=(Machine("M0", "M0", calendar_id="CAL"),),
    calendars=(Calendar("CAL", ((0, 5), (10, 20))),),
)

SPEC = {"objective": "makespan", "time_limit": 5.0, "seed": 0}
ENCODINGS = (("fjsp_cpsat_calendar", "split"), ("fjsp_cpsat_setup", "blocker"))


def main() -> None:
    load_week_modules()

    print("== C1a：日历 [(0, 5), (10, 20)]，维护 (5, 10) ==")
    print(_geometry(C1A, "M0"))
    result = get("fjsp_cpsat_setup")(C1A, SPEC)
    print(f"status={result.status}  objective={result.objective:g}  "
          f"breakdown={objective_breakdown(C1A, result.schedule)}")
    print(_timeline(C1A, "M0", result.schedule))
    print("  `X` 在 [0, 4)，`Y` 在 [10, 13)：中间那 6 分钟不是「空闲」，")
    print("  是机器**不可用**——`Y` 就算提前知道也没法在 5 分钟那一刻开工。")
    print("  日历约束和优先级约束的差别就在这：它不是「先来后到」，是「这时没机器」。")

    print()
    print("== C1b：日历改成整段 [(0, 20)]，维护仍在 (5, 10) ==")
    print(_geometry(C1B, "M0"))
    result_b = get("fjsp_cpsat_setup")(C1B, SPEC)
    print(f"status={result_b.status}  objective={result_b.objective:g}  "
          f"breakdown={objective_breakdown(C1B, result_b.schedule)}")
    print(_timeline(C1B, "M0", result_b.schedule))
    print("  `X` 只要 4 分钟，第一段就装得下；`Y` 要 6 分钟，第一段只有 5 分钟长，")
    print("  所以几何计算先把 `[0, 5)` 这一段**筛掉**，`Y` 的起点域里根本没有它。")
    print("  两条编码共用这一份筛选：`blocker` 用起点域表达，`split` 用可选区间表达，")
    print("  筛错了两种编码会一起错——这也是它们必须给同一个答案的原因。")

    print()
    print("== 手工排出的违规时间线 ==")
    for label, instance, schedule in _violations():
        print(f"  {label}")
        print(f"    {_fingerprint(schedule)}")
        print(f"    验证器：{schedule_errors(instance, schedule) or '（无错误）'}")
    print("  前两条都同时踩了日历与维护：`[4, 7)` 与 `[6, 9)` 既不在任何一个日历窗里，")
    print("  又和维护窗 `(5, 10)` 相交，所以两条诊断一起报。第三条只报 `maintenance`——")
    print("  `C1b` 的日历是整段 `[0, 20)`，没被踩到。**两条检查是分开做的**，")
    print("  标签不同意味着修的地方也不同：报 `calendar` 要去调班次，报 `maintenance`")
    print("  要去调检修计划。")
    print("  最后一条合法：Y 贴着维护窗结束开工，`[start, end)` 是半开区间，")
    print("  `end = 10` 与维护窗 `(5, 10)` 没有公共点——「贴边」不算重叠。")

    print()
    print("== 两条日历编码：规模不同，答案必须相同 ==")
    # 表头按**显示宽度**补空格：汉字占两列，`:<n` 只数字符不数宽度。
    print(f"{'实例':<4}{'  '}{'编码':<4}{'      '}{'变量':>4}{'  '}"
          f"{'约束':>4}{'  '}{'状态':<4}{'      '}{'Cmax':>4}{'  '}  排程")
    for name, instance in (("C1a", C1A), ("C1b", C1B)):
        for method, mode in ENCODINGS:
            item = get(method)(instance, SPEC)
            size = item.detail["model_size"]
            print(f"{name:<6}{mode:<10}{size['variables']:>6}"
                  f"{size['constraints']:>6}  {item.status:<10}"
                  f"{item.objective:>6.0f}  {_fingerprint(item.schedule)}")
    print("  `split` 给每个 `(工序, 机器, 可用窗)` 一个布尔变量，窗越多变量越多；")
    print("  `blocker` 只用起点域 + 停机区间，变量数不随窗数增长。")
    print("  规模差是**编码**的差，不是可行集的差：两行两两相等才是这里要的结论。")

    print()
    print("== C1c：一道 11 分钟的工序，两段窗都装不下 ==")
    print(_geometry(C1C, "M0", with_domain=True))
    infeasible = get("fjsp_cpsat_setup")(C1C, SPEC)
    print(f"status={infeasible.status}  原因={infeasible.detail['failure_reason']}")
    print("  这不是「搜索没找到」：`[0, 5)` 与 `[10, 20)` 两段都比 11 分钟短，")
    print("  起点域算出来是空的，模型里没有一条合法的时间线可建，所以判 `INFEASIBLE`。")
    print("  生产上的读法也一样：**要么加一次加班窗，要么把这单分到别的机器**——")
    print("  日历硬度不是排程算法能自己解决的事。")


def _violations() -> list[tuple[str, FJSPInstance, Schedule]]:
    """手工排出的四条时间线：两条违规、一条只踩维护、一条只是贴着停机段。"""
    return [
        (
            "C1a：Y 在 X 刚结束后开工（[4, 7)），跨进停机段：",
            C1A,
            Schedule(
                (
                    ScheduledOperation("X", "M0", 0, 4),
                    ScheduledOperation("Y", "M0", 4, 7),
                )
            ),
        ),
        (
            "C1a：Y 整段塞进停机段（[6, 9)），X 挪到第二段末尾：",
            C1A,
            Schedule(
                (
                    ScheduledOperation("Y", "M0", 6, 9),
                    ScheduledOperation("X", "M0", 16, 20),
                )
            ),
        ),
        (
            "C1b：同样从 4 开工（[4, 10)），但日历是整段，只踩维护：",
            C1B,
            Schedule(
                (
                    ScheduledOperation("X", "M0", 0, 4),
                    ScheduledOperation("Y", "M0", 4, 10),
                )
            ),
        ),
        (
            "C1a：Y 从维护窗结束那一刻开工（[10, 13)）：",
            C1A,
            Schedule(
                (
                    ScheduledOperation("X", "M0", 0, 4),
                    ScheduledOperation("Y", "M0", 10, 13),
                )
            ),
        ),
    ]


def _geometry(instance: FJSPInstance, machine_id: str, *, with_domain: bool = False) -> str:
    """打印 `allowed_windows` / `fitting_windows` / `starting_domain` 的实测结果。

    这三行是「模型为什么只允许这些位置」的直接证据：它们不是散文描述，
    而是建模型时真正传进 CP-SAT 的那份几何。
    """
    horizon = 0
    for _, hi in instance.calendar_window(machine_id):
        horizon = max(horizon, hi)
    for _, hi in instance.maintenance_windows(machine_id):
        horizon = max(horizon, hi)
    segments = allowed_windows(instance, machine_id, horizon)
    lines = [
        f"  日历窗 {instance.calendar_window(machine_id)}"
        f"  维护 {instance.maintenance_windows(machine_id)}",
        f"  扣掉维护后的可用区段 = {segments}",
    ]
    for op in instance.operations:
        if any(item == machine_id for item, _ in op.machine_times):
            duration = op.time_on(machine_id)
            lines.append(
                f"  工序 {op.id}(p={duration}): 装得下的窗 = "
                f"{fitting_windows(segments, duration)}"
            )
            if with_domain:
                lines.append(
                    f"    起点域 = {starting_domain(segments, duration)}"
                    "   <- 空的就是这道题判 INFEASIBLE 的依据"
                )
    return "\n".join(lines)


def _timeline(instance: FJSPInstance, machine_id: str, schedule: Schedule) -> str:
    """一行字符画：字母 = 工序，`#` = 停机，`.` = 可用但空着。"""
    end = _display_horizon(instance, machine_id)
    segments = allowed_windows(instance, machine_id, end)
    cells = ["#" for _ in range(end)]
    for lo, hi in segments:
        for tick in range(lo, min(hi, end)):
            cells[tick] = "."
    for item in schedule.operations:
        if item.machine_id != machine_id:
            continue
        for tick in range(item.start_time, item.end_time):
            cells[tick] = item.operation_id[0]
    return f"  M0 {''.join(cells)}   (0 -> {end})   # = 停机"


def _display_horizon(instance: FJSPInstance, machine_id: str) -> int:
    horizon = 0
    for _, hi in instance.calendar_window(machine_id):
        horizon = max(horizon, hi)
    for _, hi in instance.maintenance_windows(machine_id):
        horizon = max(horizon, hi)
    return horizon


def _fingerprint(schedule: Schedule) -> str:
    return ";".join(
        f"{item.operation_id}[{item.start_time}, {item.end_time})"
        for item in sorted(schedule.operations, key=lambda item: item.start_time)
    )


if __name__ == "__main__":
    main()
