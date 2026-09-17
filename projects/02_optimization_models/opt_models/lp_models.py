"""Week 1 的三类 LP 模型：生产计划、运输、指派，以及它们的对偶。

**为什么这一周不注册进 benchmark registry。** ``@register`` 的契约要求调度类
方法在 ``SolveResult`` 里带上 ``Schedule``；而 LP 解是一个**参数模型**的解——
它没有工序、没有机器、没有排程，只有一个数值目标与一组影子价格。硬塞进注册表
会逼着我们给 ``schedule`` 填 ``None``，再假装它和 MILP 落在同一张比较表里。
Week 1 的产出因此走独立入口 :func:`solve_model`，证据落在 ``artifacts/month2_w1/``；
Week 2 的单机 MILP 才回到注册表（那时解里真的有 ``Schedule``）。

模型层只做三件事：把问题写成 LP、把解读出来、把**解释解需要的元数据**一并交给
调用方（变量名、约束名、系数、方向、右端项）。计时、落盘、跨方法比较属于
``opt_experiments``，不在这一层。

三条建模纪律，贯穿本文件：

1. **所有上界都写成行，不写成变量上界。** 产量上限、需求上限、能力上限一律
   作为约束行出现。原因是对偶表（第 :func:`build_dual` 节）只对 ``x >= 0`` 的
   变量成立；把上界藏在变量里，对偶目标就会漏掉对应的项，强对偶表面上「不成立」。
2. **每个模型都带上结构化系数记录**（:class:`Row`）。读 ``dual_value()`` 只给出
   一个数，要解释它必须有「这条约束是什么、系数是多少」的原始数据。
3. **求解器没说 ``OPTIMAL`` 就不给对偶。** 影子价格来自**最优基**；不可行或
   未求解的模型上，``dual_value()`` 返回的 0 是噪声，把它当影子价格是伪证据。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Any

from ortools.linear_solver import pywraplp

#: pywraplp 的状态码 -> 本仓库统一状态词表（与 ``opt_solvers.result.STATUSES`` 对齐）。
STATUS_NAMES: dict[int, str] = {
    pywraplp.Solver.OPTIMAL: "OPTIMAL",
    pywraplp.Solver.FEASIBLE: "FEASIBLE",
    pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
    pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
    pywraplp.Solver.ABNORMAL: "ABNORMAL",
    pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
}

#: 有可行解、因而可以读 primal 值的状态。
SOLVED_STATUSES = ("OPTIMAL", "FEASIBLE")

#: **实测记录（不是理论结论）**：本环境的 ``pywraplp`` 9.15 + GLOP 后端对**无界**
#: LP 也返回状态码 2，即词表里的 ``INFEASIBLE``；``UNBOUNDED``（3）一次也没出现过。
#: 例子：``min -x, x >= 0``（无约束）返回 2，而它显然可行、只是没有最优解。
#: 因此状态 2 只应读作「**没有最优解**」，绝不能读作「可行域为空」。
#: 要区分「不可行」与「无界」必须另找证据（手算、加人工界、或换一个后端）。
#: 本文件把状态码如实翻译，并在报告里显式记录这条限制。
GLOP_STATUS_CAVEAT = (
    "GLOP returns status 2 for both infeasible and unbounded LPs; "
    "status 2 means 'no optimum', not 'empty feasible set'."
)

#: 默认数值容差。GLOP 的默认原始/对偶可行性容差是 1e-8 量级，取 1e-9 比求解器
#: 自己能保证的更严——所以它只用来做**事后对拍**，不用来放宽求解器行为。
DEFAULT_TOLERANCE = 1e-9


# ---------------------------------------------------------------------------
# 结构化记录
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Row:
    """一条约束的结构化记录：名字、系数、方向、右端项。

    ``terms`` 用元组而不是字典，是为了让遍历顺序确定（可复现输出的前提）。
    """

    name: str
    terms: tuple[tuple[str, float], ...]
    sense: str  # "<=" / ">=" / "="
    rhs: float

    def coefficients(self) -> dict[str, float]:
        return dict(self.terms)

    def activity(self, values: dict[str, float]) -> float:
        """按给定变量取值计算这条约束左端项的取值 ``a'x``。"""
        return sum(coef * values[name] for name, coef in self.terms)


