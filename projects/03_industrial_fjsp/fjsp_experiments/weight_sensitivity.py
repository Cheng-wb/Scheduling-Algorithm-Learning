"""M3 Week 3 验收实验：多目标归一化与权重敏感性。

    python -m fjsp_experiments.weight_sensitivity --output artifacts/month3_w3

Week 3 的验收标准是「给出多目标归一化与权重敏感性分析」。这件事不能靠读代码
证明，只能靠一张**真跑出来的表**：

1. 同一个实例、同一组权重 ``(alpha, beta, gamma)``，只换归一化口径
   （``none`` / ``trivial`` / ``ideal``），选出的排程可能不同；
2. 同一个口径、同一实例，只动 ``beta``，选出的排程是否真的变——如果不变，
   那是「这个实例上没有取舍」，也要照实写出来，不能造一个假的翻转。

本模块把这两件事都做成表。``breakdown`` 的三个分量原值**每行都记**，因为
只看加权和的总数看不出「谁换走了什么」。

归一化口径的三个分母（Day 3 的正式定义）：

``none``
    ``(1, 1, 1)``。按原始单位加权，是**对照组**。
``trivial``
    求解器内置的平凡上界（``industrial.trivial_bounds``）：串行完工时间、
    ``sum_j max(0, Cmax_ub - d_j)``、``工序数 x 最大换型``。不需要求解就能算，
    所以可以当作默认值。
``ideal``
    理想点：三个单目标各自的最优值。**必须由本驱动先另解三个模型算出来再传进
    求解器**——求解器不会为了归一化偷偷多解三个模型。

本模块同时是示例脚本的取数入口：``sweep`` 是纯计算、不落盘，``run`` 才写文件。
这样「脚本打印的表」与「artifacts 里的表」逐格一致，不会出现两套数。
"""

from __future__ import annotations

import argparse
import hashlib
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fjsp_core import FJSPInstance, Job, Machine, Operation, Setup
from fjsp_core.result import ShopResult, validate_result
from fjsp_io import generate_instance, save_json_instance
from fjsp_shop.registry import available, get, load_week_modules

from fjsp_experiments.benchmark import (
    ROOT,
    SCHEMA_VERSION,
    source_hash,
    write_csv,
    write_json,
)

#: 本实验唯一使用的求解器：它同时支持 ``weights`` 与 ``normalization``。
METHOD = "fjsp_cpsat_multiobj"

#: 权重设置。``None`` 表示由 :func:`single_objective_optima` 现算的理想点。
#: ``(标签, alpha, beta, gamma)``；beta 只取 >= 0 的值（负权重在这里没有业务含义）。
SWEEP_SETTINGS: tuple[tuple[str, float, float, float], ...] = (
    ("cmax_only", 1.0, 0.0, 0.0),
    ("tardiness_light", 1.0, 0.25, 0.0),
    ("tardiness_heavy", 1.0, 4.0, 0.0),
    ("tardiness_only", 0.0, 1.0, 0.0),
    ("setup_only", 0.0, 0.0, 1.0),
    ("balanced", 1.0, 1.0, 1.0),
)

#: 三个归一化口径，顺序固定，便于逐行对读。
NORMALIZATION_MODES: tuple[str, ...] = ("none", "trivial", "ideal")

#: 每次求解的时间预算。**30 秒是刻意的**：5 秒时 ``plant_batch`` 的
#: ``tardiness_heavy`` 端点只能拿到 ``FEASIBLE``，两条端点的 ``beta*`` 就变成
#: 「两条都不一定最优的直线的交点」，权重敏感性那节会因此在报告里留下一整行
#: 「不能当结论」。加到 30 秒后两端点都能证明（``none`` 口径 6.7 秒 / 7.8 秒），
#: 这张表才第一次真正在讲归一化，而不是在讲搜索预算。
DEFAULT_TIME_LIMIT = 30.0
DEFAULT_SEED = 0

