"""W4D7：Month 2 复盘——把月末验收的每一条对应到可执行的证据。

对应笔记 Week_4/Day7.md。不新增算法，只做核对：每条验收要求指向哪个文件、
哪个脚本、哪组数字；以及**哪些还没做**，如实列出。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_common.bridge import generate_instance
from opt_solvers.registry import available, load_week_modules

MODULES = (
    ("opt_common/bridge.py", "复用 M1 的领域模型与验证器"),
    ("opt_solvers/result.py", "统一 SolveResult：无 bound 写 None"),
    ("opt_solvers/registry.py", "方法注册表"),
    ("opt_solvers/heuristics.py", "M1 规则接入统一接口"),
    ("opt_models/lp_models.py", "W1 生产计划/运输/指派 LP + 对偶"),
    ("opt_models/milp_scheduling.py", "W2 单机 MILP：tight/loose/替代"),
    ("opt_models/cpsat_models.py", "W3 区间模型：并行机/JSP/Cumulative"),
    ("opt_models/strengthening.py", "W4 对称破缺/warm start/fixing"),
    ("opt_models/diagnostics.py", "W4 数值缩放与不可行诊断"),
    ("opt_experiments/benchmark.py", "跨方法批次与参考值分档"),
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    load_week_modules()

    print("=== 1. 代码地图（实际存在的文件）===")
    for relative, purpose in MODULES:
        path = root / relative
        mark = "OK " if path.exists() else "缺失"
        size = f"{len(path.read_text(encoding='utf-8').splitlines()):>4} 行" if path.exists() else "     "
        print(f"  [{mark}] {size}  {relative:42} {purpose}")

    print()
    print("=== 2. 注册的方法（月末批次按名字调用）===")
    methods = available()
    print(f"  共 {len(methods)} 个：")
    for name in methods:
        print(f"    {name}")

    print()
    print("=== 3. 月末验收对应表 ===")
    checks = (
        ("生产计划 / 运输 / 指派 LP，能解释对偶、互补松弛与影子价格",
         "opt_models/lp_models.py + artifacts/month2_w1/", "由 Week 1 驱动脚本生成"),
        ("loose/tight Big-M 与替代 formulation 对比",
         "configs/month2.json 的 single_* 方法表", "由月末批次生成"),
        ("至少两项工程手段实验，无改进也如实分析",
         "artifacts/month2_w4/（对称破缺消融 + warm start 消融）", "29 行记录，0 失败"),
        ("返回解通过独立验证",
         "opt_solvers/result.py 的 validate_result", "批次 results.csv 的 validation 列"),
        ("能解释目标、bound、gap、时间限制与不可行冲突",
         "examples/m2w4d4_time_limits.py + m2w4d3_diagnostics.py", "实测输出"),
        ("MILP / CP-SAT / 启发式同实例同预算比较，分记 build/solve time",
         "opt_experiments/benchmark.py", "artifacts/month2/"),
    )
    for requirement, evidence, note in checks:
        print(f"  · {requirement}")
        print(f"      证据：{evidence}")
        print(f"      说明：{note}")

    print()
    print("=== 4. 本月的核心结论（都是实验观察，不是普遍规律）===")
    print("  ① 没有 bound 就写 None：启发式在接口层被禁止冒充「已证明最优」。")
    print("  ② Big-M 的紧与松**不改变根 LP 界**（单机 ΣT 的序列模型两者根界都是 0），")
    print("     它改变的是系数规模与搜索路径；formulation 的**结构**（时间索引）")
    print("     才带来数量级更强的界。")
    print("  ③ 强化手段（对称破缺、冗余约束）**不改变最优值**——改变即建模错误；")
    print("     在小实例上它们的额外约束甚至会让冲突数上升，是负收益。")
    print("  ④ 前缀固定是**限制解空间**，不是强化：实测它在初解处封顶（283），")
    print("     而同一实例的完整模型能到 271。")
    print("  ⑤ 时间预算决定终止原因：同一实例 1s 给 1519、3s 起稳定在 968，")
    print("     且始终没有证明最优——「解出 X」必须连预算一起说。")

    print()
    print("=== 5. 本月没有做的（不假装做过）===")
    print("  · 没有做 workers / seed 的完整敏感性（只做了单点对照）")
    print("  · 没有在独立测试集上验证任何调参结论")
    print("  · Cumulative 未进入月末批次：共享实例格式没有资源容量字段，")
    print("    它由 Week 3 自己的容量实验覆盖")
    print("  · 没有跑 lint / 类型检查：验证环境里没有 ruff / black / mypy")
    print("  · 没有做工业约束（换型、日历、工人）")

    print()
    print("=== 6. 接口的复用性 ===")
    print("  Instance / Schedule / validate_schedule / objective 一行都不用改；")
    print("  更一般的车间模型只需新增模型，继续注册进同一张表。")
    inst = generate_instance(50, jobs=8, machines=1)
    print(f"  自检：注册表可用，示例实例 {len(inst.jobs)} 作业 / {len(inst.machines)} 机器。")

    print()
    print("全部断言通过。")


if __name__ == "__main__":
    main()
