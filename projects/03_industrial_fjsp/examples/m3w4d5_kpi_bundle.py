"""M3 Week 4 Day 5：多目标 KPI 与完整 JSON 输入输出。

两件事：

* ``fjsp_io.kpi`` 把一条排程读成一组 KPI（``Cmax``、``ΣT``、加权迟期、换型、
  ``utilization``、准时率…），每个数都能回到排程上手工核一遍；
* ``fjsp_io.json_bundle`` 把「实例 + 结果 + KPI」写进**一个** JSON，读回来
  与原件逐字段相等。排程不是只存在内存里 —— 存下来读回来还是同一条。

从任何工作目录都能跑：
    python examples/m3w4d5_kpi_bundle.py
"""

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.objective import evaluate, parse_weights, total_setup_time
from fjsp_experiments.w4_industrial import ablation_instance
from fjsp_io.json_bundle import Bundle, bundles_equal, make_bundle
from fjsp_io.kpi import format_kpi, kpi_report, normalize
from fjsp_shop.registry import get, load_week_modules

SPEC = {"objective": "makespan", "time_limit": 15.0, "seed": 0}


def main() -> None:
    load_week_modules()
    instance = ablation_instance("+worker")
    result = get("fjsp_cpsat_full")(instance, dict(SPEC))
    schedule = result.schedule
    print(f"=== 1. 先解一条排程（status={result.status}，Cmax={result.objective:g}）===")
    for item in sorted(schedule.operations, key=lambda x: x.start_time):
        print(
            f"  {item.operation_id}  {item.machine_id}"
            f"  [{item.start_time},{item.end_time})  {item.worker_id}"
        )

    print()
    print("=== 2. KPI 报告 ===")
    report = kpi_report(instance, schedule)
    print(format_kpi(report))

    print()
    print("=== 3. 抽三个数手工核对 ===")
    # ScheduledOperation 只记 operation_id，订单归属要从实例的工序表反查。
    job_of = {op.id: op.job_id for op in instance.operations}
    completions = {
        job.id: max(
            item.end_time
            for item in schedule.operations
            if job_of[item.operation_id] == job.id
        )
        for job in instance.jobs
    }
    print(f"  完工时刻：{completions}")
    by_due = [
        f"{job.id}: max(0,{completions[job.id]}-{job.due_date})"
        for job in instance.jobs
        if job.due_date is not None
    ]
    print(f"  迟期项：{'；'.join(by_due)}")
    print(f"  报告里的 total_tardiness = {report.total_tardiness}（上式的和）")
    print(f"  换型：独立函数 total_setup_time = {total_setup_time(instance, schedule)}"
          f"　报告里的 setup_time = {report.setup_time}")
    print("  工人负载：")
    for item in report.worker_kpi:
        print(
            f"    {item.resource_id} load={item.load} span={item.span} "
            f"utilization={item.utilization:g}"
        )
    print("  注意 span 不是 load：工人可能闲着等机器。utilization = load / span。")

    print()
    print("=== 4. JSON bundle 往返 ===")
    bundle = make_bundle(instance, result)
    text = json.dumps(bundle.to_dict(), ensure_ascii=False, sort_keys=True)
    print(f"  序列化长度：{len(text)} 字符")
    restored = Bundle.from_dict(json.loads(text))
    print(f"  bundles_equal(原件, 读回来) = {bundles_equal(bundle, restored) or '[] 完全相等'}")
    print("  往返比的是：实例、排程（每道工序的机器/时刻/资源）、KPI 每个字段。")

    print()
    print("=== 5. 改一个数字，看差异清单能不能指出位置 ===")
    raw = json.loads(text)
    raw["result"]["schedule"]["operations"][0]["end_time"] += 1
    broken = Bundle.from_dict(raw)
    print(f"  bundles_equal(原件, 被改过) = {bundles_equal(bundle, broken)}")
    print("  返回的是**差异清单**而不是 True/False，就是为了这一刻。")

    print()
    print("=== 6. 归一化：相对参考排程打分 ===")
    reference = kpi_report(
        instance,
        get("fjsp_cpsat_full")(ablation_instance("+locked"), dict(SPEC)).schedule,
    )
    values = normalize(report, reference)
    for key, value in sorted(values.items()):
        print(f"  {key:22s} {value:g}")
    print(f"  Cmax 复核：{report.cmax} / {reference.cmax} = {report.cmax / reference.cmax:g}")


if __name__ == "__main__":
    main()