@dataclass(frozen=True, slots=True, eq=False)
class LPModel:
    """一个 LP 的完整句柄：求解器对象 + 解释解所需的全部元数据。

    ``solver`` 的内部状态会随求解推进，但句柄的**绑定关系**（哪个名字对应哪个
    变量/约束、系数是多少、目标是什么方向）在构造完成时就固定了，所以句柄本身
    是 frozen 的。``eq=False`` 是因为句柄比较没有意义——要比较两个模型请比较
    它们的 ``rows`` 与 ``objective_coeffs``。
    """

    name: str
    sense: str  # "min" / "max"
    var_names: tuple[str, ...]
    objective_coeffs: tuple[float, ...]
    rows: tuple[Row, ...]
    solver: Any
    variables: dict[str, Any]
    constraints: dict[str, Any]
    objective: Any
    meta: dict[str, Any]

    @property
    def num_variables(self) -> int:
        return len(self.var_names)

    @property
    def num_rows(self) -> int:
        return len(self.rows)

    @property
    def constraint_names(self) -> tuple[str, ...]:
        return tuple(row.name for row in self.rows)

    def row(self, name: str) -> Row:
        for item in self.rows:
            if item.name == name:
                return item
        raise KeyError(name)

    def coefficient(self, row_name: str, var_name: str) -> float:
        """取 ``A[row][var]``。缺省为 0，与稀疏矩阵的语义一致。"""
        return self.row(row_name).coefficients().get(var_name, 0.0)


# ---------------------------------------------------------------------------
# 建模层：纯数据 -> LPModel
# ---------------------------------------------------------------------------


def _assemble(
    name: str,
    sense: str,
    var_names: tuple[str, ...],
    objective_coeffs: tuple[float, ...],
    rows: tuple[Row, ...],
    meta: dict[str, Any] | None = None,
    var_bounds: dict[str, tuple[float | None, float | None]] | None = None,
) -> LPModel:
    """把纯数据装配成 GLOP 模型并返回句柄。

    ``var_bounds`` 缺省为全部 ``[0, +inf)``；只有对偶模型才需要 ``y <= 0`` 或
    自由变量，那时按名字给出界。
    """
    solver = pywraplp.Solver.CreateSolver("GLOP")
    if solver is None:  # pragma: no cover - GLOP 随 ortools 一起发布
        raise RuntimeError("GLOP backend unavailable: check the ortools install")

    infinity = solver.infinity()
    variables: dict[str, Any] = {}
    for var_name in var_names:
        lower, upper = (var_bounds or {}).get(var_name, (0.0, None))
        # 自由变量是 ``(-inf, +inf)``。把 ``None`` 一律当成 ``+inf`` 会让自由变量
        # 变成 ``[+inf, +inf]``、``y <= 0`` 变成 ``[+inf, 0]``——模型直接 ABNORMAL。
        variables[var_name] = solver.NumVar(
            -infinity if lower is None else lower,
            infinity if upper is None else upper,
            var_name,
        )

    constraints: dict[str, Any] = {}
    for row in rows:
        if row.sense == "<=":
            lower, upper = -infinity, row.rhs
        elif row.sense == ">=":
            lower, upper = row.rhs, infinity
        elif row.sense == "=":
            lower, upper = row.rhs, row.rhs
        else:
            raise ValueError(f"unknown row sense: {row.sense!r}")
        constraint = solver.Constraint(lower, upper, row.name)
        for var_name, coefficient in row.terms:
            constraint.SetCoefficient(variables[var_name], coefficient)
        constraints[row.name] = constraint

    objective = solver.Objective()
    if sense == "max":
        objective.SetMaximization()
    elif sense == "min":
        objective.SetMinimization()
    else:
        raise ValueError(f"unknown objective sense: {sense!r}")
    for var_name, coefficient in zip(var_names, objective_coeffs):
        objective.SetCoefficient(variables[var_name], coefficient)

    return LPModel(
        name=name,
        sense=sense,
        var_names=var_names,
        objective_coeffs=objective_coeffs,
        rows=rows,
        solver=solver,
        variables=variables,
        constraints=constraints,
        objective=objective,
        meta=meta or {},
    )


