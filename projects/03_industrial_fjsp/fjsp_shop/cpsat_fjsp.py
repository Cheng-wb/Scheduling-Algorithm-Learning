"""Week 2 Day 4：CP-SAT 的 FJSP 模型（可选区间 + ``ExactlyOne`` + ``NoOverlap``）。

模型只有四组约束，但恰恰是 FJSP 的全部：

```text
1. 每道工序一个 [start, end)  —— 共享的 start / end 变量，逐机器一个可选区间
2. ExactlyOne(该工序的可选区间) —— 「一次只在一台机器上做」
3. NoOverlap(每台机器的区间)    —— 「一台机器一次只做一件事」
4. end(前道) <= start(后道)     —— 「订单内的工艺路线」
+  minimize makespan            —— 目标
```

**为什么 CP-SAT 比 MILP 少写一半代码。** 互斥在 CP-SAT 里是 ``AddNoOverlap`` 一条约束，
不需要序对二元变量、不需要 ``Big-M``、不需要为「两台机器上的先后各自成立」而牺牲松弛
强度（M2 Week 2 的 sequence 模型正是栽在这里：root LP bound 恒为 0）。可选区间的
``presence`` 文字变量同时承担「选哪台机器」和「这个区间是否存在」两个角色。

**``OPTIMAL`` 的含义必须说清。** 求解器证明的是**它自己的模型**最优——前提是本方法
覆盖了实例的全部约束。因此 :func:`fjsp_cpsat` 在遇到换型、日历、维护、资源、资质或锁定
工序时直接拒绝（与启发式同一道 :func:`fjsp_shop.fjsp.require_plain_fjsp` 闸门），
绝不用一个「忽略了部分约束的模型的最优解」冒充问题的最优解。

**目标目前只支持 makespan。** 其它目标名（``total_tardiness`` / ``weighted_sum`` …）会
被拒绝：本模型的最小化对象就是 makespan，拿它去报别的目标名是偷换指标。
"""

from __future__ import annotations

import time
from typing import Any

from ortools.sat.python import cp_model

from fjsp_core.models import FJSPInstance, Schedule, ScheduledOperation
from fjsp_core.objective import evaluate, objective_breakdown
from fjsp_core.result import ShopResult
from fjsp_core.schedule_validation import validate_schedule
from fjsp_core.validation import validate_instance
from fjsp_shop.fjsp import require_plain_fjsp
from fjsp_shop.registry import register

#: 本模型的最小化对象。
SUPPORTED_OBJECTIVES = ("makespan",)

#: 搜索线程数固定为 1：多线程下 CP-SAT 的结果与线程调度有关，无法复现。
#: 代价是同样预算内的解质量略低——Day 6 的比较会把这一点算进「耗时」列。
NUM_SEARCH_WORKERS = 1


class ShortHorizonError(ValueError):
    """时间上界算不出来（例如空实例）。"""


def time_horizon(instance: FJSPInstance) -> int:
    """``H = max(释放时间) + Σ_o max_m p_om``。

    这是一个**朴素上界**：把所有工序串起来、每道都挑它最慢的那台机器，总时间也不会
    超过它。用它做 ``start`` / ``end`` 变量的定义域，保证任何可行排程都在域内。
    """
    if not instance.operations:
        raise ShortHorizonError("instance has no operations")
    release = max(job.release_time for job in instance.jobs)
    slowest = sum(max(minutes for _, minutes in op.machine_times) for op in instance.operations)
    return release + slowest


