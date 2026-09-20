"""M3 Week 1 Day 7：本周复盘 —— 交付核对、总表、以及一次自测。

五节：

```text
1. 交付核对   四个注册方法、五个模块文件、测试文件与手写样例是否都在
2. 总表       四个实例 x 四个方法：状态 / 目标值 / 界 / 与最优的差 / 耗时
3. 测试       从项目目录跑一次 python -m pytest -q，打印结果行
4. 适用条件   每个方法一句话的适用范围与陷阱
5. 自测       五个问题先自己答，再看脚本算出来的答案
```

运行：``python examples/m3w1d7_week1_review.py``
"""

import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.result import validate_result
from fjsp_core.schedule_validation import validate_schedule
from fjsp_io.generator import generate_instance
from fjsp_shop.flowshop import flow_johnson, flow_neh
from fjsp_shop.jsp import PRIORITY_RULES, jsp_cpsat, jsp_priority
from fjsp_shop.registry import available, load_week_modules

PROJECT = Path(__file__).resolve().parents[1]
WEEK1_METHODS = ("flow_johnson", "flow_neh", "jsp_priority", "jsp_cpsat")
DELIVERABLES = (
    "fjsp_shop/flowshop.py",
    "fjsp_shop/jsp.py",
    "fjsp_shop/graph.py",
    "fjsp_shop/gantt.py",
    "fjsp_io/standard.py",
    "fjsp_experiments/week1_gantt.py",
    "tests/test_week1.py",
    "tests/data/tiny2x2.jsp",
    "tests/data/tiny3x3.jsp",
    "tests/data/tiny4x2.jsp",
)
INSTANCES = (
    ("flow_5x3", dict(seed=100, jobs=5, machines=3, operations_per_job=3,
                      flow_shop=True, flexibility=1)),
    ("flow_8x4", dict(seed=101, jobs=8, machines=4, operations_per_job=4,
                      flow_shop=True, flexibility=1)),
    ("jsp_6x4", dict(seed=102, jobs=6, machines=4, operations_per_job=3, flexibility=1)),
    ("jsp_8x5", dict(seed=103, jobs=8, machines=5, operations_per_job=4, flexibility=1)),
)
METHODS = {
    "flow_johnson": lambda instance: flow_johnson(instance, {"objective": "makespan"}),
    "flow_neh": lambda instance: flow_neh(instance, {"objective": "makespan"}),
    "jsp_priority": lambda instance: jsp_priority(
        instance, {"objective": "makespan", "priority": "mwr"}
    ),
    "jsp_cpsat": lambda instance: jsp_cpsat(
        instance, {"objective": "makespan", "time_limit": 30.0, "seed": 0}
    ),
}


