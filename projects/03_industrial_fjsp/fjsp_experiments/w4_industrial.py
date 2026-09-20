"""Week 4 实验：**逐条约束消融**（base → +setup → +calendar → +qualification → +worker → +locked）。

    python -m fjsp_experiments.w4_industrial --output artifacts/month3_w4

沿用 M2 批次那条顺序纪律：**版本状态必须在创建输出目录之前捕获**。否则刚写进输出
目录的 ``config.json`` 会被 git 当成未跟踪文件，``working_tree_dirty`` 恒为 True，
这个标记就废了。

消融的做法是**累加**而不是**删除**：从一个只有「机器相关工时 + 柔性 + 释放/交期」
的基础实例出发，每次加上一条约束，得到一个约束集越来越大的实例序列。

这样做的关键好处是**单调性可检验**：每加一条约束，可行域只会变小（时间窗、资质、
锁定都是限制；强制占用工序资源也是限制），所以**目标函数值只可能变差（变大）或者
不变**。这条性质如果被观测到违反，就说明有一处建模写错了方向 —— 比逐条对比数字更
强的检查。报告里会显式核对它。

报告纪律（M1 起没变过）：目标值由**独立评估器**重算，不由求解器自报；``OPTIMAL``
只说明求解器证明了自己的模型最优，排程可行性另由独立验证器判定；**某条约束没有
改变最优值时，直接写「没有改变」**，不编一个「轻微影响」的说法。
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
import time
import traceback
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fjsp_core.models import (
    Calendar,
    FJSPInstance,
    Job,
    Machine,
    Maintenance,
    Operation,
    Qualification,
    Setup,
    Worker,
)
from fjsp_core.objective import evaluate, parse_weights
from fjsp_core.result import ShopResult, validate_result
from fjsp_io.generator import generate_instance
from fjsp_io.parser import save_json_instance
from fjsp_shop.registry import available, describe_missing, get, load_week_modules

from fjsp_experiments.benchmark import (
    ROOT,
    SCHEMA_VERSION,
    _git,
    source_hash,
    write_csv,
    write_json,
)

#: 消融链。顺序就是「约束一层层加上去」的顺序，也是报告里的行顺序。
STAGES: tuple[tuple[str, str], ...] = (
    ("base", "机器相关工时 + 柔性 + 释放/交期"),
    ("+setup", "sequence-dependent setup（工序族换型）"),
    ("+calendar", "机器日历（可用窗）"),
    ("+qualification", "机器资质（谁能做）"),
    ("+worker", "次生资源能力 + 容量（谁能开、同时开几个）"),
    ("+locked", "WIP / 锁定工序（已在机不可再选）"),
)

TIME_LIMIT = 15.0


# ---------------------------------------------------------------------------
# 消融实例：同一份工序数据，逐层加约束
# ---------------------------------------------------------------------------
def ablation_instance(stage: str) -> FJSPInstance:
    """第 ``stage`` 层（含）之前的全部约束都打开。

    工序数据自始至终不变 —— 消融比较的必须是同一批活，否则数字没法解释。
    """
    order = [name for name, _ in STAGES]
    level = order.index(stage)

    # --- 基础：只有 FJSP 本身（机器相关工时 + 柔性 + 释放/交期）-------------
    jobs = (
        Job("J0", ("A", "B"), release_time=0, due_date=14, weight=1.0),
        Job("J1", ("C", "D"), release_time=0, due_date=12, weight=1.0),
    )
    operations = (
        # A、B 同族 F0；C、D 同族 F1 —— 这样 batching 才有的可谈。
        Operation("A", "J0", 0, (("M0", 5), ("M1", 4)), family="F0"),
        Operation("B", "J0", 1, (("M0", 6), ("M1", 5)), family="F0"),
        Operation("C", "J1", 0, (("M0", 4), ("M1", 6)), family="F1"),
        Operation("D", "J1", 1, (("M0", 5), ("M1", 5)), family="F1"),
    )
    instance = FJSPInstance(
        jobs=jobs,
        operations=operations,
        # 基础层**不能**写 calendar_id：指向一张不存在的日历会被 validate_instance
        # 直接判为非法实例（Diagnostic: unknown calendar），消融链第一行就废了。
        machines=(Machine("M0", "M0"), Machine("M1", "M1")),
    )

    if level >= 1:  # +setup
        instance = replace(
            instance,
            setups=(
                Setup("F0", "F0", 0),
                Setup("F0", "F1", 3),
                Setup("F1", "F0", 4),
                Setup("F1", "F1", 0),
            ),
        )
    if level >= 2:  # +calendar
        # M0 只在 [0,10) 可用；M1 在 [0,10) 与 [16,40) 两段可用。
        instance = replace(
            instance,
            calendars=(
                Calendar("CAL0", ((0, 10),)),
                Calendar("CAL1", ((0, 10), (16, 40))),
            ),
            machines=(Machine("M0", "M0", calendar_id="CAL0"),
                      Machine("M1", "M1", calendar_id="CAL1")),
        )
    if level >= 3:  # +qualification
        # 没有 (M0, F1)：F1 的两道工序（C、D）只能上 M1。
        instance = replace(
            instance,
            qualifications=(
                Qualification("M0", "F0"),
                Qualification("M1", "F0"),
                Qualification("M1", "F1"),
            ),
        )
    if level >= 4:  # +worker
        instance = replace(
            instance,
            workers=(
                Worker("W0", "小张", ("M0",), 1),
                Worker("W1", "小李", ("M1",), 1),
                Worker("W2", "多面手", ("M0", "M1"), 1),
            ),
        )
    if level >= 5:  # +locked
        # C 已经上机：机器与开工时刻都钉死。start=20 落在 M1 的第二个窗内，
        # 所以它不与日历冲突 —— 消融要看的是「锁定本身」的作用。
        #
        # 为什么挑 20 而不是自然最优里的 16：**锁定必须真的挡路，这一层才有信息量**。
        # 不加锁时 C 自然排在 [16,22)；锁到 20 之后 C 与它后面的 D 都被推后，
        # 目标值从 27 变成 31。这是一次「已经做出的生产决策」的代价，
        # 也正是 WIP 锁定在真实车间里的样子。
        instance = replace(
            instance,
            operations=tuple(
                replace(op, locked_machine_id="M1", locked_start=20)
                if op.id == "C"
                else op
                for op in instance.operations
            ),
        )
    return instance


# ---------------------------------------------------------------------------
# 求解与记录
# ---------------------------------------------------------------------------
def _row(
    run_id: str,
    instance: FJSPInstance,
    method: str,
    stage: str,
    objective: str,
    seed: int,
    time_limit: float,
) -> dict[str, Any]:
    spec = {"objective": objective, "time_limit": time_limit, "seed": seed}
    row: dict[str, Any] = {
        "run_id": run_id,
        "instance": instance.meta.get("name", "ablation"),
        "stage": stage,
        "method": method,
        "objective_name": objective,
        "seed": seed,
        "time_limit": time_limit,
    }
    started = time.perf_counter()
    try:
        result: ShopResult = get(method)(instance, dict(spec))
    except Exception as exc:  # 单次求解失败不能中断整轮
        row.update(
            {
                "status": "FAILED",
                "objective": None,
                "best_bound": None,
                "gap": None,
                "iterations": None,
                "build_time": None,
                "solve_time": None,
                "wall_time": round(time.perf_counter() - started, 6),
                "cmax": None,
                "total_tardiness": None,
                "setup": None,
                "validation": "",
                "failure_reason": f"{type(exc).__name__}: {exc}",
                "solver_reported_objective": None,
                "objective_matches_solver": None,
            }
        )
        row["failure_traceback"] = traceback.format_exc()[-400:]
        return row

    diagnostics = validate_result(instance, result)
    row.update(result.to_row())
    row["wall_time"] = round(time.perf_counter() - started, 6)
    row["validation"] = "; ".join(diagnostics)
    row["failure_reason"] = ""
    if diagnostics:
        row["status"] = "INVALID_SOLUTION"
        row["failure_reason"] = (
            f"independent validator rejected the schedule: {diagnostics[:3]}"
        )
    row["solver_reported_objective"] = (
        None if result.schedule is None else round(result.objective, 6)
    )
    # 独立重算：不信任求解器读数（M1 起的纪律）
    if result.schedule is not None:
        recomputed = evaluate(
            instance,
            result.schedule,
            objective,
            parse_weights(spec),
        )
        row["objective_recomputed"] = round(recomputed, 6)
        row["objective_matches_solver"] = abs(recomputed - result.objective) < 1e-6
    else:
        row["objective_recomputed"] = None
        row["objective_matches_solver"] = None
    row["cp_model_presolve"] = result.detail.get("cp_model_presolve")
    row["setup_encoding"] = result.detail.get("setup_encoding")
    row["model_variables"] = result.detail.get("model_variables")
    return row


def run(output: Path) -> list[dict[str, Any]]:
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output must be empty (preserve previous experiments): {output}")

    # --- 版本状态：必须在创建输出目录之前 -------------------------------
    frozen_commit = _git("rev-parse", "HEAD")
    frozen_dirty = bool(_git("status", "--porcelain"))
    frozen_source = source_hash()

    output.mkdir(parents=True, exist_ok=True)
    (output / "instances").mkdir(exist_ok=True)

    module_failures = load_week_modules()
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
            "time_limit_seconds": TIME_LIMIT,
            "unavailable_modules": module_failures,
            "registered_methods": available(),
            "ablation_chain": [
                {"stage": name, "adds": note} for name, note in STAGES
            ],
            "objective": "makespan",
            "seed": 0,
            "budget_unit": "one solver call under a shared wall-clock time limit",
        },
    )

    rows: list[dict[str, Any]] = []

    # --- 实验 1：逐条约束消融（同一份工序数据，约束逐层累加）-------------
    for stage, _note in STAGES:
        instance = ablation_instance(stage)
        instance = replace(instance, meta={"name": "ablation"})
        save_json_instance(instance, output / "instances" / f"ablation{stage}.json")
        for method in ("fjsp_cpsat_full", "fjsp_cpsat_qualified"):
            rows.append(
                _row(
                    f"ablation__{stage}__{method}",
                    instance,
                    method,
                    stage,
                    "makespan",
                    seed=0,
                    time_limit=TIME_LIMIT,
                )
            )

    # --- 实验 2：batch 实例上两个方法的正面对比 --------------------------
    batch_instances = {
        "ind_worker": (
            dict(
                seed=202, jobs=6, machines=4, operations_per_job=3,
                flexibility=2, worker_count=2, setup_families=2,
            ),
            "makespan",
        ),
        "ind_qualified": (
            dict(
                seed=203, jobs=8, machines=5, operations_per_job=3, flexibility=3,
                setup_families=3, calendar_windows=1, maintenance_count=2,
                worker_count=3, locked_count=1, release_max=6,
            ),
            "weighted_sum",
        ),
    }
    for name, (kwargs, objective) in batch_instances.items():
        instance = generate_instance(**kwargs)
        instance = replace(instance, meta={"name": name})
        save_json_instance(instance, output / "instances" / f"{name}.json")
        for method in ("fjsp_cpsat_full", "fjsp_cpsat_qualified"):
            rows.append(
                _row(
                    f"{name}__main__{method}",
                    instance,
                    method,
                    "batch",
                    objective,
                    seed=0,
                    time_limit=TIME_LIMIT,
                )
            )

    write_csv(output / "results.csv", rows)
    write_json(
        output / "ablation.json",
        _ablation_payload(rows),
    )
    _report(rows, output)
    return rows


def _ablation_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """消融链的机器可读版本：每层目标值、相对上一层的增量、以及单调性核对。"""
    def chain(method: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        previous: float | None = None
        for stage, note in STAGES:
            selected = [
                row
                for row in rows
                if row["stage"] == stage and row["method"] == method
            ]
            row = selected[0] if selected else None
            value = None if row is None else row.get("objective")
            if value is not None:
                value = float(value)
            out.append(
                {
                    "stage": stage,
                    "adds": note,
                    "method": method,
                    "status": None if row is None else row["status"],
                    "objective": value,
                    "delta_vs_previous": (
                        None if value is None or previous is None else round(value - previous, 6)
                    ),
                    "changed": (
                        None if value is None or previous is None else value != previous
                    ),
                    "wall_time": None if row is None else row["wall_time"],
                    "solve_time": None if row is None else row["solve_time"],
                    "iterations": None if row is None else row["iterations"],
                    "best_bound": None if row is None else row["best_bound"],
                    "validation": None if row is None else row["validation"],
                }
            )
            if value is not None:
                previous = value
        return out

    payload = {
        "objective": "makespan",
        "seed": 0,
        "time_limit": TIME_LIMIT,
        "note": (
            "每加一条约束，可行域只会变小，所以目标值只会变大或不变。"
            "违反这条单调性的行一定是建模写错了方向。"
        ),
        "chains": {method: chain(method) for method in ("fjsp_cpsat_full", "fjsp_cpsat_qualified")},
    }
    for method, items in payload["chains"].items():
        values = [item["objective"] for item in items if item["objective"] is not None]
        payload.setdefault("monotone_non_decreasing", {})[method] = all(
            later >= earlier for earlier, later in zip(values, values[1:])
        )
    return payload


def _report(rows: list[dict[str, Any]], output: Path) -> None:
    payload = _ablation_payload(rows)
    lines = [
        "# M3 Week 4 实验：逐条工业约束的消融（脚本生成）",
        "",
        f"时间预算 {TIME_LIMIT:g} 秒／次，seed 0，单线程。目标函数 `makespan`。",
        "**同一份工序数据**，约束逐层累加：`base` → `+setup` → `+calendar` →",
        "`+qualification` → `+worker` → `+locked`。",
        "",
        "每加一条约束可行域只会变小，所以目标值**只会变大或不变**。这条单调性",
        "同时是正确性检查：违反它的那一行一定是建模方向写错了。",
        "",
    ]

    for method, items in payload["chains"].items():
        lines += [
            f"## 消融链：`{method}`",
            "",
            "| 阶段 | 新增约束 | 状态 | 目标值 | 相对上一层 | 目标值变化 | wall(s) | 分支数 |",
            "|---|---|---|---:|---:|---|---:|---:|",
        ]
        for item in items:
            value = "—" if item["objective"] is None else f"{item['objective']:g}"
            delta = (
                "—"
                if item["delta_vs_previous"] is None
                else f"{item['delta_vs_previous']:+g}"
            )
            if item["changed"] is None:
                changed = "—"
            elif item["changed"]:
                changed = "**变了**"
            else:
                changed = "没有改变"
            wall = "—" if item["wall_time"] is None else f"{item['wall_time']:.2f}"
            iters = "—" if item["iterations"] is None else str(item["iterations"])
            lines.append(
                f"| `{item['stage']}` | {item['adds']} | {item['status']} | {value} | "
                f"{delta} | {changed} | {wall} | {iters} |"
            )
        mono = payload["monotone_non_decreasing"][method]
        lines += [
            "",
            f"单调性核对（目标值随约束增加不下降）：**{'通过' if mono else '未通过'}**。",
            "",
        ]

    lines += [
        "## 怎么读这张表",
        "",
        "* 「没有改变」是**结论**，不是「测不出来」。约束加上去之后可行域一样会缩小，",
        "  只是这个实例的最优解恰好落在缩小后的区域里，所以目标值没动。",
        "  约束是否真的生效，看的是验证器的诊断标签与 `MODEL_COVERAGE` 表，不是这里的数字。",
        "* `fjsp_cpsat_full` 与 `fjsp_cpsat_qualified` 只差**换型的编码方式**（精确槽位链 vs",
        "  区间膨胀）。两者在同一行的差值是「保守编码切掉了多少」。",
        "* 目标值由独立评估器重算；`OPTIMAL` 只说明求解器证明了自己的模型最优，",
        "  排程可行性另由独立验证器判定。",
        "* `best_bound` 为空表示该行没有可用下界（见 `fjsp_core.result` 的约定：",
        "  **没有界就写空，不写 0**）。",
        "",
        "## 明细",
        "",
        "| run_id | 方法 | 阶段 | 状态 | 目标值 | 独立重算 | 一致 | 验证 |",
        "|---|---|---|---|---:|---:|---|---|",
    ]
    for row in rows:
        value = "—" if row.get("objective") is None else f"{float(row['objective']):g}"
        recomputed = (
            "—"
            if row.get("objective_recomputed") is None
            else f"{float(row['objective_recomputed']):g}"
        )
        match = {True: "是", False: "**否**", None: "—"}[row.get("objective_matches_solver")]
        lines.append(
            f"| `{row['run_id']}` | `{row['method']}` | `{row['stage']}` | {row['status']} | "
            f"{value} | {recomputed} | {match} | {row.get('validation') or 'OK'} |"
        )
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts" / "month3_w4"
    )
    args = parser.parse_args()
    rows = run(args.output)
    failed = sum(1 for r in rows if r["status"] in ("FAILED", "INVALID_SOLUTION"))
    print(f"runs={len(rows)}, failed={failed}, output={args.output.resolve()}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
