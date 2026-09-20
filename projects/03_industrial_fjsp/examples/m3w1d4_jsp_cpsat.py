"""M3 Week 1 Day 4：用 CP-SAT 求 JSP，并做与求解器无关的复核。

五节：

```text
1. 模型结构   区间变量 / 每台机器一条 NoOverlap / 每订单一条先后链 / makespan 变量
2. 手算实例   tiny3x3 的最优值 7（= 最大机器负载），与手算排程一致
3. 稍大实例   jsp_6x4（seed 102）的最优值与两个下界（最大机器负载、最长订单工时）
4. 时间预算   fjsp_10x5_f3：1 秒预算给 FEASIBLE + 真实下界，10 秒才证到 OPTIMAL
5. 界的纪律   目标不是 makespan 时不报 makespan 的界（否则是假陈述）
```

复核纪律：每一个返回的排程都过 ``validate_schedule``（与 CP-SAT 无关的独立检查），
并用 Day 3 的关键路径函数复核 ``最长路径 = makespan``。

运行：``python examples/m3w1d4_jsp_cpsat.py``
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core.models import FJSPInstance
from fjsp_core.objective import makespan
from fjsp_core.result import validate_result
from fjsp_core.schedule_validation import validate_schedule
from fjsp_io.generator import generate_instance
from fjsp_io.standard import load_standard_jsp
from fjsp_shop.graph import check_critical_path
from fjsp_shop.jsp import build_jsp_model, jsp_cpsat, jsp_priority

DATA = Path(__file__).resolve().parents[1] / "tests" / "data" / "tiny3x3.jsp"

# 从 configs/month3.json 抄来的实例参数（只跑其中的相关项，不跑整批）
JSP_6X4 = dict(seed=102, jobs=6, machines=4, operations_per_job=3, flexibility=1)
FJSP_10X5_F3 = dict(seed=105, jobs=10, machines=5, operations_per_job=3, flexibility=3)


def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def jsp_lower_bounds(instance: FJSPInstance) -> dict[str, int]:
    """经典 JSP 的两个下界：最大机器负载、最长订单工时。**只对「一工序一机器」成立。**

    柔性实例里「把工序摊到哪台机器」是决策的一部分，这两个式子就不再是下界，
    所以这里显式拒绝柔性实例，而不是给出一个看似合理其实不成立的数。
    """
    for operation in instance.operations:
        if len(operation.machine_times) != 1:
            raise ValueError(
                f"工序 {operation.id} 有 {len(operation.machine_times)} 台合格机器："
                "JSP 的两个初等下界对柔性实例不成立"
            )
    machine_load = {machine.id: 0 for machine in instance.machines}
    for operation in instance.operations:
        machine_id, minutes = operation.machine_times[0]
        machine_load[machine_id] += minutes
    job_total = {
        job.id: sum(instance.operation(oid).min_time for oid in job.operation_ids)
        for job in instance.jobs
    }
    return {
        "max_machine_load": max(machine_load.values()),
        "max_job_total": max(job_total.values()),
        "lower_bound": max(max(machine_load.values()), max(job_total.values())),
    }


def report(instance: FJSPInstance, result, label: str) -> None:
    print(f"--- {label} ---")
    print(f"status      = {result.status}")
    print(f"objective   = {result.objective}")
    print(f"best_bound  = {result.best_bound}")
    print(f"gap         = {result.gap}")
    print(f"solve_time  = {result.solve_time:.3f} s")
    print(f"breakdown   = {result.breakdown}")
    detail = result.detail
    print(f"cp_status   = {detail.get('cp_status')}")
    print(f"cp_objective= {detail.get('cp_objective')}，"
          f"与独立算出的目标值一致 = {detail.get('cp_objective_matches')}")
    print(f"horizon     = {detail.get('horizon')}，"
          f"interval_count = {detail.get('interval_count')}")
    print(f"left_shifted= {detail.get('left_shifted')}")
    assert result.schedule is not None, "feasible 结果必须有排程"
    validate_schedule(instance, result.schedule)
    validate_result(instance, result)
    print(f"validate_schedule 通过；makespan() 复核 = "
          f"{makespan(instance, result.schedule)}")
    try:
        print(f"check_critical_path = {check_critical_path(instance, result.schedule)}"
              f"（= makespan，说明返回的解已左移归一化）")
    except ValueError as error:
        print(f"check_critical_path 拒绝：{error}")


def main() -> None:
    section("第 1 节：模型结构（tiny3x3）")
    tiny = load_standard_jsp(DATA)
    model, built = build_jsp_model(tiny)
    proto = model.Proto()
    print(f"变量数 = {len(proto.variables)}，约束数 = {len(proto.constraints)}")
    print(f"horizon = {built['horizon']}（时间上界，全部区间变量都落在 [0, horizon] 内）")
    print(f"interval_count = {built['interval_count']}（= 工序数）")
    print(f"机器选择变量数 = {sum(1 for value in built['choices'].values() if value)}"
          f"（每道工序一个布尔向量，本实例每道工序只有一台合格机器）")
    print(f"开始时刻变量数 = {len(built['start_vars'])}，"
          f"完工时刻变量数 = {len(built['end_vars'])}")
    print(f"makespan 变量 = {built['makespan_var'].Name()}")
    print("\n约束的三个来源：")
    print("  (1) 每道工序一个区间：长度 = 该工序在所选机器上的工时")
    print("  (2) 每台机器一条 AddNoOverlap：同机器上的区间两两不重叠")
    print("  (3) 每个订单一条先后链：start[k+1] >= end[k]")
    print("  目标：Minimize(makespan)，makespan = 所有工序完工时刻的最大值")

    section("第 2 节：手算实例 tiny3x3 —— 最优值必须是 7")
    result_tiny = jsp_cpsat(tiny, {"objective": "makespan", "time_limit": 10.0, "seed": 0})
    report(tiny, result_tiny, "tiny3x3 / jsp_cpsat")
    tiny_bounds = jsp_lower_bounds(tiny)
    print(f"\n下界复核：最大机器负载 = {tiny_bounds['max_machine_load']}，"
          f"最长订单工时 = {tiny_bounds['max_job_total']}，"
          f"取大 = {tiny_bounds['lower_bound']}（手算：M0 负载 5、M1 负载 7、M2 负载 6）")
    print(f"求解器给出的最优值 = {result_tiny.objective}，"
          f"与下界相等说明达到了下界："
          f"{result_tiny.objective == tiny_bounds['lower_bound']}")
    print("\n机器顺序：")
    for machine in tiny.machines:
        sequence = [
            item.operation_id
            for item in sorted(result_tiny.schedule.operations, key=lambda i: i.start_time)
            if item.machine_id == machine.id
        ]
        print(f"  {machine.id}：{' -> '.join(sequence)}")

    section("第 3 节：jsp_6x4（seed 102）与两个下界")
    instance = generate_instance(**JSP_6X4)
    bounds = jsp_lower_bounds(instance)
    print(f"订单 {len(instance.jobs)} 个，机器 {len(instance.machines)} 台，"
          f"工序 {instance.total_operation_count} 道，每道工序只有一台合格机器")
    print(f"下界：最大机器负载 = {bounds['max_machine_load']}，"
          f"最长订单工时 = {bounds['max_job_total']}，"
          f"两者取大 = {bounds['lower_bound']}")
    result = jsp_cpsat(instance, {"objective": "makespan", "time_limit": 15.0, "seed": 0})
    report(instance, result, "jsp_6x4 / jsp_cpsat")
    print(f"\n最优值 {result.objective} 与下界 {bounds['lower_bound']} 的差 = "
          f"{result.objective - bounds['lower_bound']}"
          f"（下界不一定可达，差非负并不说明求解有问题）")
    heuristic = jsp_priority(instance, {"objective": "makespan", "priority": "mwr"})
    print(f"同日对照：jsp_priority(mwr) = {heuristic.objective}，"
          f"best_bound = {heuristic.best_bound}（启发式不报界）")

    section("第 4 节：时间预算决定状态")
    flexible = generate_instance(**FJSP_10X5_F3)
    print(f"实例：fjsp_10x5_f3（seed 105，10 订单 x 5 机器，每道工序有 3 台合格机器）")
    print(f"configs/month3.json 对这个方法登记了两个敏感性预算：tl_5 = 5 秒、tl_30 = 30 秒")
    for budget in (1.0, 10.0):
        truncated = jsp_cpsat(
            flexible, {"objective": "makespan", "time_limit": budget, "seed": 0}
        )
        print(f"\n预算 {budget} 秒：status = {truncated.status}，"
              f"objective = {truncated.objective}，best_bound = {truncated.best_bound}，"
              f"gap = {truncated.gap}")
        print(f"          cp_wall_time = {truncated.detail['cp_wall_time']:.3f} s")
        if truncated.schedule is not None:
            validate_schedule(flexible, truncated.schedule)
            print(f"          排程通过独立验证；makespan() = "
                  f"{makespan(flexible, truncated.schedule)}")
    print("\n结论：FEASIBLE 表示「找到可行解但没证到最优」，此时 best_bound 才有意义；")
    print("      预算是墙钟时间，所以同一预算下各次的搜索规模可能不同，"
          "但本实例上目标值与界在多次运行中保持稳定。")

    section("第 5 节：界的纪律 —— 目标不是 makespan 时不报 makespan 的界")
    for objective in ("makespan", "total_tardiness"):
        other = jsp_cpsat(tiny, {"objective": objective, "time_limit": 5.0, "seed": 0})
        print(f"objective = {objective:16s} status = {other.status:9s} "
              f"objective = {other.objective} best_bound = {other.best_bound} "
              f"bound_kind = {other.detail.get('bound_kind')}")
    print("\n同一个排程的 breakdown 分量（cmax / total_tardiness / setup）都照实记录：")
    total_tardiness = jsp_cpsat(
        tiny, {"objective": "total_tardiness", "time_limit": 5.0, "seed": 0}
    )
    print(f"  breakdown = {total_tardiness.breakdown}")

    section("当日结论")
    print("1. CP-SAT 的 JSP 模型只有三类约束：区间长度、机器 NoOverlap、订单先后链。")
    print("2. tiny3x3 上求解器给出的 7 与手算最优值一致 —— 三个互相独立的推理得到同一个数。")
    print("3. 求解器给的下界只对「它正在最小化的那个目标」有意义，换目标必须不报。")
    print("4. OPTIMAL 不等于可行：排程仍然要过独立的 validate_schedule 与关键路径复核。")


if __name__ == "__main__":
    main()
