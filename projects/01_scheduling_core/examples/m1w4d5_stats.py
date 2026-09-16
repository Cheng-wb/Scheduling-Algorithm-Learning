"""M1W4D5 统计复盘：复算 summary.csv 的均值、演示 10/10/13 统计量、审计甘特数据。

只读 artifacts/month1_refactored：不写文件、不重新出图、不重跑基准。
"""

import csv
import json
import statistics
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_core.objective import makespan
from scheduling_core.schedule import Schedule, ScheduledOperation
from scheduling_core.schedule_validation import validate_schedule
from scheduling_io.parser import load_json_instance

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "artifacts" / "month1_refactored"
GANTT_RUN = "routes_12__main__first__0"
SHOWCASE = ("single_12", "main", "sa")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}"


def section_one(results: list[dict[str, str]], summary: list[dict[str, str]]) -> None:
    print("== 1. 统计单位：summary.csv 的一行是什么 ==")
    print("  分组键 = (instance, group, algorithm)，一行汇总同一组内的三个 seed。")
    print("  字段：" + ", ".join(summary[0]))
    print(f"  results.csv 行数 = {len(results)}（逐次运行）；summary.csv 行数 = {len(summary)}（逐组汇总）。")
    print("  successful/failed 分开计数，失败不会被当成 0 分写进均值。")
    print()


def section_two(results: list[dict[str, str]], summary: list[dict[str, str]]) -> None:
    print("== 2. 从 results.csv 手算均值，与 summary.csv 对拍 ==")
    instance, group, algorithm = SHOWCASE
    picked = [
        row
        for row in results
        if (row["instance"], row["group"], row["algorithm"]) == SHOWCASE
    ]
    row = next(
        item
        for item in summary
        if (item["instance"], item["group"], item["algorithm"]) == SHOWCASE
    )
    values = [float(item["objective"]) for item in picked]
    total = sum(values)
    print(f"  {instance} / {group} / {algorithm} 的三行 objective（seed 0,1,2）：")
    for item, value in zip(picked, values):
        print(f"    seed={item['seed']}  objective={item['objective']}  status={item['status']}  evaluations={item['evaluations']}")
    print(f"  手算：( {values[0]} + {values[1]} + {values[2]} ) / 3 = {total} / 3 = {total / 3!r}")
    print(f"  summary.csv 的 mean = {float(row['mean'])!r}")
    assert total / 3 == float(row["mean"]), SHOWCASE
    print("  两者相等：summary.csv 的均值确实来自 results.csv 的原始 objective，没有二次取整。")
    print()

    checked = 0
    for item in summary:
        key = (item["instance"], item["group"], item["algorithm"])
        scores = [
            float(other["objective"])
            for other in results
            if (other["instance"], other["group"], other["algorithm"]) == key
        ]
        assert len(scores) == int(item["successful"]), key
        assert statistics.mean(scores) == float(item["mean"]), key
        assert statistics.median(scores) == float(item["median"]), key
        assert statistics.stdev(scores) == float(item["stdev"]), key
        assert min(scores) == float(item["best"]), key
        checked += 1
    print(f"  逐组复算：{checked} 组的 mean / median / stdev / best 全部与 results.csv 一致。")
    print("  其中 stdev 由 statistics.stdev 计算，分母是 n-1（样本标准差），见第 4 节。")
    print()


