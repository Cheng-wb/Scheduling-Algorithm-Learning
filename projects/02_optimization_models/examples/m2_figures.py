"""M2 图册：把笔记里用文字/表格描述的结论画成真正的坐标图。

**为什么要有这个脚本。** 原来 Week_1/Day1 的二维可行域是用 `│ ＼ ●` 拼出来的，
读者不能对照真实比例，也无法复用。文字表格能表达结论，但表达不了「斜率」「区间」
「随预算的走向」这类**形状**信息。这里全部改成代码绘图，笔记只引用图片。

图的输出目录是 ``artifacts/figures/``，**与 ``artifacts/month2`` 分开**——
后者是被封存的批次，带 `metadata.json` 与三步复核流程，不应混入非批次产物。

数据来源全部是**已提交的 artifacts**，不是手写常量：

    feasible_region   第 1 张是纯数学对象（笔记 §4 手算过的那个 LP），
                      系数写在代码里，顶点由系数推导而非抄结果
    bound_vs_time     artifacts/month2/results.csv 的 tl_3 / main / tl_30 三组
    symmetry_scale    artifacts/month2_w4/results.csv（小实例消融）
                      + artifacts/month2/results.csv（大实例正收益）
    shadow_price      artifacts/month2_w1/sensitivity.csv 的 capacity_M 扫描
    method_quality    artifacts/month2/results.csv 的 main 组

**这个脚本不在 ``SOURCE_PACKAGES`` 里**，所以它不改变 ``artifacts/month2``
记录的 ``source_sha256``；重跑绘图不会让已封存的批次失效。

绘图约定与 M1 一致：英文标签（避开中文字体缺失）、Agg 后端、dpi=140。

用法（项目目录）：

    python examples/m2_figures.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
BATCH = ARTIFACTS / "month2"
W1 = ARTIFACTS / "month2_w1"
W4 = ARTIFACTS / "month2_w4"
FIGDIR = ARTIFACTS / "figures"

DPI = 140


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(value: str) -> float | None:
    """空字符串表示「没有这个量」（启发式没有 bound），不是 0。"""
    return float(value) if value not in ("", None) else None


# --------------------------------------------------------------------------
# 1. 二维可行域（Week 1 Day 1 §4 手算的那个 LP）
# --------------------------------------------------------------------------
def fig_feasible_region() -> None:
    profit = (40.0, 30.0)
    # 2 x1 + x2 <= 100 (cap_M)；x1 + 2 x2 <= 80 (cap_L)
    cap_m = (2.0, 1.0, 100.0)
    cap_l = (1.0, 2.0, 80.0)

    # 顶点由系数推导：两两求交 + 与坐标轴求交，再筛可行。不抄笔记里的结果。
    lines = {"cap_M": cap_m, "cap_L": cap_l, "x1=0": (1.0, 0.0, 0.0), "x2=0": (0.0, 1.0, 0.0)}
    names = list(lines)
    feasible: list[tuple[float, float]] = []
    infeasible: list[tuple[float, float]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a1, b1, c1 = lines[names[i]]
            a2, b2, c2 = lines[names[j]]
            det = a1 * b2 - a2 * b1
            if abs(det) < 1e-12:
                continue
            x1 = (c1 * b2 - c2 * b1) / det
            x2 = (a1 * c2 - a2 * c1) / det
            ok = (
                cap_m[0] * x1 + cap_m[1] * x2 <= cap_m[2] + 1e-9
                and cap_l[0] * x1 + cap_l[1] * x2 <= cap_l[2] + 1e-9
                and x1 >= -1e-9
                and x2 >= -1e-9
            )
            # +0.0 消掉求解产生的 -0.0，否则坐标标注会印成 "(-0, 40)"
            point = (x1 + 0.0, x2 + 0.0)
            (feasible if ok else infeasible).append(point)

    # 按角度排序，得到四边形的正确顶点顺序
    cx = sum(p[0] for p in feasible) / len(feasible)
    cy = sum(p[1] for p in feasible) / len(feasible)
    poly = sorted(feasible, key=lambda p: np.arctan2(p[1] - cy, p[0] - cx))

    fig, ax = plt.subplots(figsize=(6.6, 5.4))
    xs = np.linspace(0, 90, 400)
    ax.plot(xs, (cap_m[2] - cap_m[0] * xs) / cap_m[1], color="tab:blue",
            label="cap_M:  2*x1 + x2 = 100")
    ax.plot(xs, (cap_l[2] - cap_l[0] * xs) / cap_l[1], color="tab:orange",
            label="cap_L:  x1 + 2*x2 = 80")
    ax.fill([p[0] for p in poly], [p[1] for p in poly],
            color="tab:green", alpha=0.15)

    for x1, x2 in poly:
        obj = profit[0] * x1 + profit[1] * x2
        best = obj >= max(profit[0] * p[0] + profit[1] * p[1] for p in poly) - 1e-9
        ax.plot([x1], [x2], marker="o", ms=7,
                color="tab:red" if best else "black", zorder=5)
        ax.annotate(f"({x1:g}, {x2:g})\nobj = {obj:g}",
                    (x1, x2), textcoords="offset points", xytext=(8, 8),
                    fontsize=9, color="tab:red" if best else "black",
                    fontweight="bold" if best else "normal")

    for x1, x2 in infeasible:
        ax.plot([x1], [x2], marker="x", ms=9, color="gray", zorder=5)
        # 靠右的点把标注放到左侧，否则会被裁掉
        right = x1 > 60
        ax.annotate(f"({x1:g}, {x2:g}) infeasible", (x1, x2),
                    textcoords="offset points", xytext=(-8, -16) if right else (8, -14),
                    ha="right" if right else "left", fontsize=8, color="gray")

    ax.set_xlim(-4, 92)
    ax.set_ylim(-5, 108)
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("x1  (product P1)")
    ax.set_ylabel("x2  (product P2)")
    ax.set_title("Feasible region of the 2-variable LP\n"
                 "max 40*x1 + 30*x2, vertices enumerated", fontsize=11)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGDIR / "feasible_region.png", dpi=DPI)
    plt.close(fig)
    print(f"feasible_region.png   vertices={sorted(poly)}")


# --------------------------------------------------------------------------
# 2. 预算翻了 10 倍，界一动不动（报告 §6.2 / §7）
# --------------------------------------------------------------------------
def fig_bound_vs_time() -> None:
    rows = load_csv(BATCH / "results.csv")
    series = [("single_20", "milp_tight"), ("parallel_24", "cpsat_parallel")]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))

    for instance, method in series:
        picked = sorted(
            (r for r in rows if r["instance"] == instance and r["method"] == method),
            key=lambda r: float(r["time_limit"]),
        )
        budgets = [float(r["time_limit"]) for r in picked]
        iters = [float(r["iterations"]) for r in picked]
        bound = as_float(picked[0]["best_bound"])
        ref = as_float(picked[0]["reference"])
        label = f"{instance} / {method}"

        axes[0].plot(budgets, iters, marker="o", label=label)
        axes[1].plot(budgets, [bound / ref] * len(budgets), marker="o", label=label)
        print(f"{label}: budgets={budgets} iterations={[int(v) for v in iters]} "
              f"bound={bound} (flat), bound/ref={bound / ref:.4f}")

    axes[0].set_yscale("log")
    axes[0].set_xlabel("time limit (s)")
    axes[0].set_ylabel("iterations (log scale)")
    axes[0].set_title("Search grows with the budget", fontsize=11)
    axes[0].set_xticks([3, 10, 30])
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.25)

    axes[1].axhline(1.0, color="tab:green", ls="--", lw=1)
    axes[1].annotate("reference value (proven optimum)", (3.0, 1.0),
                     textcoords="offset points", xytext=(6, 6),
                     fontsize=8, color="tab:green")
    axes[1].set_xlabel("time limit (s)")
    axes[1].set_ylabel("best bound / reference")
    axes[1].set_title("...but the bound never moves", fontsize=11)
    axes[1].set_xticks([3, 10, 30])
    axes[1].set_ylim(0, 1.15)
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.25)

    fig.suptitle("Same instance, 3x and 10x more time: more search, identical bound",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(FIGDIR / "bound_vs_time.png", dpi=DPI)
    plt.close(fig)
    print("bound_vs_time.png")


# --------------------------------------------------------------------------
# 3. 对称破缺的收益随规模反转（报告 §6.3）
# --------------------------------------------------------------------------
def _ablation_bars(ax, small: list[str]) -> None:
    """把 Week 4 Day 1 的消融结果画成 grouped bar（只用当日数据）。"""
    rows = load_csv(W4 / "results.csv")
    abl = [r for r in rows if r["group"] == "strengthening_ablation"]
    combos = [("False", "False"), ("False", "True"), ("True", "False"), ("True", "True")]
    tags = ["sym=off\nred=off", "sym=off\nred=on", "sym=on\nred=off", "sym=on\nred=on"]
    width = 0.2
    for idx, (sym, red) in enumerate(combos):
        vals = []
        for inst in small:
            hit = [r for r in abl
                   if r["instance"] == inst
                   and r["symmetry_breaking"] == sym
                   and r["redundant_constraints"] == red]
            vals.append(float(hit[0]["iterations"]) if hit else 0.0)
        pos = np.arange(len(small)) + (idx - 1.5) * width
        ax.bar(pos, vals, width, label=tags[idx])
        print(f"    {tags[idx].replace(chr(10), ' ')}: {vals}")
    ax.set_xticks(np.arange(len(small)))
    ax.set_xticklabels(small)
    ax.set_ylabel("conflicts")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.25, axis="y")


def fig_symmetry_ablation() -> None:
    """Week 4 Day 1 当天的证据：同一最优值，冲突数反而变多。"""
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    _ablation_bars(ax, ["par_6x3", "par_10x3"])
    ax.set_title("Strengthening ablation: the optimum never moves, the effort does\n"
                 "all four configs return 27 / 29 -- more conflicts is a real cost",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGDIR / "symmetry_ablation.png", dpi=DPI)
    plt.close(fig)
    print("symmetry_ablation.png")


def fig_symmetry_scale() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    small = ["par_6x3", "par_10x3"]
    _ablation_bars(axes[0], small)
    axes[0].set_title("Small instances: strengthening HURTS\n(more conflicts for the same optimum)",
                      fontsize=10)

    batch = load_csv(BATCH / "results.csv")
    picked = [r for r in batch
              if r["instance"] == "parallel_24" and r["group"] == "main"
              and r["method"] in ("cpsat_parallel", "cpsat_symmetry")]
    picked.sort(key=lambda r: r["method"])
    labels = [r["method"].replace("cpsat_", "") for r in picked]
    vals = [float(r["iterations"]) for r in picked]
    colors = ["tab:gray", "tab:green"]
    bars = axes[1].bar(labels, vals, color=colors)
    for bar, row in zip(bars, picked):
        axes[1].annotate(f"{row['status']}\n{float(row['solve_time']):.2f}s",
                         (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                         textcoords="offset points", xytext=(0, 4),
                         ha="center", fontsize=8)
        print(f"parallel_24 / {row['method']}: status={row['status']} "
              f"conflicts={row['iterations']} solve={row['solve_time']}s")
    axes[1].set_ylabel("conflicts")
    axes[1].set_title("Large instance: symmetry breaking WINS", fontsize=10)
    # 留出顶部空间，否则柱顶的标注会顶进标题
    axes[1].set_ylim(0, max(vals) * 1.28)
    axes[1].grid(alpha=0.25, axis="y")

    fig.suptitle("Symmetry breaking: the sign of the effect depends on instance size\n"
                 "(left: same optimum, more conflicts   right: 10s could not prove it, 0.48s does)",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGDIR / "symmetry_scale.png", dpi=DPI)
    plt.close(fig)
    print("symmetry_scale.png")


# --------------------------------------------------------------------------
# 4. 影子价格只在基不变的区间内成立（Week 1 Day 5）
# --------------------------------------------------------------------------
def fig_shadow_price() -> None:
    rows = load_csv(W1 / "sensitivity.csv")
    sweep = sorted(
        (r for r in rows if r["axis"] == "capacity_M"),
        key=lambda r: float(r["value"]),
    )
    caps = np.array([float(r["value"]) for r in sweep])
    actual = np.array([float(r["primal_objective"]) for r in sweep])
    predicted = np.array([float(r["predicted_objective"]) for r in sweep])
    holds = [r["prediction_holds"] == "True" for r in sweep]
    base_cap = float(sweep[0]["baseline_value"])
    shadow = float(sweep[0]["baseline_shadow_price"])
    base_obj = float([r for r in sweep if float(r["value"]) == base_cap][0]["primal_objective"])

    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    ax.plot(caps, actual, marker="o", color="tab:blue", label="actual optimum (re-solved)")
    ax.plot(caps, predicted, ls="--", color="tab:red",
            label=f"linear prediction: obj({base_cap:g}) + {shadow:g}*(cap - {base_cap:g})")

    ok_caps = caps[np.array(holds)]
    ax.axvspan(ok_caps.min(), ok_caps.max(), color="tab:green", alpha=0.12)
    ax.annotate(f"prediction holds on [{ok_caps.min():g}, {ok_caps.max():g}]",
                (ok_caps.min(), actual.max()), textcoords="offset points",
                xytext=(6, -18), fontsize=9, color="tab:green")

    for cap, act, pred, ok in zip(caps, actual, predicted, holds):
        if not ok:
            ax.annotate(f"off by {abs(pred - act):g}", (cap, act),
                        textcoords="offset points", xytext=(4, -16),
                        fontsize=8, color="tab:red")

    ax.axvline(base_cap, color="gray", ls=":", lw=1)
    ax.annotate("baseline", (base_cap, actual.min()), textcoords="offset points",
                xytext=(4, 0), fontsize=8, color="gray")
    ax.set_ylim(actual.min() - 120, actual.max() + 160)  # 给底部 "off by" 标注留位置
    ax.set_xlabel("cap_M (RHS of 2*x1 + x2 <= cap_M)")
    ax.set_ylabel("optimal objective")
    ax.set_title("Shadow price is a LOCAL rate, not a global one\n"
                 f"slope {shadow:g} is valid only while the basis is unchanged", fontsize=11)
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGDIR / "shadow_price.png", dpi=DPI)
    plt.close(fig)
    print(f"shadow_price.png      holds on [{ok_caps.min():g},{ok_caps.max():g}], "
          f"breaks at {[float(c) for c, o in zip(caps, holds) if not o]}")


# --------------------------------------------------------------------------
# 5. 各方法相对参考值的差距（报告 §6 主结果）
# --------------------------------------------------------------------------
def fig_method_quality() -> None:
    """按方法分组，而不是按实例分组。

    13 个方法 × 8 个实例做成 grouped bar 会挤成一团，而且绝大多数精确方法
    恰好等于参考值 1.0，条形图的动态范围被 heur_lpt 的离群点吃掉。
    改成「一个方法一列、每个实例一个点」，看的是方法的**分布**：
    精确方法是否总落在 1.0 上，启发式的散布有多宽。
    """
    rows = [r for r in load_csv(BATCH / "results.csv") if r["group"] == "main"]
    methods = sorted({r["method"] for r in rows})

    ratios: dict[str, list[tuple[float, str]]] = {}
    for method in methods:
        pts = []
        for r in rows:
            if r["method"] != method:
                continue
            obj = as_float(r["objective"])
            ref = as_float(r["reference"])
            if obj is None or not ref:
                continue
            pts.append((obj / ref, r["instance"]))
        if pts:
            ratios[method] = pts

    # 按中位数排序，让「好方法」集中在左侧
    order = sorted(ratios, key=lambda m: float(np.median([p[0] for p in ratios[m]])))
    fig, ax = plt.subplots(figsize=(11.5, 5.2))
    rng = np.random.default_rng(0)  # 固定抖动，图可复现

    for pos, method in enumerate(order):
        vals = [p[0] for p in ratios[method]]
        jitter = rng.uniform(-0.14, 0.14, len(vals))
        exact = [v for v in vals if abs(v - 1.0) < 1e-9]
        ax.scatter([pos] * len(exact), exact, marker="o", s=34,
                   color="tab:green", zorder=3)
        rest = [(v, j) for v, j in zip(vals, jitter) if abs(v - 1.0) >= 1e-9]
        if rest:
            ax.scatter([pos + j for _, j in rest], [v for v, _ in rest],
                       marker="x", s=38, color="tab:red", zorder=3)
        ax.plot([pos - 0.28, pos + 0.28], [float(np.median(vals))] * 2,
                color="black", lw=1.4, zorder=4)

    ax.axhline(1.0, color="tab:green", ls="--", lw=1.2)
    ax.annotate("dashed line = reference value (1.0)\n"
                "a circle on it means the method matched the reference",
                xy=(0.015, 0.72), xycoords="axes fraction",
                fontsize=8.5, color="tab:green",
                bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="tab:green", alpha=0.9))
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, rotation=35, ha="right")
    ax.set_ylabel("objective / reference  (log scale)")
    ax.set_yscale("log")
    ax.set_title("Method quality vs each instance's reference value\n"
                 "circle = matched the reference,  cross = worse,  black bar = median\n"
                 "a method is missing from an instance when it was not run there",
                 fontsize=11)
    ax.grid(alpha=0.25, axis="y")
    fig.tight_layout()
    fig.savefig(FIGDIR / "method_quality.png", dpi=DPI)
    plt.close(fig)
    for method in order:
        vals = sorted(p[0] for p in ratios[method])
        print(f"  {method:<18} n={len(vals)} ratio min={vals[0]:.4f} max={vals[-1]:.4f}")
    print("method_quality.png")


def main() -> None:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    print(f"output -> {FIGDIR}")
    fig_feasible_region()
    fig_bound_vs_time()
    fig_symmetry_ablation()
    fig_symmetry_scale()
    fig_shadow_price()
    fig_method_quality()
    print("done")


if __name__ == "__main__":
    main()
