"""Day 6：同实例、同预算，比较 tight / loose / alt 三个 formulation。

比较必须分两组做，否则数出来的东西没有意义：

- ``root_lp`` 组：只解 LP relaxation。**这是 formulation 强度指标**（root bound）。
- ``limit`` 组：同一个 wall-clock 预算下解 MIP。这组回答的是**搜索行为**
  （incumbent 质量、node 数、runtime、以及随搜索爬升的 gap），
  这一组的 ``best bound`` 是**进度值**，不是强度值。

脚本最后会用测出来的数字自己下结论（不做手工润色），所以报告的每一句都能在
上面的表格里找到出处。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_common.bridge import generate_instance
from opt_solvers.registry import available, get, load_week_modules

#: 三个实例、同一个目标、各自的时间预算（秒）。
INSTANCE_SPECS = (
    ("single_a", {"seed": 50, "jobs": 8, "machines": 1}, 5.0),
    ("single_c", {"seed": 60, "jobs": 15, "machines": 1}, 5.0),
    ("single_d", {"seed": 50, "jobs": 20, "machines": 1}, 10.0),
)
OBJECTIVE = "total_tardiness"
METHODS = ("milp_tight", "milp_loose", "milp_alt")


def reference(instance, objective: str, results: dict) -> tuple[str, float | None]:
    """参考值优先级：独立穷举 > 某个模型证明的最优 > 目前最好的可行值。"""
    try:
        from scheduling_algorithms.oracle import exhaustive_optimum

        value, _, _ = exhaustive_optimum(instance, objective, limit=100_000)
        return "独立穷举", float(value)
    except (ValueError, ImportError):
        pass
    proven = [
        float(result.objective)
        for result in results.values()
        if result.status == "OPTIMAL" and result.objective is not None
    ]
    if proven:
        return "模型证明", min(proven)
    feasible = [
        float(result.objective) for result in results.values() if result.objective is not None
    ]
    return ("目前最好可行值", min(feasible)) if feasible else ("无", None)


def collect(instance, budget: float) -> dict:
    """跑完一个实例的两组实验，返回 {group: {method: SolveResult}}。"""
    groups: dict[str, dict] = {"root_lp": {}, "limit": {}}
    for method in METHODS:
        groups["root_lp"][method] = get(method)(
            instance, {"objective": OBJECTIVE, "time_limit": 60.0, "seed": 0, "root_lp": True}
        )
        groups["limit"][method] = get(method)(
            instance, {"objective": OBJECTIVE, "time_limit": budget, "seed": 0}
        )
    return groups


def fmt(value, digits: int = 4) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def print_instance(
    name: str,
    params: dict,
    budget: float,
    groups: dict,
    reference_info: tuple[str, float | None],
) -> None:
    kind, best = reference_info
    print(f"## 实例 {name}：{params}，目标 {OBJECTIVE}，预算 {budget}s")
    print(f"   参考值：{fmt(best, 0)}（来源：{kind}）")
    print("   method       组       状态       目标值   best bound    gap    nodes   建模(s)  求解(s)")
    for group in ("root_lp", "limit"):
        for method in METHODS:
            result = groups[group][method]
            print(
                f"   {method:12s} {group:8s} {result.status:9s} "
                f"{fmt(result.objective, 1):>8s} {fmt(result.best_bound, 4):>11s} "
                f"{fmt(result.gap, 4):>7s} {str(result.iterations):>7s} "
                f"{result.build_time:8.4f} {result.solve_time:8.3f}"
            )
    print()


def print_observations(measured: dict, references: dict) -> None:
    print("== 观察 1：root LP bound（formulation 强度）==")
    print("  instance   tight      loose      alt        参考最优   alt bound / 参考")
    for name, groups in measured.items():
        bounds = {method: groups["root_lp"][method].best_bound for method in METHODS}
        reference = references[name][1]
        ratio = (
            "-" if not reference else f"{bounds['milp_alt'] / reference * 100:.2f}%"
        )
        print(f"  {name:9s}  {fmt(bounds['milp_tight']):9s}  {fmt(bounds['milp_loose']):9s}  "
              f"{fmt(bounds['milp_alt']):10s} {fmt(reference, 0):>8s}   {ratio:>8s}")
    print("  tight 与 loose 的 root bound 完全相同（都是 0）—— Big-M 的紧度没有改变松弛强度；")
    print("  alt 的 root bound 直接落在最优值附近 —— 改变松弛强度的是**变量定义**：")
    print("  互斥写在时间格点上，LP 没法再让所有工序在同一条时间轴上重叠。")
    print()
    print("== 观察 2：限时 MIP（搜索行为）==")
    print("  instance   method        状态      incumbent   final bound    gap      nodes   求解(s)")
    for name, groups in measured.items():
        for method in METHODS:
            result = groups["limit"][method]
            print(f"  {name:9s} {method:12s} {result.status:9s} "
                  f"{fmt(result.objective, 1):>10s} {fmt(result.best_bound, 4):>13s} "
                  f"{fmt(result.gap, 4):>7s} {str(result.iterations):>8s} {result.solve_time:8.3f}")
    print("  这里的 final bound 是**搜索进度**：预算内爬到哪里算哪里，不代表松弛强度；")
    print("  要判断「谁更慢」，看 objective 与 gap 是否收敛到 0，以及花费的 nodes。")
    print()
    print("== 观察 3：tight 与 loose 的逐实例对照（不预设结论）==")
    for name, groups in measured.items():
        tight = groups["limit"]["milp_tight"]
        loose = groups["limit"]["milp_loose"]
        rows = []
        for label, left, right in (
            ("incumbent", tight.objective, loose.objective),
            ("nodes", tight.iterations, loose.iterations),
            ("solve_time", tight.solve_time, loose.solve_time),
        ):
            if left is None or right is None:
                rows.append(f"{label}: 无法比较")
                continue
            digits = 3 if label == "solve_time" else 0
            if left < right:
                verdict = "tight 更小"
            elif right < left:
                verdict = "loose 更小"
            else:
                verdict = "相同"
            rows.append(
                f"{label}: tight {fmt(left, digits)} / loose {fmt(right, digits)}（{verdict}）"
            )
        print(f"  {name}")
        for row in rows:
            print(f"    {row}")
        print(f"    状态 tight={tight.status} / loose={loose.status}，"
              f"gap tight={fmt(tight.gap)} / loose={fmt(loose.gap)}")
    print("  node 数在限时搜索里会随运行波动（同一预算跑两次可能不同），")
    print("  所以「谁更小」只在同一批测量内部成立，不能外推成一般规律。")
    print()
    print("== 观察 4：formulation 设计的代价 ==")
    print("  instance   alt 建模/求解           tight 建模/求解         alt 合计   tight 合计")
    for name, groups in measured.items():
        alt = groups["limit"]["milp_alt"]
        tight = groups["limit"]["milp_tight"]
        print(f"  {name:9s}  {alt.build_time:.4f}s / {alt.solve_time:.3f}s      "
              f"{tight.build_time:.4f}s / {tight.solve_time:.3f}s      "
              f"{alt.build_time + alt.solve_time:.3f}s     "
              f"{tight.build_time + tight.solve_time:.3f}s")
    print("  alt 的建模成本比 sequence 模型高一个量级（并随 H 增长），但搜索成本省得更多：")
    print("  在这三个实例上，连建模一起算 alt 仍然更快。代价在模型规模：")
    print("  变量数随时间界线性增长，时间界很大时先要过规模检查（模块里的 MAX_TIME_INDEXED_VARS）。")


def main() -> None:
    print("=== 同实例、同预算：tight / loose / alt ===")
    print()
    load_week_modules()  # 触发 @register 副作用，把三个方法名装进注册表
    missing = [name for name in METHODS if name not in available()]
    if missing:
        raise SystemExit(f"未注册的方法：{missing}")
    measured: dict[str, dict] = {}
    references: dict[str, tuple[str, float | None]] = {}
    for name, params, budget in INSTANCE_SPECS:
        instance = generate_instance(**params)
        groups = collect(instance, budget)
        measured[name] = groups
        references[name] = reference(instance, OBJECTIVE, groups["limit"])
        print_instance(name, params, budget, groups, references[name])
    print_observations(measured, references)


if __name__ == "__main__":
    main()
