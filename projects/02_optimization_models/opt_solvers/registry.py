"""方法注册表：让 benchmark 按名字调用四种来源的求解方法。

M2 的比较要跨 LP / MILP / CP-SAT / 启发式四类方法。如果 benchmark 直接
``import`` 每个周模块的函数，那么任何一周还没实现时整个批次就跑不起来。
这里用一张注册表把「方法名」和「可调用对象」解耦：

* 每个周模块在自己的文件里 ``@register("milp_tight")``；
* benchmark 只认识名字，通过 :func:`get` 取函数；
* 名字没注册时 :func:`describe_missing` 给出可读的失败原因，
  批次把它记成 ``FAILED`` 而不是崩溃——与 M1「失败留痕」的纪律一致。

**统一签名**：``solve_fn(instance, spec) -> SolveResult``，其中 ``spec`` 是
配置里该方法那一段（含 ``time_limit`` 等参数）。调度类方法必须在结果里带上
``schedule``；纯参数模型（LP）允许 ``schedule=None``。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from opt_common.bridge import Instance
from opt_solvers.result import SolveResult


class SolveFn(Protocol):
    """所有求解方法的统一签名。"""

    def __call__(self, instance: Instance, spec: dict[str, Any]) -> SolveResult: ...


_REGISTRY: dict[str, SolveFn] = {}
_DESCRIPTIONS: dict[str, str] = {}


def register(name: str, description: str = "") -> Callable[[SolveFn], SolveFn]:
    """把 ``name`` 绑定到一个求解函数。重复注册同一个名字会抛错。"""

    def decorator(fn: SolveFn) -> SolveFn:
        if name in _REGISTRY:
            raise ValueError(f"method already registered: {name}")
        _REGISTRY[name] = fn
        _DESCRIPTIONS[name] = description or (fn.__doc__ or "").strip().splitlines()[0]
        return fn

    return decorator


def get(name: str) -> SolveFn:
    if name not in _REGISTRY:
        raise KeyError(name)
    return _REGISTRY[name]


def has(name: str) -> bool:
    return name in _REGISTRY


def available() -> list[str]:
    return sorted(_REGISTRY)


def describe(name: str) -> str:
    return _DESCRIPTIONS.get(name, "")


def describe_missing(names: list[str]) -> list[str]:
    """返回配置里**尚未注册**的方法名，供批次提前报告。"""
    return [n for n in names if n not in _REGISTRY]


def load_week_modules() -> list[str]:
    """导入四个周模块，触发它们的 ``@register`` 副作用。

    缺失的模块不会让整批失败：返回没能导入的模块名列表，由调用方记录。
    这样「Week 3 还没写」不会阻塞 Week 2 的实验。
    """
    import importlib

    failed: list[str] = []
    for module in (
        "opt_models.lp_models",
        "opt_models.milp_scheduling",
        "opt_models.cpsat_models",
        "opt_models.strengthening",
    ):
        try:
            importlib.import_module(module)
        except ImportError as exc:  # 模块尚未实现
            failed.append(f"{module}: {exc}")
    return failed