# ---------------------------------------------------------------------------
# 生产计划 LP
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProductionData:
    """生产计划 LP 的全部参数。**集合先写、数值后写**，与笔记的建模步骤一致。

    ``max_demand`` 为空元组时**不生成**需求上限行（用于只看产能的手算小例子）；
    同理 ``min_delivery`` 为空时也不生成交付下限行。两个「空」都是显式语义，
    不是「填 0」——填 0 会生成一条 ``x_p >= 0`` 的冗余行，白白污染对偶表。
    """

    name: str
    products: tuple[str, ...]
    resources: tuple[str, ...]
    profit: tuple[float, ...]  # 对齐 products
    usage: tuple[tuple[float, ...], ...]  # usage[resource][product]
    capacity: tuple[float, ...]  # 对齐 resources
    max_demand: tuple[float, ...] = ()
    min_delivery: tuple[float, ...] = ()

    def with_capacity(self, resource: str, value: float) -> "ProductionData":
        return replace(
            self, capacity=_replace_at(self.capacity, self.resources.index(resource), value)
        )

    def with_profit(self, product: str, value: float) -> "ProductionData":
        return replace(
            self, profit=_replace_at(self.profit, self.products.index(product), value)
        )

    def with_max_demand(self, product: str, value: float) -> "ProductionData":
        if not self.max_demand:
            raise ValueError("this scenario has no demand rows to perturb")
        return replace(
            self, max_demand=_replace_at(self.max_demand, self.products.index(product), value)
        )

    def with_min_delivery(self, product: str, value: float) -> "ProductionData":
        if not self.min_delivery:
            raise ValueError("this scenario has no delivery rows to perturb")
        return replace(
            self,
            min_delivery=_replace_at(self.min_delivery, self.products.index(product), value),
        )


def _replace_at(values: tuple[float, ...], index: int, value: float) -> tuple[float, ...]:
    return values[:index] + (value,) + values[index + 1 :]


def build_production_lp(data: ProductionData) -> LPModel:
    """生产计划 LP：``max Σ profit_p x_p`` s.t. 产能 ``<=`` / 需求 ``<=`` / 交付 ``>=``。

    约束命名约定（对偶变量的名字由它派生，所以必须稳定）：

    ``cap_<资源>``      每单位产品消耗的资源乘产量，总和不超过产能
    ``demand_<产品>``   ``x_p <= max_demand_p``
    ``delivery_<产品>`` ``x_p >= min_delivery_p``
    """
    var_names = tuple(f"x_{product}" for product in data.products)
    rows: list[Row] = []
    for index, resource in enumerate(data.resources):
        terms = tuple(
            (var_names[j], float(data.usage[index][j]))
            for j in range(len(data.products))
            if float(data.usage[index][j]) != 0.0
        )
        rows.append(Row(f"cap_{resource}", terms, "<=", float(data.capacity[index])))
    if data.max_demand:
        for index, product in enumerate(data.products):
            rows.append(
                Row(f"demand_{product}", ((var_names[index], 1.0),), "<=", float(data.max_demand[index]))
            )
    if data.min_delivery:
        for index, product in enumerate(data.products):
            # 下限为 0 的交付行与变量下界 ``x_p >= 0`` 完全重复，跳过。
            # 需求上限不同：上限为 0 是「这个产品不许生产」，是一条真约束。
            if float(data.min_delivery[index]) == 0.0:
                continue
            rows.append(
                Row(
                    f"delivery_{product}",
                    ((var_names[index], 1.0),),
                    ">=",
                    float(data.min_delivery[index]),
                )
            )
    return _assemble(
        name=data.name,
        sense="max",
        var_names=var_names,
        objective_coeffs=tuple(float(value) for value in data.profit),
        rows=tuple(rows),
        meta={
            "kind": "production",
            "products": data.products,
            "resources": data.resources,
            "capacity": dict(zip(data.resources, data.capacity)),
        },
    )


# ---------------------------------------------------------------------------
# 运输 LP 与指派 LP
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TransportData:
    """运输 LP 的参数。要求**产销平衡**（``Σ supply == Σ demand``）。"""

    name: str
    sources: tuple[str, ...]
    destinations: tuple[str, ...]
    supply: tuple[float, ...]
    demand: tuple[float, ...]
    cost: tuple[tuple[float, ...], ...]  # cost[source][destination]


@dataclass(frozen=True, slots=True)
class AssignmentData:
    """指派 LP 的参数。要求**方阵**（``len(agents) == len(tasks)``）。"""

    name: str
    agents: tuple[str, ...]
    tasks: tuple[str, ...]
    cost: tuple[tuple[float, ...], ...]  # cost[agent][task]


