"""M3 Week 3 Day 6：在带约束实例上比较各模型——谁收得下、谁解得动、谁解得准。

前三天的模型各管一个约束面（换型、日历、多目标）。放到**同一个**实例上，
比较就会暴露出三类问题，它们需要分开定位：

1. **模型边界**：有些模型直接拒收带工业约束的实例。这是设计选择，不是缺陷——
   拒收比给出一条无视约束的排程诚实。问题是**调用方**怎么知道该换哪个模型；
2. **规模与时间**：两条日历编码描述同一个可行集，规模可以差三成，
   而规模大的那条在本次实例上反而解得快。规模不是耗时的代理指标；
3. **质量**：同一个实例、同一个最优值下往往有**多条**最优排程，
   单目标模型返回哪一条不由目标决定——于是可能出现「单目标最优解被另一个
   目标的解**支配**」这种反直觉现象。

    python examples/m3w3d6_model_comparison.py

实例两个：`D6`（3 工序，手算可核对）与 `G201`（seed 201，4 单 3 机 12 工序，
带日历、维护、换型、交期）。不可行定位用四个迷你实例，覆盖建模期判死与
搜索期证明两种 `INFEASIBLE`。
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
    Setup,
    objective_breakdown,
)
from fjsp_io import generate_instance
from fjsp_shop.registry import get, load_week_modules

#: D6：两台机器、三道工序。`M0` 有日历与维护，换型 F0<->F1 各 2 分钟。
#: 手算 min Cmax = 13：`A[0, 4)`（第一段可用区段到 6 为止），换型 2 分钟后
#: `B` 要 3 分钟，`[6, 9)` 会跨进停机段 `(6, 10)`，所以 `B` 只能等第二段 `[10, 13)`。
#: 日历写 `((0, 7), (10, 30))` 而不是 `((0, 6), (10, 30))`：维护窗 `(6, 10)`
#: 要把 `(0, 7)` **削成** `(0, 6)`，否则维护就被日历蕴含了（Day 5 的 `C1a` 正是那种情形）。
#: 可用区段仍是 `((0, 6), (10, 30))`，所以上面的手算一字不改。
D6 = FJSPInstance(
    jobs=(
        Job("J0", ("A",), due_date=8),
        Job("J1", ("B",), due_date=6),
        Job("J2", ("C",), due_date=20),
    ),
    operations=(
        Operation("A", "J0", 0, (("M0", 4),), family="F0"),
        Operation("B", "J1", 0, (("M0", 3),), family="F1"),
        Operation("C", "J2", 0, (("M1", 5),), family="F0"),
    ),
    machines=(Machine("M0", "M0", calendar_id="CAL0"), Machine("M1", "M1")),
    calendars=(Calendar("CAL0", ((0, 7), (10, 30))),),
    maintenances=(Maintenance("MT", "M0", ((6, 10),)),),
    setups=(Setup("F0", "F1", 2), Setup("F1", "F0", 2)),
)

#: 上一代模型：只认「释放时间 + 工序」，带日历/维护/换型就拒收。
LEGACY_METHODS = ("fjsp_cpsat", "fjsp_shortest", "fjsp_random")

#: 本周的三条模型：换型编码、日历编码、加权多目标（换型编码 + 日历 blocker）。
WEEK3_METHODS = ("fjsp_cpsat_setup", "fjsp_cpsat_calendar", "fjsp_cpsat_multiobj")

TIME_LIMIT = 10.0
#: 只固定预算与随机种子；目标由调用处覆盖（**覆盖要写在展开之后**）。
BASE_SPEC = {"time_limit": TIME_LIMIT, "seed": 0}


def main() -> None:
    load_week_modules()

    print("== 第一件事：谁收得下这个实例 ==")
    print("  D6 = 2 机器 3 工序，日历 + 维护 + 换型 + 交期。")
    for method in LEGACY_METHODS:
        print(f"  {method:<18} -> {_refusal(method)}")
    for method in WEEK3_METHODS:
        print(f"  {method:<18} -> 接受")
    print("  拒收信息里点名了三个不认识的约束：`calendars, maintenances, setups`。")
    print("  这是**可诊断的失败**：调用方据此换模型，而不是拿到一条少算换型、")
    print("  跨过停机段的排程还以为它能执行。")

    print()
    print("== 第二件事：同一个可行集，两条编码的规模与耗时 ==")
    plant = generate_instance(
        201,
        jobs=4,
        machines=3,
        operations_per_job=3,
        flexibility=2,
        release_max=3,
        due_factor=1.2,
        setup_families=2,
        calendar_windows=1,
        maintenance_count=1,
    )
    print(f"  G201 = {len(plant.jobs)} 订单 / {len(plant.machines)} 机器 / "
          f"{len(plant.operations)} 工序 / {len(plant.setups)} 条换型规则 / "
          f"{len(plant.calendars)} 个日历 / {len(plant.maintenances)} 段维护")
    for machine in plant.machines:
        print(f"    {machine.id} 日历 {plant.calendar_window(machine.id)} "
              f"维护 {plant.maintenance_windows(machine.id)}")
    print()
    # 表头按**显示宽度**补空格：汉字占两列，`:<n` 只数字符不数宽度。
    print(_row("方法", "编码", "变量", "约束", "状态", "Cmax", "建模(s)", "求解(s)"))
    for method in ("fjsp_cpsat_setup", "fjsp_cpsat_calendar"):
        result = get(method)(plant, {"objective": "makespan", **BASE_SPEC})
        size = result.detail["model_size"]
        print(_row(
            method, result.detail["calendar_mode"], size["variables"], size["constraints"],
            result.status, f"{result.objective:.0f}", f"{result.build_time:.2f}",
            f"{result.solve_time:.2f}",
        ))
    print("  两条编码都拿到 63，但 `split` 的模型大三成，却解得更快：")
    print("  变量数与约束数只是规模的**描述**，不是耗时的预测——这是本次实例的实测，")
    print("  不是普遍规律。（`split` 每个候选窗一个布尔变量，窗多了还会继续涨。）")

    print()
    print("== 第三件事：单目标最优 ≠ 多目标最优 ==")
    print(_row("目标", "状态", "Cmax", "ΣT", "setup", "等权加和", aligns=("l", "l", "r", "r", "r", "r")))
    rows: dict[str, dict] = {}
    for objective in ("makespan", "total_tardiness", "total_setup_time"):
        result = get("fjsp_cpsat_setup")(plant, {"objective": objective, **BASE_SPEC})
        parts = objective_breakdown(plant, result.schedule)
        rows[objective] = parts
        print(_row(
            f"min {objective}", result.status, f"{parts['cmax']:.0f}",
            f"{parts['total_tardiness']:.0f}", f"{parts['setup']:.0f}",
            f"{_equal_sum(parts):.0f}", aligns=("l", "l", "r", "r", "r", "r"),
        ))
    balanced = get("fjsp_cpsat_multiobj")(
        plant,
        {
            "objective": "weighted_sum",
            "time_limit": TIME_LIMIT,
            "seed": 0,
            "weights": {"alpha": 1.0, "beta": 1.0, "gamma": 1.0},
            "normalization": {"mode": "none"},
        },
    )
    clean = objective_breakdown(plant, balanced.schedule)
    print(_row(
        "(1, 1, 1) 加权和", balanced.status, f"{clean['cmax']:.0f}",
        f"{clean['total_tardiness']:.0f}", f"{clean['setup']:.0f}",
        f"{_equal_sum(clean):.0f}", aligns=("l", "l", "r", "r", "r", "r"),
    ))
    best = rows["makespan"]
    print()
    print("  把四行按等权 (1, 1, 1) 加和排序：")
    print(f"    等权模型 {_equal_sum(clean):.0f} < min ΣT {_equal_sum(rows['total_tardiness']):.0f}"
          f" < min Cmax {_equal_sum(best):.0f} < min setup {_equal_sum(rows['total_setup_time']):.0f}")
    print(f"  最扎眼的是 min Cmax 那一行：它的解是 ({best['cmax']:.0f}, "
          f"{best['total_tardiness']:.0f}, {best['setup']:.0f})，")
    print(f"  而等权模型的解是 ({clean['cmax']:.0f}, {clean['total_tardiness']:.0f}, "
          f"{clean['setup']:.0f})——**Cmax 相同、setup 相同，ΣT 少 "
          f"{best['total_tardiness'] - clean['total_tardiness']:.0f} 分钟**。")
    print("  也就是说：`min Cmax` 的模型返回了一条**被支配**的排程。这不是求解器出错：")
    print("  Cmax 最小的排程有多条，模型只被要求把 Cmax 压到最小值，没有义务在这些")
    print("  并列解里挑 ΣT 最小的那条。**目标没写的量，模型不会替你优化。**")
    print("  工程含义：想让等权意义下的排程最好，就把三个分量写进同一个目标；")
    print("  只跑单目标，就要接受并列解里可能挑到差的那一条。")

    print()
    print("== 第四件事：目标覆盖不到的差异 ==")
    print("  D6 上把目标换成 `total_setup_time`：两个方向的换型都是 2 分钟，")
    print("  所以**每条**「先 A 后 B」或「先 B 后 A」的顺序都付一样的 2 分钟——目标退化了。")
    print()
    print(_row("方法", "状态", "目标值", "Cmax", "ΣT", "setup", "排程",
               aligns=("l", "l", "r", "r", "r", "r", "l")))
    for method in ("fjsp_cpsat_setup", "fjsp_cpsat_calendar"):
        result = get(method)(D6, {"objective": "total_setup_time", **BASE_SPEC})
        parts = objective_breakdown(D6, result.schedule)
        print(_row(
            method, result.status, f"{result.objective:.0f}", f"{parts['cmax']:.0f}",
            f"{parts['total_tardiness']:.0f}", f"{parts['setup']:.0f}",
            _result_line(result), aligns=("l", "l", "r", "r", "r", "r", "l"),
        ))
    print("  两行都是 OPTIMAL、目标值都是 2，但 `ΣT` 差了 12 分钟、Cmax 差了 5 分钟：")
    print("  `split` 把 `M0` 的两道工序都排进第二段窗（`B[10, 13)` 后 `A[15, 19)`），")
    print("  换型那 2 分钟正好垫在中间；`blocker` 把 `B` 排在最前面、`A` 挪到第二段开头。")
    print("  `C[0, 5)` 在另一台机器上，与这个取舍无关。")
    print("  两条都满足目标，质量却不同——**目标函数的值相等时，排程没有唯一解**，")
    print("  选到哪一条由搜索路径决定。要挑，就得把 Cmax 也写进目标（或做后处理）。")

    print()
    print("== 第五件事：不可行怎么定位 ==")
    for label, instance in _infeasible_cases():
        result = get("fjsp_cpsat_setup")(instance, {"objective": "makespan", **BASE_SPEC})
        reason = result.detail.get("failure_reason")
        line = _result_line(result)
        print(f"  {label}")
        if reason:
            print(f"    status={result.status}  原因={reason}")
        elif result.status == "INFEASIBLE":
            print(f"    status={result.status}  原因=（空——不是建模型时判死的）")
        else:
            print(f"    status={result.status}  排程={line}")
    print()
    print("  四种情形分两类：")
    print("    `operation Z fits in no allowed window` 是**建模期**判死的：")
    print("    每台机器上装得下这道工序的窗一个都没有，模型压根没有合法时间线可建；")
    print("    另两条的失败原因是空的，是**搜索期**证明的——它们各自的原因不同：")
    print("    释放时间那条是 `release = 10` 与窗 `(0, 5)` 交集为空（工序自己放得下，")
    print("    是释放时间把它推到了窗外）；窗总长那条是两道工序争同一段窗，")
    print("    单独看都放得下，合起来没有交集。")
    print("  两种 `INFEASIBLE` 要修的地方也不一样：前者要放宽日历或换机器，")
    print("  后者要么加窗、要么把释放时间提前。")
    print("  最后一条是边界对照：释放时间 12 落在**第二个**窗里，题目**可行**。")
    print("  所以「释放时间 + 日历」不是必然不可行——要看释放时刻之后还剩多少")
    print("  可用窗口，而不是看释放时间本身有多大。")


def _refusal(method: str) -> str:
    """把上一代模型拒收实例时的异常消息原样取出来。"""
    try:
        get(method)(D6, {"objective": "makespan", **BASE_SPEC})
    except ValueError as exc:
        return f"拒收：{exc}"
    return "接受"


def _infeasible_cases() -> list[tuple[str, FJSPInstance]]:
    """四个迷你实例：三种不可行 + 一条勉强可行的边界。"""
    return [
        (
            "窗比工序短：`Z` 要 11 分钟，两段窗分别只有 5 / 10 分钟",
            FJSPInstance(
                jobs=(Job("J0", ("Z",)),),
                operations=(Operation("Z", "J0", 0, (("M0", 11),)),),
                machines=(Machine("M0", "M0", calendar_id="CAL"),),
                calendars=(Calendar("CAL", ((0, 5), (10, 20))),),
            ),
        ),
        (
            "释放时间晚于最后一个窗：`release = 10`，窗只到 5",
            FJSPInstance(
                jobs=(Job("J0", ("Z",), release_time=10),),
                operations=(Operation("Z", "J0", 0, (("M0", 3),)),),
                machines=(Machine("M0", "M0", calendar_id="CAL"),),
                calendars=(Calendar("CAL", ((0, 5),)),),
            ),
        ),
        (
            "窗总长不够：两道 3 分钟的工序抢一段 5 分钟的窗",
            FJSPInstance(
                jobs=(Job("J0", ("P",)), Job("J1", ("Q",))),
                operations=(
                    Operation("P", "J0", 0, (("M0", 3),)),
                    Operation("Q", "J1", 0, (("M0", 3),)),
                ),
                machines=(Machine("M0", "M0", calendar_id="CAL"),),
                calendars=(Calendar("CAL", ((0, 5),)),),
            ),
        ),
        (
            "释放时间落在第二个窗内：`release = 12`，但窗是 `(0, 5)` 与 `(10, 20)`",
            FJSPInstance(
                jobs=(Job("J0", ("Z",), release_time=12),),
                operations=(Operation("Z", "J0", 0, (("M0", 3),)),),
                machines=(Machine("M0", "M0", calendar_id="CAL"),),
                calendars=(Calendar("CAL", ((0, 5), (10, 20))),),
            ),
        ),
    ]


def _row(*cells: object, aligns: tuple[str, ...] | None = None) -> str:
    """按**显示宽度**排一行表：汉字占两列，`str.ljust` 只数字符数。

    宽度取每一列的固定值（见 :data:`COLUMNS`），这样同一场景的表头与数据行
    一定对齐；`aligns` 里 `'r'` 表示这一列右对齐（数字列），`'l'` 左对齐。
    """
    modes = aligns or ("l",) * len(cells)
    return "  ".join(
        _pad(str(cell), COLUMNS[index], modes[index]) for index, cell in enumerate(cells)
    )


def _pad(text: str, width: int, mode: str) -> str:
    shown = sum(2 if ord(char) > 0x2E7F else 1 for char in text)
    filler = " " * max(0, width - shown)
    return filler + text if mode == "r" else text + filler


#: 各列的显示宽度。三张表共用一组宽度，省得每个表头单独数字符。
COLUMNS = (22, 10, 7, 6, 7, 9, 12, 9)


def _result_line(result) -> str:
    """把排程压成一行 `工序[开工, 完工)`，按开工时刻排序。"""
    if not result.schedule or not result.schedule.operations:
        return ""
    return ";".join(
        f"{item.operation_id}[{item.start_time}, {item.end_time})"
        for item in sorted(result.schedule.operations, key=lambda item: item.start_time)
    )


def _equal_sum(parts: dict) -> float:
    """把三个分量按等权 (1, 1, 1) 直接相加，不做归一化。"""
    return parts["cmax"] + parts["total_tardiness"] + parts["setup"]


if __name__ == "__main__":
    main()