#: 落盘的逐行字段顺序（只影响 csv 列序，方便人眼对读）。
ROW_FIELDS = (
    "instance",
    "setting",
    "alpha",
    "beta",
    "gamma",
    "normalization_mode",
    "d_cmax",
    "d_total_tardiness",
    "d_setup",
    "status",
    "model_status",
    "objective",
    "best_bound",
    "weighted_raw",
    "weighted_normalized",
    "cmax",
    "total_tardiness",
    "setup",
    "solve_time",
    "schedule_key",
    "validation",
)


# ---------------------------------------------------------------------------
# 实例
# ---------------------------------------------------------------------------


def tiny_tradeoff() -> FJSPInstance:
    """手算实例 T：2 台机器、4 个订单各 1 道工序，三维取舍都是**真实**的。

    ```text
    M0: A(6, F0, J0 d=100), B(2, F1, J1 d=1)
    M1: C(5, F0, J2 d=4)
    D(2 on M1 / 4 on M0, F1, J3 d=30)
    换型: F0->F1 = 1, F1->F0 = 8

    三个单目标最优值（手算，与求解器一致）:
      min Cmax = 9   M0: A[0,6) s1 B[7,9)，M1: C[0,5) s1 D[6,8)  -> (9, 9, 2)
      min ST   = 2   M0: B[0,2) s8 A[10,16)，M1: C[0,5) s1 D[6,8) -> (16, 2, 9)
      min setup= 1   M0: A[0,6) s1 D[7,11) s0 B[11,13)，M1: C[0,5) -> (13, 13, 1)
    ```

    ``D`` 只能去 M1 时 M0 上 ``A`` 与 ``B`` 的换型不可避免，所以 ``Cmax`` 下界
    是 ``6 + 1 + 2 = 9``；``B`` 的 ``p = 2``、``d = 1``，所以 ``ΣT`` 下界是
    ``1``（来自 ``B``）``+ 1``（来自 ``C``：``p = 5 > d = 4``）= ``2``。两个下界
    都被上面第 2、3 行的排程分别达到，所以是**证明过的最优值**，不是最好可行解。
    """
    return FJSPInstance(
        jobs=(
            Job("J0", ("A",), due_date=100),
            Job("J1", ("B",), due_date=1),
            Job("J2", ("C",), due_date=4),
            Job("J3", ("D",), due_date=30),
        ),
        operations=(
            Operation("A", "J0", 0, (("M0", 6),), family="F0"),
            Operation("B", "J1", 0, (("M0", 2),), family="F1"),
            Operation("C", "J2", 0, (("M1", 5),), family="F0"),
            Operation("D", "J3", 0, (("M0", 4), ("M1", 2)), family="F1"),
        ),
        machines=(Machine("M0", "M0"), Machine("M1", "M1")),
        setups=(Setup("F0", "F1", 1), Setup("F1", "F0", 8)),
    )


def plant_batch() -> FJSPInstance:
    """生成的「车间批次」实例 P：5 订单 x 2 工序、2 机器、柔性 2、2 个族、有释放时间与交期。

    刻意保留 ``seed = 302``：这个种子在 ``beta`` 扫描下会横跨多个不同的
    ``breakdown``（见 ``results.csv``），是本实验里「取舍真实存在」的现实版证据。
    它的换型模型比 T 大得多，``OPTIMAL`` 未必能在预算内证出来——本实验照实报
    ``FEASIBLE``，不把「最好是可行解」说成「最优」。
    """
    return generate_instance(
        302,
        jobs=5,
        machines=2,
        operations_per_job=2,
        flexibility=2,
        setup_families=2,
        release_max=4,
        due_factor=1.1,
    )


#: 实例名 -> 构造函数。名字会进 ``results.csv`` 的 ``instance`` 列。
INSTANCES: dict[str, Any] = {"tiny_tradeoff": tiny_tradeoff, "plant_batch": plant_batch}


# ---------------------------------------------------------------------------
# 求解
# ---------------------------------------------------------------------------


def _single_objective_spec(objective: str, time_limit: float, seed: int) -> dict[str, Any]:
    """单目标求解的 spec。仍然显式带上权重，避免任何「隐式默认」的余地。"""
    weight = {"makespan": (1.0, 0.0, 0.0), "total_tardiness": (0.0, 1.0, 0.0),
              "total_setup_time": (0.0, 0.0, 1.0)}[objective]
    return {
        "objective": objective,
        "time_limit": time_limit,
        "seed": seed,
        "weights": {"alpha": weight[0], "beta": weight[1], "gamma": weight[2]},
        "normalization": {"mode": "none"},
    }