def build_transportation_lp(data: TransportData) -> LPModel:
    """运输 LP：``min Σ c_ij x_ij`` s.t. 每源出清、每汇满足、``x >= 0``。

    产销不平衡不在这里「自动」加虚拟源/汇——那样会在调用方不知情的情况下改变
    模型规模。不平衡时直接报错，把虚拟节点这个建模决策留给使用者。
    """
    total_supply = sum(float(value) for value in data.supply)
    total_demand = sum(float(value) for value in data.demand)
    if abs(total_supply - total_demand) > DEFAULT_TOLERANCE:
        raise ValueError(
            f"transportation model must be balanced: supply={total_supply}, demand={total_demand}"
        )
    var_names = tuple(
        f"x_{source}_{destination}"
        for source in data.sources
        for destination in data.destinations
    )
    rows: list[Row] = []
    for i, source in enumerate(data.sources):
        terms = tuple(
            (f"x_{source}_{data.destinations[j]}", 1.0)
            for j in range(len(data.destinations))
        )
        rows.append(Row(f"supply_{source}", terms, "=", float(data.supply[i])))
    for j, destination in enumerate(data.destinations):
        terms = tuple(
            (f"x_{data.sources[i]}_{destination}", 1.0) for i in range(len(data.sources))
        )
        rows.append(Row(f"demand_{destination}", terms, "=", float(data.demand[j])))
    return _assemble(
        name=data.name,
        sense="min",
        var_names=var_names,
        objective_coeffs=tuple(
            float(data.cost[i][j])
            for i in range(len(data.sources))
            for j in range(len(data.destinations))
        ),
        rows=tuple(rows),
        meta={"kind": "transportation", "sources": data.sources, "destinations": data.destinations},
    )


def build_assignment_lp(data: AssignmentData) -> LPModel:
    """指派 LP：``min Σ c_ij x_ij`` s.t. 每人恰好一任务、每任务恰好一人、``x >= 0``。

    **这里刻意不给 ``x_ij`` 加 ``x_ij <= 1`` 的变量上界。** 行约束
    ``Σ_j x_ij = 1`` 配合 ``x >= 0`` 已经蕴含 ``x_ij <= 1``，加上去只会让对偶
    多出一组上界对应的项，把「对偶目标 = ``b'y``」这个干净的结论弄脏。
    """
    if len(data.agents) != len(data.tasks):
        raise ValueError(
            f"assignment model must be square: {len(data.agents)} agents vs {len(data.tasks)} tasks"
        )
    var_names = tuple(
        f"x_{agent}_{task}" for agent in data.agents for task in data.tasks
    )
    rows: list[Row] = []
    for agent in data.agents:
        terms = tuple((f"x_{agent}_{task}", 1.0) for task in data.tasks)
        rows.append(Row(f"agent_{agent}", terms, "=", 1.0))
    for task in data.tasks:
        terms = tuple((f"x_{agent}_{task}", 1.0) for agent in data.agents)
        rows.append(Row(f"task_{task}", terms, "=", 1.0))
    return _assemble(
        name=data.name,
        sense="min",
        var_names=var_names,
        objective_coeffs=tuple(
            float(data.cost[i][j])
            for i in range(len(data.agents))
            for j in range(len(data.tasks))
        ),
        rows=tuple(rows),
        meta={"kind": "assignment", "agents": data.agents, "tasks": data.tasks},
    )


# ---------------------------------------------------------------------------
# 本周的固定算例：笔记里的每一个数字都来自这里
# ---------------------------------------------------------------------------

#: 两变量生产计划（只有产能、没有需求行）。Day 1 用它枚举极点。
#: ``max 40 x_P1 + 30 x_P2`` s.t. ``2 x_P1 + x_P2 <= 100``、``x_P1 + 2 x_P2 <= 80``。
PRODUCTION_2D = ProductionData(
    name="prod_2d",
    products=("P1", "P2"),
    resources=("M", "L"),
    profit=(40.0, 30.0),
    usage=((2.0, 1.0), (1.0, 2.0)),
    capacity=(100.0, 80.0),
)

#: 三产品生产计划（Day 2 起的主算例）。比 ``PRODUCTION_2D`` 多一个产品 ``P3``
#: 与三条需求上限行：``P3`` 的单位资源利润最高，因此一进来就把最优基换掉。
PRODUCTION_BASE = ProductionData(
    name="prod_base",
    products=("P1", "P2", "P3"),
    resources=("M", "L"),
    profit=(40.0, 30.0, 25.0),
    usage=((2.0, 1.0, 1.0), (1.0, 2.0, 1.0)),
    capacity=(100.0, 80.0),
    max_demand=(40.0, 50.0, 80.0),
)

#: 故意不可行的生产计划：合同要求至少交付 60 件 ``P2``，而 60 件 ``P2``
#: 需要 60 单位 ``M`` 与 120 单位 ``L``，后者超过 ``L`` 的产能 80。
PRODUCTION_INFEASIBLE = replace(
    PRODUCTION_BASE,
    name="prod_infeasible",
    min_delivery=(0.0, 60.0, 0.0),
)

