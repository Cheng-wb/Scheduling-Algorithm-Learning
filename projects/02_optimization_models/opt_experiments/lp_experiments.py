"""Week 1 实验驱动：把 LP / 对偶 / 互补松弛 / 敏感性的证据落到 ``artifacts/month2_w1/``。

    python -m opt_experiments.lp_experiments

与 M2 的批次纪律一致（配置驱动换成清单驱动、先算后写、失败留痕、不覆盖非空目录），
并针对 LP 补三件事：

1. **对偶是独立求解出来的。** ``dual_objective`` 不是抄 primal 的目标值，而是把
   :func:`opt_models.lp_models.build_dual` 造出来的对偶 LP 单独跑一遍的结果。
   两者相等是强对偶的一次**数值对拍**，不是同义反复。
2. **没有的信息写空。** 不可行模型的影子价格、reduced cost 一律留空——求解器在
   没有最优基时返回的 0 是噪声。把它写成 0 会让「互补松弛全部成立」看起来通过。
3. **容差进报告。** :data:`TOLERANCE` 是事后对拍用的阈值，报告里显式写出用了多少、
   以及实测到的最大残差是多少，让读者能自己判断这 1e-9 是不是合理。

产物：``results.csv``（一行一个 LP 场景）、``complementarity.csv``（互补松弛逐对明细）、
``sensitivity.csv``（影子价格的局部有效范围）、``metadata.json``、``report.md``。
"""

from __future__ import annotations