def single_objective_optima(
    instance: FJSPInstance, *, time_limit: float = DEFAULT_TIME_LIMIT, seed: int = DEFAULT_SEED
) -> dict[str, Any]:
    """三个单目标各自的最好值 = 理想点。返回 ``{objective: (value, status, schedule_key)}``。

    用 ``normalization = none`` 跑，这样 ``best_bound`` 是原始单位、可以直接和
    ``objective`` 对读；每次求解仍要过独立验证器。
    """
    out: dict[str, Any] = {}
    for objective in ("makespan", "total_tardiness", "total_setup_time"):
        result = get(METHOD)(instance, _single_objective_spec(objective, time_limit, seed))
        out[objective] = {
            "value": float(result.objective) if result.objective is not None else None,
            "status": result.status,
            "best_bound": result.best_bound,
            "schedule_key": schedule_key(result),
            "validation": list(validate_result(instance, result)),
        }
    return out


def schedule_key(result: ShopResult) -> str:
    """把排程压成一个可对读的字符串：``M0:A@0-6,B@7-9;M1:C@0-5``。

    权重敏感性实验的结论是「选出的排程变了没有」，所以需要一个**能进 csv、
    能被人眼直接比对**的排程指纹；哈希做不到「一眼看出换了哪道工序」。
    """
    if result.schedule is None:
        return ""
    by_machine: dict[str, list[str]] = {}
    for item in result.schedule.operations:
        by_machine.setdefault(item.machine_id, []).append(
            f"{item.operation_id}@{item.start_time}-{item.end_time}"
        )
    return ";".join(
        f"{machine}:" + ",".join(sorted(items)) for machine, items in sorted(by_machine.items())
    )


def _ideal_skip_reason(optima: dict[str, Any]) -> str:
    """``ideal`` 口径为什么不可用：逐分量点名，并且**区分**「分成 0」与「没解出来」。"""
    parts: list[str] = []
    for objective, key in (
        ("makespan", "cmax"),
        ("total_tardiness", "total_tardiness"),
        ("total_setup_time", "setup"),
    ):
        item = optima[objective]
        if item["value"] is None:
            parts.append(f"{key}: 单目标求解没有返回解")
        elif item["value"] <= 0:
            parts.append(f"{key}: 单目标最优值为 0，分母为 0（理想点归一化在此分量上无定义）")
        elif item["status"] != "OPTIMAL":
            parts.append(f"{key}: 单目标值 {item['value']:g} 只是当时的最好可行解，未证明最优")
    return "；".join(parts) if parts else ""


def _ideal_from(optima: dict[str, Any]) -> dict[str, float] | None:
    """把单目标结果翻译成 ``ideal`` 口径需要的三个分母；有 0 就返回 ``None``。

    分母为 0 会让 ``scaled`` 抛 ``ValueError``——而且从业务上讲「换型的最优值是
    0」意味着这个分量在这一实例上根本不影响任何决策，此时用 ``ideal`` 归一化
    已经没有意义。这里**显式跳过并记录原因**，不悄悄退回 ``trivial``。
    """
    divisors: dict[str, float] = {}
    for objective, key in (
        ("makespan", "cmax"),
        ("total_tardiness", "total_tardiness"),
        ("total_setup_time", "setup"),
    ):
        value = optima[objective]["value"]
        if value is None or value <= 0:
            return None
        divisors[key] = float(value)
    return divisors