def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def main() -> None:
    section("第 1 节：交付核对")
    print(f"只 import 了本周的两个模块时，available() = {available()}")
    failures = load_week_modules()
    registered = available()
    print(f"\n导入仓库里全部模块后，available() 里一共有 {len(registered)} 个方法；"
          f"本周四个是否都在："
          f"{all(method in registered for method in WEEK1_METHODS)}")
    print("（这一行只报个数不报名字：名字属于各自的模块，核对本周只看交集。）")
    print(f"load_week_modules() 没能导入的模块："
          f"{failures if failures else '无（当前全部导入成功）'}")
    for method in WEEK1_METHODS:
        print(f"  注册方法 {method:14s} 在 registry 里：{method in registered}")
    missing = [method for method in WEEK1_METHODS if method not in registered]
    assert not missing, f"缺少注册方法：{missing}"
    print("\n本周文件：")
    for relative in DELIVERABLES:
        path = PROJECT / relative
        if path.exists():
            print(f"  {relative:36s} {path.stat().st_size:7d} 字节")
        else:
            print(f"  {relative:36s} 缺失")

    section("第 2 节：四个实例 x 四个方法")
    header = (f"{'实例':10s} {'方法':14s} {'状态':9s} {'目标值':>6s} {'界':>6s} "
              f"{'与最优差':>8s} {'耗时':>8s}")
    print(header)
    print("-" * len(header))
    observations: list[str] = []
    for name, spec in INSTANCES:
        instance = generate_instance(**spec)
        reference = jsp_cpsat(instance, {"objective": "makespan", "time_limit": 30.0, "seed": 0})
        assert reference.status == "OPTIMAL", "参考解必须是 OPTIMAL，否则不能当参照"
        validate_schedule(instance, reference.schedule)
        for method_name in WEEK1_METHODS:
            result = METHODS[method_name](instance)
            if result.schedule is not None:
                validate_schedule(instance, result.schedule)
                validate_result(instance, result)
            bound = "-" if result.best_bound is None else f"{result.best_bound:.0f}"
            if result.objective is None:
                value, gap = "-", "-"
            else:
                value = f"{result.objective:.0f}"
                gap = f"{result.objective - reference.objective:.0f}"
            print(f"{name:10s} {method_name:14s} {result.status:9s} "
                  f"{value:>6s} {bound:>6s} {gap:>8s} {result.solve_time:7.3f}s")
        observations.append(
            f"{name}：CP-SAT 最优 {reference.objective:.0f}"
            f"（{reference.detail.get('branches')} 分支），"
            f"NEH {flow_neh(instance, {}).objective if instance.meta['flow_shop'] else '不适用'}"
        )
    print("\n参考列（CP-SAT 的结果就是参考，它是 OPTIMAL）：")
    for line in observations:
        print(f"  {line}")

    section("第 3 节：跑一次测试（只跑 Week 1 相关的两个文件）")
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q",
         "tests/test_week1.py", "tests/test_foundation.py"],
        cwd=PROJECT, capture_output=True, text=True, check=False,
    )
    tail = [line for line in completed.stdout.strip().splitlines() if line.strip()]
    print(f"工作目录 = {PROJECT}")
    print(f"命令 = python -m pytest -q tests/test_week1.py tests/test_foundation.py")
    print(f"返回码 = {completed.returncode}")
    print(f"结果行 = {tail[-1] if tail else '(无输出)'}")
    print("说明：这里只跑 Week 1 自己的用例（tests/test_week1.py）与共享地基的 40 个用例")
    print("      （tests/test_foundation.py，本周没有改动它）。整仓库的总数会随仓库里的")
    print("      文件增减而变化，不是一个稳定的核对量，所以不作为本节的判据。")

    section("第 4 节：四个方法的适用范围（一句话版）")
    print("  flow_johnson  只对 F2||Cmax 精确；>=3 台机器退化为瓶颈机对上的 Johnson，")
    print("                状态报 FEASIBLE 并在 detail 里写清 applicability。")
    print("  flow_neh      m 台机器 flow shop 的启发式：总工时降序逐个插到最靠前的最优位置。")
    print("  jsp_priority  非延迟列表调度 + 优先级规则（mwr/mopnr/spt/lpt/fifo），")
    print("                规则可换但结果确定性不变；带日历/维护/资源时明确 FAILED。")
    print("  jsp_cpsat     JSP 与「每道工序多台合格机器」都能建模；返回前做左移归一化，")
    print("                只有目标就是 makespan 时才报下界。")

    section("第 5 节：自测（先自己答，再看脚本算的）")
    print("自测 1：三台机器时 Johnson 给出的 11 是最优吗？")
    from examples.m3w1d1_flowshop_rules import THREE_MACHINE, build_flow_shop

    three_flow = build_flow_shop(THREE_MACHINE)
    johnson = flow_johnson(three_flow, {})
    neh = flow_neh(three_flow, {})
    print(f"  答：不是。本实例 Johnson = {johnson.objective}，NEH = {neh.objective}，")
    print(f"      枚举最优 = 10（Day 5 的枚举器算过），Johnson 只是启发式。")

    print("\n自测 2：启发式结果的 best_bound 应该是多少？")
    print(f"  答：{neh.best_bound}（None）。下界只能由能给出证明的方法提供，")
    print("      拿目标值当下界是假陈述。")

    print("\n自测 3：什么时候「最长路径长度 = makespan」成立？")
    print("  答：排程是左移的（每道工序都取最早可行开工时刻）时成立；")
    print("      被人工推迟过的排程上不成立，Day 3 第 4 节演示过。")

    print("\n自测 4：标准格式解析器的验证强度到哪？")
    print("  答：只用 tests/data/ 下手写的同格式小文件验证过；")
    print("      OR-Library 原始的 FT/LA/ABZ 文件不在本仓库，也没有下载。")

    print("\n自测 5：五条优先级规则里哪条最好？")
    for name, _ in INSTANCES:
        instance = generate_instance(**dict(INSTANCES)[name])
        values = {
            rule: jsp_priority(instance, {"objective": "makespan", "priority": rule}).objective
            for rule in PRIORITY_RULES
        }
        best = min(values, key=lambda rule: values[rule])
        print(f"  {name}：最好的是 {best}，各规则 = "
              f"{', '.join(f'{rule} {values[rule]:.0f}' for rule in PRIORITY_RULES)}")
    print("  答：没有一条在四个实例上都最好（flow shop 上 spt 领先，job shop 上 mwr 领先），")
    print("      所以只报观察，不据此调参。")

    section("当日结论")
    print("1. 四个方法都在 registry 里注册，都能被 configs/month3.json 直接调用。")
    print("2. 每个返回的排程在这一整周里都过了独立的 validate_schedule。")
    print("3. 启发式与精确解法的差别被如实记录：状态不同、有没有界不同、与最优的差不同。")
    print("4. 「不适用」和「更差」是两件事：job shop 上的 flow 方法报 FAILED，不是报一个大数。")


if __name__ == "__main__":
    main()