import argparse
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opt_experiments.benchmark import source_hash, write_csv, write_json
from opt_models.lp_models import (
    ASSIGNMENT_BASE,
    DEFAULT_TOLERANCE,
    PRODUCTION_2D,
    PRODUCTION_BASE,
    PRODUCTION_INFEASIBLE,
    TRANSPORT_BASE,
    LPModel,
    LPSolution,
    build_assignment_lp,
    build_dual,
    build_production_lp,
    build_transportation_lp,
    complementarity_rows,
    dual_feasibility_violation,
    duality_gap,
    max_complementarity_violation,
    max_reduced_cost_identity_error,
    production_capacity_grid,
    production_demand_grid,
    production_profit_grid,
    solve_model,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts" / "month2_w1"
SCHEMA_VERSION = 1

#: 事后对拍的容差。GLOP 自己的原始/对偶可行性容差在 1e-8 量级，这里取更严的 1e-9：
#: 容差只用来判断「实测残差是不是数值尘埃」，不用来放宽求解器行为。
TOLERANCE = DEFAULT_TOLERANCE


# --- 场景清单 --------------------------------------------------------------


def core_scenarios() -> list[tuple[str, str, LPModel, str]]:
    """(name, kind, model, note)：Week 1 的核心场景。"""
    return [
        (
            "prod_2d",
            "production",
            build_production_lp(PRODUCTION_2D),
            "两变量两约束：Day 1 用它枚举极点",
        ),
        (
            "prod_base",
            "production",
            build_production_lp(PRODUCTION_BASE),
            "三产品两资源 + 三条需求上限：本周主算例",
        ),
        (
            "prod_infeasible",
            "production",
            build_production_lp(PRODUCTION_INFEASIBLE),
            "x_P2 <= 50 与 x_P2 >= 60 直接冲突：故意不可行",
        ),
        (
            "transport_base",
            "transportation",
            build_transportation_lp(TRANSPORT_BASE),
            "2 源 3 汇产销平衡：等式行、自由对偶变量",
        ),
        (
            "assign_base",
            "assignment",
            build_assignment_lp(ASSIGNMENT_BASE),
            "3x3 指派：LP relaxation 恰好给出整数解",
        ),
    ]


def sensitivity_scenarios() -> list[tuple[str, str, LPModel, dict[str, Any]]]:
    """Day 5 的敏感性场景：(name, kind, model, 扰动元数据)。"""
    items: list[tuple[str, str, LPModel, dict[str, Any]]] = []
    baseline = solve_model(build_production_lp(PRODUCTION_BASE))
    for resource in ("M", "L"):
        for data in production_capacity_grid(resource):
            index = PRODUCTION_BASE.resources.index(resource)
            value = data.capacity[index]
            base_value = PRODUCTION_BASE.capacity[index]
            items.append(
                (
                    f"cap_{resource}_{value:g}",
                    "sensitivity_capacity",
                    build_production_lp(data),
                    {
                        "axis": f"capacity_{resource}",
                        "kind_axis": "rhs",
                        "value": value,
                        "baseline_value": base_value,
                        "baseline_objective": baseline.objective,
                        "baseline_shadow": baseline.dual[f"cap_{resource}"],
                        "shadow_row": f"cap_{resource}",
                    },
                )
            )
    for data in production_profit_grid("P2"):
        index = PRODUCTION_BASE.products.index("P2")
        value = data.profit[index]
        items.append(
            (
                f"profit_P2_{value:g}",
                "sensitivity_profit",
                build_production_lp(data),
                {
                    "axis": "profit_P2",
                    "kind_axis": "cost",
                    "value": value,
                    "baseline_value": PRODUCTION_BASE.profit[index],
                    "baseline_objective": baseline.objective,
                    "baseline_shadow": baseline.reduced_cost["x_P2"],
                    "shadow_row": "x_P2",
                },
            )
        )
    for data in production_demand_grid("P1"):
        index = PRODUCTION_BASE.products.index("P1")
        value = data.max_demand[index]
        items.append(
            (
                f"demand_P1_{value:g}",
                "sensitivity_demand",
                build_production_lp(data),
                {
                    "axis": "max_demand_P1",
                    "kind_axis": "rhs",
                    "value": value,
                    "baseline_value": PRODUCTION_BASE.max_demand[index],
                    "baseline_objective": baseline.objective,
                    "baseline_shadow": baseline.dual["demand_P1"],
                    "shadow_row": "demand_P1",
                },
            )
        )
    return items


# --- 单场景记录 ------------------------------------------------------------


def _empty_row(name: str, kind: str, model: LPModel, note: str) -> dict[str, Any]:
    return {
        "name": name,
        "kind": kind,
        "note": note,
        "sense": model.sense,
        "num_variables": model.num_variables,
        "num_rows": model.num_rows,
        "status": "",
        "primal_objective": None,
        "dual_objective": None,
        "duality_gap": None,
        "dual_status": "",
        "dual_involution_ok": None,
        "max_constraint_residual": None,
        "max_reduced_cost_identity": None,
        "max_complementarity": None,
        "max_dual_feasibility_violation": None,
        "complementarity_ok": None,
        "solve_time": None,
    }


def evaluate(name: str, kind: str, model: LPModel, note: str = "") -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """跑一个场景，返回 (结果行, 互补松弛明细)。

    求解顺序刻意是「先解原始、再看状态、最后才决定要不要碰对偶」：状态不是
    ``OPTIMAL`` 时根本没有影子价格可读，此时去构造对偶只会得到一串噪声。
    """
    row = _empty_row(name, kind, model, note)
    solution: LPSolution = solve_model(model)
    row["status"] = solution.status
    row["primal_objective"] = solution.objective
    row["solve_time"] = round(solution.solve_time, 6)

    if not solution.dual_available:
        # 不可行 / 未求解：不给对偶，也不给任何「0」填充。
        # 对偶模型仍然构造并求解一次——「原问题没有最优解时对偶是什么状态」
        # 本身就是弱对偶的一条证据，只是它的状态不能反推原问题的可行性（见报告）。
        dual_model = build_dual(model)
        dual_solution = solve_model(dual_model)
        row["dual_status"] = dual_solution.status
        row["dual_objective"] = dual_solution.objective
        return row, []

    dual_model = build_dual(model)
    dual_solution = solve_model(dual_model)
    row["dual_status"] = dual_solution.status
    row["dual_objective"] = dual_solution.objective
    row["duality_gap"] = duality_gap(solution.objective, dual_solution.objective)
    row["max_constraint_residual"] = solution.max_constraint_residual
    row["max_reduced_cost_identity"] = max_reduced_cost_identity_error(model, solution)
    row["max_complementarity"] = max_complementarity_violation(model, solution)
    row["max_dual_feasibility_violation"] = dual_feasibility_violation(model, solution)
    complementarity = max_complementarity_violation(model, solution)
    row["complementarity_ok"] = (
        None if complementarity is None else bool(complementarity <= TOLERANCE)
    )

    # 对偶的对偶应当等价于原问题：这是对 build_dual 结构正确性的一次无参检查。
    involution = solve_model(build_dual(dual_model))
    row["dual_involution_ok"] = (
        involution.objective is not None
        and abs(float(involution.objective) - float(solution.objective)) <= 1e-6
    )

    detail = [
        {"scenario": name, **item}
        for item in complementarity_rows(model, solution)
    ]
    return row, detail


def _sensitivity_row(base_row: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """把敏感性场景的结果行补上「预测 vs 实测」两列。

    **两类扰动的预测规则不一样**，混用会得出错误结论：

    ``rhs_linear``（扰动产能、需求上限）
        预测 = 基准目标 + 基准影子价格 x 扰动量。只在**基不变的区间**内成立。

    ``reduced_cost_breakeven``（扰动单位利润）
        reduced cost 不是斜率而是**盈亏平衡价**：在 ``c_j`` 升到
        ``基准利润 - rc_j`` 之前，``x_j`` 一直是 0，目标值**不变**；
        越过这个点目标才开始上升。把 rc 当斜率用（``基准目标 + rc x delta``）
        会预测出「降价 5 反而多赚 25」这种明显的错。
    """
    value = float(meta["value"])
    baseline_value = float(meta["baseline_value"])
    delta = value - baseline_value
    shadow = float(meta["baseline_shadow"])
    baseline_objective = float(meta["baseline_objective"])
    observed = base_row["primal_objective"]

    if meta["kind_axis"] == "cost":
        break_even = baseline_value - shadow  # rc = c_j - z_j < 0，需上升 |rc| 才进入基
        inside = value <= break_even + 1e-9
        predicted = baseline_objective if inside else None
        if observed is None:
            holds = None
        elif inside:
            holds = bool(abs(float(observed) - baseline_objective) <= 1e-6)
        else:
            holds = bool(float(observed) > baseline_objective + 1e-6)
        rule = "reduced_cost_breakeven"
    else:
        break_even = None
        predicted = baseline_objective + shadow * delta
        holds = (
            None
            if observed is None
            else bool(abs(float(observed) - predicted) <= 1e-6)
        )
        rule = "rhs_linear"

    return {
        **base_row,
        "axis": meta["axis"],
        "value": value,
        "baseline_value": baseline_value,
        "delta": delta,
        "baseline_shadow_price": shadow,
        "prediction_rule": rule,
        "break_even_value": break_even,
        "predicted_objective": predicted,
        "prediction_error": (
            None if predicted is None or observed is None else abs(float(observed) - predicted)
        ),
        "prediction_holds": holds,
        "shadow_row": meta["shadow_row"],
    }


# --- 元数据与报告 ----------------------------------------------------------


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
        )
        return out.stdout.strip()
    except OSError:
        return ""


def _build_metadata(output: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": _git("rev-parse", "HEAD"),
        "working_tree_dirty": bool(_git("status", "--porcelain")),
        "source_sha256": source_hash(),
        "tolerance": TOLERANCE,
        "tolerance_rationale": (
            "GLOP 的原始/对偶可行性容差在 1e-8 量级；事后对拍取更严的 1e-9，"
            "用来区分「数值尘埃」与「真的违反」。"
        ),
        "scenarios": len(rows),
        "scenarios_with_optimal": sum(1 for r in rows if r["status"] == "OPTIMAL"),
        "glop_status_caveat": (
            "实测：本环境的 GLOP 后端对无界 LP 也返回状态码 2（INFEASIBLE），"
            "UNBOUNDED（3）不会出现。状态 2 只能读作「没有最优解」。"
        ),
        "solver_backend": "OR-Tools pywraplp / GLOP (continuous LP)",
        "output_dir": str(output.resolve()),
    }


def _fmt(value: Any, digits: int = 10) -> str:
    """空值打印成 ``—``：报告里不能出现「0 表示没测」。"""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.{digits}g}"


