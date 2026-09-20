"""统一求解结果：Flow Shop 启发式 / JSP CP-SAT / FJSP 各类方法说同一种话。

沿用 M2 确立的三条纪律（它们不是可选项，是让比较成立的前提）：

1. **没有 bound 就写 ``None``。** 启发式没有下界。把 ``best_bound`` 填成目标值
   会让 ``gap`` 恒为 0，看起来「已证明最优」——这是最严重的伪证据。
2. **``build_time`` 与 ``solve_time`` 分开记。** 建模慢与求解慢是两种问题。
3. **``OPTIMAL`` 不等于解可行。** 返回的排程必须过 ``validate_schedule``。

M3 额外增加一个字段：``breakdown``。Week 3 把目标扩展成
``α·Cmax + β·ΣT + γ·setup``，只报一个加权和会让**三个分量的取舍**完全不可见，
所以每次求解都把分量原值一并留下。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fjsp_core.models import Schedule
from fjsp_core.schedule_validation import schedule_errors

#: 与 M2 保持一致的状态词表，便于跨月比较。
STATUSES = (
    "OPTIMAL",
    "FEASIBLE",
    "INFEASIBLE",
    "UNKNOWN",
    "MODEL_INVALID",
    "FEASIBLE_OR_UNKNOWN",
    "FAILED",
    "NOT_SOLVED",
)

FEASIBLE_STATUSES = ("OPTIMAL", "FEASIBLE", "FEASIBLE_OR_UNKNOWN")


@dataclass(frozen=True, slots=True)
class ShopResult:
    """一次求解的完整记录。"""

    method: str
    status: str
    schedule: Schedule | None = None
    objective: float | None = None
    best_bound: float | None = None
    build_time: float = 0.0
    solve_time: float = 0.0
    iterations: int | None = None
    breakdown: dict[str, float] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"unknown status: {self.status}")
        if self.objective is not None and self.best_bound is not None:
            if self.best_bound > self.objective + 1e-6:
                raise ValueError("best_bound > objective: 下界高于可行解，检查目标方向")

    @property
    def wall_time(self) -> float:
        return self.build_time + self.solve_time

    @property
    def has_solution(self) -> bool:
        return self.objective is not None

    @property
    def gap(self) -> float | None:
        """相对 gap = (objective − best_bound) / max(1, |objective|)。

        任一端为 ``None`` 就返回 ``None``（**不是 0**）；已证明最优时是 0.0。
        """
        if self.objective is None or self.best_bound is None:
            return None
        return (self.objective - self.best_bound) / max(1.0, abs(self.objective))

    @property
    def proven_optimal(self) -> bool:
        return self.status == "OPTIMAL"

    def to_row(self) -> dict[str, Any]:
        row: dict[str, Any] = {
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
        for key in ("cmax", "total_tardiness", "setup"):
            row[key] = self.breakdown.get(key)
        return row


def validate_result(instance, result: ShopResult) -> list[str]:
    """用**独立验证器**检查返回排程；不信任求解器自己的声明。"""
    if result.schedule is None:
        return []
    return list(schedule_errors(instance, result.schedule))
