"""多目标 KPI 报表：把一个**已验证**的排程翻译成业务方能读的一页数字。

    from fjsp_io.kpi import kpi_report
    report = kpi_report(instance, schedule)

设计上有三条纪律：

1. **先验证，再算数。** 本模块不检查可行性（和 ``fjsp_core.objective`` 一样）。
   一个排程已经通过了 ``validate_schedule``，这里的数字才有意义；否则你会得到
   「一个坏排程的漂亮 KPI」。
2. **原值优先，比率其次。** ``KPIReport`` 的字段分两层：``cmax`` / ``total_tardiness``
   / ``setup_time`` 这些是**原值**（分钟），``utilization`` / ``setup_share`` /
   ``on_time_rate`` 是**比率**（无量纲）。混着看会得出错误结论，所以字段命名上
   就把两者分开：比率一律以 ``_rate`` / ``_share`` / ``utilization`` 结尾。
3. **不做归一化加权。** 见 :func:`normalize` 的文档——归一化基准是业务定价，
   不是数学结论。本模块只提供「相对某个参考排程的比值」，把定价权留给调用方。
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from fjsp_core.models import FJSPInstance, Schedule
from fjsp_core.objective import (
    job_completion_times,
    max_lateness,
    total_setup_time,
    total_tardiness,
    weighted_tardiness,
)

#: 机器不是次生资源，它的「容量」恒为 1。写成常量而不是硬编码字面量，
#: 是为了在报表里显式声明这个假设。
MACHINE_CAPACITY = 1


@dataclass(frozen=True, slots=True)
class ResourceKPI:
    """一个资源（机器或工人）的占用情况。

    ``span`` 是**可见窗口**：该资源第一次被占用到最后一次被占用结束之间的长度。
    ``load`` 是实际加工时长之和。``utilization = load / span``。

    **为什么不用「排程总长」当分母？** 因为那会把「这个工人根本没参与后半个排程」
    算成低效，而实际上他只是没被安排任务——那是排程决策的结果，不是资源的问题。
    可见窗口是更诚实的口径。``span == 0``（完全没被用到）时 ``utilization`` 记为
    ``0.0`` 而**不是** ``NaN``：JSON 不允许 NaN，报表也不该出现 ``nan``。
    """

    resource_id: str
    capacity: int
    load: int
    span: int
    utilization: float
    operations: int


@dataclass(frozen=True, slots=True)
class KPIReport:
    """一份排程的多目标 KPI。字段全部可 JSON 序列化，round-trip 后逐个相等。"""

    # --- 交期维度 ---------------------------------------------------------
    cmax: int
    total_tardiness: int
    weighted_tardiness: float
    max_lateness: int
    jobs_with_due_date: int
    jobs_on_time: int
    on_time_rate: float
    mean_flow_time: float

    # --- 换型维度 ---------------------------------------------------------
    setup_time: int
    setup_share: float

    # --- 资源维度 ---------------------------------------------------------
    machine_kpi: tuple[ResourceKPI, ...]
    worker_kpi: tuple[ResourceKPI, ...]
    machine_utilization: float
    worker_utilization: float
    worker_load: dict[str, int] = field(default_factory=dict)

    # --- 口径声明 ---------------------------------------------------------
    normalization_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["machine_kpi"] = [asdict(item) for item in self.machine_kpi]
        data["worker_kpi"] = [asdict(item) for item in self.worker_kpi]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KPIReport":
        """**不重算**，直接读回存下来的数字。

        重算会让 round-trip 依赖于「当时用的是同一份实现」，而报表是要归档的证据。
        读回就是读回。
        """
        return cls(
            cmax=int(data["cmax"]),
            total_tardiness=int(data["total_tardiness"]),
            weighted_tardiness=float(data["weighted_tardiness"]),
            max_lateness=int(data["max_lateness"]),
            jobs_with_due_date=int(data["jobs_with_due_date"]),
            jobs_on_time=int(data["jobs_on_time"]),
            on_time_rate=float(data["on_time_rate"]),
            mean_flow_time=float(data["mean_flow_time"]),
            setup_time=int(data["setup_time"]),
            setup_share=float(data["setup_share"]),
            machine_kpi=tuple(
                ResourceKPI(**item) for item in data["machine_kpi"]
            ),
            worker_kpi=tuple(ResourceKPI(**item) for item in data["worker_kpi"]),
            machine_utilization=float(data["machine_utilization"]),
            worker_utilization=float(data["worker_utilization"]),
            worker_load={
                str(key): int(value)
                for key, value in data.get("worker_load", {}).items()
            },
            normalization_note=str(data.get("normalization_note", "")),
        )


def _resource_kpi(
    resource_id: str,
    capacity: int,
    spans: list[tuple[int, int]],
) -> ResourceKPI:
    """从一串 ``[start, end)`` 半开区间汇总出一个资源的口径。

    区间之间可以**相接**（``end == next start``）：相接不产生重叠，和验证器的
    ``[start, end)`` 约定一致。
    """
    if not spans:
        return ResourceKPI(resource_id, capacity, 0, 0, 0.0, 0)
    load = sum(end - start for start, end in spans)
    span = max(end for _, end in spans) - min(start for start, _ in spans)
    utilization = round(load / span, 6) if span > 0 else 0.0
    return ResourceKPI(resource_id, capacity, load, span, utilization, len(spans))


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def kpi_report(instance: FJSPInstance, schedule: Schedule) -> KPIReport:
    """算出全部 KPI。**调用方必须先 ``validate_schedule``。**"""
    completion = job_completion_times(instance, schedule)
    cmax = max(completion.values(), default=0)

    # 交期：没有 due_date 的订单不参与迟交统计——这条口径必须和
    # ``fjsp_core.objective.total_tardiness`` 完全一致，否则两个模块会互相矛盾。
    with_due = [job for job in instance.jobs if job.due_date is not None]
    on_time = sum(
        1 for job in with_due if completion.get(job.id, 0) <= job.due_date
    )

    setup = total_setup_time(instance, schedule)

    machine_spans: dict[str, list[tuple[int, int]]] = {
        machine.id: [] for machine in instance.machines
    }
    worker_spans: dict[str, list[tuple[int, int]]] = {
        worker.id: [] for worker in instance.workers
    }
    for item in schedule.operations:
        machine_spans.setdefault(item.machine_id, []).append(
            (item.start_time, item.end_time)
        )
        if item.worker_id is not None:
            worker_spans.setdefault(item.worker_id, []).append(
                (item.start_time, item.end_time)
            )

    machine_kpi = tuple(
        _resource_kpi(machine.id, MACHINE_CAPACITY, machine_spans.get(machine.id, []))
        for machine in instance.machines
    )
    # 工人按 id 排序，保证报表可复现（实例里的顺序是生成顺序，不该泄漏到报表上）。
    worker_kpi = tuple(
        _resource_kpi(
            worker.id,
            worker.capacity,
            worker_spans.get(worker.id, []),
        )
        for worker in sorted(instance.workers, key=lambda item: item.id)
    )

    def _aggregate(items: tuple[ResourceKPI, ...]) -> float:
        total_load = sum(item.load for item in items)
        total_span = sum(item.span for item in items)
        return round(total_load / total_span, 6) if total_span > 0 else 0.0

    return KPIReport(
        cmax=cmax,
        total_tardiness=total_tardiness(instance, schedule),
        weighted_tardiness=round(weighted_tardiness(instance, schedule), 6),
        max_lateness=max_lateness(instance, schedule),
        jobs_with_due_date=len(with_due),
        jobs_on_time=on_time,
        on_time_rate=round(on_time / len(with_due), 6) if with_due else 0.0,
        mean_flow_time=_mean([float(value) for value in completion.values()]),
        setup_time=setup,
        setup_share=round(setup / cmax, 6) if cmax > 0 else 0.0,
        machine_kpi=machine_kpi,
        worker_kpi=worker_kpi,
        machine_utilization=_aggregate(machine_kpi),
        worker_utilization=_aggregate(worker_kpi),
        worker_load={item.resource_id: item.load for item in worker_kpi},
        normalization_note=NORMALIZATION_NOTE,
    )


NORMALIZATION_NOTE = (
    "分量原值不可直接相加：Cmax 与 ΣT 的单位是「分钟」、换型时间也是分钟但语义是"
    "「非增值时间」、utilization 无量纲。要加权必须先定基准。"
    "本模块只提供 normalize() 给出的「相对某参考排程的比值」，"
    "基准取哪个排程（下界 / 基线 / 上期实际）是业务决策。"
)


def normalize(
    report: KPIReport, reference: KPIReport
) -> dict[str, float]:
    """三个目标分量相对 **参考排程** 的比值。

    ``reference`` 通常是同一个实例上的基线排程（或上一版排程）。返回
    ``{'cmax': ..., 'total_tardiness': ..., 'setup': ...}``，值为
    ``当前 / 参考``：``< 1`` 表示更好。

    **参考值为 0 时返回 1.0 并附一条说明**——而不是返回 ``inf`` 或 ``nan``。
    零分母意味着「参考排程在这一项上是完美的」，此时比值没有信息量，任何实数
    都是错的答案；返回 1.0 是**约定**（表示「无法区分」），调用方必须检查
    ``report`` 里的原值才能知道发生了什么。
    """
    out: dict[str, float] = {}
    for key, current, base in (
        ("cmax", report.cmax, reference.cmax),
        ("total_tardiness", report.total_tardiness, reference.total_tardiness),
        ("setup", report.setup_time, reference.setup_time),
    ):
        out[key] = round(current / base, 6) if base > 0 else 1.0
    return out


def format_kpi(report: KPIReport) -> str:
    """一页纯 ASCII 的文本报表。**刻意不用任何非 ASCII 的排版符号**：
    示例脚本的 stdout 要能在 GBK 控制台上打印，破折号和上标都会炸。"""
    lines = [
        "== KPI ==",
        f"  Cmax (makespan)          : {report.cmax}",
        f"  total tardiness          : {report.total_tardiness}",
        f"  weighted tardiness       : {report.weighted_tardiness:g}",
        f"  max lateness             : {report.max_lateness}",
        f"  on-time                  : {report.jobs_on_time}/{report.jobs_with_due_date}"
        f"  (rate {report.on_time_rate:g})",
        f"  mean flow time           : {report.mean_flow_time:g}",
        f"  setup time               : {report.setup_time}"
        f"  (share of Cmax {report.setup_share:g})",
        f"  machine utilization      : {report.machine_utilization:g}",
        f"  worker utilization       : {report.worker_utilization:g}",
        "  -- workers --",
    ]
    for item in report.worker_kpi:
        lines.append(
            f"    {item.resource_id}: load={item.load} span={item.span}"
            f" cap={item.capacity} ops={item.operations}"
            f" utilization={item.utilization:g}"
        )
    return "\n".join(lines)


def _guard_finite(value: float) -> float:
    """JSON 不允许 NaN / inf。任何算出非有限值的地方都该在写盘前就暴露。"""
    if not math.isfinite(value):
        raise ValueError(f"non-finite KPI value: {value!r}")
    return value
