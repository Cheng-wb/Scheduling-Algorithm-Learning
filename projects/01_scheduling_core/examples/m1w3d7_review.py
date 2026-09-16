"""M1W3D7 复盘：方法对照表、共同保证与默认配置下的一次小实例对照实验。"""

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_algorithms.oracle import exhaustive_optimum
from scheduling_algorithms.search import SearchConfig, solve
from scheduling_core.objective import total_tardiness
from scheduling_io.generator import generate_instance

ROOT = Path(__file__).resolve().parents[1]

METHODS = [
    (
        "random",
        "重抽一个随机排列与一组随机合法指派",
        "只保留严格改善的候选，否则丢弃",
        "大量无效抽样，几乎不看邻域结构",
    ),
    (
        "first",
        "按固定扫描顺序取第一个严格改善的邻居",
        "等值与更差的邻居都不接受",
        "对扫描顺序敏感，可能拿到的是「第一个」而非「最好」",
    ),
    (
        "best",
        "把一整圈邻居扫完，再取其中最好的改善邻居",
        "等值与更差的邻居都不接受",
        "每轮评价数最多，预算容易被一整圈扫描吃光",
    ),
    (
        "multistart",
        "first 扫描到局部最优后，用随机起点重启",
        "重启本身可以把当前解变差，但不覆盖历史最好",
        "探索深度与起点数的取舍，重启评价也计预算",
    ),
    (
        "sa",
        "按 rng 选 swap / insert / reassign 随机邻居",
        "等值接受，更差的按 exp(-Δ/T) 概率接受",
        "对参数与目标尺度敏感，需要多种子观察分布",
    ),
]


def fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}"


def print_method_table() -> None:
    print("== 1. 五种搜索方法对照（不只看名字） ==")
    for name, step, treatment, cost in METHODS:
        print(f"{name:<11} 下一步：{step}")
        print(f"{'':<11} 等值/坏解：{treatment}")
        print(f"{'':<11} 主要代价：{cost}")
    print()


def print_guarantees() -> None:
    print("== 2. 共同保证与共同不保证 ==")
    print("共同保证：")
    print("  - 不超过预算：评价数 <= budget，初始化、no-op、拒绝、重启全部计入。")
    print("  - 返回已发现的最好可行解：返回的是历史 best，不是最后一次 current。")
    print("  - 固定配置下轨迹可复现：同 Instance + 同 SearchConfig 得到同一条 trace。")
    print("共同不保证：")
    print("  - 一般实例上的全局最优：有限预算的启发式只给可行解，不给最优性证明。")
    print()


def print_default_config(config: dict) -> None:
    search = config["search"]
    print("== 3. 本月默认配置（configs/month1.json） ==")
    print(f"  seeds            = {config['seeds']}")
    print(f"  algorithms       = {config['algorithms']}")
    print(f"  budget           = {search['budget']}")
    print(f"  temperature (T0) = {search['temperature']}")
    print(f"  cooling          = {search['cooling']}")
    print(f"  restart_interval = {search['restart_interval']}")
    print(f"  sensitivity      = {[item for item in config['sensitivity']]}")
    print("  来源：可快速重跑的教学设置，不是独立验证集上选出的生产参数。")
    print()


def main() -> None:
    config = json.loads((ROOT / "configs" / "month1.json").read_text(encoding="utf-8"))
    search = config["search"]
    budget = search["budget"]

    print_method_table()
    print_guarantees()
    print_default_config(config)

    # 与 configs/month1.json 的 tiny_single 完全同参数：seed=10、4 个单机作业。
    instance = generate_instance(10, jobs=4, machines=1)
    optimum, _, enumerated = exhaustive_optimum(instance, "total_tardiness")
    print("== 4. 小实例真实对照（seed=10, 4 jobs, 1 machine, total_tardiness） ==")
    print(f"  枚举参考：{enumerated} 个组合，optimum = {fmt(optimum)}")
    print(f"  {'算法':<11}{'objective':>10}{'evaluations':>13}  status")
    table: dict[str, dict] = {}
    for algorithm in config["algorithms"]:
        settings = SearchConfig(
            algorithm=algorithm,
            objective="total_tardiness",
            budget=budget,
            seed=config["seeds"][0],
            temperature=search["temperature"],
            cooling=search["cooling"],
            restart_interval=search["restart_interval"],
        )
        result = solve(instance, settings)
        replay = solve(instance, settings)
        table[algorithm] = {
            "objective": result.objective,
            "evaluations": result.evaluations,
            "status": result.status,
        }
        print(
            f"  {algorithm:<11}{fmt(result.objective):>10}{result.evaluations:>13}  {result.status}"
        )

        # 共同保证：不超预算、返回最好可行解、固定配置可复现。
        assert result.evaluations == len(result.trace) <= budget
        assert result.objective == total_tardiness(instance, result.schedule)
        assert result.objective == result.trace[-1].best
        assert [point.best for point in result.trace] == sorted(
            (point.best for point in result.trace), reverse=True
        )
        assert result.trace == replay.trace and result.schedule == replay.schedule

    # First / Best 在邻域扫完且无改善时提前停机。
    for algorithm in ("first", "best"):
        assert table[algorithm]["status"] == "LOCAL_OPTIMUM"
        assert table[algorithm]["evaluations"] < budget
    # random / sa / multistart 用满预算。
    for algorithm in ("random", "sa", "multistart"):
        assert table[algorithm]["evaluations"] == budget
        assert table[algorithm]["status"] == "BUDGET"
    # multistart 遇到「没移动」会重启而不是停机，因此永远不会返回 LOCAL_OPTIMUM。
    assert table["multistart"]["status"] != "LOCAL_OPTIMUM"
    print()

    print("== 5. 结论 ==")
    print(
        f"  同一实例、同一预算 {budget} 下：first/best 因邻域扫尽提前停机，"
        f"random/sa/multistart 用满全部评价。"
    )
    print(
        f"  LPT 基线 objective={fmt(table['lpt']['objective'])} 高于枚举 optimum={fmt(optimum)}，"
        f"说明「返回一个可行解」不等于「返回最优解」。"
    )
    print("  提前停机不是坏事也不是好事，它只是让横轴长度不同：画收敛曲线时不能把早停画成跑满预算。")
    print("  全部断言通过。")


if __name__ == "__main__":
    main()
