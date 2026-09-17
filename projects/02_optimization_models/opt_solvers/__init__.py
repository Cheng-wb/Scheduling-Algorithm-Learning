"""求解器包装层：统一结果接口、方法注册表与 M1 基线适配。"""

from opt_solvers import heuristics  # noqa: F401  (导入即注册 M1 基线方法)
from opt_solvers.registry import available, get, has, load_week_modules, register
from opt_solvers.result import (
    FEASIBLE_STATUSES,
    STATUSES,
    SolveResult,
    require_feasible,
    validate_result,
)

__all__ = [
    "STATUSES",
    "FEASIBLE_STATUSES",
    "SolveResult",
    "require_feasible",
    "validate_result",
    "register",
    "get",
    "has",
    "available",
    "load_week_modules",
]