#: 运输算例：2 源 3 汇、产销平衡（``20 + 25 = 15 + 20 + 10 = 45``）。
TRANSPORT_BASE = TransportData(
    name="transport_base",
    sources=("S1", "S2"),
    destinations=("D1", "D2", "D3"),
    supply=(20.0, 25.0),
    demand=(15.0, 20.0, 10.0),
    cost=((4.0, 6.0, 8.0), (6.0, 4.0, 3.0)),
)

#: 指派算例：3 人 3 任务、最优指派唯一（``J1 -> W2, J2 -> W1, J3 -> W3``）。
ASSIGNMENT_BASE = AssignmentData(
    name="assign_base",
    agents=("J1", "J2", "J3"),
    tasks=("W1", "W2", "W3"),
    cost=((9.0, 2.0, 7.0), (6.0, 4.0, 3.0), (5.0, 8.0, 1.0)),
)


#: 产能扰动网格。两条都刻意跨过基准模型影子价格的**两个折点**，
#: 这样「区间内预测成立、区间外预测失效」才有数据可看。
CAPACITY_GRID_M = (60.0, 70.0, 80.0, 90.0, 100.0, 110.0, 120.0, 130.0, 140.0)
CAPACITY_GRID_L = (
    40.0,
    50.0,
    60.0,
    70.0,
    80.0,
    90.0,
    100.0,
    110.0,
    120.0,
    130.0,
    140.0,
    150.0,
)


def production_capacity_grid(resource: str) -> list[ProductionData]:
    """沿某一资源产能扫一格：用于验证影子价格的**局部**有效范围（Day 5）。"""
    values = CAPACITY_GRID_M if resource == "M" else CAPACITY_GRID_L
    return [PRODUCTION_BASE.with_capacity(resource, value) for value in values]


def production_profit_grid(product: str) -> list[ProductionData]:
    """沿某一产品单位利润扫一格：用于找 reduced cost 对应的**盈亏平衡价**。"""
    return [
        PRODUCTION_BASE.with_profit(product, float(value))
        for value in (25, 30, 35, 40, 45)
    ]


def production_demand_grid(product: str) -> list[ProductionData]:
    """沿某一产品需求上限扫一格：用于观察需求行从松到紧的切换。"""
    return [
        PRODUCTION_BASE.with_max_demand(product, float(value))
        for value in (10, 15, 20, 25, 30, 40)
    ]


# ---------------------------------------------------------------------------
# 对偶：按标准对偶表构造，供强/弱对偶对拍
# ---------------------------------------------------------------------------


def build_dual(model: LPModel) -> LPModel:
    """按标准对偶表构造 ``model`` 的**显式**对偶 LP。

    命名约定：对偶变量 ``y_<原约束名>``，对偶约束 ``d_<原变量名>``。这样
    「谁是谁的对偶」不靠位置索引，靠名字就能对上，笔记里的对照表因此可以直接
    由代码生成。

    对偶表（原始为 ``min`` 时；``max`` 时左右对调）：

    ``原始 <= 行`` -> ``y <= 0``，``原始 >= 行`` -> ``y >= 0``，``原始 = 行`` -> ``y`` 自由；
    ``x_j >= 0``  -> 对偶第 ``j`` 条约束为 ``<= c_j``，
    ``x_j <= 0``  -> 为 ``>= c_j``，``x_j`` 自由 -> 为 ``= c_j``。

    唯一**不支持**的形式是变量带有限上界（或有限的非零下界）。那种情况下
    上界本身就是一条额外的约束行，套用这张表会漏掉它对应的对偶项，算出来的
    「对偶目标」比强对偶要求的少一截。这里用 ``ValueError`` 挡住，而不是悄悄
    给出一个缺项的对偶。所以本文件三个 builder 都把上界写成**行**。
    """
    primal_is_max = model.sense == "max"
    dual_sense = "min" if primal_is_max else "max"
    infinity = model.solver.infinity()

    dual_variable_names = tuple(f"y_{row.name}" for row in model.rows)
    dual_bounds: dict[str, tuple[float | None, float | None]] = {}
    for row in model.rows:
        if row.sense == "=":
            dual_bounds[f"y_{row.name}"] = (None, None)
        elif (row.sense == "<=") == primal_is_max:
            dual_bounds[f"y_{row.name}"] = (0.0, None)
        else:
            dual_bounds[f"y_{row.name}"] = (None, 0.0)

    inequality_sense = ">=" if dual_sense == "min" else "<="
    reversed_sense = "<=" if dual_sense == "min" else ">="
    coefficients = {row.name: row.coefficients() for row in model.rows}
    dual_rows: list[Row] = []
    for index, var_name in enumerate(model.var_names):
        variable = model.variables[var_name]
        lower, upper = variable.lb(), variable.ub()
        if lower == 0.0 and upper == infinity:
            row_sense = inequality_sense  # x_j >= 0
        elif lower == -infinity and upper == infinity:
            row_sense = "="  # x_j 自由 -> 对偶约束取等号
        elif lower == -infinity and upper == 0.0:
            row_sense = reversed_sense  # x_j <= 0
        else:
            raise ValueError(
                f"build_dual cannot handle bounded variables: {var_name} has "
                f"bounds [{lower}, {upper}]; write the bound as an explicit row instead"
            )
        terms = tuple(
            (f"y_{row.name}", coefficients[row.name][var_name])
            for row in model.rows
            if coefficients[row.name].get(var_name, 0.0) != 0.0
        )
        dual_rows.append(
            Row(
                name=f"d_{var_name}",
                terms=terms,
                sense=row_sense,
                rhs=float(model.objective_coeffs[index]),
            )
        )

    return _assemble(
        name=f"dual_of_{model.name}",
        sense=dual_sense,
        var_names=dual_variable_names,
        objective_coeffs=tuple(float(row.rhs) for row in model.rows),
        rows=tuple(dual_rows),
        meta={"kind": "dual", "derived_from": model.name},
        var_bounds=dual_bounds,
    )


