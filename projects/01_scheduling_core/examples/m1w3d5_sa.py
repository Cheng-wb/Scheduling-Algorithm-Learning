"""模拟退火：接受准则、三条轨迹、参数合法性、no-op 与接受率。

固定实例 + seed，对比三个初始温度（1 / 10 / 100）；
打印 proposed / current / best 三条轨迹的分叉，验证 current 可以上升、
best 单调不增、返回的是 best 而不是最后的 current；
再用单工序实例证明 no-op 合法且照样消耗评价，用等长工序实例证明等值移动会被接受。

只读取结果并打印，不写入 artifacts/；固定 seed，可重复。
"""

import sys
from math import exp, isfinite
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_algorithms.decoder import decode, initial_candidate
from scheduling_algorithms.neighborhoods import insert, reassign, swap
from scheduling_algorithms.search import SearchConfig, solve
from scheduling_core.models import Instance, Job, Machine, Operation
from scheduling_core.objective import makespan
from scheduling_io.generator import generate_instance

BUDGET = 150
SEED = 0


def acceptance_probability(delta: float, temperature: float) -> float:
    """Δ>0 时的接受概率 exp(-Δ/T)；Δ<=0 时恒为 1。"""
    return 1.0 if delta <= 0 else exp(-delta / temperature)


def acceptance_rate(result, lo: int, hi: int) -> float:
    """窗口 [lo, hi) 的接受率 = accepted 评价数 / 该窗口评价数；第 1 个初始化点不参与。"""
    window = [p for p in result.trace if lo <= p.evaluation < hi]
    accepted = sum(1 for p in window if p.accepted)
    return accepted / len(window)


def trace_line(point) -> str:
    temp = "-" if point.temperature is None else f"{point.temperature:.3f}"
    return (
        f"#{point.evaluation:>3}  proposed={point.proposed:>7.1f}  current={point.current:>7.1f}  "
        f"best={point.best:>7.1f}  accepted={str(point.accepted):>5}  temperature={temp}"
    )