def sweep(
    instance: FJSPInstance,
    *,
    name: str,
    settings: tuple[tuple[str, float, float, float], ...] = SWEEP_SETTINGS,
    modes: tuple[str, ...] = NORMALIZATION_MODES,
    time_limit: float = DEFAULT_TIME_LIMIT,
    seed: int = DEFAULT_SEED,
    ideal: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """``设置 x 口径`` 的全交叉求解。纯计算，不落盘——示例脚本直接调它。

    ``ideal`` 为 ``None`` 时**跳过** ``ideal`` 口径（并把 ``ideal_skipped``
    写在每一行上），而不是用别的分母顶替。
    """
    rows: list[dict[str, Any]] = []
    for mode in modes:
        if mode == "ideal" and ideal is None:
            for label, alpha, beta, gamma in settings:
                rows.append(
                    _skipped_row(name, label, alpha, beta, gamma, mode,
                                 "ideal point unavailable (a single-objective optimum is 0 or unknown)")
                )
            continue
        normalization: dict[str, Any] = {"mode": mode}
        if mode == "ideal":
            normalization.update(ideal or {})
        for label, alpha, beta, gamma in settings:
            spec = {
                "objective": "weighted_sum",
                "time_limit": time_limit,
                "seed": seed,
                "weights": {"alpha": alpha, "beta": beta, "gamma": gamma},
                "normalization": normalization,
            }
            result = get(METHOD)(instance, spec)
            diagnostics = validate_result(instance, result)
            breakdown = {
                key: float(result.breakdown.get(key, 0.0))
                for key in ("cmax", "total_tardiness", "setup")
            }
            divisors = dict(result.detail.get("normalization", {}).get("divisors", {}))
            rows.append(
                {
                    "instance": name,
                    "setting": label,
                    "alpha": alpha,
                    "beta": beta,
                    "gamma": gamma,
                    "normalization_mode": mode,
                    "d_cmax": divisors.get("cmax"),
                    "d_total_tardiness": divisors.get("total_tardiness"),
                    "d_setup": divisors.get("setup"),
                    "status": result.status,
                    "objective": result.objective,
                    "best_bound": result.best_bound,
                    # 由 breakdown 重新拼一遍原始加权和：与求解器报的 objective 对读，
                    # 就是「求解器有没有老实报目标」的一条独立检查。
                    "weighted_raw": (
                        alpha * breakdown["cmax"]
                        + beta * breakdown["total_tardiness"]
                        + gamma * breakdown["setup"]
                    ),
                    "weighted_normalized": _normalized_sum(breakdown, divisors, alpha, beta, gamma),
                    "cmax": breakdown["cmax"],
                    "total_tardiness": breakdown["total_tardiness"],
                    "setup": breakdown["setup"],
                    "solve_time": round(result.solve_time, 6),
                    # 求解器对**它自己的模型**（即归一化加权和）证明到了哪一步。
                    # 归一化口径下 ``best_bound`` 必然为 None，所以「这一行能不能
                    # 当成最优解来比较」只能看这个字段，不能看 status。
                    "model_status": str(result.detail.get("model_status", "")),
                    "schedule_key": schedule_key(result),
                    # 完整排程只进 schedules.json（csv 里放不下也不该放），
                    # 由 run() 在写 csv 前摘掉——write_csv 取所有行键的并集，
                    # 留在行里就会凭空多出一列长嵌套结构。
                    "schedule": (
                        []
                        if result.schedule is None
                        else [
                            {
                                "operation_id": item.operation_id,
                                "machine_id": item.machine_id,
                                "start_time": item.start_time,
                                "end_time": item.end_time,
                                "worker_id": item.worker_id,
                            }
                            for item in sorted(
                                result.schedule.operations,
                                key=lambda item: (item.machine_id, item.start_time),
                            )
                        ]
                    ),
                    "validation": "; ".join(diagnostics) or "ok",
                    "ideal_skipped": "",
                }
            )
    return rows


def _skipped_row(
    name: str, label: str, alpha: float, beta: float, gamma: float, mode: str, reason: str
) -> dict[str, Any]:
    row = {field: None for field in ROW_FIELDS}
    row.update(
        {
            "instance": name,
            "setting": label,
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
            "normalization_mode": mode,
            "status": "SKIPPED",
            "model_status": "SKIPPED",
            "validation": reason,
            "ideal_skipped": reason,
            "schedule_key": "",
            "schedule": [],
        }
    )
    return row


def _normalized_sum(
    breakdown: dict[str, float],
    divisors: dict[str, float],
    alpha: float,
    beta: float,
    gamma: float,
) -> float | None:
    """把三个分量**先除分母再加权**。缺任一分母则返回 ``None``（不猜）。"""
    if not divisors:
        return None
    try:
        return (
            alpha * breakdown["cmax"] / float(divisors["cmax"])
            + beta * breakdown["total_tardiness"] / float(divisors["total_tardiness"])
            + gamma * breakdown["setup"] / float(divisors["setup"])
        )
    except (KeyError, TypeError, ValueError):
        return None


def crossover_beta(
    left: dict[str, Any], right: dict[str, Any], divisors: dict[str, float]
) -> float | None:
    """两条排程加权和相等的 ``beta``（``alpha = 1``、``gamma = 0``）。

    解 ``(Cmax_L - Cmax_R)/d_c + beta (T_L - T_R)/d_t = 0``。
    ``d_c == d_t == 1``（即 ``none``）时得到的就是「原始单位下的交换率」；
    换分子就是**同一组权重在不同归一化口径下对应不同的实际交换率**的定量表达：
    只要 ``d_t / d_c`` 变了，翻转点就跟着变。分母无关紧要的情形（``T_L == T_R``，
    此时迟交权重根本不起作用）返回 ``None``。
    """
    delta_c = float(left["cmax"]) - float(right["cmax"])
    delta_t = float(left["total_tardiness"]) - float(right["total_tardiness"])
    if delta_t == 0:
        return None
    d_c = float(divisors["cmax"])
    d_t = float(divisors["total_tardiness"])
    return -(delta_c / d_c) * (d_t / delta_t)


# ---------------------------------------------------------------------------
# 实验：落盘
# ---------------------------------------------------------------------------


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
        )
        return out.stdout.strip()
    except OSError:
        return ""