def build_report(
    rows: list[dict[str, Any]],
    sensitivity_rows: list[dict[str, Any]],
    production_duals: dict[str, float],
) -> str:
    """生成 report.md。所有数字都来自本次运行，没有一个是手写的。"""
    lines = [
        "# M2 Week 1 实验汇总（脚本生成）",
        "",
        f"容差 `TOLERANCE = {TOLERANCE:g}`。空值表示**该方法不提供**这个量，",
        "不是 0——本文件里没有任何一个 `0.0` 是「没测」的意思。",
        "",
        "## 1. 场景与目标值",
        "",
        "`primal` 与 `dual` 是**两次独立求解**（对偶模型由 `build_dual` 构造），",
        "两者相等是强对偶的数值对拍。`dual_involution_ok` 检查「对偶的对偶」",
        "是否回到原问题的目标值。",
        "",
        "| 场景 | 类型 | 状态 | 变量 | 约束 | primal | dual | \\|gap\\| | 对偶的对偶 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['name']} | `{row['kind']}` | {row['status']} | {row['num_variables']} | "
            f"{row['num_rows']} | {_fmt(row['primal_objective'])} | {_fmt(row['dual_objective'])} | "
            f"{_fmt(row['duality_gap'], 3)} | {_fmt(row['dual_involution_ok'])} |"
        )

    lines += [
        "",
        "## 2. 数值对拍",
        "",
        "`max_constraint_residual` 是原始可行性残差（由本模块按系数**重算**，",
        "不是抄求解器的活动值）；`max_reduced_cost_identity` 检查",
        "`reduced_cost = c_j - Σ a_ij y_i` 这条符号约定；`max_complementarity`",
        "是全部 `\\|x*rc\\|` 与 `\\|slack*y\\|` 的最大值。",
        "",
        "| 场景 | 可行性残差 | rc 恒等式误差 | 互补松弛 | 对偶可行违反 | 互补松弛通过 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        if row["status"] != "OPTIMAL":
            continue
        lines.append(
            f"| {row['name']} | {_fmt(row['max_constraint_residual'], 3)} | "
            f"{_fmt(row['max_reduced_cost_identity'], 3)} | {_fmt(row['max_complementarity'], 3)} | "
            f"{_fmt(row['max_dual_feasibility_violation'], 3)} | {_fmt(row['complementarity_ok'])} |"
        )

    lines += [
        "",
        "## 3. 生产计划的影子价格（`prod_base`）",
        "",
        "| 约束 | 影子价格 |",
        "|---|---:|",
    ]
    for key, value in production_duals.items():
        lines.append(f"| `{key}` | {_fmt(value, 12)} |")
    lines += [
        "",
        "三条需求上限都没顶住（松弛量大于 0），所以它们的影子价格是 0——",
        "**不是**「这些约束没用」，而是「在现在这个解上，放松一单位不会让目标变大」。",
        "",
        "## 4. 敏感性：影子价格的局部有效范围（Day 5）",
        "",
        "两类扰动用**两条不同的预测规则**，混用会得出错误结论：",
        "",
        "* `rhs_linear`（扰动产能、需求上限）：预测 = 基准目标 + 基准影子价格 x `delta`，",
        "  只在基不变的区间内成立，跨过折点立刻失效；",
        "* `reduced_cost_breakeven`（扰动单位利润）：reduced cost 不是斜率而是**盈亏平衡价**，",
        "  在利润升到 `break_even` 之前 `x_j` 保持为 0、目标值不变。把 rc 当斜率用会",
        "  预测出「降价反而多赚」这种明显的错。",
        "",
        "| 场景 | 轴 | 取值 | delta | 影子价格(基准) | 盈亏平衡值 | 规则 | 实测目标 | 预测目标 | 预测误差 | 预测成立 |",
        "|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|",
    ]
    for row in sensitivity_rows:
        lines.append(
            f"| {row['name']} | `{row['axis']}` | {row['value']:g} | {row['delta']:+g} | "
            f"{row['baseline_shadow_price']:.10g} | {_fmt(row['break_even_value'])} | "
            f"`{row['prediction_rule']}` | {_fmt(row['primal_objective'])} | "
            f"{_fmt(row['predicted_objective'])} | {_fmt(row['prediction_error'], 3)} | "
            f"{_fmt(row['prediction_holds'])} |"
        )

    lines += [
        "",
        "## 5. 求解器状态码的一条实测限制",
        "",
        "`prod_infeasible` 的状态是 `INFEASIBLE`，但**这个状态码不能证明可行域为空**：",
        "本环境的 GLOP 后端对无界 LP 也返回同一个状态码（实测 `min -x, x >= 0`",
        "同样返回 2）。该算例「真的不可行」是靠手算确认的——",
        "`x_P2 <= 50` 与 `x_P2 >= 60` 直接冲突。",
        "",
        "## 6. 复现",
        "",
        "在项目目录下运行：",
        "",
        "```bash",
        "python -m opt_experiments.lp_experiments",
        "```",
        "",
        "输出目录必须为空或不存在；重跑前请先自行移走旧目录。",
        "",
    ]
    return "\n".join(lines)


# --- 入口 ------------------------------------------------------------------


def run(output: Path) -> list[dict[str, Any]]:
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output must be empty (preserve previous experiments): {output}")
    output.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    complementarity: list[dict[str, Any]] = []
    for name, kind, model, note in core_scenarios():
        row, detail = evaluate(name, kind, model, note)
        rows.append(row)
        complementarity.extend(detail)

    sensitivity_rows: list[dict[str, Any]] = []
    for name, kind, model, meta in sensitivity_scenarios():
        base_row, detail = evaluate(name, kind, model, meta["axis"])
        rows.append(base_row)
        complementarity.extend(detail)
        sensitivity_rows.append(_sensitivity_row(base_row, meta))

    production_model = build_production_lp(PRODUCTION_BASE)
    production_solution = solve_model(production_model)
    production_duals = {
        row_name: production_solution.dual.get(row_name)
        for row_name in production_model.constraint_names
    }

    write_csv(output / "results.csv", rows)
    write_csv(output / "complementarity.csv", complementarity)
    write_csv(output / "sensitivity.csv", sensitivity_rows)
    write_json(output / "metadata.json", _build_metadata(output, rows))
    (output / "report.md").write_text(
        build_report(rows, sensitivity_rows, production_duals), encoding="utf-8"
    )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = run(args.output)
    solved = sum(1 for row in rows if row["status"] == "OPTIMAL")
    print(
        f"scenarios={len(rows)}, optimal={solved}, "
        f"tolerance={TOLERANCE:g}, output={args.output.resolve()}"
    )


if __name__ == "__main__":
    main()