# ---------------------------------------------------------------------------
# 求解与解释
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LPSolution:
    """一次 LP 求解的完整记录：状态、原解、对偶解、残差。

    ``objective`` 只在 :data:`SOLVED_STATUSES` 下才非空。不可行时 ``pywraplp``
    的 ``Objective().Value()`` 会返回 ``0.0``——把它当目标值写进结果表，
    就是把「没有解」伪装成「解为 0」。
    """

    model: str
    sense: str
    status: str
    objective: float | None
    primal: dict[str, float]
    reduced_cost: dict[str, float]
    dual: dict[str, float]
    activity: dict[str, float]
    slack: dict[str, float]
    dual_available: bool
    max_constraint_residual: float | None
    solve_time: float

    @property
    def has_solution(self) -> bool:
        return self.objective is not None


def solve_model(model: LPModel) -> LPSolution:
    """求解 ``model`` 并一次性抽出 primal / slack / reduced cost / shadow price。

    读数的三个来源：

    * ``variable.solution_value()`` -> primal ``x_j``
    * ``variable.reduced_cost()``   -> ``c_j - a_j'y``（原始的对偶松弛）
    * ``constraint.dual_value()``   -> 影子价格 ``y_i``

    ``activity`` 由本模块**自己**按系数重算，不依赖求解器的 ``Constraint``
    接口（``pywraplp`` 的 ``Constraint`` 也没有 ``activity()``）。这样约束是否
    被满足就是一次独立复算，而不是把求解器的话再抄一遍。
    """
    started = time.perf_counter()
    status = STATUS_NAMES.get(model.solver.Solve(), "UNKNOWN")
    solve_time = time.perf_counter() - started

    if status not in SOLVED_STATUSES:
        return LPSolution(
            model=model.name,
            sense=model.sense,
            status=status,
            objective=None,
            primal={},
            reduced_cost={},
            dual={},
            activity={},
            slack={},
            dual_available=False,
            max_constraint_residual=None,
            solve_time=solve_time,
        )

    primal = {name: model.variables[name].solution_value() for name in model.var_names}
    activity = {row.name: row.activity(primal) for row in model.rows}
    residual = max(
        (_row_violation(row, activity[row.name]) for row in model.rows), default=0.0
    )
    dual_available = status == "OPTIMAL"
    if dual_available:
        reduced_cost = {
            name: model.variables[name].reduced_cost() for name in model.var_names
        }
        dual = {row.name: model.constraints[row.name].dual_value() for row in model.rows}
        slack = {row.name: row_slack(row, activity[row.name]) for row in model.rows}
    else:
        reduced_cost, dual, slack = {}, {}, {}

    return LPSolution(
        model=model.name,
        sense=model.sense,
        status=status,
        objective=float(model.objective.Value()),
        primal=primal,
        reduced_cost=reduced_cost,
        dual=dual,
        activity=activity,
        slack=slack,
        dual_available=dual_available,
        max_constraint_residual=residual,
        solve_time=solve_time,
    )


