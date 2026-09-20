"""M3 Week 3 Day 2：加权迟交与 `α·Cmax + β·ΣT + γ·setup` 的取舍。

一个 2 机器、4 订单、1 道工序的极小实例 T。它小到每一行都能手算，却又同时藏着
`Cmax`、`ΣT`、`setup` 三个分量之间的**真实**取舍——不是搜索噪声。

    python examples/m3w3d2_weighted_multiobj.py

脚本做四件事：

1. 打印实例 T，并说明它的三个单目标最优值各自被哪条排程达到；
2. 区分「不带订单权重的 `ΣT`」与「带订单权重的 `weighted_tardiness`」，
   并说明模型最小化的是前者；
3. 用四组权重跑同一个实例，逐行打印 `breakdown` 与**手算**的加权和；
4. 把两条候选排程在 `β` 轴上的胜负手算成一张表，再与求解器的选择对照。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_core import (
    FJSPInstance,
    Job,
    Machine,
    Operation,
    Setup,
    Weights,
    objective_breakdown,
    total_tardiness,
    weighted_sum,
    weighted_tardiness,
)
from fjsp_shop.registry import get, load_week_modules

#: 实例 T。换型矩阵刻意不对称：`F0 -> F1` 只要 1 分钟，反向要 8 分钟。
INSTANCE = FJSPInstance(
    jobs=(
        Job("J0", ("A",), due_date=100, weight=1.0),
        Job("J1", ("B",), due_date=1, weight=3.0),
        Job("J2", ("C",), due_date=4, weight=1.0),
        Job("J3", ("D",), due_date=30, weight=1.0),
    ),
    operations=(
        Operation("A", "J0", 0, (("M0", 6),), family="F0"),
        Operation("B", "J1", 0, (("M0", 2),), family="F1"),
        Operation("C", "J2", 0, (("M1", 5),), family="F0"),
        Operation("D", "J3", 0, (("M0", 4), ("M1", 2)), family="F1"),
    ),
    machines=(Machine("M0", "M0"), Machine("M1", "M1")),
    setups=(Setup("F0", "F1", 1), Setup("F1", "F0", 8)),
)

#: 两条候选排程：手算的 `(Cmax, ΣT, setup)` 与手写的机器顺序。
#: `S1` 先做长的 `A`（`Cmax` 小，但急单 `B` 被拖到第 9 分钟）；`S2` 先做急的 `B`。
CANDIDATES = {
    "S1": (9.0, 9.0, 2.0, "M0: A[0,6) 换型1 B[7,9)；M1: C[0,5) 换型1 D[6,8)"),
    "S2": (16.0, 2.0, 9.0, "M0: B[0,2) 换型8 A[10,16)；M1: C[0,5) 换型1 D[6,8)"),
}

#: 两条候选排程的指纹，格式与 :func:`_schedule_key` 一致。**手写**在这里，
#: 用来和求解器真正返回的排程对读：只有两边完全相符，下面的胜负表才成立。
CANDIDATE_KEYS = {
    "S1": "M0:A@0-6,B@7-9;M1:C@0-5,D@6-8",
    "S2": "M0:B@0-2,A@10-16;M1:C@0-5,D@6-8",
}

#: `(标签, alpha, beta, gamma)`。
SETTINGS = (
    ("只优化 Cmax", 1.0, 0.0, 0.0),
    ("Cmax 与 ΣT 持平", 1.0, 1.0, 0.0),
    ("ΣT 压倒 Cmax", 1.0, 4.0, 0.0),
    ("三个分量一起看", 1.0, 1.0, 1.0),
    ("只看 setup", 0.0, 0.0, 1.0),
)


def main() -> None:
    load_week_modules()

    print("== 实例 T：2 机器、4 订单、每单 1 道工序 ==")
    print(f"{'工序':<6}{'订单':<6}{'可上机器(p)':<18}{'族':<5}{'交期':>6}{'权重':>6}")
    for job in INSTANCE.jobs:
        for op_id in job.operation_ids:
            op = INSTANCE.operation(op_id)
            machines = " ".join(f"{m}({p})" for m, p in op.machine_times)
            print(
                f"{op.id:<6}{job.id:<6}{machines:<18}{op.family:<5}"
                f"{job.due_date:>6}{job.weight:>6.1f}"
            )
    print("换型：F0 -> F1 = 1 分钟，F1 -> F0 = 8 分钟（刻意不对称）")

    print()
    print("== 先看清「带权重」和「不带权重」的迟交是两回事 ==")
    first = next(iter(_setting_specs()))
    probe = get("fjsp_cpsat_multiobj")(INSTANCE, first[1])
    plain = total_tardiness(INSTANCE, probe.schedule)
    weighted = weighted_tardiness(INSTANCE, probe.schedule)
    print(f"  在「{first[0]}」解出来的排程上：")
    print(f"    ΣT                  = {plain:g}（每个订单的迟交分钟数直接相加）")
    print(f"    weighted_tardiness  = {weighted:g}（J1 权重 3，它的迟交分钟数要乘 3）")
    print("  模型最小化的是前者 `ΣT`：`Job.weight` 目前只进 `weighted_tardiness`，")
    print("  不进 `fjsp_cpsat_multiobj` 的目标——想按订单权重排产，得先改模型的目标表达式。")

    print()
    print("== 同一实例、同一求解器，只换权重 ==")
    print(
        f"{'设置':<16}{'α':>5}{'β':>5}{'γ':>5}{'Cmax':>7}{'ΣT':>6}{'setup':>7}"
        f"{'模型报的 obj':>13}{'手算 αCmax+βΣT+γsetup':>22}  排程"
    )
    rows: list[tuple[str, float, float, float, float, float, float, float, str]] = []
    for label, spec, alpha, beta, gamma in _setting_specs():
        result = get("fjsp_cpsat_multiobj")(INSTANCE, spec)
        parts = objective_breakdown(INSTANCE, result.schedule)
        hand = weighted_sum(INSTANCE, result.schedule, Weights(alpha, beta, gamma))
        key = _schedule_key(result)
        rows.append((label, alpha, beta, gamma, parts["cmax"], parts["total_tardiness"],
                     parts["setup"], result.objective or 0.0, key))
        print(
            f"{label:<16}{alpha:>5.1f}{beta:>5.1f}{gamma:>5.1f}"
            f"{parts['cmax']:>7.1f}{parts['total_tardiness']:>6.1f}{parts['setup']:>7.1f}"
            f"{result.objective or 0.0:>13.2f}{hand:>22.2f}  {key}"
        )
    print("「模型报的 obj」与「手算」两列必须逐行相等——这是求解器没有偷换目标的证据。")

    print()
    print("== 两条候选排程在 β 轴上的胜负（手算） ==")
    for tag, parts in CANDIDATES.items():
        print(f"{tag} = {_describe(parts[:3])}")
        print(f"     {parts[3]}")
        print(f"     指纹 {CANDIDATE_KEYS[tag]}")
    print()
    print(f"{'β':>5}{'S1 的 αCmax+βΣT':>18}{'S2 的 αCmax+βΣT':>18}   谁赢")
    for beta in (0.0, 0.5, 1.0, 2.0, 4.0):
        s1 = 1.0 * 9.0 + beta * 9.0
        s2 = 1.0 * 16.0 + beta * 2.0
        who = "S1" if s1 < s2 else ("S2" if s2 < s1 else "并列")
        print(f"{beta:>5.1f}{s1:>18.2f}{s2:>18.2f}   {who}")
    print()
    print("令两者相等：(α·9 + β·9 + γ·2) = (α·16 + β·2 + γ·9)")
    print("  ->  7β - 7α - 7γ = 0  ->  S1 更优当且仅当 β <= α + γ")
    print("  取 α=1、γ=0 时翻转点正好在 β = 1；β=1 那一步是**精确并列**，")
    print("  求解器返回哪一条都合法，所以那一行只能当「并列」，不能当「翻转」。")

    print()
    print("== 求解器的选择与手算预测对照 ==")
    print("预测规则 `S1 更优当且仅当 β <= α + γ` 只在 `α=1、γ=0` 的族里做过推导，")
    print("所以下表只对这一族下判断；其余设置只能报「求解器选了哪条」。")
    print()
    print(f"{'设置':<16}{'α':>5}{'β':>5}{'γ':>5}   {'预测':<8}{'实际'}")
    tags = {fingerprint: tag for tag, fingerprint in CANDIDATE_KEYS.items()}
    for label, alpha, beta, gamma, *_rest, key in rows:
        if alpha == 1.0 and gamma == 0.0:
            predicted = "S1" if beta <= alpha + gamma else "S2"
        else:
            predicted = "不适用"
        print(f"{label:<16}{alpha:>5.1f}{beta:>5.1f}{gamma:>5.1f}   "
              f"{predicted:<8}{tags.get(key, '第三条排程: ' + key)}")


def _setting_specs():
    for label, alpha, beta, gamma in SETTINGS:
        yield (
            label,
            {
                "objective": "weighted_sum",
                "time_limit": 5.0,
                "seed": 0,
                "weights": {"alpha": alpha, "beta": beta, "gamma": gamma},
                # 原始单位：Day 2 只看取舍本身，先不做归一化，免得两件事混在一起
                "normalization": {"mode": "none"},
            },
            alpha,
            beta,
            gamma,
        )


def _schedule_key(result) -> str:
    """排程指纹：``M0:A@0-6,B@7-9;M1:C@0-5``。

    只写「哪台机器上放了哪些工序」是**不够**的——S1 与 S2 的机器分组完全相同，
    差别只在工序的先后。所以指纹必须带上开工时刻，否则两条不同的排程会同名。
    """
    by_machine: dict[str, list[str]] = {}
    for item in result.schedule.operations:
        by_machine.setdefault(item.machine_id, []).append(
            (item.start_time, f"{item.operation_id}@{item.start_time}-{item.end_time}")
        )
    return ";".join(
        f"{machine}:" + ",".join(text for _, text in sorted(items))
        for machine, items in sorted(by_machine.items())
    )


def _describe(parts: tuple[float, float, float]) -> str:
    cmax, tardiness, setup = parts
    return f"(Cmax {cmax:g}, ΣT {tardiness:g}, setup {setup:g})"


if __name__ == "__main__":
    main()
