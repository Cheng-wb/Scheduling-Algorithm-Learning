"""目标评估：单一职责，只算指标，不做可行性检查。

调用方必须**先**用 ``validate_schedule`` 验证再评价；否则会得到「一个坏排程的
漂亮数字」（M1 的纪律，M3 继续遵守）。

多目标按 M3 的计划扩展为 ``α·Cmax + β·ΣT + γ·setup``，但**权重归一化是调用方的
责任**：本模块只按给定权重线性加权，不做量纲统一。理由见 ``weighted_sum`` 的文档。
"""

from __future__ import annotations

from dataclasses import dataclass

from fjsp_core.models import FJSPInstance, Schedule


def job_completion_times(instance: FJSPInstance, schedule: Schedule) -> dict[str, int]:
    """每个订单的完工时间：该订单最后一道工序的 ``end_time``。"""
    completion: dict[str, int] = {}
    for item in schedule.operations:
        op = instance.operation(item.operation_id)
        completion[op.job_id] = max(completion.get(op.job_id, 0), item.end_time)
    return completion


def makespan(instance: FJSPInstance, schedule: Schedule) -> int:
    """最后一个订单完成的时间。空排程为 0。"""
    times = job_completion_times(instance, schedule)
    return max(times.values(), default=0)


def total_tardiness(instance: FJSPInstance, schedule: Schedule) -> int:
    """Σ max(0, C_j − d_j)。没有交期的订单不参与。恒非负。"""
    completion = job_completion_times(instance, schedule)
    return sum(
        max(0, completion.get(job.id, 0) - job.due_date)
        for job in instance.jobs
        if job.due_date is not None
    )


def weighted_tardiness(instance: FJSPInstance, schedule: Schedule) -> float:
    """Σ w_j · max(0, C_j − d_j)。"""
    completion = job_completion_times(instance, schedule)
    return float(
        sum(
            job.weight * max(0, completion.get(job.id, 0) - job.due_date)
            for job in instance.jobs
            if job.due_date is not None
        )
    )


def max_lateness(instance: FJSPInstance, schedule: Schedule) -> int:
    """max_j (C_j − d_j)。**可以为负**（全部提前完成时）。无交期的订单不参与。"""
    completion = job_completion_times(instance, schedule)
    values = [
        completion.get(job.id, 0) - job.due_date
        for job in instance.jobs
        if job.due_date is not None
    ]
    return max(values, default=0)


def total_setup_time(instance: FJSPInstance, schedule: Schedule) -> int:
    """总换型时间：按每台机器上的加工顺序累加相邻工序的 ``setup``。

    未定义换型方向的相邻对按 0 计——**但这只在验证器已经报过 ``setup undefined``
    时才安全**。所以本函数同样要求调用方先验证。
    """
    total = 0
    by_machine: dict[str, list] = {}
    for item in schedule.operations:
        by_machine.setdefault(item.machine_id, []).append(item)
    for items in by_machine.values():
        ordered = sorted(items, key=lambda item: item.start_time)
        for previous, current in zip(ordered, ordered[1:]):
            try:
                total += instance.setup_minutes(
                    instance.operation(previous.operation_id).family,
                    instance.operation(current.operation_id).family,
                )
            except KeyError:
                continue
    return total


def worker_load(instance: FJSPInstance, schedule: Schedule) -> dict[str, int]:
    """每个次生资源的占用时长之和（不区分机器）。"""
    load: dict[str, int] = {}
    for item in schedule.operations:
        if item.worker_id is None:
            continue
        load[item.worker_id] = load.get(item.worker_id, 0) + (
            item.end_time - item.start_time
        )
    return load


# ---------------------------------------------------------------------------
# 多目标：加权和
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Weights:
    """``α·Cmax + β·ΣT + γ·setup`` 的权重。

    **三个分量的量纲不同**（时间 / 迟交量 / 换型时间），所以线性加权之前必须做
    归一化，而这一步不可能由本模块替调用方决定——归一化基准取决于业务对
    「一分钟的迟交」和「一分钟的换型」的相对定价。

    因此这里只做两件事：按给定权重相加、把**各分量原值**一并暴露出来，
    让调用方能自己检查权重是否真的表达了意图（见 ``objective_breakdown``）。
    """

    alpha: float = 1.0  # Cmax
    beta: float = 0.0  # ΣT
    gamma: float = 0.0  # setup

    def __post_init__(self) -> None:
        if self.alpha == 0 and self.beta == 0 and self.gamma == 0:
            raise ValueError("all weights are zero: the objective would be constant")


def objective_breakdown(instance: FJSPInstance, schedule: Schedule) -> dict[str, float]:
    """三个分量的原值。做权重敏感性分析时必须先看它，再看加权和。"""
    return {
        "cmax": float(makespan(instance, schedule)),
        "total_tardiness": float(total_tardiness(instance, schedule)),
        "setup": float(total_setup_time(instance, schedule)),
    }


def weighted_sum(
    instance: FJSPInstance, schedule: Schedule, weights: Weights
) -> float:
    """``α·Cmax + β·ΣT + γ·setup``，按**原值**加权，不做归一化。"""
    parts = objective_breakdown(instance, schedule)
    return (
        weights.alpha * parts["cmax"]
        + weights.beta * parts["total_tardiness"]
        + weights.gamma * parts["setup"]
    )


#: 单一目标名 → 评估函数。多目标 ``weighted_sum`` 单独走权重参数。
OBJECTIVES: dict[str, str] = {
    "makespan": "Cmax",
    "total_tardiness": "Σ max(0, C_j − d_j)",
    "weighted_tardiness": "Σ w_j·max(0, C_j − d_j)",
    "total_setup_time": "总换型时间",
    "weighted_sum": "α·Cmax + β·ΣT + γ·setup",
}


def evaluate(
    instance: FJSPInstance,
    schedule: Schedule,
    name: str = "makespan",
    weights: Weights | None = None,
) -> float:
    """按名字求值。未知名字抛 ``KeyError``（**不静默回落到 Cmax**）。"""
    if name == "weighted_sum":
        return weighted_sum(instance, schedule, weights or Weights())
    if name == "makespan":
        return float(makespan(instance, schedule))
    if name == "total_tardiness":
        return float(total_tardiness(instance, schedule))
    if name == "weighted_tardiness":
        return weighted_tardiness(instance, schedule)
    if name == "total_setup_time":
        return float(total_setup_time(instance, schedule))
    raise KeyError(f"unknown objective: {name!r}")


def parse_weights(spec: dict) -> Weights | None:
    """从方法参数里读权重；缺省返回 ``None``（由 :func:`evaluate` 取默认）。"""
    raw = spec.get("weights")
    if raw is None:
        return None
    if isinstance(raw, Weights):
        return raw
    return Weights(
        alpha=float(raw.get("alpha", 1.0)),
        beta=float(raw.get("beta", 0.0)),
        gamma=float(raw.get("gamma", 0.0)),
    )
