"""Week 4：工业约束 II —— 资质、次生资源、工序族 batching、WIP 锁定与紧急订单。

本模块提供两个注册方法（``configs/month3.json`` 按名字调用它们）：

| 方法 | 覆盖的约束 | 换型的编码 |
|---|---|---|
| `fjsp_cpsat_qualified` | 机器相关工时 + 柔性 + 释放/交期 + 日历 + 维护 + **资质** + **次生资源** + WIP 锁定 | **保守**（区间膨胀 + `AddNoOverlap`） |
| `fjsp_cpsat_full` | 上面全部 **加上** sequence-dependent setup 的**精确**编码 | **精确**（每台机器一条槽位链，`AddElement` + `AddAllowedAssignments`） |

两者的差别只有一处，但这一处是可测量的：**换型是「够用就好」还是「当作决策」**。

* 保守编码：把工序 `i` 的机器占用区间膨胀成 ``[start_i, end_i + max_outgoing_setup(family_i))``，
  然后在同一台机器上做 `AddNoOverlap`。因为 ``end_i + max_outgoing >= end_i + setup(family_i -> family_j)``，
  相邻工序之间一定留够了换型间隔 —— **永远不会产出验证器不接受的排程**，代价是非相邻的
  组合也会被多留，可行域被收紧。
* 精确编码：每台机器上把「实际在场的工序」排成一条**槽位链**。第 ``p`` 个槽位由
  ``AddElement`` 指向「这一槽是哪道工序」（缺席工序的 ``pres`` 为 0，会被单调性推到链尾），
  相邻槽位之间用 ``AddAllowedAssignments`` 查表得到该对工序的换型常量 ``gap``。
  准确性的三条依据写在 :func:`_add_machine_sequences` 的文档里 —— 核心是
  ``Σpres == Σx`` 保证每道在场工序恰好占据一个槽位、``pres`` 单调保证链只有一条、
  ``gap`` 之和因此恰好等于真实相邻对的换型之和，可以直接进目标函数。

**为什么不用 `AddCircuit`。** 第一版就是这么写的：源点连到每道可上该机器的工序、工序之间连
``start_j >= end_i + setup`` 的弧、再连回汇点。它在 ``fjsp_cpsat_full`` 上**恒为 INFEASIBLE**。
根因是 ``AddCircuit`` 要求每个节点的**出度恰好为 1**，而「源点 → 每道在场工序」这一组弧在
多于一道工序时出度就 > 1；用最小复现验证过：1 条强制弧 → INFEASIBLE，1 条非强制弧 → OPTIMAL。
第二版改用 ``AddElement`` 槽位链，性质不变（仍是精确编码）但没有回路约束的出度限制。

**为什么也不用「两两析取 + 全局顺序变量」。** 因为 ``seq[i][j]`` 只能表达「i 在 j 之前」，
不能表达「i 紧邻 j」。给**所有**同机工序对都加换型间隔会过约束：
当 ``setup(f0 -> f2) > setup(f0 -> f1) + p_f1 + setup(f1 -> f2)`` 时，它会把可行解切掉。

**次生资源采用「强制占用」语义**：只要实例给了 ``workers``，每道工序**必须**占用一名
能操作其选定机器的资源。验证器只检查「被指派的资源」，是否强制占用由业务决定
（``schedule_validation`` 的注释写明了这一点）；这里选择强制，是为了让 ``capacity``
真的成为约束，而不是被「不指派就没事」绕过。

模型覆盖表见 :data:`MODEL_COVERAGE`；``tests/test_week4.py`` 会机械地核对每一行的
字段确实存在、且确实被验证器或本模块读到。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from ortools.sat.python import cp_model

from fjsp_core.models import (
    FJSPInstance,
    Job,
    Machine,
    Maintenance,
    Operation,
    Qualification,
    Schedule,
    ScheduledOperation,
    Worker,
)
from fjsp_core.objective import OBJECTIVES, evaluate, parse_weights
from fjsp_core.result import ShopResult
from fjsp_core.schedule_validation import schedule_errors
from fjsp_core.validation import FJSPInstanceError, validate_instance
from fjsp_shop.registry import register

#: 浮点权重在 CP-SAT 里必须变成整数系数；乘以它再四舍五入。
WEIGHT_SCALE = 1000


# ---------------------------------------------------------------------------
# 模型覆盖表：约束 → 模型字段 → 验证器检查 → 求解器用法
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CoverageRow:
    """一行「约束确实被建模」的证据。"""

    constraint: str  # 约束名（中文）
    owner: type  # 声明该字段的 dataclass
    field: str  # 模型字段名
    validator_check: str  # 独立验证器里的诊断标签
    solver_use: str  # 求解器里的用法
    evidence: tuple[str, ...]  # 必须出现在验证器或求解器源码里的标识符


#: 十条真实约束 + 一条「不进约束只进目标」的业务规则，共 11 行。
#: ``Machine.group`` **不在表内**：它是为对称破缺预留的声明字段，当前没有任何约束语义，
#: 与其假装它是一条约束，不如在这里写明它没有被用到。
MODEL_COVERAGE: tuple[CoverageRow, ...] = (
    CoverageRow(
        constraint="机器相关工时与柔性（FJSP 的定义特征）",
        owner=Operation,
        field="machine_times",
        validator_check="illegal assignment / duration",
        solver_use="duration[op] == Σ_m p_om · x[op][m]，且 Σ_m x[op][m] == 1",
        evidence=("time_on", "machine_times"),
    ),
    CoverageRow(
        constraint="释放时间（订单不可提前开工）",
        owner=Job,
        field="release_time",
        validator_check="release",
        solver_use="start[op] >= release_time(job)",
        evidence=("release_time",),
    ),
    CoverageRow(
        constraint="交期与加权迟交（进目标函数）",
        owner=Job,
        field="due_date",
        validator_check="（不进可行性，只进 Objective）",
        solver_use="T_j >= C_j − d_j 且 T_j >= 0，min α·Cmax + β·Σw_j T_j",
        evidence=("due_date",),
    ),
    CoverageRow(
        constraint="sequence-dependent setup（工序族换型）",
        owner=Operation,
        field="family",
        validator_check="overlap / setup undefined",
        solver_use="full：槽位链相邻槽的 AddAllowedAssignments 查表；qualified：区间膨胀 AddNoOverlap",
        evidence=("setup_minutes", "family"),
    ),
    CoverageRow(
        constraint="机器日历（可用窗）",
        owner=Machine,
        field="calendar_id",
        validator_check="calendar",
        solver_use="工序必须整体落在该机器某个可用窗内（窗口选择 BoolVar）",
        evidence=("calendar_window", "calendar_id"),
    ),
    CoverageRow(
        constraint="计划维护（不可用窗）",
        owner=Maintenance,
        field="windows",
        validator_check="maintenance",
        solver_use="对每个维护窗二选一：end <= lo 或 start >= hi",
        evidence=("maintenance_windows",),
    ),
    CoverageRow(
        constraint="机器资质（谁能做）",
        owner=Qualification,
        field="family",
        validator_check="qualification",
        solver_use="合格机器集合 = {q.machine_id | q.family == op.family}，其余 x 变量不创建",
        evidence=("qualifications", "qualification"),
    ),
    CoverageRow(
        constraint="次生资源能力（能操作哪台机器）",
        owner=Worker,
        field="machine_ids",
        validator_check="worker: ... cannot operate ...",
        solver_use="w[op][worker] 在 worker 不能操作的机器上被压成 0",
        evidence=("can_operate",),
    ),
    CoverageRow(
        constraint="次生资源容量（同时做几个）",
        owner=Worker,
        field="capacity",
        validator_check="worker: ... double-booked / peak > capacity",
        solver_use="AddCumulative(该资源的所有可选区间, 需求 1, 容量 capacity)",
        evidence=("capacity", "AddCumulative"),
    ),
    CoverageRow(
        constraint="WIP / 锁定工序（已在机不可再选）",
        owner=Operation,
        field="locked_machine_id",
        validator_check="locked",
        solver_use="可选机器收窄为 locked_machine_id；locked_start 非空时 start 被钉死",
        evidence=("locked_machine_id", "locked_start"),
    ),
    CoverageRow(
        constraint="紧急订单优先级（只进目标，不进约束）",
        owner=Job,
        field="priority",
        validator_check="（**故意不进**验证器：改了优先级，可行域不变）",
        solver_use="spec['urgency'] 打开时，加权迟交的有效权重变成 w_j·(1 + priority_j)",
        evidence=("priority",),
    ),
)


# ---------------------------------------------------------------------------
# 预处理：合格机器、时间界、换型查询
# ---------------------------------------------------------------------------


class _ModelDeclined(Exception):
    """输入不适合本模型（而不是「无解」）。"""


def time_horizon(instance: FJSPInstance) -> int:
    """所有工序开工时刻的合法上界。

    三条来源取最大：``释放时间 + Σ最大工时 + 换型总量``（无日历的机器），
    以及每个日历/维护窗的右端点（有日历的机器上工序必须落在窗内，因此开工不会晚于窗尾）。

    这不是紧界，只是为了让 ``IntVar`` 有有限定义域；界太松只会让 CP-SAT 的传播变弱，
    不会切掉可行解。
    """
    total = sum(max(time for _, time in op.machine_times) for op in instance.operations)
    setup_max = max((item.minutes for item in instance.setups), default=0)
    release_max = max((job.release_time for job in instance.jobs), default=0)
    longest = max(
        (max(time for _, time in op.machine_times) for op in instance.operations),
        default=1,
    )
    bound = release_max + total + setup_max * len(instance.operations) + longest + 1
    for calendar in instance.calendars:
        for _, hi in calendar.windows:
            bound = max(bound, hi + longest + 1)
    for item in instance.maintenances:
        for _, hi in item.windows:
            bound = max(bound, hi + longest + 1)
    return bound


def qualified_machine_ids(instance: FJSPInstance, op: Operation) -> tuple[str, ...]:
    """按资质与 WIP 锁定收窄后的可选机器。

    与验证器**完全同构**：只有实例里存在资质记录、且工序有 ``family`` 时才查资质
    （否则「没填资质」会被误判成「没有机器有资质」）；``locked_machine_id`` 直接
    把可选集合收窄成一个元素。
    """
    allowed: set[str] | None = None
    if instance.qualifications and op.family is not None:
        allowed = {q.machine_id for q in instance.qualifications if q.family == op.family}
    out: list[str] = []
    for machine_id, _ in op.machine_times:
        if allowed is not None and machine_id not in allowed:
            continue
        if op.locked_machine_id is not None and machine_id != op.locked_machine_id:
            continue
        out.append(machine_id)
    return tuple(out)


def machine_end_bound(instance: FJSPInstance, machine_id: str) -> int | None:
    """该机器上任何工序**完工时刻**的合法上界；``None`` 表示这台机器没有日历窗。

    有日历的机器上，工序必须整体落在某个可用窗内，所以 ``end <= max(hi)``。
    这是把 ``start`` 的定义域收紧一个数量级的关键：seed 203 的日历窗最右端是 100，
    而没有这条时 ``time_horizon`` 给的是 591（六个窗口那么宽）。
    ``IntVar`` 定义域从 591 收到 100，CP-SAT 的传播强度完全是两个量级。
    """
    windows = instance.calendar_window(machine_id)
    if not windows:
        return None
    return max(hi for _, hi in windows)


def operation_bounds(
    instance: FJSPInstance, op: Operation, machines: tuple[str, ...], base: int
) -> tuple[int, int, int]:
    """一道工序的 ``(start_upper, end_upper, dur_upper)``。

    只要**有一台**合格机器没有日历窗，这道工序的上界就只能是 ``base``
    —— 所以这里是「全都有窗才收紧」，不是取最小。
    """
    durations = [op.time_on(machine_id) or 0 for machine_id in machines]
    dur_upper = max(durations) if durations else base
    bounds = [machine_end_bound(instance, machine_id) for machine_id in machines]
    end_upper = base if any(item is None for item in bounds) else max(bounds)
    end_upper = max(end_upper, dur_upper)
    dur_lower = min(durations) if durations else 1
    return end_upper - max(1, dur_lower), end_upper, dur_upper


def setup_lookup(instance: FJSPInstance, from_family: str | None, to_family: str | None):
    """返回 ``(minutes, defined)``；任一为空、同族、或实例根本没有换型矩阵时是 ``(0, True)``。

    最后一条很重要：验证器只在 ``instance.setups`` 非空时才检查换型间隔，
    所以「没给换型矩阵」意味着**没有换型约束**，而不是「所有换型都未定义」。
    """
    if not instance.setups:
        return 0, True
    if from_family is None or to_family is None or from_family == to_family:
        return 0, True
    for item in instance.setups:
        if item.from_family == from_family and item.to_family == to_family:
            return item.minutes, True
    return 0, False


def max_outgoing_setup(instance: FJSPInstance, from_family: str | None) -> int:
    """同族出口换型的最大值：保守编码里用来膨胀**前驱**的占用区间。"""
    if from_family is None:
        return 0
    return max(
        (item.minutes for item in instance.setups if item.from_family == from_family),
        default=0,
    )


# ---------------------------------------------------------------------------
# 建模
# ---------------------------------------------------------------------------


class _Built:
    """一次建模的产物：模型、变量表、以及「模型目标是否等于真实目标」的判定。"""

    def __init__(self, instance: FJSPInstance) -> None:
        self.instance = instance
        self.model = cp_model.CpModel()
        self.horizon = time_horizon(instance)
        self.start: dict[str, Any] = {}
        self.start_upper: dict[str, int] = {}
        self.end_upper: dict[str, int] = {}
        self.duration_upper: dict[str, int] = {}
        self.end: dict[str, Any] = {}
        self.duration: dict[str, Any] = {}
        self.assign: dict[str, dict[str, Any]] = {}
        self.worker_var: dict[str, dict[str, Any]] = {}
        self.choice: dict[str, tuple[str, ...]] = {}
        self.setup_total: Any = None
        self.objective_name = "makespan"
        self.weights: Any = None
        self.objective_scale = 1
        self.objective_exact = True
        self.notes: dict[str, Any] = {}

    def value(self, solver: cp_model.CpSolver, var: Any) -> int:
        return int(solver.Value(var))


def _prepare_choices(instance: FJSPInstance) -> dict[str, tuple[str, ...]]:
    choices = {op.id: qualified_machine_ids(instance, op) for op in instance.operations}
    empty = [op_id for op_id, machines in choices.items() if not machines]
    if empty:
        raise _ModelDeclined(
            "no eligible machine after qualification/lock filtering: " + ", ".join(sorted(empty))
        )
    return choices


def _worker_options(
    instance: FJSPInstance, op: Operation, machines: tuple[str, ...]
) -> tuple[str, ...]:
    """能操作 ``op`` 的**任一**可选机器的资源。空集合表示这道工序无人可做。"""
    return tuple(
        worker.id
        for worker in instance.workers
        if any(worker.can_operate(machine_id) for machine_id in machines)
    )


# ---------------------------------------------------------------------------
# 贪心预热解：保证「至少有一个可行解」这件事不依赖搜索运气
# ---------------------------------------------------------------------------


def _advance_past_unavailability(
    instance: FJSPInstance, machine_id: str, est: int, duration: int
) -> int | None:
    """把开工时刻往后推到「既不越出日历窗、也不撞维护窗」的最早位置。

    日历与维护会互相推：推过维护窗可能又落到日历窗之外，所以这里循环到稳定。
    ``None`` 表示这台机器上**根本放不下**（例如日历窗都比工序短）。
    """
    windows = instance.calendar_window(machine_id)
    blockers = instance.maintenance_windows(machine_id)
    for _ in range(64):  # 窗口数量有限，循环次数有界；上限只是防御性写法
        if windows:
            placed = None
            for lo, hi in windows:
                start = max(est, lo)
                if start + duration <= hi:
                    placed = start
                    break
            if placed is None:
                return None
            est = placed
        moved = False
        for lo, hi in blockers:
            if est < hi and lo < est + duration:
                est = hi
                moved = True
        if not moved:
            return est
    return None


#: 预热解尝试的工序顺序。全部是**确定性**的：给定实例，先试哪个后试哪个固定。
#: 单跑一种顺序会在日历实例上卡死（实测 seed 203：按订单顺序把最后一个可用窗
#: 填满后，剩下的工序再也放不下），所以这里跑几种再取最好的。
GREEDY_ORDERS: tuple[tuple[str, tuple], ...] = (
    ("job_major", ()),
    ("stage_major", ()),
    ("edd", ()),
    ("weight_desc", ()),
)


def _order_key(instance: FJSPInstance, name: str):
    jobs = {job.id: job for job in instance.jobs}
    if name == "stage_major":
        return lambda op: (op.position, op.job_id, op.id)
    if name == "edd":
        return lambda op: (
            jobs[op.job_id].due_date if jobs[op.job_id].due_date is not None else 10**9,
            op.position,
            op.job_id,
            op.id,
        )
    if name == "weight_desc":
        return lambda op: (
            -jobs[op.job_id].weight,
            jobs[op.job_id].due_date if jobs[op.job_id].due_date is not None else 10**9,
            op.position,
            op.job_id,
            op.id,
        )
    return lambda op: (op.job_id, op.position, op.id)


def greedy_hint(
    instance: FJSPInstance, *, orders: tuple[str, ...] | None = None
) -> dict[str, tuple[str, int, str | None]] | None:
    """一个确定性的列表调度解：``{op_id: (machine_id, start, worker_id)}``。

    **为什么要在 CP-SAT 之前做这件事。** 实测 ``fjsp_cpsat_full`` 在 5 秒预算下
    对 6 jobs 的工业实例返回 ``UNKNOWN``（连一个可行解都没找到）—— ``status`` 里
    没有解，下游的 CSV 就只能写空值。加一个预热解可以把「有没有解」从搜索运气
    变成结构保证：``status`` 至少是 ``FEASIBLE``，搜索从贪心解往上爬而不是从零开始。

    它对每种工序顺序各跑一遍列表调度：对每道工序，在合格机器上算出「满足
    release / precedence / 锁定 / 换型 / 日历 / 维护」的最早开工，再挑一个能操作
    该机器的空闲资源，取**完工最早**的组合。最后返回**最大完工时间最小**的那个
    完整解。

    **为什么要试多种顺序。** 单跑「按订单」这一种会卡死：seed 203 的日历只有
    ``(0,50)`` 与 ``(60,100)`` 两个窗，按订单顺序会把最后一个窗填满，剩下的工序
    再也放不下。换一种顺序（按工序阶段、按交期、按权重）得到的占用形状不同，
    通常就有解了。顺序表是常量，所以这件事仍然是**确定性**的。

    它是**保守**的：资源按「串行」处理（容量 >1 也串行用），所以结果一定可行，
    但通常不是最优——这正是预热解该有的样子。全部顺序都失败时返回 ``None``，
    此时不给提示，让 CP-SAT 自己判断。
    """
    if not instance.operations:
        return None
    best_plan = None
    best_span = None
    for name in orders if orders is not None else tuple(item[0] for item in GREEDY_ORDERS):
        plan = _greedy_pass(instance, _order_key(instance, name))
        if plan is None:
            continue
        span = max(start + instance.operation(op_id).time_on(machine_id)
                   for op_id, (machine_id, start, _) in plan.items())
        if best_span is None or span < best_span:
            best_plan, best_span = plan, span
    return best_plan


def _greedy_pass(instance: FJSPInstance, order_key) -> dict[str, tuple[str, int, str | None]] | None:
    """单次列表调度。``None`` = 这种顺序下放不下全部工序。"""
    machine_frontier: dict[str, int] = {m.id: 0 for m in instance.machines}
    machine_family: dict[str, str | None] = {m.id: None for m in instance.machines}
    worker_free: dict[str, int] = {w.id: 0 for w in instance.workers}
    job_ready: dict[str, int] = {job.id: job.release_time for job in instance.jobs}
    plan: dict[str, tuple[str, int, str | None]] = {}

    order = sorted(instance.operations, key=order_key)
    for op in order:
        best: tuple[int, str, int, str | None] | None = None  # (完工, 机器, 开工, 资源)
        for machine_id in qualified_machine_ids(instance, op):
            duration = op.time_on(machine_id)
            if duration is None or duration <= 0:
                continue
            est = max(job_ready[op.job_id], machine_frontier[machine_id])
            if op.locked_start is not None:
                est = max(est, op.locked_start)
            # 换型：必须等于真实相邻对的换型量，否则验证器的 overlap 检查会挂
            try:
                gap = instance.setup_minutes(machine_family[machine_id], op.family)
            except KeyError:
                return None  # 换型方向未定义：这个实例超出贪心的表达能力
            if gap:
                est = max(est, machine_frontier[machine_id] + gap)
            start = _advance_past_unavailability(instance, machine_id, est, duration)
            if start is None:
                continue
            # 资源：从能操作这台机器的资源里挑最早空出来的那个
            if instance.workers:
                candidates = [
                    worker
                    for worker in instance.workers
                    if worker.can_operate(machine_id)
                ]
                if not candidates:
                    continue
                for worker in candidates:
                    begin = max(start, worker_free[worker.id])
                    begin = _advance_past_unavailability(
                        instance, machine_id, begin, duration
                    )
                    if begin is None:
                        continue
                    finish = begin + duration
                    if best is None or finish < best[0]:
                        best = (finish, machine_id, begin, worker.id)
            else:
                finish = start + duration
                if best is None or finish < best[0]:
                    best = (finish, machine_id, start, None)
        if best is None:
            return None
        finish, machine_id, start, worker_id = best
        plan[op.id] = (machine_id, start, worker_id)
        machine_frontier[machine_id] = finish
        machine_family[machine_id] = op.family
        job_ready[op.job_id] = finish
        if worker_id is not None:
            worker_free[worker_id] = finish
    return plan


def plan_to_schedule(
    instance: FJSPInstance, plan: dict[str, tuple[str, int, str | None]]
) -> Schedule:
    """把贪心解变成 ``Schedule``，以便用**独立评估器**（而不是求解器读数）算目标值。"""
    items = []
    for op in instance.operations:
        machine_id, start, worker_id = plan[op.id]
        duration = op.time_on(machine_id)
        items.append(
            ScheduledOperation(op.id, machine_id, start, start + duration, worker_id)
        )
    return Schedule(tuple(items))


def _hint_objective(
    built: _Built, instance: FJSPInstance, plan: dict[str, tuple[str, int, str | None]]
) -> float | None:
    """预热解在**真实目标**下的值；不适用时返回 ``None``。

    记录它的意义：求解器最后报的目标如果比它还差，说明搜索连起点都没走远，
    这时候该看的是参数而不是模型。
    """
    try:
        schedule = plan_to_schedule(instance, plan)
        return float(
            evaluate(instance, schedule, built.objective_name, built.weights)
        )
    except Exception:
        return None


def apply_hint(
    built: _Built, plan: dict[str, tuple[str, int, str | None]]
) -> bool:
    """把贪心解翻译成 CP-SAT 的 ``AddHint``。

    ``AddHint`` 只是提示：不可行时 CP-SAT 直接忽略，不会让模型变不可行。
    但仍然先自查一遍，避免把明显对不上的东西塞进去浪费搜索时间。
    """
    model = built.model
    for op_id, (machine_id, start, worker_id) in plan.items():
        if machine_id not in built.assign.get(op_id, {}):
            return False
        model.AddHint(built.start[op_id], start)
        model.AddHint(built.assign[op_id][machine_id], 1)
        if worker_id is not None and worker_id in built.worker_var.get(op_id, {}):
            model.AddHint(built.worker_var[op_id][worker_id], 1)
    return True


def build_model(
    instance: FJSPInstance, spec: dict[str, Any], *, exact_setup: bool
) -> _Built:
    """建好模型但**不求解**。``exact_setup=False`` 走保守换型编码。

    抛出 :class:`_ModelDeclined` 表示「本模型不适用」（而不是「不可行」）。
    """
    validate_instance(instance)
    built = _Built(instance)
    model = built.model
    base = built.horizon
    built.choice = _prepare_choices(instance)

    # 逐工序收紧定义域。``base`` 是全局上界；有日历的机器可以紧得多。
    for op in instance.operations:
        start_upper, end_upper, dur_upper = operation_bounds(
            instance, op, built.choice[op.id], base
        )
        built.start_upper[op.id] = start_upper
        built.end_upper[op.id] = end_upper
        built.duration_upper[op.id] = dur_upper
    # 全局地平线取「逐工序上界的最大值」：它一定 ≤ ``base``，
    # 且对每一道工序都成立（``operation_bounds`` 对没有日历的机器回落到 ``base``）。
    built.horizon = max(built.end_upper.values())

    uses_workers = bool(instance.workers)
    if uses_workers:
        starved = [
            op.id
            for op in instance.operations
            if not _worker_options(instance, op, built.choice[op.id])
        ]
        if starved:
            raise _ModelDeclined("no worker can operate any eligible machine for: " + ", ".join(starved))

    if not exact_setup and instance.setups:
        # 保守编码要求换型矩阵在「会同时出现在某台机器上的族」之间是完整的：
        # 缺方向时它没法只禁止那一对（没有顺序变量），只能整体拒绝。
        families = {op.family for op in instance.operations if op.family is not None}
        missing = [
            (a, b)
            for a in sorted(families)
            for b in sorted(families)
            if a != b and not setup_lookup(instance, a, b)[1]
        ]
        if missing:
            raise _ModelDeclined(
                "conservative setup encoding needs a complete matrix over "
                f"{sorted(families)}; missing {missing}"
            )
        built.notes["setup_encoding"] = "conservative_interval_inflation"
    elif instance.setups:
        built.notes["setup_encoding"] = "exact_slot_chain"
        undefined_seen = 0
        for a in {op.family for op in instance.operations if op.family is not None}:
            for b in {op.family for op in instance.operations if op.family is not None}:
                if a != b and not setup_lookup(instance, a, b)[1]:
                    undefined_seen += 1
        built.notes["undefined_setup_directions"] = undefined_seen
    else:
        built.notes["setup_encoding"] = "none"

    # --- 变量：选机、开始、结束、工时 -------------------------------------
    for op in instance.operations:
        machines = built.choice[op.id]
        built.start[op.id] = model.NewIntVar(
            0, built.start_upper[op.id], f"start_{op.id}"
        )
        built.end[op.id] = model.NewIntVar(0, built.end_upper[op.id], f"end_{op.id}")
        built.duration[op.id] = model.NewIntVar(
            1, built.duration_upper[op.id], f"dur_{op.id}"
        )
        row = {m: model.NewBoolVar(f"x_{op.id}_{m}") for m in machines}
        built.assign[op.id] = row
        model.AddExactlyOne(list(row.values()))
        expr = None
        for machine_id, var in row.items():
            term = op.time_on(machine_id) * var
            expr = term if expr is None else expr + term
        model.Add(built.duration[op.id] == expr)
        model.Add(built.end[op.id] == built.start[op.id] + built.duration[op.id])

    # --- 释放时间与工艺路线 precedence -------------------------------------
    for job in instance.jobs:
        for operation_id in job.operation_ids:
            model.Add(built.start[operation_id] >= job.release_time)
        for before, after in zip(job.operation_ids, job.operation_ids[1:]):
            model.Add(built.start[after] >= built.end[before])

    # --- WIP 锁定 ----------------------------------------------------------
    for op in instance.operations:
        if op.locked_start is not None:
            model.Add(built.start[op.id] == op.locked_start)

    # --- 日历与维护：逐工序、逐机器条件约束 --------------------------------
    for op in instance.operations:
        for machine_id, var in built.assign[op.id].items():
            windows = instance.calendar_window(machine_id)
            if windows:
                picks = [
                    model.NewBoolVar(f"cal_{op.id}_{machine_id}_{i}")
                    for i in range(len(windows))
                ]
                model.AddExactlyOne(picks)
                for pick, (lo, hi) in zip(picks, windows):
                    model.Add(built.start[op.id] >= lo).OnlyEnforceIf([var, pick])
                    model.Add(built.end[op.id] <= hi).OnlyEnforceIf([var, pick])
            for index, (lo, hi) in enumerate(instance.maintenance_windows(machine_id)):
                before = model.NewBoolVar(f"mt_{op.id}_{machine_id}_{index}")
                model.Add(built.end[op.id] <= lo).OnlyEnforceIf([var, before])
                model.Add(built.start[op.id] >= hi).OnlyEnforceIf([var, before.Not()])

    # --- 机器占用与换型 ----------------------------------------------------
    # 机器不重叠：两条路都加 `AddNoOverlap`。精确槽位链已经蕴含了它（冗余约束），
    # 但 CP-SAT 在区间上的传播远强于元素约束链，实测它能显著加快找可行解。
    # 精确路径**不能**用膨胀版（见 :func:`_add_machine_no_overlap` 的说明）。
    _add_machine_no_overlap(built, instance, inflate_setup=not exact_setup)
    if exact_setup:
        built.setup_total = _add_machine_sequences(built)

    # --- 次生资源 ----------------------------------------------------------
    if uses_workers:
        _add_workers(built)

    # --- 目标 --------------------------------------------------------------
    _add_objective(built, spec)

    # --- 预热解 ------------------------------------------------------------
    # 放在目标之后：``AddHint`` 不影响约束，只影响搜索的起点。
    if bool(spec.get("hint", True)):
        plan = greedy_hint(instance)
        if plan is not None:
            built.notes["hint_source"] = "greedy_list_schedule"
            built.notes["hint_accepted"] = apply_hint(built, plan)
            built.notes["hint_value"] = _hint_objective(built, instance, plan)
        else:
            built.notes["hint_source"] = "none"
    return built


def _add_machine_no_overlap(
    built: _Built, instance: FJSPInstance, *, inflate_setup: bool
) -> None:
    """机器不重叠。``inflate_setup`` 决定工序区间是否按「出口换型最大值」膨胀。

    * ``inflate_setup=True``（保守编码）：区间膨胀后 ``AddNoOverlap``。因为
      ``end_i + max_outgoing >= end_i + setup(family_i -> family_j)``，相邻工序之间
      一定留够了换型间隔 —— 这条约束**独自就足够**表达换型，也永远不会产出验证器
      不接受的排程。代价是可行域被收紧。
    * ``inflate_setup=False``（精确编码）：区间**不膨胀**，只做 `[start, end)` 的
      `AddNoOverlap`。它由槽位链的 ``start_{p+1} >= end_p + gap``（``gap >= 0``）
      蕴含，是纯粹为传播而加的冗余约束。

    **这里踩过一次坑，值得记下来。** 精确编码那一版最初也用了膨胀版，理由是
    「槽位链已经蕴含了不重叠，再加一条冗余约束只会更强」。这个理由**是错的**：
    槽位链蕴含的只是**不重叠**，而膨胀版额外要求「相邻工序之间至少隔一个
    ``max_outgoing``」，那是**严格更强**的约束，会把合法解切掉。
    实测：消融链走到 ``+locked`` 那层时，``full`` 报 INFEASIBLE，而这个实例
    有一个手算可行解 —— 手工排程里 D 紧接 C（同族、不需要换型），膨胀版却要求
    它们之间空出 ``setup(F1 -> *) = 4`` 分钟。同一份模型在 batch 实例上一直偏好
    「更保守但更快」的解，根因也是它。
    """
    model = built.model
    for machine_id in instance.machine_ids:
        intervals = []
        for op in instance.operations:
            var = built.assign[op.id].get(machine_id)
            if var is None:
                continue
            inflate = max_outgoing_setup(instance, op.family) if inflate_setup else 0
            intervals.append(
                model.NewOptionalIntervalVar(
                    built.start[op.id],
                    built.duration[op.id] + inflate,
                    built.end[op.id] + inflate,
                    var,
                    f"iv_{op.id}_{machine_id}",
                )
            )
        if intervals:
            model.AddNoOverlap(intervals)


def _add_machine_sequences(built: _Built) -> Any:
    """精确编码：每台机器一条「槽位链」，换型总量随之精确可得。

    对机器 ``m`` 的候选工序列表（长度 ``K``）开 ``K`` 个槽位：

    ```text
    slot_op[p]    槽位 p 放的工序：0 = 空槽，k+1 = 候选列表第 k 道
    slot_start[p] = AddElement(slot_op[p], [0] + 各工序的 start)
    slot_end[p]   = AddElement(slot_op[p], [0] + 各工序的 end)
    pres[p]       = AddElement(slot_op[p], [0] + 各工序的 x)   # 该槽位是否真的被占
    表约束        (slot_op[p], slot_op[p+1], gap[p]) ∈ {(甲, 乙, setup(族甲,族乙))}
    间隔          slot_start[p+1] >= slot_end[p] + gap[p]   （两个槽位都被占时才强制）
    ```

    三条性质让这条链是**精确**的，而不是近似的：

    1. ``pres[p] = x[slot_op[p]]`` 且 ``Σ_p pres[p] == Σ_k x_k``：若同一道工序占两个槽位，
       右边就比左边多算一次 —— 所以每道在场工序恰好占一个槽位、且在场工序全部进链。
    2. ``pres`` 单调不增 ⇒ 空槽只能出现在尾部 ⇒ 在场工序构成**一条**链（而不是一片森林，
       森林会漏掉「时间上相邻但没连边」的那对工序，正是验证器要抓的 `overlap`）。
    3. 换型总量 = 所有相邻槽位的 ``gap`` 之和 ⇒ 可以精确进目标函数。

    因为 ``gap`` 由表约束按**真实前后工序**取值，链上相邻对才付换型；
    「两两析取 + 全局顺序变量」做不到这一点：``seq[i][j]`` 只能表达「i 在 j 之前」，
    不能表达「i 紧邻 j」，把间隔加给所有同机工序对会在
    ``setup(a->c) > setup(a->b) + p_b + setup(b->c)`` 时切掉可行解。
    """
    model = built.model
    instance = built.instance
    zero = model.NewConstant(0)
    setup_terms: list[Any] = []
    max_setup = max((item.minutes for item in instance.setups), default=0)
    for machine_id in instance.machine_ids:
        present = [op for op in instance.operations if machine_id in built.assign[op.id]]
        if not present:
            continue
        kinds = len(present)
        start_array = [zero] + [built.start[op.id] for op in present]
        end_array = [zero] + [built.end[op.id] for op in present]
        pres_array = [zero] + [built.assign[op.id][machine_id] for op in present]

        slot_op: list[Any] = []
        slot_start: list[Any] = []
        slot_end: list[Any] = []
        pres: list[Any] = []
        for p in range(kinds):
            op_slot = model.NewIntVar(0, kinds, f"slot_{machine_id}_{p}")
            s_slot = model.NewIntVar(0, built.horizon, f"sstart_{machine_id}_{p}")
            e_slot = model.NewIntVar(0, built.horizon, f"send_{machine_id}_{p}")
            p_slot = model.NewIntVar(0, 1, f"pres_{machine_id}_{p}")
            model.AddElement(op_slot, start_array, s_slot)
            model.AddElement(op_slot, end_array, e_slot)
            model.AddElement(op_slot, pres_array, p_slot)
            slot_op.append(op_slot)
            slot_start.append(s_slot)
            slot_end.append(e_slot)
            pres.append(p_slot)
        for p in range(kinds - 1):
            model.Add(pres[p] >= pres[p + 1])
        model.Add(sum(pres) == sum(pres_array[1:]))

        table: list[tuple[int, int, int]] = [(0, b, 0) for b in range(kinds + 1)]
        table += [(a, 0, 0) for a in range(1, kinds + 1)]
        for a, first in enumerate(present, start=1):
            for b, second in enumerate(present, start=1):
                minutes, defined = setup_lookup(instance, first.family, second.family)
                if defined:
                    table.append((a, b, minutes))
        for p in range(kinds - 1):
            gap = model.NewIntVar(0, max_setup, f"gap_{machine_id}_{p}")
            model.AddAllowedAssignments([slot_op[p], slot_op[p + 1], gap], table)
            model.Add(slot_start[p + 1] >= slot_end[p] + gap).OnlyEnforceIf(
                [pres[p], pres[p + 1]]
            )
            if max_setup:
                setup_terms.append(gap)
    if not setup_terms:
        return None
    total = None
    for term in setup_terms:
        total = term if total is None else total + term
    return total


def _add_workers(built: _Built) -> None:
    """强制占用 + 能力过滤 + 容量（`AddCumulative`）。"""
    model = built.model
    instance = built.instance
    per_worker: dict[str, list[Any]] = {worker.id: [] for worker in instance.workers}
    for op in instance.operations:
        options = _worker_options(instance, op, built.choice[op.id])
        row: dict[str, Any] = {}
        for worker_id in options:
            row[worker_id] = model.NewBoolVar(f"w_{op.id}_{worker_id}")
        built.worker_var[op.id] = row
        model.AddExactlyOne(list(row.values()))
        for worker_id, var in row.items():
            worker = next(w for w in instance.workers if w.id == worker_id)
            for machine_id, machine_var in built.assign[op.id].items():
                if not worker.can_operate(machine_id):
                    model.Add(var == 0).OnlyEnforceIf(machine_var)
            per_worker[worker_id].append(
                model.NewOptionalIntervalVar(
                    built.start[op.id],
                    built.duration[op.id],
                    built.end[op.id],
                    var,
                    f"wiv_{op.id}_{worker_id}",
                )
            )
    for worker in instance.workers:
        intervals = per_worker[worker.id]
        if not intervals:
            continue
        model.AddCumulative(intervals, [1] * len(intervals), worker.capacity)


def _integral(value: float, scale: int) -> bool:
    return abs(round(value * scale) - value * scale) < 1e-9


def _add_objective(built: _Built, spec: dict[str, Any]) -> None:
    """把 ``spec['objective']`` 翻译成 CP-SAT 的整数目标，并记下「模型目标 == 真实目标」。"""
    model = built.model
    instance = built.instance
    name = spec.get("objective", "makespan")
    if name not in OBJECTIVES:
        raise _ModelDeclined(f"unknown objective: {name!r}")
    weights = parse_weights(spec)
    urgency = bool(spec.get("urgency", False))
    built.objective_name = name
    built.weights = weights

    completion: dict[str, Any] = {}
    for job in instance.jobs:
        var = model.NewIntVar(0, built.horizon, f"C_{job.id}")
        model.AddMaxEquality(var, [built.end[op_id] for op_id in job.operation_ids])
        completion[job.id] = var

    cmax = model.NewIntVar(0, built.horizon, "Cmax")
    # ``late`` 的下界要能容下「完成 0 而交期很大」的情况，所以把最大交期也算进来。
    due_max = max(
        (job.due_date for job in instance.jobs if job.due_date is not None),
        default=0,
    )
    built.horizon = max(built.horizon, due_max)
    model.AddMaxEquality(cmax, list(completion.values()))
    zero = model.NewConstant(0)

    tardy: dict[str, tuple[Any, Any]] = {}  # job_id -> (T_var, 有效权重)
    for job in instance.jobs:
        if job.due_date is None:
            continue
        late = model.NewIntVar(-built.horizon, built.horizon, f"L_{job.id}")
        model.Add(late == completion[job.id] - job.due_date)
        var = model.NewIntVar(0, built.horizon, f"T_{job.id}")
        model.AddMaxEquality(var, [late, zero])
        effective = job.weight * (1.0 + job.priority if urgency else 1.0)
        tardy[job.id] = (var, effective)
    if urgency:
        built.notes["urgency_applied"] = True
        built.notes["urgent_jobs"] = sorted(
            job.id for job in instance.jobs if job.priority
        )

    terms: list[Any] = []
    scale = 1
    exact = True
    if name == "makespan":
        terms.append(cmax)
    elif name == "total_tardiness":
        terms.extend(var for var, _ in tardy.values())
    elif name == "weighted_tardiness":
        scale = WEIGHT_SCALE
        for _, effective in tardy.values():
            exact = exact and _integral(effective, scale)
        terms.extend(round(w * scale) * var for var, w in tardy.values())
    elif name == "total_setup_time":
        if built.setup_total is None:
            raise _ModelDeclined("objective total_setup_time needs the exact setup encoding")
        terms.append(built.setup_total)
    elif name == "weighted_sum":
        scale = WEIGHT_SCALE
        alpha = weights.alpha if weights else 1.0
        beta = weights.beta if weights else 0.0
        gamma = weights.gamma if weights else 0.0
        exact = _integral(alpha, scale) and _integral(beta, scale) and _integral(gamma, scale)
        if round(alpha * scale):
            terms.append(round(alpha * scale) * cmax)
        if round(beta * scale):
            terms.extend(round(beta * scale) * var for var, _ in tardy.values())
        if round(gamma * scale):
            if built.setup_total is None:
                # 保守编码没有换型变量：换型项只能从搜索目标里去掉，并在 detail 里说明。
                built.notes["setup_term_ignored_in_search"] = True
                exact = False
            else:
                terms.append(round(gamma * scale) * built.setup_total)
    if not terms:
        # 目标退化成常数：退回最小化 Cmax，并明确标注「模型目标 != 真实目标」。
        built.notes["degenerate_objective_fallback"] = name
        terms.append(cmax)
        exact = False
    target = terms[0]
    for term in terms[1:]:
        target = target + term
    model.Minimize(target)
    built.objective_scale = scale
    built.objective_exact = exact


# ---------------------------------------------------------------------------
# 求解与结果整理
# ---------------------------------------------------------------------------


def recompute_objective(
    instance: FJSPInstance,
    schedule: Schedule,
    name: str,
    weights: Any,
    *,
    urgency: bool,
) -> float:
    """**独立于求解器**重算目标值。urgency 打开时用有效权重。

    与 ``fjsp_core.objective.evaluate`` 的差别只有一处：迟交项在 urgency 下的有效
    权重是 ``w_j · (1 + priority_j)``，而 ``evaluate`` 只会用裸 ``w_j``
    —— ``Weights`` 是全局三个数，装不下「逐订单优先级」这个维度。

    这个差别必须显式处理，否则 ``result.objective`` 报的是**模型根本没有优化的数**：
    实测一个两工序的小实例，模型最优 10.0、``evaluate`` 却报 5.0，差一倍。
    """
    from fjsp_core.objective import (
        job_completion_times,
        makespan,
        max_lateness,
        total_setup_time,
        weighted_tardiness,
    )

    if not urgency or name not in ("total_tardiness", "weighted_tardiness", "weighted_sum"):
        return float(evaluate(instance, schedule, name, weights))

    completion = job_completion_times(instance, schedule)
    pi_t = 0.0
    for job in instance.jobs:
        if job.due_date is None:
            continue
        late = max(0, completion.get(job.id, 0) - job.due_date)
        pi_t += job.weight * (1.0 + job.priority) * late
    if name == "weighted_tardiness":
        return float(pi_t)
    alpha = weights.alpha if weights else 1.0
    beta = weights.beta if weights else 0.0
    gamma = weights.gamma if weights else 0.0
    plain_t = sum(
        max(0, completion.get(job.id, 0) - job.due_date)
        for job in instance.jobs
        if job.due_date is not None
    )
    return float(
        alpha * makespan(instance, schedule)
        + beta * plain_t
        + gamma * total_setup_time(instance, schedule)
    )


def _no_solution(method: str, status: str, detail: dict[str, Any]) -> ShopResult:
    return ShopResult(method=method, status=status, detail=detail)


def _extract(built: _Built, solver: cp_model.CpSolver) -> Schedule:
    operations = []
    for op in built.instance.operations:
        machine_id = next(
            m for m, var in built.assign[op.id].items() if solver.Value(var) == 1
        )
        worker_id = None
        row = built.worker_var.get(op.id)
        if row:
            worker_id = next(w for w, var in row.items() if solver.Value(var) == 1)
        operations.append(
            ScheduledOperation(
                op.id,
                machine_id,
                int(solver.Value(built.start[op.id])),
                int(solver.Value(built.end[op.id])),
                worker_id,
            )
        )
    return Schedule(tuple(operations))


def solve_with(
    instance: FJSPInstance, spec: dict[str, Any], method: str, *, exact_setup: bool
) -> ShopResult:
    """建模型 → 求解 → 独立验证 → 独立重算目标值。"""
    started = time.perf_counter()
    try:
        built = build_model(instance, spec, exact_setup=exact_setup)
    except _ModelDeclined as exc:
        return _no_solution(
            method,
            "MODEL_INVALID",
            {"declined": str(exc), "build_time": round(time.perf_counter() - started, 6)},
        )
    except FJSPInstanceError as exc:
        return _no_solution(
            method,
            "MODEL_INVALID",
            {"invalid_instance": str(exc), "build_time": round(time.perf_counter() - started, 6)},
        )
    build_time = time.perf_counter() - started

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(spec.get("time_limit", 15.0))
    # 默认单线程 + 固定种子 = 同样输入给出同样输出（Week 1 的确定性契约在 CP-SAT 上的落点）。
    # 多线程（``spec['num_search_workers'] > 1``）通常更快找到更好的可行解，但实测**不可复现**：
    # 同一个 6 job 实例、同样 10s 预算跑三次得到 97 / 98 / 97，所以默认不开。
    solver.parameters.num_search_workers = int(spec.get("num_search_workers", 1))
    solver.parameters.random_seed = int(spec.get("seed", 0))
    # 精确换型编码的 presolve 极贵：实测 seed 203 在 5 秒预算下 **分支数为 0** ——
    # 全部时间耗在 presolve，搜索一次都没开始，status 是 UNKNOWN（连可行解都没有）。
    # 关掉 presolve、并把线性化降到 0 之后，同一个 5 秒预算能给出可行解，
    # 而 15 秒预算下的最好解与默认设置**完全一样**（80000）。所以精确路径默认关。
    solver.parameters.cp_model_presolve = bool(
        spec.get("presolve", not exact_setup)
    )
    solver.parameters.linearization_level = int(
        spec.get("linearization_level", 0 if exact_setup else 1)
    )
    solve_started = time.perf_counter()
    raw = solver.Solve(built.model)
    solve_time = time.perf_counter() - solve_started

    detail: dict[str, Any] = dict(built.notes)
    detail["solver"] = "ortools.cp_model.CpSolver"
    detail["num_search_workers"] = solver.parameters.num_search_workers
    detail["cp_model_presolve"] = bool(solver.parameters.cp_model_presolve)
    detail["linearization_level"] = int(solver.parameters.linearization_level)
    detail["seed_effective"] = True
    detail["iterations_kind"] = "cp_sat_branches"
    detail["model_variables"] = len(built.model.Proto().variables)
    detail["model_constraints"] = len(built.model.Proto().constraints)
    detail["horizon"] = built.horizon
    detail["exact_setup"] = exact_setup

    status_name = solver.StatusName(raw)
    if raw == cp_model.INFEASIBLE:
        detail["failure_reason"] = "CP-SAT proved the model infeasible"
        return ShopResult(
            method=method, status="INFEASIBLE", build_time=build_time,
            solve_time=solve_time, detail=detail,
        )
    if raw == cp_model.MODEL_INVALID:
        detail["failure_reason"] = "CP-SAT rejected the model"
        return ShopResult(
            method=method, status="MODEL_INVALID", build_time=build_time,
            solve_time=solve_time, detail=detail,
        )
    if raw not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        detail["failure_reason"] = f"solver status {status_name} without an incumbent"
        return ShopResult(
            method=method, status="UNKNOWN", build_time=build_time,
            solve_time=solve_time, detail=detail,
        )

    schedule = _extract(built, solver)
    diagnostics = schedule_errors(instance, schedule)
    if diagnostics:
        detail["validator"] = diagnostics[:5]
        detail["failure_reason"] = "independent validator rejected the schedule"
        return ShopResult(
            method=method, status="FAILED", build_time=build_time,
            solve_time=solve_time, iterations=int(solver.NumBranches()), detail=detail,
        )

    weights = parse_weights(spec)
    urgency = bool(spec.get("urgency", False))
    value = recompute_objective(
        instance, schedule, built.objective_name, weights, urgency=urgency
    )
    bounded = raw == cp_model.OPTIMAL
    if bounded:
        best_bound = value
    elif built.objective_exact:
        best_bound = min(float(solver.BestObjectiveBound()) / built.objective_scale, value)
    else:
        best_bound = None
    detail["model_objective_exact"] = built.objective_exact
    detail["objective_scale"] = built.objective_scale
    detail["solver_best_bound"] = float(solver.BestObjectiveBound()) / built.objective_scale
    detail["bound_kind"] = (
        "proven" if bounded else ("cp_sat_bound" if built.objective_exact else "not_provided")
    )
    if bounded and built.objective_exact:
        # 模型目标与真实目标一致且已证明最优：重算值就是最优值。
        best_bound = value
    if not bounded and not built.objective_exact:
        # 模型目标是代理目标（例如丢掉了换型项）：模型界不是真实目标的界，必须留空。
        best_bound = None

    from fjsp_core.objective import objective_breakdown

    return ShopResult(
        method=method,
        status="OPTIMAL" if bounded else "FEASIBLE",
        schedule=schedule,
        objective=value,
        best_bound=best_bound,
        build_time=build_time,
        solve_time=solve_time,
        iterations=int(solver.NumBranches()),
        breakdown=objective_breakdown(instance, schedule),
        detail=detail,
    )


@register(
    "fjsp_cpsat_qualified",
    "FJSP CP-SAT：机器相关工时 + 释放/交期 + 日历/维护 + 资质 + 次生资源 + WIP 锁定",
)
def fjsp_cpsat_qualified(instance: FJSPInstance, spec: dict[str, Any]) -> ShopResult:
    """资质与次生资源求解器（换型用保守编码）。

    * 资质：合格机器集合 = ``{q.machine_id | q.family == op.family}``（仅当实例给了资质）。
    * 次生资源：每道工序**必须**占用一名能操作其选定机器的资源（``Worker.machine_ids``），
      同时占用数不超过 ``Worker.capacity``（``AddCumulative``）。
    * 返回的 ``Schedule`` 里每道工序都带 ``worker_id``。
    """
    return solve_with(instance, spec, "fjsp_cpsat_qualified", exact_setup=False)


@register(
    "fjsp_cpsat_full",
    "全工业约束 CP-SAT：本月的 headline 求解器（换型用精确槽位链编码）",
)
def fjsp_cpsat_full(instance: FJSPInstance, spec: dict[str, Any]) -> ShopResult:
    """全约束求解器：工时随机器变化 + 柔性 + 释放/交期 + 顺序相关换型 +
    日历/维护 + 资质 + 资源容量 + WIP 锁定。

    ``spec`` 支持 ``objective``（见 ``fjsp_core.objective.OBJECTIVES``）、``time_limit``、
    ``seed``、``weights``，以及 ``urgency``（把 ``Job.priority`` 变成加权迟交的权重放大，
    **只改目标函数，不改任何约束**）。
    """
    return solve_with(instance, spec, "fjsp_cpsat_full", exact_setup=True)
