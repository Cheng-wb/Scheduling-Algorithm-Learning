"""Week 2 的四个手算实例：7 天笔记、实验脚本与 ``tests/test_week2.py`` 共用同一组对象。

把实例集中在一处，是为了让「笔记里写的数」和「脚本打出来的数」来自同一个对象——
M1 的教训是同一个手算例子在不同笔记里被各自抄一遍，改一个参数就对不上了。

四个实例各自负责一个问题：

| 函数 | 规模 | 它要被用来测什么 |
|---|---|---|
| :func:`tiny_2x2` | 2 订单 × 2 工序，2 机器 | 四种方法**一致**落在最优（``makespan = 下界 = 2``） |
| :func:`gap_2x2` | 2 订单 × 2 工序，2 机器 | 附加式解码与插入式解码的**差距**（15 对 12） |
| :func:`assign_2x3` | 2 订单 × 2 工序，3 机器 | 指派策略**分歧**：最快机器 ≠ 负载均衡 |
| :func:`jsp_fixed_2x2` | 2 订单 × 2 工序，2 机器，``flexibility = 1`` | FJSP 方法在**退化成 JSP** 时仍然正确 |

全部工时都是手写的（不来自生成器），因为本周的笔记要逐条手算它们。释放时间都为 0，
交期给得很宽（30），这样 ``makespan`` 是唯一被优化的指标，不会与迟交混淆。
"""

from __future__ import annotations

from fjsp_core.models import FJSPInstance, Job, Machine, Operation

DUE = 30  # 手算实例一律给很宽的交期：本周只谈 makespan


def _two_machines() -> tuple[Machine, ...]:
    return (Machine("M0", "M0"), Machine("M1", "M1"))


def tiny_2x2() -> FJSPInstance:
    """两个订单各自偏爱的机器不同：J0 走 M0、J1 走 M1，两列各 2 分钟。

    最优 ``makespan = 2``，而且这个 2 同时等于下界
    ``max(max_o min_m p_om, ceil(Σ_o min_m p_om / |M|)) = max(1, ceil(4/2)) = 2``。
    也就是说这个实例的最优性不靠穷举也能证明——**下界碰上界**。
    """
    return FJSPInstance(
        jobs=(Job("J0", ("O00", "O01"), 0, DUE, 1.0), Job("J1", ("O10", "O11"), 0, DUE, 1.0)),
        operations=(
            Operation("O00", "J0", 0, (("M0", 1), ("M1", 3))),
            Operation("O01", "J0", 1, (("M0", 1), ("M1", 3))),
            Operation("O10", "J1", 0, (("M0", 3), ("M1", 1))),
            Operation("O11", "J1", 1, (("M0", 3), ("M1", 1))),
        ),
        machines=_two_machines(),
    )


def gap_2x2() -> FJSPInstance:
    """专为「附加式 vs 插入式解码」设计：同一个指派 + 同一个顺序，两种解码差 3 分钟（``17`` 对 ``14``）。

    关键结构是 M0 上被**工艺路线**逼出来的一段空档 ``[0, 12)``：``O11`` 必须等 ``O10``
    在 M1 上做完（t=12）才能开工，于是它落在 ``[12, 14)``；而 ``O01`` 的机器在 t=4 就
    已空闲。附加式解码看不见这段空档，把 ``O01`` 排到 14 之后；插入式把它放进空档。

    工时**逐机器不同**（``O10`` 在 M1 上 8 分钟、在 M0 上 9 分钟），否则这个实例会退化成
    「有选择但选谁都一样」，测不出机器选择的意义。
    """
    return FJSPInstance(
        jobs=(Job("J0", ("O00", "O01"), 0, DUE, 1.0), Job("J1", ("O10", "O11"), 0, DUE, 1.0)),
        operations=(
            Operation("O00", "J0", 0, (("M0", 2), ("M1", 4))),
            Operation("O01", "J0", 1, (("M0", 3), ("M1", 5))),
            Operation("O10", "J1", 0, (("M0", 9), ("M1", 8))),
            Operation("O11", "J1", 1, (("M0", 2), ("M1", 6))),
        ),
        machines=_two_machines(),
    )


def assign_2x3() -> FJSPInstance:
    """三台机器上的指派分歧：M0 对三道工序都最快，全塞进去反而更差。

    ``O00`` 在 M0 上只要 3 分钟、在 M2 上要 9 分钟，但当 ``O00`` 轮到被指派时
    M0 已经背了 6 分钟负载，所以「预计负载最小」会把它放到 M2。这是
    「局部最快」与「全局均衡」第一次分道扬镳的地方。
    """
    return FJSPInstance(
        jobs=(Job("J0", ("O00", "O01"), 0, DUE, 1.0), Job("J1", ("O10", "O11"), 0, DUE, 1.0)),
        operations=(
            Operation("O00", "J0", 0, (("M0", 3), ("M1", 6), ("M2", 9))),
            Operation("O01", "J0", 1, (("M0", 5), ("M1", 4), ("M2", 8))),
            Operation("O10", "J1", 0, (("M0", 3), ("M1", 7), ("M2", 6))),
            Operation("O11", "J1", 1, (("M0", 6), ("M1", 4), ("M2", 9))),
        ),
        machines=(Machine("M0", "M0"), Machine("M1", "M1"), Machine("M2", "M2")),
    )


def jsp_fixed_2x2() -> FJSPInstance:
    """每道工序只有一台合格机器：``flexibility = 1``，FJSP 退化成经典 JSP。

    最优 ``makespan = 7``：M0 必须做完 ``O00``（3）与 ``O11``（4），两者都只能在这台
    机器上做，所以 ``7`` 是下界也是可达的。**FJSP 方法必须照样给出 7。**
    """
    return FJSPInstance(
        jobs=(Job("J0", ("O00", "O01"), 0, DUE, 1.0), Job("J1", ("O10", "O11"), 0, DUE, 1.0)),
        operations=(
            Operation("O00", "J0", 0, (("M0", 3),)),
            Operation("O01", "J0", 1, (("M1", 2),)),
            Operation("O10", "J1", 0, (("M1", 2),)),
            Operation("O11", "J1", 1, (("M0", 4),)),
        ),
        machines=_two_machines(),
    )


#: 名字 → 构造函数。脚本与测试都按名字取，避免各自 new 一遍。
TOY_INSTANCES = {
    "tiny_2x2": tiny_2x2,
    "gap_2x2": gap_2x2,
    "assign_2x3": assign_2x3,
    "jsp_fixed_2x2": jsp_fixed_2x2,
}