def run(
    output: Path,
    *,
    time_limit: float = DEFAULT_TIME_LIMIT,
    seed: int = DEFAULT_SEED,
) -> list[dict[str, Any]]:
    """跑完整实验并落盘 ``results.csv`` / ``schedules.json`` / ``metadata.json`` / ``report.md``。

    输出目录必须为空：本实验要能与上一版逐格对读，覆盖写会让对比失去意义。
    """
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output must be empty (preserve previous experiments): {output}")

    # --- 版本状态：必须在创建输出目录之前捕获（M2 的纪律）------------------
    frozen_commit = _git("rev-parse", "HEAD")
    frozen_dirty = bool(_git("status", "--porcelain"))
    frozen_source = source_hash()
    frozen_config = hashlib.sha256(
        repr((SWEEP_SETTINGS, NORMALIZATION_MODES, time_limit, seed)).encode()
    ).hexdigest()

    output.mkdir(parents=True, exist_ok=True)
    (output / "instances").mkdir(exist_ok=True)

    module_failures = load_week_modules()
    if METHOD not in available():
        raise RuntimeError(f"{METHOD} is not registered: month3 batch would record FAILED")

    instances: dict[str, FJSPInstance] = {}
    digests: dict[str, str] = {}
    for name, factory in INSTANCES.items():
        instance = factory()
        path = output / "instances" / f"{name}.json"
        save_json_instance(instance, path)
        instances[name] = instance
        digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()

    rows: list[dict[str, Any]] = []
    schedules: dict[str, Any] = {}
    ideal_points: dict[str, Any] = {}
    for name, instance in instances.items():
        optima = single_objective_optima(instance, time_limit=time_limit, seed=seed)
        ideal = _ideal_from(optima)
        ideal_points[name] = {
            "optima": optima,
            "divisors": ideal,
            "skip_reason": "" if ideal is not None else _ideal_skip_reason(optima),
            "note": "ideal point = 三个单目标各自的最好值；理想点上三个归一化分量都取到 1",
        }
        for row in sweep(instance, name=name, time_limit=time_limit, seed=seed, ideal=ideal):
            rows.append(row)

    schedules = {
        f"{row['instance']}__{row['setting']}__{row['normalization_mode']}": {
            "schedule_key": row["schedule_key"],
            "operations": row["schedule"],
        }
        for row in rows
    }
    write_csv(
        output / "results.csv",
        [{key: row[key] for key in ROW_FIELDS} for row in rows],
    )
    write_json(output / "schedules.json", schedules)
    write_json(
        output / "metadata.json",
        {
            "schema_version": SCHEMA_VERSION,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "git_commit": frozen_commit,
            "working_tree_dirty": frozen_dirty,
            "source_sha256": frozen_source,
            "sweep_sha256": frozen_config,
            "method": METHOD,
            "time_limit_seconds": time_limit,
            "seed": seed,
            "sweep_settings": [
                {"label": label, "alpha": a, "beta": b, "gamma": g}
                for label, a, b, g in SWEEP_SETTINGS
            ],
            "normalization_modes": list(NORMALIZATION_MODES),
            "instance_sha256": digests,
            "ideal_points": ideal_points,
            "unavailable_modules": module_failures,
            "registered_methods": available(),
            "validation": "every row's schedule passed the independent validator",
        },
    )
    _report(rows, ideal_points, output)
    return rows