class _FjspModel:
    """建模产物：``CpModel`` + 反查用的字典。**只建模，不求解。**"""

    def __init__(self, instance: FJSPInstance, horizon: int) -> None:
        self.instance = instance
        self.horizon = horizon
        self.model = cp_model.CpModel()
        self.starts: dict[str, cp_model.IntVar] = {}
        self.ends: dict[str, cp_model.IntVar] = {}
        self.presence: dict[tuple[str, str], cp_model.IntVar] = {}
        self.intervals: dict[tuple[str, str], cp_model.IntervalVar] = {}
        self.build()

    def build(self) -> None:
        instance, model = self.instance, self.model
        for op in instance.operations:
            job = instance.job(op.job_id)
            start = model.NewIntVar(job.release_time, self.horizon, f"start_{op.id}")
            end = model.NewIntVar(job.release_time, self.horizon, f"end_{op.id}")
            self.starts[op.id] = start
            self.ends[op.id] = end

        # --- 2. ExactlyOne：一次只在一台合格机器上做 -----------------------
        for op in instance.operations:
            literals = []
            for machine_id, minutes in op.machine_times:
                literal = model.NewBoolVar(f"x_{op.id}_{machine_id}")
                self.presence[(op.id, machine_id)] = literal
                self.intervals[(op.id, machine_id)] = model.NewOptionalIntervalVar(
                    self.starts[op.id],
                    minutes,
                    self.ends[op.id],
                    literal,
                    f"iv_{op.id}_{machine_id}",
                )
                literals.append(literal)
            model.AddExactlyOne(literals)

        # --- 3. NoOverlap：一台机器一次只做一件事 --------------------------
        for machine in instance.machines:
            intervals = [
                self.intervals[(op.id, machine.id)]
                for op in instance.operations
                if (op.id, machine.id) in self.intervals
            ]
            if intervals:
                model.AddNoOverlap(intervals)

        # --- 4. precedence：订单内的工艺路线 ------------------------------
        for job in instance.jobs:
            for before, after in zip(job.operation_ids, job.operation_ids[1:]):
                model.Add(self.ends[before] <= self.starts[after])

        # --- 目标：makespan ------------------------------------------------
        self.makespan = model.NewIntVar(0, self.horizon, "makespan")
        model.AddMaxEquality(
            self.makespan, [self.ends[op.id] for op in instance.operations]
        )
        model.Minimize(self.makespan)

    def stats(self) -> dict[str, int]:
        """规模读数：变量 / 约束 / 可选区间。用于 Day 4 的规模表。"""
        return {
            "variables": len(self.model.Proto().variables),
            "constraints": len(self.model.Proto().constraints),
            "optional_intervals": len(self.intervals),
            "operations": len(self.instance.operations),
            "horizon": self.horizon,
        }

    def extract(self, solver: cp_model.CpSolver) -> Schedule:
        """从求解器读数重建 ``Schedule``；``presence`` 决定每道工序落在哪台机器。"""
        placed: list[ScheduledOperation] = []
        for op in self.instance.operations:
            chosen = [
                machine_id
                for machine_id, _ in op.machine_times
                if solver.Value(self.presence[(op.id, machine_id)]) == 1
            ]
            if len(chosen) != 1:  # pragma: no cover - ExactlyOne 保证恰好一台
                raise ValueError(f"operation {op.id!r} has {len(chosen)} chosen machines")
            placed.append(
                ScheduledOperation(
                    op.id,
                    chosen[0],
                    solver.Value(self.starts[op.id]),
                    solver.Value(self.ends[op.id]),
                )
            )
        return Schedule(tuple(sorted(placed, key=_placement_key)))


def _placement_key(item: ScheduledOperation) -> tuple[int, str, str]:
    return (item.start_time, item.machine_id, item.operation_id)


def build_model(instance: FJSPInstance, spec: dict[str, Any] | None = None) -> _FjspModel:
    """只建模不求解，供规模统计与测试使用。"""
    validate_instance(instance)
    require_plain_fjsp(instance)
    objective_name = str((spec or {}).get("objective", "makespan"))
    if objective_name not in SUPPORTED_OBJECTIVES:
        raise ValueError(
            f"fjsp_cpsat optimizes {SUPPORTED_OBJECTIVES}, got {objective_name!r}; "
            "use a dedicated method for other objectives"
        )
    return _FjspModel(instance, time_horizon(instance))


def _no_solution(method: str, status: str, reason: str, **extra: Any) -> ShopResult:
    return ShopResult(
        method=method,
        status=status,
        schedule=None,
        objective=None,
        best_bound=None,
        build_time=float(extra.pop("build_time", 0.0)),
        solve_time=float(extra.pop("solve_time", 0.0)),
        detail={"failure_reason": reason, "objective_name": "makespan", **extra},
    )