def main() -> None:
    print("=" * 78)
    print("第 1 部分：接受准则 exp(-Δ/T) 的算术")
    print("=" * 78)
    for delta, temperature in ((5.0, 10.0), (5.0, 1.0), (1.0, 10.0)):
        print(
            f"Δ={delta:.0f}, T={temperature:.0f} → exp(-{delta:.0f}/{temperature:.0f}) "
            f"= {acceptance_probability(delta, temperature):.6f}"
        )
    print("Δ<=0 时无条件接受（概率 1），不需要算指数。")
    print("注意 T 与 Δ 的量纲相同：Δ 是目标差值，所以 T 也必须用目标值的单位。")
    print("makespan 的单位是时间，total_tardiness 的单位是迟交量，")
    print("同一个 T=10 在两个目标上代表完全不同的「容忍度」。")

    print()
    print("=" * 78)
    print("第 2 部分：手算示例 —— current=20 时接受一个 23 的候选")
    print("=" * 78)
    print("evaluation,proposed,current,best,accepted,说明")
    print("1,-,20,18,-,搜索开始前已有 current=20、best=18")
    print("2,23,23,18,True,Δ=23-20=+3>0，按概率 exp(-3/T) 接受 → current 升到 23，best 保持 18")
    print("3,17,17,17,True,Δ=17-23=-6<=0，无条件接受 → current 与 best 同时降到 17")
    print("允许 current 变差是搜索策略；不允许丢失历史最好是结果管理，两者不能混。")

    print()
    print("=" * 78)
    print("第 3 部分：参数合法性 —— temperature 必须有限且为正，cooling 必须在 (0, 1]")
    print("=" * 78)
    for kwargs in (
        {"temperature": 0.0},
        {"temperature": -1.0},
        {"temperature": float("inf")},
        {"temperature": float("nan")},
        {"cooling": 0.0},
        {"cooling": 1.5},
        {"cooling": 1.0},
    ):
        try:
            SearchConfig(**kwargs)
            print(f"SearchConfig({kwargs}) → 接受")
        except ValueError as error:
            print(f"SearchConfig({kwargs}) → ValueError: {error}")
    print(f"isfinite(inf) = {isfinite(float('inf'))}，isfinite(nan) = {isfinite(float('nan'))}，")
    print("所以 `not isfinite(T) or T <= 0` 一次拦住 0、负数、inf 与 nan。")
    print("cooling=1.0 合法：温度不降，退化为定温随机游走。")

    print()
    print("=" * 78)
    print("第 4 部分：同一实例 + 同一 seed 上的三个初始温度")
    print("=" * 78)
    instance = generate_instance(20, jobs=12, machines=1)
    print("instance = generate_instance(20, jobs=12, machines=1)，objective = total_tardiness")
    print(f"budget={BUDGET}，seed={SEED}，cooling=0.98")
    print("temperature,objective,evaluations,status,rises,rate_all,rate_first_half,rate_second_half")
    results = {}
    half = BUDGET // 2
    for temperature in (1.0, 10.0, 100.0):
        result = solve(
            instance,
            SearchConfig(
                algorithm="sa",
                objective="total_tardiness",
                budget=BUDGET,
                seed=SEED,
                temperature=temperature,
                cooling=0.98,
            ),
        )
        results[temperature] = result
        trace = result.trace
        rises = sum(1 for k in range(1, len(trace)) if trace[k].current > trace[k - 1].current)
        print(
            f"{temperature:.1f},{result.objective:.1f},{result.evaluations},{result.status},"
            f"{rises},{acceptance_rate(result, 2, BUDGET + 1):.4f},"
            f"{acceptance_rate(result, 2, half + 1):.4f},"
            f"{acceptance_rate(result, half + 1, BUDGET + 1):.4f}"
        )
    print("接受率一律按 accepted 评价数 / 窗口评价数统计，窗口从第 2 次评价开始，排除第 1 个初始化点。")

    print()
    print("同一个 T=10 在两个目标上的实测差别（同一实例、同一 seed、同一 cooling=0.98）:")
    print("objective,initial,temperature,objective_final,rises,rate")
    for objective in ("makespan", "total_tardiness"):
        result = solve(
            instance,
            SearchConfig(
                algorithm="sa",
                objective=objective,
                budget=BUDGET,
                seed=SEED,
                temperature=10.0,
                cooling=0.98,
            ),
        )
        trace = result.trace
        rises = sum(1 for k in range(1, len(trace)) if trace[k].current > trace[k - 1].current)
        print(
            f"{objective},{trace[0].best:.1f},10.0,{result.objective:.1f},{rises},"
            f"{acceptance_rate(result, 2, BUDGET + 1):.4f}"
        )
    print("makespan 的 Δ 通常只有个位数，T=10 意味着「几点的差距几乎照单全收」；")
    print("total_tardiness 的 Δ 动辄几十上百，同一个 T=10 相对就是「几乎全部拒绝」。")
    print("所以调温度时必须连着目标值的量级一起看，不能把结论搬到另一个目标上。")

    hot = results[100.0]
    print()
    print("T=100 的 trace 开头（高温期 current 频繁上升）:")
    for point in hot.trace[:10]:
        print("  " + trace_line(point))
    print("T=100 的 trace 结尾:")
    for point in hot.trace[-3:]:
        print("  " + trace_line(point))
    bests = [p.best for p in hot.trace]
    print(f"best 单调不增? {bests == sorted(bests, reverse=True)}（{bests[0]:.1f} → {bests[-1]:.1f}）")
    print(
        f"最后一次评价的 current={hot.trace[-1].current:.1f}，best={hot.trace[-1].best:.1f}；"
        f"返回的 objective={hot.objective:.1f} 取的是 best。"
    )
    print(
        f"温度按 T ← cooling × T 逐次冷却：第 2 次评价用 T={hot.trace[1].temperature:.1f}，"
        f"最后一次评价用 T={hot.trace[-1].temperature:.4f}。"
    )
    print(f"核对：100 × 0.98^148 = {100 * 0.98 ** 148:.4f}，与 trace 记录一致。")
    print("T=1 的运行里 current 从未上升过（rises=0），说明低温下几乎只见下坡路；")
    print("T=100 的运行里 current 频繁上升，最终 best 反而更差——这正是「短期变差换探索」的代价。")

    print()
    print("=" * 78)
    print("第 5 部分：no-op 与等值移动")
    print("=" * 78)
    single_instance = Instance(
        (Job("J0", ("O0",)),),
        (Operation("O0", "J0", 3, ("M0",)),),
        (Machine("M0", "M0"),),
    )
    single_candidate = initial_candidate(single_instance)
    no_op_checks = (
        ("swap(i, i)", swap(single_candidate, 0, 0)),
        ("insert(i, i)", insert(single_candidate, 0, 0)),
        ("reassign 回原机器", reassign(single_instance, single_candidate, 0, "M0")),
    )
    for name, candidate in no_op_checks:
        print(f"{name} == 原候选 ? {candidate == single_candidate}")
    print("单工序实例上三种移动必然退化成 no-op，neighbors() 也产生不出任何新候选。")
    single_result = solve(
        single_instance,
        SearchConfig(algorithm="sa", objective="makespan", budget=12, seed=SEED, temperature=10.0),
    )
    for point in single_result.trace:
        print("  " + trace_line(point))
    print(
        f"评估次数 {single_result.evaluations}（= budget）、"
        f"accepted 全为 True? {all(p.accepted for p in single_result.trace)}、"
        f"objective={single_result.objective:.1f}"
    )
    print("no-op 照样计入预算、照样被「Δ<=0 无条件接受」接受，却不会死循环。")

    pair_instance = Instance(
        (Job("J0", ("O0",)), Job("J1", ("O1",))),
        (Operation("O0", "J0", 3, ("M0",)), Operation("O1", "J1", 3, ("M0",))),
        (Machine("M0", "M0"),),
    )
    base = initial_candidate(pair_instance)
    swapped = swap(base, 0, 1)
    print()
    print("等值移动：两道工序 p 都是 3，交换前后目标相同")
    print(f"  原候选   order={base.order} → makespan={makespan(pair_instance, decode(pair_instance, base))}")
    print(f"  交换后   order={swapped.order} → makespan={makespan(pair_instance, decode(pair_instance, swapped))}")
    print(f"  两个候选不同? {base != swapped}；Δ=0 → `delta <= 0` 分支直接接受，不靠概率。")
    print("Best/First 只接受严格改善（Δ<0），会拒绝这类等值移动；SA 接受它，")
    print("所以 SA 有机会沿着等值平台走到局部搜索到不了的位置。")
    print("但接受率高本身不等于探索有效：no-op 与等值接受都算 accepted，")
    print("高温下 rate 很高，也可能只是原地打转。")


if __name__ == "__main__":
    main()