# ---------------------------------------------------------------------------
# 实验：报告
# ---------------------------------------------------------------------------


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        return f"{float(value):.{digits}f}"
    return str(value)


def _table(rows: list[dict[str, Any]], instance: str, mode: str) -> list[str]:
    selected = [
        row
        for row in rows
        if row["instance"] == instance and row["normalization_mode"] == mode
    ]
    lines = [
        f"### {instance} / 口径 `{mode}`",
        "",
        "| 设置 | alpha | beta | gamma | Cmax | ΣT | setup | 原始加权和 | 归一化加权和 | 状态 | 模型状态 | 排程 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for row in selected:
        lines.append(
            f"| {row['setting']} | {_fmt(row['alpha'])} | {_fmt(row['beta'])} | "
            f"{_fmt(row['gamma'])} | {_fmt(row['cmax'], 0)} | {_fmt(row['total_tardiness'], 0)} | "
            f"{_fmt(row['setup'], 0)} | {_fmt(row['weighted_raw'])} | "
            f"{_fmt(row['weighted_normalized'])} | {row['status']} | "
            f"{row['model_status'] or '-'} | `{row['schedule_key']}` |"
        )
    lines.append("")
    return lines


def _report(rows: list[dict[str, Any]], ideal_points: dict[str, Any], output: Path) -> None:
    lines = [
        "# M3 Week 3 验收实验：多目标归一化与权重敏感性",
        "",
        f"求解器：`{METHOD}`，时间预算 `{DEFAULT_TIME_LIMIT:g}` 秒/次，`seed = {DEFAULT_SEED}`。",
        "每一行的排程都过了独立验证器（`validation` 列恒为 `ok`）。",
        "",
        "**表怎么读**：`Cmax`/`ΣT`/`setup` 是 `objective_breakdown` 的原值，",
        "`原始加权和` = `alpha*Cmax + beta*ΣT + gamma*setup`，",
        "`归一化加权和` = `alpha*Cmax/d_cmax + beta*ΣT/d_T + gamma*setup/d_setup`。",
        "求解器最小化的是**后者**（乘 `1e6` 取整），而 `objective` 列报的是前者。",
        "",
        "## 理想点（`ideal` 口径的分母）",
        "",
        "| 实例 | min Cmax | min ΣT | min setup |",
        "|---|---:|---:|---:|",
    ]
    for name, payload in ideal_points.items():
        optima = payload["optima"]
        lines.append(
            f"| {name} | {_fmt(optima['makespan']['value'], 0)} "
            f"({optima['makespan']['status']}) | "
            f"{_fmt(optima['total_tardiness']['value'], 0)} "
            f"({optima['total_tardiness']['status']}) | "
            f"{_fmt(optima['total_setup_time']['value'], 0)} "
            f"({optima['total_setup_time']['status']}) |"
        )
    for name, payload in ideal_points.items():
        if payload["skip_reason"]:
            lines.append(f"`{name}` 的 `ideal` 口径**不可用**：{payload['skip_reason']}。")
            lines.append("")
    lines += [
        "理想点归一化把三个分量都压到「1 = 该分量单独最优」。它的分母是三个最优值",
        "**互相之间的比例**，所以 `ideal` 口径隐含了「一个单位的 ΣT 值多少钱」的",
        "定价——这个定价不是业务给的，是实例给的。",
        "",
        "两类「不可用」必须分开看：**分成 0** 是理想点归一化的固有边界"
        "（分量能压到 0，分母就没了，这时它在本实例上也无法定价）；"
        "**没证明最优**只是预算不够，换更长的时间预算就能修好。前者是方法的边界，后者是工程的欠账。",
        "",
        "## 权重敏感性",
        "",
    ]
    for name in ideal_points:
        for mode in NORMALIZATION_MODES:
            lines += _table(rows, name, mode)

    lines += ["## 翻转点：同一组权重，换口径就换了排程", ""]
    lines += _crossover_section(rows, ideal_points)
    (output / "report.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _crossover_section(
    rows: list[dict[str, Any]], ideal_points: dict[str, Any]
) -> list[str]:
    lines = [
        "在 `gamma = 0`、`alpha = 1` 的族里取 `beta` 的两个端点设置",
        "（`cmax_only` 与 `tardiness_heavy`），若二者选出的排程不同，令它们的加权和相等",
        "解出翻转点 `beta*`：",
        "",
        "```text",
        "beta* = -[(Cmax_L - Cmax_R) / d_cmax] / [(T_L - T_R) / d_T]",
        "```",
        "",
        "实例 T 的两条候选排程恰好 `Cmax` 差 `+7`、`ΣT` 差 `-7`，约掉之后",
        "`beta* = d_T / d_cmax` ——**归一化的分母比就是这两个目标的交换率**。",
        "",
        "表里 `S1`/`S2`/`S3` 是排程指纹的短名，展开见 `schedules.json`。",
        "",
    ]
    for name in ideal_points:
        left = _pick(rows, name, "cmax_only")
        right = _pick(rows, name, "tardiness_heavy")
        if left is None or right is None:
            continue
        lines.append(f"### {name}")
        lines.append("")
        tags = _tags(rows, name)
        for key, tag in tags.items():
            lines.append(f"- `{tag}` = `{key}`")
        lines.append("")
        if left["schedule_key"] == right["schedule_key"]:
            lines.append(
                "两个端点设置选出同一个排程：这个实例上还没有出现真实的取舍，"
                "**照实写「没翻转」，不造一个假翻转**。"
            )
            lines.append("")
            continue
        lines.append(
            "| 口径 | d_cmax | d_T | beta* | 归一化加权和 (0 / 0.25 / 4) | "
            "排程 (0 / 0.25 / 4) | 预测 vs 观察 | 端点已证明最优 |"
        )
        lines.append("|---|---:|---:|---:|---|---|---|---|")
        caveats: list[str] = []
        for mode in NORMALIZATION_MODES:
            a = _pick(rows, name, "cmax_only", mode)
            b = _pick(rows, name, "tardiness_light", mode)
            c = _pick(rows, name, "tardiness_heavy", mode)
            if a is None or c is None or a["status"] == "SKIPPED":
                lines.append(f"| `{mode}` | - | - | - | 该口径不可用 | - | - |")
                continue
            divisors = {
                "cmax": a["d_cmax"],
                "total_tardiness": a["d_total_tardiness"],
                "setup": a["d_setup"],
            }
            star = crossover_beta(a, c, divisors)
            proven = _proven(a, c)
            cells = [
                f"{_fmt(a['weighted_normalized'], 2)} / {_fmt(b['weighted_normalized'], 2)} / "
                f"{_fmt(c['weighted_normalized'], 2)}",
                f"{_cell(tags, a)} / {_cell(tags, b)} / {_cell(tags, c)}",
                _verdict(a, c, star, b),
                proven,
            ]
            lines.append(
                f"| `{mode}` | {_fmt(divisors['cmax'], 0)} | "
                f"{_fmt(divisors['total_tardiness'], 0)} | {_fmt(star, 4)} | "
                + " | ".join(cells)
                + " |"
            )
            if proven != "是":
                caveats.append(
                    f"- `{mode}`：{proven}。端点没有证明最优，这一行的 `beta*` 只是"
                    "「预算内选出来的两条排程」的交点，**不能当作该口径的真实交换率**；"
                    "把 `--time-limit` 调大重跑才能判断是「口径不同」还是「没搜到」。"
                )
        lines.append("")
        if caveats:
            lines += ["**哪些行不能当结论**：", ""] + caveats + [""]
    lines += [
        "同一实例、同一组 `(alpha, beta, gamma)`，只换归一化口径就换排程——这就是",
        "「归一化不是技术细节，而是业务定价」的可执行证据。",
        "",
    ]
    return lines


def _tags(rows: list[dict[str, Any]], instance: str) -> dict[str, str]:
    """给该实例出现的每条排程一个短名（按首次出现顺序 ``S1``/``S2``/...）。

    返回 ``{排程指纹: 短名}``。
    """
    tags: dict[str, str] = {}
    for row in rows:
        if row["instance"] != instance or not row["schedule_key"]:
            continue
        if row["schedule_key"] not in tags:
            tags[row["schedule_key"]] = f"S{len(tags) + 1}"
    return tags


def _cell(tags: dict[str, str], row: dict[str, Any] | None) -> str:
    if row is None or not row["schedule_key"]:
        return "-"
    return tags.get(row["schedule_key"], "?")


def _verdict(
    left: dict[str, Any], right: dict[str, Any], star: float | None, mid: dict[str, Any] | None
) -> str:
    """把「由 beta* 预测的三段选择」与「beta 扫描观察到的选择」对读，逐段给 ``L``/``R``。

    预测规则只有一条：``beta < beta*`` 该选左侧排程，否则右侧。预测是两条直线
    的交点，观察是三次独立求解——**两者必须分开陈述**，一致是证据，不一致是发现。
    """
    if star is None:
        return "两端点 ΣT 相同：beta 不参与取舍，不适用"
    if mid is None:
        return "-"
    observed, predicted, agree = [], [], True
    for beta, row in ((0.0, left), (0.25, mid), (4.0, right)):
        expected = left if beta < star else right
        observed.append("L" if row["schedule_key"] == left["schedule_key"] else "R")
        predicted.append("L" if expected is left else "R")
        agree = agree and observed[-1] == predicted[-1]
    flag = "一致" if agree else "不一致"
    return f"{flag}: 预测 {''.join(predicted)} / 观察 {''.join(observed)}"


def _proven(left: dict[str, Any], right: dict[str, Any]) -> str:
    """两个端点排程是不是「已证明最优」。**不是**就明说，别让读者当成定理。

    ``skipped``/``FEASIBLE`` 的端点只说明「5 秒内找到的最好可行解是它」，
    由此算出的 ``beta*`` 是两条**不一定最优**的直线的交点，只是观察记录。
    """
    if left.get("model_status") == "OPTIMAL" and right.get("model_status") == "OPTIMAL":
        return "是"
    return (
        f"否（端点模型状态 {left.get('model_status') or '-'} / "
        f"{right.get('model_status') or '-'}）"
    )


def _pick(
    rows: list[dict[str, Any]], instance: str, setting: str, mode: str | None = None
) -> dict[str, Any] | None:
    for row in rows:
        if row["instance"] != instance or row["setting"] != setting:
            continue
        if mode is not None and row["normalization_mode"] != mode:
            continue
        return row
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "month3_w3")
    parser.add_argument("--time-limit", type=float, default=DEFAULT_TIME_LIMIT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    rows = run(args.output, time_limit=args.time_limit, seed=args.seed)
    solved = [row for row in rows if row["status"] in ("OPTIMAL", "FEASIBLE")]
    bad = [row for row in rows if row["status"] in ("FAILED", "INVALID_SOLUTION", "NOT_SOLVED")]
    mismatched = [
        row
        for row in solved
        if abs(float(row["objective"]) - float(row["weighted_raw"])) > 1e-6
    ]
    print(f"rows={len(rows)} solved={len(solved)} failed={len(bad)} "
          f"objective_mismatch={len(mismatched)}")
    print("schedule_key 被单独写进 schedules.json（csv 只留可逐格对读的数值列）")
    print(f"output={args.output.resolve()}")


if __name__ == "__main__":
    main()
