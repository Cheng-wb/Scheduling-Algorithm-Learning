"""M3 Week 3：工业约束 I —— 释放时间/交期、sequence-dependent setup、机器日历与加权多目标。

三个注册方法（``configs/month3.json`` 按名字调用）：

* ``fjsp_cpsat_setup``    把 **sequence-dependent setup** 建进模型：每台机器用一条
  **紧前弧（``AddCircuit``）** 编码加工顺序，弧 ``a -> b`` 的换型时间取自
  ``instance.setup_minutes(a.family, b.family)``，于是「这台机器上的总换型时间」
  是一个**精确的线性表达式** ``Σ_弧 y[a,b]·s(a,b)``，而不是上界。
* ``fjsp_cpsat_calendar`` 把 **日历可用窗 + 计划维护窗** 建进模型：对每个
  ``(工序, 机器)`` 先算出可容纳该工序的**极大可用窗集合**，每个窗一个
  ``OptionalIntervalVar``，``AddExactlyOne`` 保证只落在一个窗里。工序因此
  **不可能**跨越日历空洞或维护窗——不是「事后检查」，而是「建模时就排除」。
* ``fjsp_cpsat_multiobj`` 加权多目标 ``α·Cmax + β·ΣT + γ·setup``。权重从
  ``spec["weights"]`` 经 :func:`fjsp_core.objective.parse_weights` 读入，
  **先归一化再加权**（见 :func:`resolve_normalization`）。

三条纪律（与 M1/M2 一脉相承）
-----------------------------

1. **三个方法都强制实例里声明的全部约束。** 一个会返回「过不了独立验证器」的排程的
   求解器是没有价值的，所以「日历只在 ``fjsp_cpsat_calendar`` 里被遵守」这种设计
   是错的。三个方法的差别在**各自重点检验的建模技术与目标处理**，不在约束覆盖面。
2. **``best_bound`` 只写求解器在「报告的目标函数」上给出的界。** 多目标模型里
   求解器证明的是**归一化后**的加权和，那不是 ``objective`` 字段里那个原始单位的
   加权和——所以此时 ``best_bound`` 必须写 ``None``，``status`` 也不能自称 ``OPTIMAL``。
   用「另一个函数的下界」冒充「这个函数的下界」是最隐蔽的伪证据。
3. **求解器说 ``OPTIMAL`` 不等于解可行**：返回前仍然调用 ``validate_schedule``，
   不通过就记 ``FAILED`` 并把诊断原样带出来。

时间与整数
----------
CP-SAT 只有整数变量。本模块模型里的时间量全部来自 ``int`` 字段
（``machine_times`` / ``release_time`` / ``due_date`` / ``setup.minutes`` / 日历窗），
所以 ``time_scale = 1`` 是恒等映射，不需要 M2 那套缩放。
唯一的小数是**权重**：归一化之后仍可能是小数，乘 ``OBJ_SCALE`` 取整再建模，
汇报时除回来——这一处（也只有这一处）引入舍入，见 :meth:`Normalization.scaled`。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from ortools.sat.python import cp_model

from fjsp_core.models import FJSPInstance, Operation, Schedule, ScheduledOperation
from fjsp_core.objective import (
    Weights,
    evaluate,
    objective_breakdown,
    parse_weights,
)
from fjsp_core.result import ShopResult
from fjsp_core.schedule_validation import validate_schedule
from fjsp_shop.registry import register

DEFAULT_TIME_LIMIT = 10.0

#: 归一化后的权重乘这个常数再取整，得到 CP-SAT 的整数目标系数。
OBJ_SCALE = 1_000_000

#: 支持的单目标名。``weighted_tardiness``（带交货期权重的迟交）不在本周范围。
SINGLE_OBJECTIVES = ("makespan", "total_tardiness", "total_setup_time")

#: 日历的两种编码。二者可行集相同，变量数与传播强度不同。
CALENDAR_MODES = ("split", "blocker")

_CP_TO_SHOP = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.UNKNOWN: "UNKNOWN",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
}

_SOLVED = (cp_model.OPTIMAL, cp_model.FEASIBLE)


class _InfeasibleByConstruction(Exception):
    """建模阶段就能判定不可行：某道工序在所有合格机器上都放不进任何一个可用窗。"""


# ---------------------------------------------------------------------------
# 时间界与可用窗
# ---------------------------------------------------------------------------


def upper_horizon(instance: FJSPInstance) -> int:
    """所有时间变量的上界 ``H``：**先按完全串行估、再顺延到最晚的窗口末端**。

    任何可行排程的 ``Cmax`` 都不超过
    ``max r_j + Σ_工序 max_m p_om + 工序数 × max setup``（完全串行）
    再加上最晚的日历/维护窗末端（窗口之间可能有很长的空洞，串行时间覆盖不到）。

    这个界**不紧，也不需要紧**：它的唯一职责是让 ``start`` / ``end`` 有界，
    避免 CP-SAT 在无界整数域上做无效搜索。
    """
    max_setup = max((item.minutes for item in instance.setups), default=0)
    longest = sum(max(time for _, time in op.machine_times) for op in instance.operations)
    serial = max((job.release_time for job in instance.jobs), default=0)
    serial += longest + max_setup * len(instance.operations)
    window_end = 0
    for machine in instance.machines:
        for _, hi in instance.calendar_window(machine.id):
            window_end = max(window_end, hi)
        for _, hi in instance.maintenance_windows(machine.id):
            window_end = max(window_end, hi)
    return int(serial + window_end) + 1


def allowed_windows(
    instance: FJSPInstance, machine_id: str, horizon: int
) -> tuple[tuple[int, int], ...]:
    """机器 ``machine_id`` 的**可用区段**：日历窗（空 = 无约束）再扣掉维护窗。

    语义与 :mod:`fjsp_core.schedule_validation` 一致：工序区间 ``[start, end)``
    必须整体落在**某一个**区段内。

    **为什么先把区段算出来，而不是把维护窗做成「不可用区间」塞进 ``AddNoOverlap``？**
    两条编码（切窗 / 起点域限制）都需要同一份区段表；把它抽成唯一的一份几何计算，
    「模型里允许的」与「验证器接受的」就由同一段代码保证一致——不一致时
    验证器会立刻报 ``calendar`` / ``maintenance``，而不是静默地放过。
    """
    calendar = instance.calendar_window(machine_id)
    base: tuple[tuple[int, int], ...] = calendar if calendar else ((0, horizon),)
    blocked = instance.maintenance_windows(machine_id)
    segments: list[tuple[int, int]] = []
    for lo, hi in base:
        pieces = [(max(lo, 0), min(hi, horizon))]
        for blocked_lo, blocked_hi in blocked:
            kept: list[tuple[int, int]] = []
            for piece_lo, piece_hi in pieces:
                if blocked_hi <= piece_lo or piece_hi <= blocked_lo:
                    kept.append((piece_lo, piece_hi))  # 不相交，原样保留
                    continue
                if piece_lo < blocked_lo:
                    kept.append((piece_lo, blocked_lo))
                if blocked_hi < piece_hi:
                    kept.append((blocked_hi, piece_hi))
            pieces = kept
        segments.extend(pieces)
    return tuple(sorted(item for item in segments if item[0] < item[1]))


def fitting_windows(
    windows: tuple[tuple[int, int], ...], duration: int
) -> tuple[tuple[int, int], ...]:
    """能**完整容纳**一道 ``duration`` 长工序的可用窗。"""
    return tuple((lo, hi) for lo, hi in windows if hi - lo >= duration)


def starting_domain(
    windows: tuple[tuple[int, int], ...], duration: int
) -> tuple[tuple[int, int], ...]:
    """把「``[s, s + duration)`` 落在某个可用窗内」翻译成 ``s`` 的区间并。

    这就是「按窗切分」与「起点域限制」两条编码共用的**唯一**几何计算：
    它算错了两种编码会一起错（并且会被独立验证器抓到），算对了两条编码
    必然给同一个可行集——``tests/test_week3.py::test_calendar_encodings_agree``
    断言的就是这件事。
    """
    return tuple((lo, hi - duration) for lo, hi in fitting_windows(windows, duration))


def _forbidden_windows(
    windows: tuple[tuple[int, int], ...], horizon: int
) -> tuple[tuple[int, int], ...]:
    """``[0, horizon]`` 内不在任何可用窗里的部分（``blocker`` 编码拿它做停机区间）。"""
    gaps: list[tuple[int, int]] = []
    cursor = 0
    for lo, hi in windows:
        if cursor < lo:
            gaps.append((cursor, lo))
        cursor = max(cursor, hi)
    if cursor < horizon:
        gaps.append((cursor, horizon))
    return tuple(gaps)


# ---------------------------------------------------------------------------
# 归一化
# ---------------------------------------------------------------------------


def trivial_bounds(instance: FJSPInstance) -> dict[str, float]:
    """三个分量的**平凡上界**，用作归一化分母（恒 > 0、确定性、不需要求解）。

    ``Cmax`` 取「完全串行 + 最晚窗末端」；``ΣT`` 取 ``Σ_j max(0, Cmax_ub − d_j)``
    （因为 ``C_j <= Cmax`` 恒成立）；``setup`` 取 ``工序数 × max setup``
    （每道工序前面至多发生一次换型）。

    平凡上界很松，会让归一化后的分量整体偏小——**这是刻意的**：它保证「不求解也能
    算出分母」，从而使 ``fjsp_cpsat_multiobj`` 的建模阶段与「另解三个单目标模型
    取理想点」完全解耦。想要紧的分母就用 ``mode = "ideal"`` 显式传进来
    （Day 3 的敏感性实验正是这么做的）。
    """
    max_setup = max((item.minutes for item in instance.setups), default=0)
    cmax = float(upper_horizon(instance))
    tardiness = float(
        sum(
            max(0.0, cmax - job.due_date)
            for job in instance.jobs
            if job.due_date is not None
        )
    )
    setup = float(max_setup * len(instance.operations))
    return {
        "cmax": cmax if cmax > 0 else 1.0,
        "total_tardiness": tardiness if tardiness > 0 else 1.0,
        "setup": setup if setup > 0 else 1.0,
    }


@dataclass(frozen=True, slots=True)
class Normalization:
    """多目标的归一化方案：``mode``（分母从哪来）+ ``divisors``（三个分母）。"""

    mode: str
    divisors: dict[str, float]

    def to_detail(self) -> dict[str, Any]:
        return {"mode": self.mode, "divisors": dict(self.divisors)}

    def scaled(self, weights: Weights) -> tuple[int, int, int, bool]:
        """返回 ``(α', β', γ', exact)``：CP-SAT 用的整数系数 + 系数是否被舍入。

        ``mode = "none"`` 时不除分母，只乘 ``OBJ_SCALE``；此时只要三个权重都能被
        ``OBJ_SCALE`` 整除，模型目标就恰好是 ``OBJ_SCALE × 原始加权和``，
        于是**下界可以精确换算回原始单位**——这是唯一能报 ``best_bound`` 的情形。
        其余情形（包含所有归一化模式）下系数都经过舍入，且模型目标与报告目标
        之间没有确定的换算关系。
        """
        raw = {
            "cmax": weights.alpha,
            "total_tardiness": weights.beta,
            "setup": weights.gamma,
        }
        coefficients: list[int] = []
        exact = self.mode == "none"
        for key in ("cmax", "total_tardiness", "setup"):
            scaled_value = raw[key] * OBJ_SCALE / self.divisors[key]
            rounded = int(round(scaled_value))
            if abs(scaled_value - rounded) > 1e-6:
                exact = False
            coefficients.append(rounded)
        alpha, beta, gamma = coefficients
        if alpha == 0 and beta == 0 and gamma == 0:
            # 分母过大导致所有权重都被舍成 0：退化成按原值取整，
            # 否则目标恒为常数，「优化」就变成了「随便找一个可行解」。
            alpha = int(round(weights.alpha * OBJ_SCALE))
            beta = int(round(weights.beta * OBJ_SCALE))
            gamma = int(round(weights.gamma * OBJ_SCALE))
            exact = False
        return alpha, beta, gamma, exact


def resolve_normalization(instance: FJSPInstance, spec: dict[str, Any]) -> Normalization:
    """从 ``spec["normalization"]`` 解析归一化方案。默认 ``mode = "trivial"``。

    ``trivial``（默认）按 :func:`trivial_bounds` 的三个平凡上界作分母。
    每个分量都落进 ``[0, 1]``，量纲被抹掉，「一分钟迟交 = 一分钟换型」这种
    隐含假设随之消失；代价是分母偏松，权重差一点可能看不出差别。

    ``ideal`` 用**单目标最优值**作分母（多目标优化的教科书做法：理想点归一化）。
    最优值必须由调用方传进来（``{"cmax": …, "total_tardiness": …, "setup": …}``）——
    算它要另解三个模型，那是驱动脚本的职责，不该由求解器偷偷做。

    ``none`` 不归一化，直接按原始单位加权。保留它是为了**对照**：
    同一组权重在两种口径下选出的排程可能不同，这件事必须能被测出来。
    """
    raw = spec.get("normalization") or {}
    mode = str(raw.get("mode", "trivial"))
    if mode == "none":
        return Normalization("none", {"cmax": 1.0, "total_tardiness": 1.0, "setup": 1.0})
    if mode == "ideal":
        divisors: dict[str, float] = {}
        for key in ("cmax", "total_tardiness", "setup"):
            value = float(raw.get(key, 0.0))
            if value <= 0:
                raise ValueError(
                    f'normalization mode "ideal" requires a positive {key!r} ideal value'
                )
            divisors[key] = value
        return Normalization("ideal", divisors)
    if mode == "trivial":
        return Normalization("trivial", trivial_bounds(instance))
    raise ValueError(f"unknown normalization mode: {mode!r}")


# ---------------------------------------------------------------------------
# 建模
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Objective:
    name: str
    weights: Weights | None
    coefficients: tuple[int, int, int]  # (α', β', γ')，已乘 OBJ_SCALE
    exact: bool  # 模型目标是否恰好是 OBJ_SCALE × 报告目标


class _Built:
    """建模产物：模型 + 读解所需的全部句柄。"""

    def __init__(
        self,
        model: cp_model.CpModel,
        instance: FJSPInstance,
        start: dict[str, Any],
        end: dict[str, Any],
        presence: dict[tuple[str, str], Any],
        job_end: dict[str, Any],
        cmax: Any,
        objective: _Objective,
        normalization: Normalization | None,
        calendar_mode: str,
        setup_arcs: list[tuple[str, str, str, Any, int]],
        horizon: int,
        infeasible_reason: str | None = None,
    ) -> None:
        self.model = model
        self.instance = instance
        self.start = start
        self.end = end
        self.presence = presence
        self.job_end = job_end
        self.cmax = cmax
        self.objective = objective
        self.normalization = normalization
        self.calendar_mode = calendar_mode
        self.setup_arcs = setup_arcs
        self.horizon = horizon
        self.infeasible_reason = infeasible_reason

    def size(self) -> dict[str, int]:
        proto = self.model.Proto()
        return {"variables": len(proto.variables), "constraints": len(proto.constraints)}


def _qualified_machines(instance: FJSPInstance, op: Operation) -> set[str] | None:
    """有资质加工 ``op.family`` 的机器；实例没给资质时返回 ``None``（= 不限制）。

    与验证器同一条规则：**只有当实例里存在任何资质记录时才检查资质**。
    """
    if not instance.qualifications or op.family is None:
        return None
    return {item.machine_id for item in instance.qualifications if item.family == op.family}


def _candidates(
    instance: FJSPInstance, op: Operation, windows: dict[str, tuple[tuple[int, int], ...]]
) -> list[tuple[str, int, tuple[tuple[int, int], ...]]]:
    """``(机器, 工时, 容得下该工序的可用窗)``：筛掉没资质与放不进去的机器。"""
    qualified = _qualified_machines(instance, op)
    result: list[tuple[str, int, tuple[tuple[int, int], ...]]] = []
    for machine_id in op.eligible_machine_ids:
        if qualified is not None and machine_id not in qualified:
            continue
        duration = op.time_on(machine_id)
        assert duration is not None, "eligible_machine_ids 来自 machine_times"
        usable = fitting_windows(windows[machine_id], duration)
        if usable:
            result.append((machine_id, duration, usable))
    return result


def _objective_of(
    model: cp_model.CpModel,
    spec: dict[str, Any],
    instance: FJSPInstance,
    setup_arcs: list[tuple[str, str, str, Any, int]],
    cmax: Any,
    tardiness: dict[str, Any],
) -> tuple[_Objective, Normalization | None]:
    """装配目标函数，返回 ``(目标描述, 归一化方案)``。未知目标名抛 ``ValueError``。"""
    name = str(spec.get("objective", "makespan"))
    setup_terms = [minutes * arc for _, _, _, arc, minutes in setup_arcs if minutes]
    setup_expr: Any = sum(setup_terms) if setup_terms else 0

    if name == "weighted_sum":
        weights = parse_weights(spec) or Weights()
        normalization = resolve_normalization(instance, spec)
        alpha, beta, gamma, exact = normalization.scaled(weights)
        terms: list[Any] = []
        if alpha and cmax is not None:
            terms.append(alpha * cmax)
        if beta and tardiness:
            terms.append(beta * sum(tardiness.values()))
        if gamma and setup_terms:
            terms.append(gamma * setup_expr)
        if terms:
            model.Minimize(sum(terms))
        return _Objective(name, weights, (alpha, beta, gamma), exact), normalization

    if name not in SINGLE_OBJECTIVES:
        raise ValueError(
            f"unsupported objective {name!r}; expected one of "
            f"{SINGLE_OBJECTIVES + ('weighted_sum',)}"
        )
    weights = parse_weights(spec)
    if name == "makespan":
        if cmax is not None:
            model.Minimize(cmax)
    elif name == "total_tardiness":
        if tardiness:
            model.Minimize(sum(tardiness.values()))
    else:  # total_setup_time
        if setup_terms:
            model.Minimize(setup_expr)
    return _Objective(name, weights, (1, 0, 0), True), None


def _add_machine_circuits(
    model: cp_model.CpModel,
    instance: FJSPInstance,
    participants: dict[str, list[tuple[Operation, int]]],
    presence: dict[tuple[str, str], Any],
    start: dict[str, Any],
    end: dict[str, Any],
) -> list[tuple[str, str, str, Any, int]]:
    """每台机器一条 circuit：弧 ``a -> b`` 表示「``a`` 紧接在 ``b`` 之前」。

    节点 0 是哑元（机器的起点/终点），节点 ``1..k`` 是可在这台机器上加工的工序。
    每个节点必须恰好有一条出弧与一条入弧；不在这台机器上的工序走**自环**
    （字面量取其 presence 的否定）。于是：

    ```text
    流入(b) = 1 - 自环(b) = presence(b)          自然成立，不需要额外的流平衡约束
    总换型  = Σ_弧 y[a,b] · setup(family_a, family_b)   精确等于「按加工顺序累加」
    ```

    **为什么用「紧前弧」而不是「先后字面量」？** 后者（``x[a,b]`` 表示 a 早于 b）
    建模更简单，但 ``Σ_{a≠b} x[a,b]·s(a,b)`` 会**高估**总换型：链 ``a -> b -> c``
    上它把 ``s(a,c)`` 也算进去了，而换型只发生在**相邻**两道工序之间。那个表达式
    或许能当启发式，作为目标函数却与 ``objective_breakdown`` 报的 ``setup`` 对不上——
    模型优化的东西就不是它报告的东西了。

    **未定义的换型方向**（换型矩阵缺项）不建弧：该相邻关系被**禁止**，而不是按 0
    处理。这样任何返回的排程都不会触发验证器的 ``setup undefined``；
    如果禁止之后无解，那是模型如实报告的 ``INFEASIBLE``，不是隐藏的建模缺口。
    """
    arcs: list[tuple[str, str, str, Any, int]] = []
    for machine in instance.machines:
        machine_id = machine.id
        members = sorted(participants[machine_id], key=lambda item: item[0].id)
        if not members:
            continue
        index_of = {op.id: position + 1 for position, (op, _) in enumerate(members)}
        dummy = 0

        unique: dict[tuple[int, int], Any] = {}

        def arc_literal(tail: int, head: int) -> Any:
            key = (tail, head)
            if key not in unique:
                unique[key] = model.NewBoolVar(f"arc[{machine_id},{tail}->{head}]")
            return unique[key]

        self_loops: list[tuple[int, int, Any]] = []
        self_loops.append(
            (dummy, dummy, model.NewBoolVar(f"machidle[{machine_id}]"))
        )
        for op, _ in members:
            node = index_of[op.id]
            self_loops.append((node, node, presence[(op.id, machine_id)].Not()))
        for op, _ in members:
            node = index_of[op.id]
            arc_literal(dummy, node)
            arc_literal(node, dummy)
        for a, _ in members:
            for b, _ in members:
                if a.id == b.id:
                    continue
                minutes = _setup_minutes(instance, a, b)
                if minutes is None:
                    continue  # 换型矩阵缺项 -> 禁止这一相邻关系
                arcs.append(
                    (machine_id, a.id, b.id, arc_literal(index_of[a.id], index_of[b.id]), minutes)
                )
        circuit = list(self_loops)
        for (tail, head), literal in unique.items():
            circuit.append((tail, head, literal))
        model.AddCircuit(circuit)

        for arc_machine, from_id, to_id, literal, minutes in arcs:
            if arc_machine != machine_id:
                continue
            # 换型间隔：紧前工序完工 + setup <= 后道工序开工（minutes = 0 时退化为不重叠）
            model.Add(start[to_id] >= end[from_id] + minutes).OnlyEnforceIf(literal)
    return arcs


def _setup_minutes(instance: FJSPInstance, before: Operation, after: Operation) -> int | None:
    """换型时间；方向未定义时返回 ``None``（调用方据此**禁止**该相邻关系）。"""
    try:
        return instance.setup_minutes(before.family, after.family)
    except KeyError:
        return None


def _build(instance: FJSPInstance, spec: dict[str, Any], *, calendar_mode: str) -> _Built:
    """建出工业约束 FJSP 模型。``calendar_mode`` 决定日历的编码方式。

    ``"split"``   每个 ``(工序, 机器, 可用窗)`` 一个 ``OptionalIntervalVar``，
                  ``AddExactlyOne`` 保证恰好落在一个窗里。窗的数量直接变成布尔变量
                  的数量——窗多时模型变大，但每个变量的语义极清楚。

    ``"blocker"`` 工序在每台机器上只有一个可选区间，日历用**起点域限制**
                  （``AddLinearExpressionInDomain`` + ``OnlyEnforceIf``）表达，
                  再把不可用区段做成固定区间塞进同一个 ``AddNoOverlap``。
                  布尔变量少，但「落在哪个窗」对求解器是隐式的。

    两条编码的可行集**完全相同**，因为二者共用 :func:`fitting_windows` /
    :func:`starting_domain` 这一份几何计算。
    """
    horizon = upper_horizon(instance)
    windows = {
        machine.id: allowed_windows(instance, machine.id, horizon)
        for machine in instance.machines
    }
    model = cp_model.CpModel()
    start: dict[str, Any] = {}
    end: dict[str, Any] = {}
    presence: dict[tuple[str, str], Any] = {}
    machine_intervals: dict[str, list[Any]] = {machine.id: [] for machine in instance.machines}
    participants: dict[str, list[tuple[Operation, int]]] = {
        machine.id: [] for machine in instance.machines
    }

    for op in instance.operations:
        start[op.id] = model.NewIntVar(0, horizon, f"start[{op.id}]")
        end[op.id] = model.NewIntVar(0, horizon, f"end[{op.id}]")
        candidates = _candidates(instance, op, windows)
        if not candidates:
            return _infeasible_by_construction(
                model, instance, f"operation {op.id} fits in no allowed window"
            )
        op_flags: list[tuple[str, Any]] = []
        alternatives: list[Any] = []
        for machine_id, duration, usable in candidates:
            flag = model.NewBoolVar(f"use[{op.id},{machine_id}]")
            op_flags.append((machine_id, flag))
            if calendar_mode == "split":
                pieces: list[Any] = []
                for index, (lo, hi) in enumerate(usable):
                    piece = model.NewBoolVar(f"win[{op.id},{machine_id},{index}]")
                    model.Add(start[op.id] >= lo).OnlyEnforceIf(piece)
                    model.Add(end[op.id] <= hi).OnlyEnforceIf(piece)
                    machine_intervals[machine_id].append(
                        model.NewOptionalIntervalVar(
                            start[op.id], duration, end[op.id], piece,
                            f"iv[{op.id},{machine_id},w{index}]",
                        )
                    )
                    pieces.append(piece)
                model.Add(flag == sum(pieces))
                alternatives.extend(pieces)
            else:
                model.AddLinearExpressionInDomain(
                    start[op.id],
                    cp_model.Domain.FromIntervals(
                        [[lo, hi - duration] for lo, hi in usable]
                    ),
                ).OnlyEnforceIf(flag)
                machine_intervals[machine_id].append(
                    model.NewOptionalIntervalVar(
                        start[op.id], duration, end[op.id], flag, f"iv[{op.id},{machine_id}]"
                    )
                )
                alternatives.append(flag)
            presence[(op.id, machine_id)] = flag
            participants[machine_id].append((op, duration))
        model.AddExactlyOne(alternatives)

        # 释放时间：不早于所属订单的释放时刻（验证器的第 4 项）
        model.Add(start[op.id] >= instance.job(op.job_id).release_time)
        # WIP：被锁定的工序，机器与开工时刻必须与给定值一致（验证器的第 11 项）
        if op.locked_start is not None:
            model.Add(start[op.id] == op.locked_start)
        if op.locked_machine_id is not None:
            for machine_id, flag in op_flags:
                model.Add(flag == (1 if machine_id == op.locked_machine_id else 0))

    # --- 订单内 precedence（验证器的第 5 项） ------------------------------
    for job in instance.jobs:
        for before, after in zip(job.operation_ids, job.operation_ids[1:]):
            model.Add(start[after] >= end[before])

    # --- 机器互斥与换型 ---------------------------------------------------
    setup_arcs: list[tuple[str, str, str, Any, int]] = []
    if instance.setups:
        setup_arcs = _add_machine_circuits(
            model, instance, participants, presence, start, end
        )
    # 同机器不重叠。两条说明：
    # 1. 有换型时 circuit 的紧前弧**已经蕴含**不重叠，这里再挂一层 AddNoOverlap
    #    是**冗余约束**：不改变可行集，但让 CP-SAT 的边查找与能量推理也能作用在
    #    同一批区间上。加与不加必须给出同一个最优值（Day 4 会实测这一点）。
    # 2. blocker 编码下，日历空洞与维护窗做成**固定区间**一起进同一个 AddNoOverlap，
    #    工序区间因此不可能与停机区间重叠。split 编码不需要它——窗外的解根本
    #    建不出可选区间。
    for machine_id, intervals in machine_intervals.items():
        if not intervals:
            continue
        combined = list(intervals)
        if calendar_mode == "blocker":
            for index, (lo, hi) in enumerate(_forbidden_windows(windows[machine_id], horizon)):
                combined.append(
                    model.NewFixedSizeIntervalVar(lo, hi - lo, f"down[{machine_id},{index}]")
                )
        model.AddNoOverlap(combined)

    # --- 目标的三个分量 ---------------------------------------------------
    job_end: dict[str, Any] = {}
    for job in instance.jobs:
        if job.operation_ids:
            job_end[job.id] = end[job.operation_ids[-1]]
    cmax: Any = None
    if job_end:
        cmax = model.NewIntVar(0, horizon, "Cmax")
        model.AddMaxEquality(cmax, list(job_end.values()))
    tardiness: dict[str, Any] = {}
    for job in instance.jobs:
        if job.due_date is None or job.id not in job_end:
            continue
        var = model.NewIntVar(0, horizon, f"T[{job.id}]")
        model.AddMaxEquality(var, [job_end[job.id] - job.due_date, 0])
        tardiness[job.id] = var

    objective, normalization = _objective_of(
        model, spec, instance, setup_arcs, cmax, tardiness
    )
    return _Built(
        model=model,
        instance=instance,
        start=start,
        end=end,
        presence=presence,
        job_end=job_end,
        cmax=cmax,
        objective=objective,
        normalization=normalization,
        calendar_mode=calendar_mode,
        setup_arcs=setup_arcs,
        horizon=horizon,
    )


def _infeasible_by_construction(
    model: cp_model.CpModel, instance: FJSPInstance, reason: str
) -> _Built:
    """建不出可行模型：返回带原因的 ``_Built``，由调用方翻成 ``INFEASIBLE``。"""
    return _Built(
        model=model,
        instance=instance,
        start={},
        end={},
        presence={},
        job_end={},
        cmax=None,
        objective=_Objective("makespan", None, (1, 0, 0), True),
        normalization=None,
        calendar_mode="",
        setup_arcs=[],
        horizon=0,
        infeasible_reason=reason,
    )


# ---------------------------------------------------------------------------
# 求解与读解
# ---------------------------------------------------------------------------


def _extract_schedule(built: _Built, solver: cp_model.CpSolver) -> Schedule:
    """从求解结果还原 ``Schedule``：每道工序找 presence 为 1 的那台机器。"""
    items: list[ScheduledOperation] = []
    for op in built.instance.operations:
        chosen = None
        for machine_id in op.eligible_machine_ids:
            flag = built.presence.get((op.id, machine_id))
            if flag is not None and solver.Value(flag) == 1:
                chosen = machine_id
                break
        if chosen is None:  # pragma: no cover - 模型保证恰好一台
            raise ValueError(f"solver left operation {op.id} unassigned")
        items.append(
            ScheduledOperation(
                operation_id=op.id,
                machine_id=chosen,
                start_time=int(solver.Value(built.start[op.id])),
                end_time=int(solver.Value(built.end[op.id])),
            )
        )
    return Schedule(tuple(items))


def _bound_and_status(
    built: _Built, solver: cp_model.CpSolver, objective: float, model_status: int
) -> tuple[float | None, str, bool]:
    """把求解器的状态与界翻译成「报告目标」上的状态与界。

    只有 **模型目标恰好等于报告目标**（``exact``）时才能直接采用求解器的读数：
    那时 ``best_bound`` 是同一个函数的下界。否则（多目标 + 归一化）求解器证明的
    是归一化后的加权和，对原始单位的加权和**不构成下界**，于是：

    * ``best_bound = None``（不是 0、不是目标值）；
    * ``status`` 从 ``OPTIMAL`` 降级为 ``FEASIBLE``——因为「已证明最优」这句话
      对**报告的目标**并不成立。求解器的原话记在 ``detail["model_status"]`` 里。
    """
    status = _CP_TO_SHOP.get(model_status, "FAILED")
    if not built.objective.exact:
        # 第三个返回值是 ``bound_clamped``：这里没有界可夹，恒为 False。
        # 「求解器证明了归一化目标最优」这件事**不写在这里**——它由
        # ``detail["model_status"]`` 表达；混进 ``bound_clamped`` 会把
        # 「界被夹到目标值」和「模型已证明最优」两件不相干的事搅在一起。
        return None, ("FEASIBLE" if model_status in _SOLVED else status), False
    assert built.objective.name != "weighted_sum" or built.objective.exact
    raw_bound = float(solver.BestObjectiveBound())
    if built.objective.name == "weighted_sum":
        raw_bound /= OBJ_SCALE
    clamped = raw_bound > objective
    return (min(raw_bound, objective) if clamped else raw_bound), status, clamped


def _solve(
    instance: FJSPInstance, spec: dict[str, Any], *, method: str, calendar_mode: str
) -> ShopResult:
    time_limit = float(spec.get("time_limit", DEFAULT_TIME_LIMIT))
    seed = int(spec.get("seed", 0))
    started = time.perf_counter()
    try:
        built = _build(instance, spec, calendar_mode=calendar_mode)
    except ValueError as exc:
        return ShopResult(
            method=method,
            status="FAILED",
            build_time=time.perf_counter() - started,
            detail={"failure_reason": f"{type(exc).__name__}: {exc}"},
        )
    build_time = time.perf_counter() - started

    if built.infeasible_reason:
        return ShopResult(
            method=method,
            status="INFEASIBLE",
            build_time=build_time,
            detail={
                "failure_reason": built.infeasible_reason,
                "calendar_mode": calendar_mode,
                "horizon": built.horizon,
            },
        )

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1  # 确定性：单线程搜索，与 M2 的纪律一致
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.random_seed = seed
    model_status = solver.Solve(built.model)
    solve_time = time.perf_counter() - started - build_time
    status = _CP_TO_SHOP.get(model_status, "FAILED")

    detail: dict[str, Any] = {
        "calendar_mode": calendar_mode,
        "objective_name": built.objective.name,
        "model_size": built.size(),
        "horizon": built.horizon,
        "num_branches": int(solver.NumBranches()),
        "time_limit": time_limit,
        "seed": seed,
        "setup_encoding": "immediate-predecessor circuit arcs" if instance.setups else "none",
        "objective_coefficients_scaled": list(built.objective.coefficients),
    }
    if built.objective.weights is not None:
        detail["weights"] = {
            "alpha": built.objective.weights.alpha,
            "beta": built.objective.weights.beta,
            "gamma": built.objective.weights.gamma,
        }
    if built.normalization is not None:
        detail["normalization"] = built.normalization.to_detail()
        detail["normalization_note"] = (
            "求解器优化的是归一化后的加权和；报告的 objective 是原始单位的加权和"
        )

    if model_status not in _SOLVED:
        return ShopResult(
            method=method,
            status=status,
            build_time=build_time,
            solve_time=solve_time,
            detail=detail,
        )

    schedule = _extract_schedule(built, solver)
    try:
        validate_schedule(instance, schedule)
    except ValueError as exc:
        # 求解器给了不可行的解：比 FAILED 更严重，必须显眼（与 benchmark 同一条纪律）
        detail["failure_reason"] = f"independent validator rejected the schedule: {exc}"
        return ShopResult(
            method=method,
            status="FAILED",
            schedule=schedule,
            build_time=build_time,
            solve_time=solve_time,
            detail=detail,
        )

    objective = evaluate(instance, schedule, built.objective.name, built.objective.weights)
    best_bound, reported_status, clamped = _bound_and_status(
        built, solver, objective, model_status
    )
    detail["model_status"] = _CP_TO_SHOP.get(model_status, "FAILED")
    if clamped:
        detail["bound_clamped"] = True
    if not built.objective.exact:
        detail["optimality_scope"] = "normalized weighted sum (not the reported objective)"
    return ShopResult(
        method=method,
        status=reported_status,
        schedule=schedule,
        objective=float(objective),
        best_bound=best_bound,
        build_time=build_time,
        solve_time=solve_time,
        iterations=int(solver.NumBranches()),
        breakdown=objective_breakdown(instance, schedule),
        detail=detail,
    )


# ---------------------------------------------------------------------------
# 注册方法
# ---------------------------------------------------------------------------


@register("fjsp_cpsat_setup")
def fjsp_cpsat_setup(instance: FJSPInstance, spec: dict[str, Any]) -> ShopResult:
    """FJSP CP-SAT：sequence-dependent setup 用紧前弧（``AddCircuit``）+ 换型间隔编码。

    日历与维护用 ``blocker`` 编码（不可用区段做成固定区间进入 ``AddNoOverlap``）——
    方法之间的差别是**重点检验的建模技术**，不是「遵守哪些约束」。
    """
    return _solve(instance, spec, method="fjsp_cpsat_setup", calendar_mode="blocker")


@register("fjsp_cpsat_calendar")
def fjsp_cpsat_calendar(instance: FJSPInstance, spec: dict[str, Any]) -> ShopResult:
    """FJSP CP-SAT：日历可用窗与计划维护窗用「按窗切分的可选区间」编码。

    每个 ``(工序, 机器, 可用窗)`` 一个 ``OptionalIntervalVar``，``AddExactlyOne``
    保证工序整体落在某一个窗里——维护窗因此不可能被跨越，也不需要事后修补。
    """
    return _solve(instance, spec, method="fjsp_cpsat_calendar", calendar_mode="split")


@register("fjsp_cpsat_multiobj")
def fjsp_cpsat_multiobj(instance: FJSPInstance, spec: dict[str, Any]) -> ShopResult:
    """FJSP CP-SAT：归一化加权和 ``α·Cmax + β·ΣT + γ·setup``。

    权重经 ``parse_weights(spec)`` 读入；``spec["normalization"]`` 选归一化口径
    （默认 ``trivial``）。求解器优化的是**归一化后**的目标，所以报告的
    ``objective``（原始单位的加权和）上**没有**可信下界，``best_bound`` 为 ``None``、
    ``status`` 不自称 ``OPTIMAL``——见 :func:`_bound_and_status`。
    """
    return _solve(instance, spec, method="fjsp_cpsat_multiobj", calendar_mode="blocker")
