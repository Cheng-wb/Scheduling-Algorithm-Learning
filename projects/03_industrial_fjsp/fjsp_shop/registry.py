"""方法注册表：让 benchmark 按名字调用 Flow Shop / JSP / FJSP 各周的方法。

与 M2 的 ``opt_solvers/registry.py`` 同一套设计：周模块在自己的文件里
``@register("name")``，benchmark 只认识名字；名字缺失记 ``FAILED`` 而不中断整批，
这样「Week 3 还没写」不会阻塞 Week 1 的实验。

**统一签名**：``solve_fn(instance, spec) -> ShopResult``，``spec`` 含
``objective``（见 ``fjsp_shop/policy.py`` 的目标名）、``time_limit``、``seed``
以及方法特有参数（``weights`` 等）。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from fjsp_core.models import FJSPInstance
from fjsp_core.result import ShopResult


class SolveFn(Protocol):
    def __call__(self, instance: FJSPInstance, spec: dict[str, Any]) -> ShopResult: ...


_REGISTRY: dict[str, SolveFn] = {}
_DESCRIPTIONS: dict[str, str] = {}


def register(name: str, description: str = "") -> Callable[[SolveFn], SolveFn]:
    """把 ``name`` 绑定到一个求解函数；重复注册抛错（防止静默覆盖）。"""

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
    return [name for name in names if name not in _REGISTRY]


#: 四个周的模块。缺失不会让整批失败。
WEEK_MODULES = (
    "fjsp_shop.flowshop",
    "fjsp_shop.jsp",
    "fjsp_shop.fjsp",
    "fjsp_shop.cpsat_fjsp",
    "fjsp_shop.industrial",
    "fjsp_shop.constraints2",
)


def load_week_modules() -> list[str]:
    """导入周模块以触发 ``@register``；返回**未能导入**的模块说明列表。"""
    import importlib

    failed: list[str] = []
    for module in WEEK_MODULES:
        try:
            importlib.import_module(module)
        except ImportError as exc:
            failed.append(f"{module}: {exc}")
    return failed