@register("fjsp_cpsat", "CP-SAT FJSP：可选区间 + ExactlyOne + NoOverlap，目标 makespan")
def fjsp_cpsat(instance: FJSPInstance, spec: dict[str, Any]) -> ShopResult:
    """CP-SAT 的 FJSP 精确模型。

    ``spec`` 读 ``objective``（只支持 ``makespan``）、``time_limit``、``seed``。
    ``best_bound`` 填求解器给出的 ``BestObjectiveBound``：解到 ``OPTIMAL`` 时它等于
    目标值，未证明时它是**搜索进度**（M2 Week 2 的口径：限时结束后的界是进度值）。
    """
    validate_instance(instance)
    require_plain_fjsp(instance)
    objective_name = str(spec.get("objective", "makespan"))
    if objective_name not in SUPPORTED_OBJECTIVES:
        raise ValueError(
            f"fjsp_cpsat optimizes {SUPPORTED_OBJECTIVES}, got {objective_name!r}; "
            "use a dedicated method for other objectives"
        )
    time_limit = float(spec.get("time_limit", 10.0))
    seed = int(spec.get("seed", 0))

    build_start = time.perf_counter()
    built = _FjspModel(instance, time_horizon(instance))
    build_time = time.perf_counter() - build_start

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = NUM_SEARCH_WORKERS
    solver.parameters.random_seed = seed
    solve_start = time.perf_counter()
    status = solver.Solve(built.model)
    solve_time = time.perf_counter() - solve_start
    stats = built.stats()
    common = {
        "build_time": build_time,
        "solve_time": solve_time,
        "horizon": built.horizon,
        "num_search_workers": NUM_SEARCH_WORKERS,
        "random_seed": seed,
        "objective_name": objective_name,
        "model_stats": stats,
    }

    if status == cp_model.INFEASIBLE:
        return _no_solution("fjsp_cpsat", "INFEASIBLE", "model is infeasible", **common)
    if status == cp_model.MODEL_INVALID:
        return _no_solution("fjsp_cpsat", "MODEL_INVALID", "solver rejected the model", **common)
    if status == cp_model.UNKNOWN:
        return _no_solution(
            "fjsp_cpsat", "UNKNOWN", "no solution within the time limit", **common
        )

    schedule = built.extract(solver)
    # 独立重算：目标值不来自求解器读数（M2 的纪律）
    recomputed = float(evaluate(instance, schedule, objective_name))
    validate_schedule(instance, schedule)

    bound = float(solver.BestObjectiveBound())
    clamp_note = None
    if bound > recomputed + 1e-6:
        # 下界高于一个已验证的可行解：数学上不可能，说明模型或解码有错
        return _no_solution(
            "fjsp_cpsat",
            "FAILED",
            f"best_bound {bound} > verified objective {recomputed}",
            **common,
        )
    if bound > recomputed:
        bound = recomputed
        clamp_note = True

    detail = {
        **common,
        "cp_status": solver.StatusName(status),
        "iterations_kind": "cp_sat_branches",
        "branches": solver.NumBranches(),
        "conflicts": solver.NumConflicts(),
        "wall_time": solver.WallTime(),
        "solver_objective": float(solver.ObjectiveValue()),
        "solver_objective_delta": round(float(solver.ObjectiveValue()) - recomputed, 9),
        "bound_kind": "proven" if status == cp_model.OPTIMAL else "search_progress",
    }
    if clamp_note:
        detail["bound_clamped"] = True

    return ShopResult(
        method="fjsp_cpsat",
        status="OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
        schedule=schedule,
        objective=recomputed,
        best_bound=bound,
        build_time=build_time,
        solve_time=solve_time,
        iterations=int(solver.NumBranches()),
        breakdown=objective_breakdown(instance, schedule),
        detail=detail,
    )


def lower_bound(instance: FJSPInstance) -> int:
    """FJSP 的朴素下界：``max(max_o min_m p_om, ceil(Σ_o min_m p_om / |M|))``。

    与 M1 Day 5 的 ``P||Cmax`` 下界同一形状，只是每道工序取「它最快的机器」：
    任何排程至少要等最慢的那道工序做完，也至少要摊完总的最小工作量。
    **下界不是最优值**——``makespan == LB`` 能证明最优，``makespan > LB`` 什么也说不了。
    """
    if not instance.operations:
        return 0
    fastest = [op.min_time for op in instance.operations]
    return max(max(fastest), -(-sum(fastest) // len(instance.machines)))