def row_slack(row: Row, activity: float) -> float:
    """行的松弛量：``<=`` 行取 ``b - a'x``，``>=`` 行取 ``a'x - b``，等式行恒为 0。

    等式行的松弛恒为 0，所以等式行上的互补松弛 ``slack * y = 0`` **自动成立**、
    不提供任何信息。真正携带信息的是不等式行上的 ``slack_i * y_i``。
    """
    if row.sense == "<=":
        return float(row.rhs - activity)
    if row.sense == ">=":
        return float(activity - row.rhs)
    return 0.0


def _row_violation(row: Row, activity: float) -> float:
    """行的可行性违反量：可行时为 0，不可行时为正。"""
    if row.sense == "<=":
        return max(0.0, float(activity - row.rhs))
    if row.sense == ">=":
        return max(0.0, float(row.rhs - activity))
    return abs(float(activity - row.rhs))


def max_primal_nonnegativity_violation(solution: LPSolution) -> float:
    """变量下界的违反量：本文件所有原始变量都是 ``x >= 0``。"""
    return max((max(0.0, -value) for value in solution.primal.values()), default=0.0)


# ---------------------------------------------------------------------------
# 对拍：互补松弛、对偶可行、reduced cost 的符号约定
# ---------------------------------------------------------------------------


def complementarity_rows(model: LPModel, solution: LPSolution) -> list[dict[str, Any]]:
    """逐对列出互补松弛的乘积。

    * 变量对：``|x_j| * |rc_j|``，理论要求为 0（``x_j`` 与它的 reduced cost 至少一个为 0）；
    * 不等式行的对：``|slack_i| * |y_i|``，理论要求为 0（约束松则影子价格为 0）。

    等式行的对不列出——它的 slack 恒为 0，乘积恒为 0，列出来只是凑数。
    """
    if not solution.dual_available:
        return []
    items: list[dict[str, Any]] = []
    for var_name in model.var_names:
        primal = solution.primal[var_name]
        reduced = solution.reduced_cost[var_name]
        items.append(
            {
                "kind": "variable",
                "name": var_name,
                "primal": primal,
                "dual": reduced,
                "product": abs(primal * reduced),
            }
        )
    for row in model.rows:
        if row.sense == "=":
            continue
        slack = solution.slack[row.name]
        dual = solution.dual[row.name]
        items.append(
            {
                "kind": "inequality_row",
                "name": row.name,
                "primal": slack,
                "dual": dual,
                "product": abs(slack * dual),
            }
        )
    return items


def max_complementarity_violation(model: LPModel, solution: LPSolution) -> float | None:
    """互补松弛的最大违反量（全部 ``|x*rc|`` 与 ``|slack*y|`` 的最大值）。

    没有对偶解时返回 ``None`` 而不是 0——**没有检查过不等于检查通过**。
    """
    if not solution.dual_available:
        return None
    items = complementarity_rows(model, solution)
    return max((item["product"] for item in items), default=0.0)


def max_reduced_cost_identity_error(model: LPModel, solution: LPSolution) -> float | None:
    """对拍 ``reduced_cost`` 的符号约定：``rc_j`` 是否等于 ``c_j - Σ_i a_ij y_i``。

    这是一个**非平凡**的检查：``rc_j`` 与 ``y_i`` 都来自求解器，但符号约定是
    ``pywraplp`` 的实现细节。把两边的数值关系独立算一遍，才能确认自己读懂的
    是「对偶松弛」而不是它的相反数。没有对偶解时返回 ``None``。
    """
    if not solution.dual_available:
        return None
    worst = 0.0
    for index, var_name in enumerate(model.var_names):
        dual_sum = sum(
            model.coefficient(row.name, var_name) * solution.dual[row.name]
            for row in model.rows
        )
        expected = float(model.objective_coeffs[index]) - dual_sum
        worst = max(worst, abs(expected - solution.reduced_cost[var_name]))
    return worst


