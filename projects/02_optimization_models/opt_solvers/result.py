"""统一求解结果接口：MILP / CP-SAT / 启发式说同一种话。

M2 的核心工程产出之一。三种方法的底层语义差别很大：

* LP / MILP 求解器返回 ``status`` + ``objective`` + ``best_bound``；
* CP-SAT 返回 ``OPTIMAL`` / ``FEASIBLE`` / ``UNKNOWN`` / ``INFEASIBLE`` /
  ``MODEL_INVALID``，并可能只给 ``objective`` 而不给可比的 bound；
* M1 的启发式（规则、局部搜索、SA）**没有任何 bound**。

如果让每种方法各自返回自己的字典，比较就会退化成「读日志」。所以这里定义
一个共同的 :class:`SolveResult`，并强制一条纪律：

    **没有 bound 就写 None，绝不填 0 或目标值冒充。**

把 ``best_bound`` 填成 ``objective`` 会让 gap 恒为 0，看起来「证明最优」，
这是求解器实验里最严重的伪证据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from opt_common.bridge import Instance, Schedule, validate_schedule

#: 求解状态词表。前五个对应 CP-SAT 的原生状态，后三个是工程包装。
STATUSES = (
    "OPTIMAL",  # 已证明最优：存在达到 best_bound 的可行解
    "FEASIBLE",  # 找到可行解，但未证明最优（时间限制 / 未搜完）
    "INFEASIBLE",  # 已证明无可行解
    "UNKNOWN",  # 求解器没能在给定预算内判定（既没找到解也没证明不可行）
    "MODEL_INVALID",  # 模型本身非法（变量界矛盾、表达式溢出等）
    "FEASIBLE_OR_UNKNOWN",  # CP-SAT 在「只找可行解」模式下的原生状态
    "FAILED",  # 包装层异常（求解抛错），失败原因放 detail
    "NOT_SOLVED",  # 求解器未被调用（例如建模阶段就报错）
)

#: 有可行解的三种状态。
FEASIBLE_STATUSES = ("OPTIMAL", "FEASIBLE", "FEASIBLE_OR_UNKNOWN")


@dataclass(frozen=True, slots=True)
class SolveResult:
    """一次求解的完整记录：状态、解、界、耗时、诊断细节。

    ``objective`` 与 ``best_bound`` 都可能是 ``None``：前者表示没找到可行解，
    后者表示该方法**不提供**可比的下界（启发式）或求解器没给出。
    """

    method: str
    status: str
    objective: float | None = None
    best_bound: float | None = None
    schedule: Schedule | None = None
    build_time: float = 0.0
    solve_time: float = 0.0
    iterations: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"unknown status: {self.status}")
        if self.objective is not None and self.best_bound is not None:
            # 下界永远不能超过已找到的可行解目标值（最小化问题）。
            # 允许 1e-6 的浮点容差，超过即说明包装层搞错了方向。
            if self.best_bound > self.objective + 1e-6:
                raise ValueError(
                    "best_bound > objective: 下界高于可行解，请检查目标方向"
                )

    @property
    def wall_time(self) -> float:
        """建模 + 求解的总耗时。比较方法时必须区分这两段。"""
        return self.build_time + self.solve_time

    @property
    def has_solution(self) -> bool:
        return self.objective is not None

    @property
    def gap(self) -> float | None:
        """相对 gap = (objective - best_bound) / max(1, |objective|)。

        任一端为 ``None`` 时返回 ``None``（**不是 0**）。已证明最优时返回 0.0。
        """
        if self.objective is None or self.best_bound is None:
            return None
        return (self.objective - self.best_bound) / max(1.0, abs(self.objective))

    @property
    def proven_optimal(self) -> bool:
        """只有状态为 OPTIMAL 才算「已证明最优」。"""
        return self.status == "OPTIMAL"

    def to_row(self) -> dict[str, Any]:
        """展开为 benchmark CSV 的一行。``None`` 保持为空，不写成 0。"""
        return {
            "method": self.method,
            "status": self.status,
            "objective": self.objective,
            "best_bound": self.best_bound,
            "gap": self.gap,
            "iterations": self.iterations,
            "build_time": round(self.build_time, 6),
            "solve_time": round(self.solve_time, 6),
            "wall_time": round(self.wall_time, 6),
        }


def validate_result(instance: Instance, result: SolveResult) -> list[str]:
    """用 M1 的**独立验证器**检查返回排程，不信任求解器自己的声明。

    返回诊断列表（空表示通过）。没有排程的结果（LP、纯参数模型）视为无约束可查。
    这是 M2 贯通验收的一部分：**求解器说 OPTIMAL 不等于解可行。**
    """
    if result.schedule is None:
        return []
    from opt_common.bridge import schedule_errors

    return list(schedule_errors(instance, result.schedule))


def require_feasible(instance: Instance, result: SolveResult) -> Schedule:
    """取出通过独立验证的排程，否则抛异常。用于测试与示例。"""
    if result.schedule is None:
        raise ValueError(f"{result.method}: 无排程可验证 (status={result.status})")
    validate_schedule(instance, result.schedule)
    return result.schedule