def section_three(summary: list[dict[str, str]]) -> None:
    print("== 3. 10 / 10 / 13：只报一个数字会丢掉什么 ==")
    sample = [10.0, 10.0, 13.0]
    mean = statistics.mean(sample)
    median = statistics.median(sample)
    stdev = statistics.stdev(sample)
    print("  示意样本（三个 seed 的 objective）：10, 10, 13")
    print(f"  均值   mean   = (10 + 10 + 13) / 3 = 33 / 3 = {mean}")
    print(f"  中位数 median = 排序后正中间的值 = {median}")
    print(
        "  样本标准差 = √(((10-11)^2 + (10-11)^2 + (13-11)^2) / (3-1))"
        f" = √(6/2) = √3 ≈ {stdev:.16f}"
    )
    print(f"  最好值 best   = {min(sample)}")
    assert mean == 11.0 and median == 10.0 and abs(stdev * stdev - 3.0) < 1e-12
    print()
    print("  只报 best=10：这一次 13 完全消失，读者会以为三次都一样好。")
    print("  只报 mean=11：看不出 10/10/13 与 11/11/11 的区别，而后者根本没有波动。")
    print("  三个统计量回答三个不同问题：best 说「最好能到多少」，mean 说「平均如何」，")
    print("  stdev 说「不同 seed 之间差异多大」。少任何一个都会得出过强的结论。")
    print()
    print("  stdev = 0 的含义是「重复运行结果相同」，不是「解更好」。本批真实数据：")
    for instance, group, algorithm in (
        ("tiny_single", "main", "lpt"),
        ("single_12", "main", "lpt"),
        ("single_12", "main", "sa"),
    ):
        row = next(
            item
            for item in summary
            if (item["instance"], item["group"], item["algorithm"])
            == (instance, group, algorithm)
        )
        print(
            f"    {instance:<12} {algorithm:<4} mean={fmt(float(row['mean'])):<8}"
            f" median={fmt(float(row['median'])):<6} stdev={float(row['stdev']):.3f}"
            f" best={fmt(float(row['best']))}"
        )
    print("  tiny_single 的枚举 optimum=36：lpt 的 stdev 是 0，但它离 optimum 比 SA 远得多。")
    print("  确定性与随机性在这里正好相反：stdev 小只说明算法更确定，不说明算法更优。")
    print()


def section_four() -> None:
    print("== 4. 分母为什么是 n-1：样本标准差不是总体标准差 ==")
    sample = [10.0, 10.0, 13.0]
    mean = statistics.mean(sample)
    deviations = [value - mean for value in sample]
    squares = [value * value for value in deviations]
    print(f"  离差 = {deviations}，离差平方 = {squares}，离差平方和 = {sum(squares)}")
    print(f"  样本标准差（分母 n-1 = 2）：√({sum(squares)}/2) = √3 ≈ {statistics.stdev(sample):.16f}")
    print(f"  总体标准差（分母 n   = 3）：√({sum(squares)}/3) = √2 ≈ {statistics.pstdev(sample):.16f}")
    assert abs(statistics.stdev(sample) * statistics.stdev(sample) - 3.0) < 1e-12
    assert abs(statistics.pstdev(sample) * statistics.pstdev(sample) - 2.0) < 1e-12
    print("  这里把三个 seed 看作「可能运行集合」的一个样本，要估计的是运行之间的波动，")
    print("  所以用 n-1 的样本标准差（无偏方差），而不是把这三个数次运行当成总体。")
    print("  注意边界：确定性算法的三次重复不算三个独立随机样本，它的 stdev=0 只是「结果不变」。")
    print()


def section_five() -> None:
    print("== 5. 甘特数据审计：宽度必须等于加工时间 ==")
    saved = json.loads((BATCH / "runs" / f"{GANTT_RUN}.json").read_text(encoding="utf-8"))
    instance_name = GANTT_RUN.split("__")[0]
    instance = load_json_instance(BATCH / "instances" / f"{instance_name}.json")
    schedule = Schedule(
        tuple(ScheduledOperation(**item) for item in saved["schedule"]["operations"])
    )
    validate_schedule(instance, schedule)
    processing = {op.id: op.processing_time for op in instance.operations}
    jobs = {job.id: job for job in instance.jobs}
    operation_job = {op.id: op.job_id for op in instance.operations}
    print(f"  run_id = {GANTT_RUN}")
    print(f"  config = {saved['config']}")
    print(f"  独立验证器 validate_schedule 通过（不调用 decoder）；makespan = {makespan(instance, schedule)}")
    print()

    by_machine: dict[str, list] = {}
    for item in schedule.operations:
        by_machine.setdefault(item.machine_id, []).append(item)
    for machine_id in sorted(by_machine):
        items = sorted(by_machine[machine_id], key=lambda entry: entry.start_time)
        print(f"  机器 {machine_id}（{len(items)} 条）：")
        print("    工序       开始  结束  宽度(=结束-开始)  p   宽度==p")
        for item in items:
            width = item.end_time - item.start_time
            value = processing[item.operation_id]
            flag = "是" if width == value else "否"
            print(f"    {item.operation_id:<10} {item.start_time:>4} {item.end_time:>5} {width:>8} {value:>10} {flag:>7}")
            assert width == value, item.operation_id
    print()

    endings = {item.operation_id: item.end_time for item in schedule.operations}
    for machine_id in sorted(by_machine):
        items = sorted(by_machine[machine_id], key=lambda entry: entry.start_time)
        cursor = 0
        for item in items:
            if item.start_time == cursor:
                cursor = item.end_time
                continue
            job = jobs[operation_job[item.operation_id]]
            predecessors = [
                endings[before]
                for before in job.operation_ids[: job.operation_ids.index(item.operation_id)]
            ]
            if item.start_time == job.release_time:
                cause = f"{job.id} 的 release_time={job.release_time} 强制等待"
            elif predecessors and item.start_time == max(predecessors):
                cause = "job 内 precedence 强制等待（前驱工序刚结束）"
            else:
                cause = "机器上暂无可用工序"
            print(f"  {machine_id} 的空闲 [{cursor},{item.start_time})：{cause}")
            cursor = item.end_time
    print("  decoder 不会向已有空隙插入工序，所以图上的空闲都是被约束逼出来的，不是算法主动空等。")
    print("  图上每根条的绘制宽度就是 end-start（benchmark.plot 用 barh(width=end-start, left=start)），")
    print("  所以「宽度 == p」既是数据自检，也是「图与数据一致」的自检。")
    print("  但图本身不证明可行：可行性由独立验证器先判，图只帮助理解。")
    print()