def dual_feasibility_violation(model: LPModel, solution: LPSolution) -> float | None:
    """对偶解的可行性违反量，同时覆盖**符号条件**与**对偶约束**。

    对偶可行的含义（原始为 ``max`` 时；``min`` 时不等号方向全部反过来）：

    * 每条 ``<=`` 行的影子价格 ``y_i >= 0``，每条 ``>=`` 行的 ``y_i <= 0``；
    * 每个变量满足 ``Σ_i a_ij y_i >= c_j``，等价于 ``rc_j <= 0``。

    ``min`` 情形下两处都取反。返回的是超出容差的最大违反量（可行时为 0 附近
    的浮点尘埃）；没有对偶解时返回 ``None``。
    """
    if not solution.dual_available:
        return None
    primal_is_max = model.sense == "max"
    worst = 0.0
    for row in model.rows:
        dual = solution.dual[row.name]
        if row.sense == "=":
            continue
        wants_nonnegative = (row.sense == "<=") == primal_is_max
        worst = max(worst, -dual if wants_nonnegative else dual)
    for var_name in model.var_names:
        reduced = solution.reduced_cost[var_name]
        worst = max(worst, reduced if primal_is_max else -reduced)
    return max(0.0, worst)


def duality_gap(primal_objective: float | None, dual_objective: float | None) -> float | None:
    """``|原始目标 - 对偶目标|``。任一端为空时返回 ``None``（不是 0）。"""
    if primal_objective is None or dual_objective is None:
        return None
    return abs(float(primal_objective) - float(dual_objective))


# ---------------------------------------------------------------------------
# 两变量 LP 的极点枚举（Day 1 的可行域演示）
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Vertex:
    """两变量 LP 的一个极点：坐标、取值、使它成为极点的紧约束。"""

    point: tuple[Fraction, Fraction]
    objective: Fraction
    tight_rows: tuple[str, ...]


def enumerate_vertices_2d(model: LPModel) -> list[Vertex]:
    """枚举只有两个变量的 LP 的全部极点（基本可行解）。

    做法：把非负约束 ``x_j >= 0`` 也当成两条直线加进来，任取两条直线解 2x2
    线性方程组，解出的交点若满足**全部**约束就是一个极点。两变量时这正是
    「基本可行解」的定义。

    用 ``Fraction(str(x))`` 读系数：``Fraction(0.1)`` 会得到二进制展开的巨型
    分数，``Fraction("0.1")`` 得到 ``1/10``——读十进制字面量才符合建模者的意图。
    精确有理数运算让「极点是否精确在交点上」不依赖浮点容差。
    """
    if model.num_variables != 2:
        raise ValueError(
            f"vertex enumeration is only defined for 2-variable LPs, got {model.num_variables}"
        )
    first, second = model.var_names
    lines: list[tuple[str, dict[str, Fraction], str, Fraction]] = [
        (f"nonneg_{name}", {name: Fraction(1)}, ">=", Fraction(0)) for name in model.var_names
    ]
    for row in model.rows:
        lines.append(
            (
                row.name,
                {name: Fraction(str(coef)) for name, coef in row.terms},
                row.sense,
                Fraction(str(row.rhs)),
            )
        )

    points: dict[tuple[Fraction, Fraction], Vertex] = {}
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            point = _solve_two_lines(lines[i], lines[j], first, second)
            if point is None or point in points:
                continue
            if not _satisfies_all(point, lines, first, second):
                continue
            values = {first: point[0], second: point[1]}
            objective = Fraction(str(model.objective_coeffs[0])) * point[0] + Fraction(
                str(model.objective_coeffs[1])
            ) * point[1]
            tight = tuple(
                row.name
                for row in model.rows
                if Fraction(str(row.rhs))
                == sum(Fraction(str(coef)) * values[name] for name, coef in row.terms)
            )
            points[point] = Vertex(point=point, objective=objective, tight_rows=tight)
    return sorted(points.values(), key=lambda item: (item.point[0], item.point[1]))


def _solve_two_lines(line_a, line_b, first: str, second: str):
    """两条直线的交点；平行时返回 ``None``。"""
    _, coefficients_a, _, rhs_a = line_a
    _, coefficients_b, _, rhs_b = line_b
    a1 = coefficients_a.get(first, Fraction(0))
    b1 = coefficients_a.get(second, Fraction(0))
    a2 = coefficients_b.get(first, Fraction(0))
    b2 = coefficients_b.get(second, Fraction(0))
    determinant = a1 * b2 - a2 * b1
    if determinant == 0:
        return None
    return ((rhs_a * b2 - rhs_b * b1) / determinant, (a1 * rhs_b - a2 * rhs_a) / determinant)


def _satisfies_all(point, lines, first: str, second: str) -> bool:
    values = {first: point[0], second: point[1]}
    for _, coefficients, sense, rhs in lines:
        activity = sum(coef * values[name] for name, coef in coefficients.items())
        if sense == "<=" and activity > rhs:
            return False
        if sense == ">=" and activity < rhs:
            return False
        if sense == "=" and activity != rhs:
            return False
    return True
