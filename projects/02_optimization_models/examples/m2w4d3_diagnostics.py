"""W4D3：数值缩放检查、构造不可行实例、按求解器能力定位冲突。

对应笔记 Week_4/Day3.md。两个独立的话题：

* **numerical scaling**：系数跨度（coefficient span）多大算大？Big-M 是主要来源。
* **不可行诊断**：求解器能告诉你「哪几条假设一起冲突」，但**不会**告诉你
  「是数据错了还是模型错了」。

注意：``diagnose_infeasibility`` 的 ``reduce_conflict`` 会对冲突集做删除过滤，
每次尝试都要重解一次。实例越大、时间上限越高，总耗时越长——示例里用小时限。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_common.bridge import generate_instance
from opt_models.diagnostics import (
    deadlines_with_slack,
    diagnose_infeasibility,
    rescale_instance,
    scaling_report,
)


def main() -> None:
    inst = generate_instance(82, jobs=6, machines=1)
    report = scaling_report(inst)

    print("== 1. 系数跨度：Big-M 是主要来源 ==")
    print(f"  jobs={report.jobs} operations={report.operations} machines={report.machines}")
    print(f"  horizon（有效时间界）        = {report.horizon}")
    print(f"  系数最小 / 最大              = {report.coefficient_min} / {report.coefficient_max}")
    print(f"  紧模型跨度 tight_model_span  = {report.tight_model_span:.1f}  （= horizon / 最小系数）")
    print(f"  Big-M 用量                   = {report.big_m}")
    print(f"  松模型跨度 big_m_span        = {report.big_m_span:.1f}")
    print()
    print("  span 是「最大系数 / 最小非零系数」的**比值**，不是绝对量级。")
    print(f"  这里松模型比紧模型大了约 {report.big_m_span / report.tight_model_span:.1f} 倍：")
    print("  同一组约束里既有 1（时间）又有 M（排序），比值越大数值条件越差。")

    print()
    print("== 2. 缩放：把时间数据整体乘一个因子 ==")
    print(f"  {'factor':>8} {'horizon':>9} {'最大系数':>9} {'span(比值)':>11} {'big_m_span':>11}")
    for factor in (1.0, 10.0, 100.0):
        scaled_report = scaling_report(rescale_instance(inst, factor))
        print(
            f"  {factor:>8.1f} {scaled_report.horizon:>9} {scaled_report.coefficient_max:>9} "
            f"{scaled_report.span:>11.1f} {scaled_report.big_m_span:>11.1f}"
        )
    print("  绝对量级（horizon、最大系数）随因子线性放大，")
    print("  而 span 是比值，**缩放不变**——所以看 span 才看得出模型的固有数值结构，")
    print("  看绝对系数只会看到你选了多大的时间单位。")

    print()
    print("== 3. 构造一个真正不可行的实例 ==")
    tight = {job.id: 0 for job in inst.jobs}
    print(f"  把每个作业的交期都压到 0：deadlines = {tight}")
    print("  每个作业至少需要一段正工时，交期 0 意味着它必须在此之前完工 —— 不可能。")

    conflict = diagnose_infeasibility(inst, tight, time_limit=3.0)
    print(f"  求解次数 = {conflict.solves}   总耗时 = {conflict.solver_wall_time:.2f}s")
    print(f"  {conflict.summary()}")
    print()
    print(f"  充分冲突集（求解器给的）: {conflict.reported_conflict}")
    print(f"  极小冲突集（删除过滤后）: {conflict.minimal_conflict}")
    print(f"  删除过滤用的步数        : {conflict.reduction_steps}")

    print()
    print("== 4. 求解器不会替你区分「数据错」和「模型错」==")
    for note in conflict.notes:
        print(f"  - {note}")
    assert conflict.status == "INFEASIBLE"
    assert conflict.minimal_conflict, "删除过滤后应当得到非空的极小冲突集"

    print()
    print("== 5. 松弛交期：可控旋钮，从不可行滑到可行 ==")
    print("  deadlines_with_slack 造 d_j = r_j + ceil(slack * p_j)；slack 越小交期越紧。")
    for slack in (0.5, 1.0, 2.0):
        probe = deadlines_with_slack(inst, slack)
        outcome = diagnose_infeasibility(inst, probe, time_limit=3.0)
        conflict_text = outcome.minimal_conflict if outcome.minimal_conflict else "无"
        print(
            f"  slack={slack:>4.1f}  status={outcome.status:11} "
            f"极小冲突集={conflict_text}  求解次数={outcome.solves}"
        )
    print("  三个 slack 全部不可行，但**冲突集在变大**：slack 越宽，能各自达标的作业越多，")
    print("  就需要更多作业凑在一起才产生冲突——冲突集是相对假设集合定义的，不是作业的固有属性。")
    print("  注意本例里即使 slack=2.0 仍不可行：单机上每个作业只有 2 倍自身工时的交期，")
    print("  而它必须等前面所有作业做完。可行的临界点要靠实验找，不能靠直觉断言。")

    print()
    print("全部断言通过。")


if __name__ == "__main__":
    main()