def section_six() -> None:
    print("== 6. 三张图各自回答什么 ==")
    rows = [
        ("quality.png", "本批次参考 gap 的分布怎样？", "显著胜过所有方法"),
        ("convergence.png", "一个实例一个 seed 的最好值何时改善？", "平均收敛速度普遍最快"),
        ("gantt.png", "一个最好排程的机器占用与空闲如何？", "图看起来紧凑就一定可行"),
    ]
    for name, question, forbidden in rows:
        path = BATCH / name
        print(f"  {name:<17} 回答：{question}")
        print(f"  {'':<17} 不能断言：{forbidden}")
        print(f"  {'':<17} 文件 {'存在' if path.is_file() else '缺失'}（{path.stat().st_size if path.is_file() else 0} 字节）")
        assert path.is_file(), name
    print()
    print("  读图前必须先读标题：quality.png 的标题写明 Mixed instances 且带 not significance；")
    print("  它把六个实例、两个不同 objective 的归一化 gap 混在一张箱线图上，只能当描述。")
    print("  不同 objective 的原始值（ΣT 与 Cmax）永远不合并求平均，详细比较回到每实例统计表。")
    print("  convergence.png 画的是 routes_12、seed=0（实例取自 rows 顺序的最后一行 main 记录，")
    print("  seed 取自第一行），是一条轨迹，不是三 seed 平均；lpt 只有一个初始点。")
    print("  gantt.png 的 run_id 是 routes_12__main__first__0（objective=41），")
    print("  而敏感性批次在同一实例上出现过 40 —— 这张图不代表全批最优。")
    print()


def section_seven() -> None:
    print("== 7. 收敛曲线审计：best 必须单调不增 ==")
    trace = read_csv(BATCH / "runs" / "routes_12__main__sa__0.trace.csv")
    best = [float(row["best"]) for row in trace]
    current = [float(row["current"]) for row in trace]
    rises_best = [index for index in range(1, len(best)) if best[index] > best[index - 1]]
    rises_current = [index for index in range(1, len(current)) if current[index] > current[index - 1]]
    print(f"  routes_12__main__sa__0 的轨迹：{len(trace)} 个评价点")
    print(f"  best 序列：首个 {best[0]} → 末个 {best[-1]}；上升次数 = {len(rises_best)}")
    print(f"  current 序列：上升次数 = {len(rises_current)}（SA 接受坏解时 current 会变差）")
    assert not rises_best
    assert rises_current
    print("  best 单调不增是定义决定的：所谓最好，就是到此为止见过的最小值。")
    print("  若图上出现上升，先检查画的是不是 current —— current 允许上升，best 不允许。")
    print(f"  本轨迹最大一次 current 上升幅度 = {max(current[index] - current[index - 1] for index in range(1, len(current)))}")
    print()


def main() -> None:
    results = read_csv(BATCH / "results.csv")
    summary = read_csv(BATCH / "summary.csv")
    section_one(results, summary)
    section_two(results, summary)
    section_three(summary)
    section_four()
    section_five()
    section_six()
    section_seven()
    print("== 8. 结论 ==")
    print("  表格的数字必须能回到 results.csv 复算，图表只是描述性辅助。")
    print("  报告结论要同时给 best / mean / stdev，并说明样本量与失败计数。")
    print("  全部断言通过。")


if __name__ == "__main__":
    main()
