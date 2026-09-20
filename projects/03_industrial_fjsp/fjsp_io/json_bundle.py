"""单文件归档：把**实例 + 求解结果 + KPI** 装进一个 JSON bundle，读回来逐个字段相等。

    from fjsp_io.json_bundle import save_bundle, load_bundle
    save_bundle(path, instance, result)
    bundle = load_bundle(path)

**为什么要有这个文件。** M1/M2 的做法是「实例单独存、结果单独存、靠 run_id 关联」。
关联靠约定，约定会被打破：只要有一边被覆盖，结果就指向一个不存在的实例，而
文件名仍然看起来完全正常。bundle 把三者绑在一个文件里，**要么全对，要么全错**，
没有第三种状态。代价是文件更大——但对几十道工序的工业实例来说完全不是问题。

**round-trip 的判定标准是「读回来的 dataclass 与原来相等」**，不是「看起来差不多」。
为此 :func:`load_bundle` 走的是与写出时**同一套**重建函数（``_instance_from_dict`` /
``schedule_from_dict`` / ``KPIReport.from_dict``），并且刻意**不重算**任何已经存下来的
数字。理由：报表是归档证据，重算会让它依赖「当时用的是同一份实现」。

bundle 自带 ``bundle_schema`` 版本号。版本不匹配时**直接报错**而不是尽力而为地解析——
一个被静默读错的 bundle 比一个读不开的 bundle 危险得多。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fjsp_core.models import FJSPInstance, Schedule
from fjsp_core.result import ShopResult, validate_result
from fjsp_io.kpi import KPIReport, kpi_report
from fjsp_io.parser import _instance_from_dict, schedule_from_dict, schedule_to_dict

BUNDLE_SCHEMA = 1


@dataclass(frozen=True, slots=True)
class Bundle:
    """一个 bundle 的三块内容。"""

    instance: FJSPInstance
    result: ShopResult
    kpi: KPIReport
    schema: int = BUNDLE_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_schema": self.schema,
            "instance": _instance_to_dict(self.instance),
            "result": {
                "method": self.result.method,
                "status": self.result.status,
                "objective": self.result.objective,
                "best_bound": self.result.best_bound,
                "build_time": self.result.build_time,
                "solve_time": self.result.solve_time,
                "iterations": self.result.iterations,
                "breakdown": dict(self.result.breakdown),
                "detail": self.result.detail,
                "schedule": (
                    None
                    if self.result.schedule is None
                    else schedule_to_dict(self.result.schedule)
                ),
            },
            "kpi": self.kpi.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Bundle":
        schema = int(data.get("bundle_schema", -1))
        if schema != BUNDLE_SCHEMA:
            raise ValueError(
                f"unsupported bundle_schema {schema!r} (expected {BUNDLE_SCHEMA})"
            )
        raw = data["result"]
        schedule: Schedule | None = None
        if raw.get("schedule") is not None:
            schedule = schedule_from_dict(raw["schedule"])
        return cls(
            instance=_instance_from_dict(data["instance"]),
            result=ShopResult(
                method=str(raw["method"]),
                status=str(raw["status"]),
                schedule=schedule,
                objective=(
                    None if raw.get("objective") is None else float(raw["objective"])
                ),
                best_bound=(
                    None if raw.get("best_bound") is None else float(raw["best_bound"])
                ),
                build_time=float(raw.get("build_time", 0.0)),
                solve_time=float(raw.get("solve_time", 0.0)),
                iterations=raw.get("iterations"),
                breakdown=dict(raw.get("breakdown", {})),
                detail=dict(raw.get("detail", {})),
            ),
            kpi=KPIReport.from_dict(data["kpi"]),
            schema=schema,
        )


def _instance_to_dict(instance: FJSPInstance) -> dict[str, Any]:
    """复用 ``fjsp_io.parser`` 的实例序列化，保证实例的写法只有一处。"""
    from dataclasses import asdict

    return asdict(instance)


def make_bundle(
    instance: FJSPInstance, result: ShopResult, *, verify: bool = True
) -> Bundle:
    """组装 bundle。``verify=True`` 时先用独立验证器检查排程。

    **默认验证。** 一个装进归档的 bundle 如果不带这个检查，就等于把
    「求解器说它可行」当成了事实——M1 起这条纪律就没松过。
    """
    if verify and result.schedule is not None:
        errors = validate_result(instance, result)
        if errors:
            raise ValueError(f"refusing to bundle an invalid schedule: {errors[:3]}")
    kpi = kpi_report(instance, result.schedule) if result.schedule is not None else None
    if kpi is None:
        raise ValueError("refusing to bundle a result without a schedule")
    return Bundle(instance=instance, result=result, kpi=kpi)


def save_bundle(
    path: str | Path, instance: FJSPInstance, result: ShopResult, *, verify: bool = True
) -> Bundle:
    bundle = make_bundle(instance, result, verify=verify)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return bundle


def load_bundle(path: str | Path) -> Bundle:
    return Bundle.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def bundles_equal(left: Bundle, right: Bundle) -> list[str]:
    """比较两个 bundle，返回**差异清单**（空列表 = 完全相等）。

    为什么返回清单而不是 ``bool``：测试挂了要能一眼看出是哪一块不等，
    「False」什么信息都没给。
    """
    differences: list[str] = []
    left_raw, right_raw = left.to_dict(), right.to_dict()
    # 先按「写出的 JSON 结构」逐块定位，让失败信息可读
    for key in ("instance", "result", "kpi"):
        if left_raw[key] != right_raw[key]:
            differences.append(key)
    if left.instance != right.instance:
        differences.append("instance(dataclass)")
    if left.kpi != right.kpi:
        differences.append("kpi(dataclass)")
    if (left.result.schedule is None) != (right.result.schedule is None):
        differences.append("result.schedule(presence)")
    elif left.result.schedule != right.result.schedule:
        differences.append("result.schedule")
    for field_name in (
        "method",
        "status",
        "objective",
        "best_bound",
        "iterations",
        "breakdown",
    ):
        if getattr(left.result, field_name) != getattr(right.result, field_name):
            differences.append(f"result.{field_name}")
    # 时间字段按「写出时的 6 位小数」比较：JSON 里存的就是六位。
    for field_name in ("build_time", "solve_time"):
        if round(getattr(left.result, field_name), 6) != round(
            getattr(right.result, field_name), 6
        ):
            differences.append(f"result.{field_name}")
    return differences
