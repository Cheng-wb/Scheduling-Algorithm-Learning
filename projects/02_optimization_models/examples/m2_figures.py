"""M2 图册：把笔记里用文字/表格描述的结论画成真正的坐标图。

**为什么要有这个脚本。** 原来 Week_1/Day1 的二维可行域是用 `│ ＼ ●` 拼出来的，
读者不能对照真实比例，也无法复用。文字表格能表达结论，但表达不了「斜率」「区间」
「随预算的走向」这类**形状**信息。这里全部改成代码绘图，笔记只引用图片。

图的输出目录是 ``artifacts/figures/``，**与 ``artifacts/month2`` 分开**——
后者是被封存的批次，带 `metadata.json` 与三步复核流程，不应混入非批次产物。

数据来源分两类，**都不抄结论**。

第一类是纯数学对象：系数写在代码里，顶点、分支树、时间线由程序重新推导，
所以图和笔记里的手算构成两条独立路径的互证。

    feasible_region      两变量生产 LP 的可行域（顶点＝约束两两求交）
    simplex_pivot_path   同一可行域上的换基路径与各步等利润线
    transport_network    2x2 运输问题的二部图与最优流（枚举 q 求得）
    bigm_geometry        Big-M 两个分支在 (S_j, S_k) 平面上的几何
    branch_and_bound     教学模型 min x+y, 2x+2y>=3 的分支树（脚本自己跑 B&B）
    interval_propagation 域收缩过程（按第 5 章 5.1 的等式逐步算）
    parallel_optional    并行机可选区间甘特（按第 5 章 5.5 的最优排程）
    cumulative_profile   Cumulative 资源剖面（第 5 章 5.7 的两组排程）

第二类是已提交的 artifacts：

    bound_vs_time        artifacts/month2/results.csv 的 tl_3 / main / tl_30 三组
    method_quality       artifacts/month2/results.csv 的 main 组
    shadow_price         artifacts/month2_w1/sensitivity.csv 的 capacity_M 扫描
    duality_certificate  artifacts/month2_w1/results.csv 的原始目标 vs 对偶目标
    complementarity      artifacts/month2_w1/complementarity.csv 的 283 对乘积
    tolerance_band       artifacts/month2_w1/results.csv 的三类残差
    root_lp_bounds       artifacts/month2_w2/results.csv 的 root_lp 组
    formulation_effort   artifacts/month2_w2/results.csv 的 limit 组
    search_evidence      artifacts/month2_w3/results.csv 的跨方法对照
    symmetry_ablation    artifacts/month2_w4/results.csv 的小实例消融
    symmetry_scale       artifacts/month2_w4/results.csv + artifacts/month2/results.csv
    warmstart_ablation   artifacts/month2_w4/results.csv 的 warmstart_ablation 组
    diagnosis_conflict   artifacts/month2_w4/results.csv 的 infeasibility_diagnosis 组
    time_limit_scan      artifacts/month2_w4/results.csv 的 time_limit_scan 组

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
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
BATCH = ARTIFACTS / "month2"
W1 = ARTIFACTS / "month2_w1"
W2 = ARTIFACTS / "month2_w2"
W3 = ARTIFACTS / "month2_w3"
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
# 0. Week 1 贯穿全周的生产 LP：系数只在这里写一次
# --------------------------------------------------------------------------
PROFIT = (40.0, 30.0)      # max 40*x1 + 30*x2
CAP_M = (2.0, 1.0, 100.0)  # 机器：2*x1 + x2 <= 100
CAP_L = (1.0, 2.0, 80.0)   # 人工：x1 + 2*x2 <= 80
X1_AXIS = (1.0, 0.0, 0.0)  # x1 = 0
X2_AXIS = (0.0, 1.0, 0.0)  # x2 = 0


def intersect(l1: tuple[float, float, float],
              l2: tuple[float, float, float]) -> tuple[float, float]:
    """两条直线 a*x1 + b*x2 = c 的交点。"""
    a1, b1, c1 = l1
    a2, b2, c2 = l2
    det = a1 * b2 - a2 * b1
    # +0.0 消掉 -0.0，否则标注会印成 "(50, -0)"
    return ((c1 * b2 - c2 * b1) / det + 0.0, (a1 * c2 - a2 * c1) / det + 0.0)


def production_vertices() -> list[tuple[float, float]]:
    """生产 LP 的可行域顶点，按角度排好序。

    顶点是**推**出来的：四条边界两两求交，筛掉不可行的交点，再按绕质心的
    角度排序。所以笔记里手算的 (50,0)、(40,20)、(0,40) 是这条路径的输出，
    不是它的输入。
    """
    lines = {"cap_M": CAP_M, "cap_L": CAP_L, "x1=0": X1_AXIS, "x2=0": X2_AXIS}
    names = list(lines)
    feasible: list[tuple[float, float]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            x1, x2 = intersect(lines[names[i]], lines[names[j]])
            ok = (
                CAP_M[0] * x1 + CAP_M[1] * x2 <= CAP_M[2] + 1e-9
                and CAP_L[0] * x1 + CAP_L[1] * x2 <= CAP_L[2] + 1e-9
                and x1 >= -1e-9
                and x2 >= -1e-9
            )
            # +0.0 消掉求解产生的 -0.0，否则坐标标注会印成 "(-0, 40)"
            if ok:
                feasible.append((x1 + 0.0, x2 + 0.0))

    cx = sum(p[0] for p in feasible) / len(feasible)
    cy = sum(p[1] for p in feasible) / len(feasible)
    return sorted(feasible, key=lambda p: np.arctan2(p[1] - cy, p[0] - cx))


# --------------------------------------------------------------------------
# 1. 二维可行域（Week 1 Day 1）
# --------------------------------------------------------------------------
def fig_feasible_region() -> None:
    profit = PROFIT
    cap_m, cap_l = CAP_M, CAP_L
    poly = production_vertices()
    # 被筛掉的交点也要画出来：说明「两直线相交」不等于「可行」
    infeasible = [
        intersect(cap_m, cap_l),
        intersect(cap_l, X1_AXIS),
        intersect(cap_m, X1_AXIS),
        intersect(cap_l, X2_AXIS),
    ]
    infeasible = [p for p in infeasible if p not in poly]

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
# 2. 换基路径：单纯形不是枚举顶点，是沿边走（Week 1 Day 2）
# --------------------------------------------------------------------------
def fig_simplex_pivot_path() -> None:
    """三个基对应的顶点＋两步转轴，以及每一步的等利润线。

    顶点由系数推出：起点是两条坐标轴的交点，第一步沿 x2=0 走到机器约束，
    第二步沿机器约束走到人工约束。路径不是抄的坐标，是「最小比值检验先被
    哪条边界挡住」的结果。
    """
    poly = production_vertices()
    path = [
        intersect(X1_AXIS, X2_AXIS),  # 初始基：s1、s2 在基里，x1=x2=0
        intersect(X2_AXIS, CAP_M),    # 转轴 1：x1 进基，先碰机器约束
        intersect(CAP_M, CAP_L),      # 转轴 2：x2 进基，被人工约束挡住
    ]
    zs = [PROFIT[0] * x1 + PROFIT[1] * x2 for x1, x2 in path]

    fig, ax = plt.subplots(figsize=(7.2, 5.6))
    ax.fill([p[0] for p in poly], [p[1] for p in poly], color="tab:green", alpha=0.12)
    xs = np.linspace(0, 90, 400)
    ax.plot(xs, (CAP_M[2] - CAP_M[0] * xs) / CAP_M[1], color="tab:blue",
            label="cap_M:  2*x1 + x2 = 100")
    ax.plot(xs, (CAP_L[2] - CAP_L[0] * xs) / CAP_L[1], color="tab:orange",
            label="cap_L:  x1 + 2*x2 = 80")

    # 每步的等利润线：z 逐次抬高，最优点处正好顶到可行域。
    # 标签偏移逐个给：否则起点和终点那两个会被坐标轴和转轴箭头压住。
    z_offset = [(16, -16), (6, -20), (12, 10)]
    for (x1, x2), z, offset in zip(path, zs, z_offset):
        gx = np.linspace(-4, 60, 200)
        ax.plot(gx, (z - PROFIT[0] * gx) / PROFIT[1], ls="--", lw=0.9,
                color="tab:purple", alpha=0.55)
        ax.annotate(f"z = {z:g}", (x1, x2), textcoords="offset points",
                    xytext=offset, fontsize=8.5, color="tab:purple")

    for idx, (x1, x2) in enumerate(path):
        ax.plot([x1], [x2], marker="o", ms=9, color="black", zorder=6)
        ax.annotate(f"basis {idx}: ({x1:g}, {x2:g})",
                    (x1, x2), textcoords="offset points", xytext=(10, 8),
                    fontsize=9, fontweight="bold", zorder=7)

    # 两步转轴的方向箭头：每一步都走到**相邻**顶点
    for (x1a, x2a), (x1b, x2b) in zip(path, path[1:]):
        ax.annotate("", (x1b, x2b), (x1a, x2a),
                    arrowprops={"arrowstyle": "-|>", "lw": 2.0, "color": "tab:red",
                                "shrinkA": 12, "shrinkB": 12})

    ax.set_xlim(-4, 92)
    ax.set_ylim(-5, 108)
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("x1  (product P1)")
    ax.set_ylabel("x2  (product P2)")
    ax.set_title("Simplex walks along edges, it does not enumerate vertices\n"
                 "each pivot moves to an ADJACENT vertex, raising z = 40*x1 + 30*x2",
                 fontsize=11)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGDIR / "simplex_pivot_path.png", dpi=DPI)
    plt.close(fig)
    print(f"simplex_pivot_path.png   path={[(round(a, 6), round(b, 6)) for a, b in path]} "
          f"z={[round(z, 6) for z in zs]}")


# --------------------------------------------------------------------------
# 3. 运输问题就是网络上的流（Week 1 Day 3）
# --------------------------------------------------------------------------
def fig_transport_network() -> None:
    """2x2 运输：一条变量＝一条边，最优流由枚举 q = x11 得到。

    供给 3、2，需求 2、3。令 q = x11，其余三个变量由守恒式推出，
    目标化成 18 - 4q，所以 q 取上界 2 最优。脚本用网格搜索复算这条结论，
    不把「最优流」当常量写进代码。
    """
    supply = (3.0, 2.0)
    demand = (2.0, 3.0)
    cost = ((1.0, 4.0), (3.0, 2.0))

    best_q, best_cost = 0.0, float("inf")
    for step in range(2001):
        q = 2.0 * step / 2000.0
        flow = ((q, supply[0] - q), (demand[0] - q, demand[1] - (supply[0] - q)))
        if any(v < -1e-9 for row in flow for v in row):
            continue
        total = sum(flow[i][j] * cost[i][j] for i in range(2) for j in range(2))
        if total < best_cost - 1e-12:
            best_q, best_cost = q, total
    flow = ((best_q, supply[0] - best_q),
            (demand[0] - best_q, demand[1] - (supply[0] - best_q)))

    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    src_y = (0.72, 0.28)
    dst_y = (0.72, 0.28)
    for i in (0, 1):
        for j in (0, 1):
            amt = flow[i][j]
            active = amt > 1e-9
            ax.plot([0.18, 0.82], [src_y[i], dst_y[j]],
                    lw=0.8 + 3.2 * (amt / max(supply)), color="tab:blue" if active else "lightgray",
                    zorder=1 + (1 if active else 0))
            ax.annotate(f"cost {cost[i][j]:g}\nflow {amt:g}",
                        (0.5, (src_y[i] + dst_y[j]) / 2), ha="center", va="center",
                        fontsize=8.5, color="tab:blue" if active else "gray",
                        bbox={"boxstyle": "round,pad=0.28", "fc": "white",
                              "ec": "tab:blue" if active else "lightgray", "alpha": 0.95},
                        zorder=5)

    for i, (label, y) in enumerate(zip(("W1", "W2"), src_y)):
        ax.scatter([0.18], [y], s=1500, color="#17324d", zorder=6)
        ax.annotate(f"{label}\nsupply {supply[i]:g}", (0.18, y), ha="center", va="center",
                    color="white", fontsize=9, zorder=7)
    for j, (label, y) in enumerate(zip(("C1", "C2"), dst_y)):
        ax.scatter([0.82], [y], s=1500, color="#922b57", zorder=6)
        ax.annotate(f"{label}\ndemand {demand[j]:g}", (0.82, y), ha="center", va="center",
                    color="white", fontsize=9, zorder=7)

    ax.text(0.5, 0.02,
            f"total cost {best_cost:g}   (q = x11 = {best_q:g})\n"
            "the gray edge carries zero flow -- it is a variable, not a decision already made",
            ha="center", fontsize=9, color="#333333")
    ax.set_title("A transport problem is a flow on a bipartite graph\n"
                 "supply and demand are equalities, so only one variable is free",
                 fontsize=11)
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.06, 1.02)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(FIGDIR / "transport_network.png", dpi=DPI)
    plt.close(fig)
    print(f"transport_network.png  q={best_q:g} cost={best_cost:g} flow={flow}")


# --------------------------------------------------------------------------
# 4. 对偶不是近似：两个目标在同一点相遇（Week 1 Day 4）
# --------------------------------------------------------------------------
def fig_duality_certificate() -> None:
    """每个 OPTIMAL 场景的原始目标与对偶目标落在 y = x 上。

    这就是「最优性证书」的可验证版本：对偶可行解给出了上界，原始可行解
    取到了这个上界，于是 bound = incumbent，不必枚举顶点也知道最优。
    """
    rows = load_csv(W1 / "results.csv")
    solved = [r for r in rows
              if r["status"] == "OPTIMAL" and as_float(r["primal_objective"]) is not None]
    primal = np.array([float(r["primal_objective"]) for r in solved])
    dual = np.array([float(r["dual_objective"]) for r in solved])
    gap = np.abs(primal - dual)
    names = [r["name"] for r in solved]
    infeasible = [r["name"] for r in rows if r["status"] != "OPTIMAL"]

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))

    lo = max(1.0, float(primal.min()) * 0.5)
    hi = float(primal.max()) * 2.0
    axes[0].plot([lo, hi], [lo, hi], color="tab:green", ls="--", lw=1.2,
                 label="y = x  (bound meets incumbent)")
    axes[0].scatter(primal, dual, marker="o", s=44, color="tab:blue",
                    edgecolor="white", zorder=4)
    axes[0].set_xscale("log")
    axes[0].set_yscale("log")
    axes[0].set_xlim(lo, hi)
    axes[0].set_ylim(lo, hi)
    axes[0].set_xlabel("primal objective  (a feasible plan)")
    axes[0].set_ylabel("dual objective  (a bound)")
    axes[0].set_title("Every solved scenario sits on the diagonal\n"
                      f"{len(solved)} scenarios, largest |primal - dual| = {gap.max():.2e}",
                      fontsize=10)
    axes[0].legend(fontsize=8.5, loc="upper left")
    axes[0].grid(alpha=0.25, which="both")

    # 右图：残差量级。0 画在 1e-16 的地板上并单独标记。
    series = [
        ("max |primal - dual|", "duality_gap", "tab:blue"),
        ("max constraint residual", "max_constraint_residual", "tab:orange"),
        ("max complementarity", "max_complementarity", "tab:purple"),
    ]
    floor = 1e-16
    for pos, (label, key, color) in enumerate(series):
        vals = [float(r[key]) for r in solved if r[key] not in ("", None)]
        exact0 = sum(1 for v in vals if v == 0.0)
        plotted = [v if v > 0 else floor for v in vals]
        axes[1].scatter(plotted, [pos] * len(plotted), s=26, color=color,
                        alpha=0.75, zorder=3)
        axes[1].annotate(f"{exact0}/{len(vals)} exactly 0", (floor, pos),
                         textcoords="offset points", xytext=(6, 9),
                         fontsize=8, color=color)

    axes[1].axvline(1e-6, color="tab:red", ls="--", lw=1.2)
    axes[1].annotate("typical solver feasibility\ntolerance (1e-06)", (1e-6, 2.45),
                     textcoords="offset points", xytext=(-4, 0), ha="right",
                     fontsize=8, color="tab:red")
    axes[1].set_xscale("log")
    axes[1].set_xlim(floor * 0.6, 1e-3)
    axes[1].set_yticks(range(len(series)))
    axes[1].set_yticklabels([s[0] for s in series], fontsize=9)
    axes[1].set_ylim(-0.6, 2.9)
    axes[1].set_xlabel("residual magnitude (log scale)")
    axes[1].set_title("What 'the certificate holds' means numerically\n"
                      "observed residuals sit orders of magnitude below the tolerance",
                      fontsize=10)
    axes[1].grid(alpha=0.25, which="both")

    fig.suptitle("Duality turns 'I checked all vertices' into 'two feasible points agree'",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(FIGDIR / "duality_certificate.png", dpi=DPI)
    plt.close(fig)
    print(f"duality_certificate.png  solved={len(solved)} max_gap={gap.max():.3e} "
          f"not_optimal={infeasible}")


# --------------------------------------------------------------------------
# 5. 互补松弛：每一对里至少有一个是 0（Week 1 Day 4 / Day 6）
# --------------------------------------------------------------------------
def fig_complementarity() -> None:
    """283 对 (primal, dual) 的乘积全部为 0。

    教科书里 x_i·y_i = 0 是「非负项之和为零则每项为零」的推论；这里把
    artifacts 里逐对算出的乘积画出来，读者可以自己数落在两条轴上的点数。
    """
    rows = load_csv(W1 / "complementarity.csv")
    primal = np.array([float(r["primal"]) for r in rows])
    dual = np.array([float(r["dual"]) for r in rows])
    product = np.array([float(r["product"]) for r in rows])
    tol = 1e-9
    both_zero = int(np.sum((np.abs(primal) <= tol) & (np.abs(dual) <= tol)))
    primal_only = int(np.sum((np.abs(primal) > tol) & (np.abs(dual) <= tol)))
    dual_only = int(np.sum((np.abs(primal) <= tol) & (np.abs(dual) > tol)))
    violated = int(np.sum(np.abs(product) > tol))
    # 图上写「全部为 0」会把话说得比数据强：34 对的乘积其实在 1e-15 以上
    # （最大 5.684e-13），只是远低于任何有意义的容差。标题里要带这个限定。
    max_product = float(np.abs(product).max())
    exact_zero = int(np.sum(product == 0.0))

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))

    # 面板 A：散点全部落在两条轴上，对角线（两个都正）是空的
    axes[0].axhspan(0, 1, color="white")
    axes[0].axvline(0, color="black", lw=0.9)
    axes[0].axhline(0, color="black", lw=0.9)
    pos_p = primal > tol
    pos_d = dual > tol
    axes[0].scatter(primal[pos_p], dual[pos_p], s=30, color="tab:blue",
                    label=f"x > 0, y = 0   ({primal_only})", zorder=4)
    axes[0].scatter(primal[pos_d], dual[pos_d], s=30, color="tab:orange",
                    label=f"x = 0, y > 0   ({dual_only})", zorder=4)
    axes[0].scatter(primal[~pos_p & ~pos_d], dual[~pos_p & ~pos_d], s=34,
                    color="tab:gray", marker="s",
                    label=f"x = 0, y = 0   ({both_zero})", zorder=4)
    axes[0].annotate("this quadrant is empty:\nx > 0 AND y > 0\nnever happens",
                     (0.62, 0.72), xycoords="axes fraction", fontsize=8.5,
                     color="tab:red", ha="center",
                     bbox={"boxstyle": "round,pad=0.35", "fc": "white",
                           "ec": "tab:red", "alpha": 0.95})
    axes[0].set_xlim(-1.5, max(primal) * 1.15)
    axes[0].set_ylim(-1.5, max(dual) * 1.15)
    axes[0].set_xlabel("primal value  (x)")
    axes[0].set_ylabel("dual value  (y)")
    axes[0].set_title(f"Complementary slackness over {len(rows)} pairs, "
                      f"{len({r['scenario'] for r in rows})} scenarios\n"
                      f"every pair lands on an axis (to a tolerance of {tol:g})",
                      fontsize=10)
    axes[0].legend(fontsize=8, loc="upper right")
    axes[0].grid(alpha=0.25)

    # 面板 B：把 prod_2d 这一个场景摊开，逐对看
    detail = [r for r in rows if r["scenario"] == "prod_2d"]
    labels = [f"{r['name']}\n({r['kind']})" for r in detail]
    pv = [float(r["primal"]) for r in detail]
    dv = [float(r["dual"]) for r in detail]
    ypos = np.arange(len(detail))
    axes[1].barh(ypos - 0.19, pv, height=0.36, color="tab:blue", label="primal x")
    axes[1].barh(ypos + 0.19, dv, height=0.36, color="tab:orange", label="dual y")
    for idx, (p, d) in enumerate(zip(pv, dv)):
        axes[1].annotate(f"{p:.2g}", (p, idx - 0.19), textcoords="offset points",
                         xytext=(4, -3), fontsize=8, color="tab:blue")
        axes[1].annotate(f"{d:.2g}", (d, idx + 0.19), textcoords="offset points",
                         xytext=(4, -3), fontsize=8, color="tab:orange")
    axes[1].set_yticks(ypos)
    axes[1].set_yticklabels(labels, fontsize=8.5)
    axes[1].set_xlabel("value")
    axes[1].set_xlim(0, 46)
    axes[1].set_title("One scenario, pair by pair (prod_2d)\n"
                      "at every row one bar is missing: that is the pairing",
                      fontsize=10)
    axes[1].legend(fontsize=8.5, loc="lower right")
    axes[1].grid(alpha=0.25, axis="x")

    fig.suptitle("Complementary slackness is not a formula to trust, it is a pairing to check",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(FIGDIR / "complementarity.png", dpi=DPI)
    plt.close(fig)
    print(f"complementarity.png  pairs={len(rows)} violated={violated} "
          f"x_only={primal_only} y_only={dual_only} both_zero={both_zero} "
          f"exact_zero={exact_zero} max_abs_product={max_product:.3e} tol={tol:g}")


# --------------------------------------------------------------------------
# 6. 残差 vs 容差：为什么「差 1e-13」不算错（Week 1 Day 6）
# --------------------------------------------------------------------------
def fig_tolerance_band() -> None:
    """绝对残差与相对残差不是一回事，容差也不是「精确等于 0」。

    取 artifacts/month2_w1/results.csv 每条约束的相对残差量级，
    在容差阶梯上标出求解器通常在哪个量级停手。
    """
    rows = load_csv(W1 / "results.csv")
    solved = [r for r in rows if r["status"] == "OPTIMAL"]

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))

    # 左：容差阶梯，说明 1e-6 这个默认值是怎么被解读的
    steps = [
        (1e-12, "residual <= 1e-12", "treated as exact"),
        (1e-9, "residual <= 1e-9", "still indistinguishable from exact"),
        (1e-6, "residual <= 1e-6", "typical solver default: ACCEPTED"),
        (1e-4, "residual <= 1e-4", "accepted by loose settings"),
        (1e-2, "residual >= 1e-2", "a real modelling error, not noise"),
    ]
    colors = ["tab:green", "tab:green", "tab:blue", "tab:orange", "tab:red"]
    for pos, ((val, label, note), color) in enumerate(zip(steps, colors)):
        axes[0].barh(pos, val, color=color, alpha=0.35, height=0.6)
        axes[0].annotate(f"{label}   -- {note}", (val, pos),
                         textcoords="offset points", xytext=(6, 0),
                         va="center", fontsize=9, color=color)
    axes[0].set_xscale("log")
    axes[0].set_xlim(1e-13, 1e-1)
    axes[0].set_yticks([])
    axes[0].set_xlabel("constraint residual magnitude (log scale)")
    axes[0].set_title("A tolerance is a decision rule, not a rounding detail\n"
                      "'feasible' means 'violates by less than a stated amount'",
                      fontsize=10)
    axes[0].grid(alpha=0.25, axis="x")

    # 右：真实残差落在阶梯的哪一级
    series = [
        ("primal residual", "max_constraint_residual", "tab:orange"),
        ("dual feasibility", "max_dual_feasibility_violation", "tab:purple"),
        ("reduced-cost identity", "max_reduced_cost_identity", "tab:brown"),
    ]
    floor = 1e-16
    for pos, (label, key, color) in enumerate(series):
        vals = [float(r[key]) for r in solved if r[key] not in ("", None)]
        plotted = [v if v > 0 else floor for v in vals]
        axes[1].scatter(plotted, [pos] * len(plotted), s=26, color=color, alpha=0.75, zorder=3)
        axes[1].annotate(f"max {max(vals):.1e}", (max(vals) or floor, pos),
                         textcoords="offset points", xytext=(6, 8),
                         fontsize=8, color=color)
    axes[1].axvline(1e-6, color="tab:blue", ls="--", lw=1.2)
    axes[1].annotate("solver default 1e-06", (1e-6, 2.4), textcoords="offset points",
                     xytext=(-4, 0), ha="right", fontsize=8.5, color="tab:blue")
    axes[1].set_xscale("log")
    axes[1].set_xlim(floor * 0.6, 1e-3)
    axes[1].set_yticks(range(len(series)))
    axes[1].set_yticklabels([s[0] for s in series], fontsize=9)
    axes[1].set_ylim(-0.6, 2.9)
    axes[1].set_xlabel("observed residual (log scale)")
    axes[1].set_title("Where the actual numbers landed\n"
                      "everything is below the tolerance, most of it exactly zero",
                      fontsize=10)
    axes[1].grid(alpha=0.25, which="both")

    fig.suptitle("Reading a residual: absolute or relative, against which tolerance, for which row",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(FIGDIR / "tolerance_band.png", dpi=DPI)
    plt.close(fig)
    worst = max(float(r["max_constraint_residual"]) for r in solved)
    print(f"tolerance_band.png  scenarios={len(solved)} worst_primal_residual={worst:.3e}")


# --------------------------------------------------------------------------
# 7. 预算翻了 10 倍，界一动不动（报告 §6.2 / §7）
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
# 8. 对称破缺的收益随规模反转（报告 §6.3）
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
# 9. 影子价格只在基不变的区间内成立（Week 1 Day 5）
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
# 10. 单机：六种顺序的目标值差在哪里（Week 2 Day 1）
# --------------------------------------------------------------------------
def single_machine_instance() -> tuple[list[str], list[int], list[int], list[int]]:
    """Week 2 Day 1 的三作业单机实例，与 examples/m2w2d1_sequence_milp.py 一致。

    A(p=3,d=4,r=0)、B(p=2,d=2,r=0)、C(p=4,d=10,r=5)。C 的释放时间让顺序
    不再是「随便排都行」——这正是要把先后关系写进模型的原因。
    """
    jobs = ["A", "B", "C"]
    release = [0, 0, 5]
    processing = [3, 2, 4]
    due = [4, 2, 10]
    return jobs, release, processing, due


def schedule_permutation(order: list[int], release: list[int],
                         processing: list[int], due: list[int]) -> tuple[list[int], int]:
    """按给定顺序做「不主动等待」排程：start = max(释放时间, 上一件完工)。"""
    starts, clock, total = [], 0, 0
    for idx in order:
        start = max(release[idx], clock)
        starts.append(start)
        clock = start + processing[idx]
        total += max(0, clock - due[idx])
    return starts, total


def fig_single_machine_orders() -> None:
    """六种顺序全部枚举，再画最优与最差两张甘特图。

    目标值由 schedule_permutation 算出，不抄教材表格。
    """
    import itertools

    jobs, release, processing, due = single_machine_instance()
    results = []
    for perm in itertools.permutations(range(len(jobs))):
        starts, total = schedule_permutation(list(perm), release, processing, due)
        results.append((list(perm), starts, total))
    results.sort(key=lambda r: r[2])
    best, worst = results[0], results[-1]

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.6))
    palette = {"A": "tab:blue", "B": "tab:orange", "C": "tab:green"}

    for ax, (order, starts, total), tag in (
        (axes[0], best, "best order"),
        (axes[1], worst, "worst order"),
    ):
        for pos, idx in enumerate(order):
            ax.barh(0, processing[idx], left=starts[pos], height=0.5,
                    color=palette[jobs[idx]], edgecolor="white")
            ax.annotate(f"{jobs[idx]}\nC={starts[pos] + processing[idx]}\n"
                        f"T={max(0, starts[pos] + processing[idx] - due[idx])}",
                        (starts[pos] + processing[idx] / 2, 0), ha="center", va="center",
                        color="white", fontsize=8.5)
            ax.axvline(due[idx], color=palette[jobs[idx]], ls=":", lw=1.1)
            ax.annotate(f"d{jobs[idx]}={due[idx]}", (due[idx], 0.36), rotation=90,
                        fontsize=7.5, color=palette[jobs[idx]], ha="right", va="bottom")
            if release[idx] > 0:
                ax.annotate(f"r{jobs[idx]}={release[idx]}", (release[idx], -0.42),
                            fontsize=7.5, color="gray", ha="center")
                ax.axvline(release[idx], color="gray", ls="--", lw=0.9)
        ax.set_xlim(-0.5, 15)
        ax.set_ylim(-0.7, 0.9)
        ax.set_yticks([])
        ax.set_xlabel("time")
        ax.set_title(f"{tag}: {' -> '.join(jobs[i] for i in order)}\n"
                     f"total tardiness = {total}", fontsize=10)
        ax.grid(alpha=0.22, axis="x")

    fig.suptitle("Enumeration is the only honest baseline for 3 jobs\n"
                 "same release times and due dates, only the sequence changes",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(FIGDIR / "single_machine_orders.png", dpi=DPI)
    plt.close(fig)
    for order, _, total in results:
        print(f"single_machine_orders.png   {'->'.join(jobs[i] for i in order):<10} T={total}")


# --------------------------------------------------------------------------
# 11. Big-M 的几何：它放松的是「不能同时成立」，不是「都不成立」（Week 2 Day 2）
# --------------------------------------------------------------------------
def fig_bigm_geometry() -> None:
    """两个作业只能一前一后，Big-M 把这条折线变成两条直边。

    纵轴 S_k、横轴 S_j，两个分支分别是 S_k >= S_j + p_j（k 在后）与
    S_j >= S_k + p_k（j 在后）。可行域是两块不连通的半平面，Big-M 用一个
    离散开关在两者之间切换。
    """
    p_j, p_k = 3, 2
    lim = 9
    m_used = 6

    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.9))
    grid = np.linspace(0, lim, 300)
    sj, sk = np.meshgrid(grid, grid)

    branch_a = sk >= sj + p_j        # y = 1，k 在 j 之后
    branch_b = sj >= sk + p_k        # y = 0，j 在 k 之后
    axes[0].contourf(sj, sk, (branch_a | branch_b).astype(float), levels=[0.5, 1.5],
                     colors=["tab:green"], alpha=0.16)
    axes[0].plot(grid, grid + p_j, color="tab:blue", lw=2, label=f"y=1:  S_k >= S_j + {p_j}")
    axes[0].plot(grid + p_k, grid, color="tab:orange", lw=2, label=f"y=0:  S_j >= S_k + {p_k}")
    axes[0].annotate("overlap is forbidden:\nboth inequalities at once\nwould force 0 >= p_j + p_k",
                     (2.0, 2.0), fontsize=9, color="tab:red", ha="center",
                     bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": "tab:red"})
    axes[0].annotate("k after j", (6.0, 1.2), fontsize=9, color="tab:blue")
    axes[0].annotate("j after k", (1.2, 6.0), fontsize=9, color="tab:orange")
    axes[0].set_xlim(0, lim)
    axes[0].set_ylim(0, lim)
    axes[0].set_xlabel("S_j  (start of job j)")
    axes[0].set_ylabel("S_k  (start of job k)")
    axes[0].set_title("What the model has to express\n"
                      "the feasible set is two disconnected half-planes",
                      fontsize=10)
    axes[0].legend(fontsize=8.5, loc="upper right")
    axes[0].grid(alpha=0.22)

    # 右：Big-M 写成的松弛。y=1 时下面的约束被推到远处。
    axes[1].contourf(sj, sk, ((sk >= sj + p_j - m_used * (1 - 1)) | (sj >= sk + p_k - m_used * 0)).astype(float),
                     levels=[0.5, 1.5], colors=["tab:green"], alpha=0.16)
    axes[1].plot(grid, grid + p_j, color="tab:blue", lw=2,
                 label=f"y=1:  S_k >= S_j + {p_j} - {m_used}*(1 - y)")
    axes[1].plot(grid, grid + p_j - m_used, color="tab:blue", lw=1.4, ls="--",
                 label=f"y=0:  the same row relaxes to S_k >= S_j - {m_used - p_j}")
    axes[1].plot(grid + p_k - m_used, grid, color="tab:orange", lw=1.4, ls="--",
                 label=f"y=1:  the other row relaxes to S_j >= S_k - {m_used - p_k}")
    axes[1].plot(grid + p_k, grid, color="tab:orange", lw=2,
                 label=f"y=0:  S_j >= S_k + {p_k} - {m_used}*y")
    axes[1].annotate(f"with M = {m_used}, the relaxed row sits entirely\n"
                     "below the axes: it forbids nothing",
                     (5.4, 0.5), fontsize=8.5, color="tab:blue",
                     bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": "tab:blue"})
    axes[1].set_xlim(0, lim)
    axes[1].set_ylim(0, lim)
    axes[1].set_xlabel("S_j  (start of job j)")
    axes[1].set_ylabel("S_k  (start of job k)")
    axes[1].set_title("How Big-M writes it\nthe inactive branch is pushed out of the box",
                      fontsize=10)
    axes[1].legend(fontsize=7.2, loc="upper right")
    axes[1].grid(alpha=0.22)

    fig.suptitle("A disjunction is not an inequality: Big-M switches between two of them",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(FIGDIR / "bigm_geometry.png", dpi=DPI)
    plt.close(fig)
    print(f"bigm_geometry.png  p_j={p_j} p_k={p_k} M={m_used}")


# --------------------------------------------------------------------------
# 12. 同一问题、三种写法：根节点 LP 界差多少（Week 2 Day 3）
# --------------------------------------------------------------------------
def fig_root_lp_bounds() -> None:
    """root_lp 组给出「松弛有多强」，与求解速度无关。

    milp_tight / milp_loose 的根 LP 界都是 0（时间变量可以全部从 0 开始，
    先后约束被小数 y 放松）；time-indexed（milp_alt）的根 LP 界已经贴到
    最优值。这就是「模型更强」的可测量含义。
    """
    rows = [r for r in load_csv(W2 / "results.csv") if r["group"] == "root_lp"]
    refs = {r["instance"]: as_float(r["reference"])
            for r in load_csv(W2 / "results.csv") if r["group"] == "limit"}
    instances = sorted({r["instance"] for r in rows})
    methods = ["milp_tight", "milp_loose", "milp_alt"]
    colors = {"milp_tight": "tab:blue", "milp_loose": "tab:orange", "milp_alt": "tab:green"}

    fig, ax = plt.subplots(figsize=(9.4, 4.9))
    width = 0.26
    # 图例按「方法」标一次，而不是在第一个实例上标一次：第一个实例
    # （parallel_a）只有 milp_alt，按 pos==0 标会让 tight/loose 永远进不了图例。
    labeled: set[str] = set()
    for pos, inst in enumerate(instances):
        ref = refs.get(inst)
        for k, method in enumerate(methods):
            hit = [r for r in rows if r["instance"] == inst and r["method"] == method]
            if not hit or ref is None:
                continue
            bound = as_float(hit[0]["best_bound"]) or 0.0
            ratio = bound / ref
            xpos = pos + (k - 1) * width
            ax.bar(xpos, ratio, width * 0.92, color=colors[method],
                   label=method if method not in labeled else None)
            labeled.add(method)
            ax.annotate(f"{bound:g}", (xpos, ratio), textcoords="offset points",
                        xytext=(0, 4), ha="center", fontsize=8.5)
        ax.annotate(f"optimum = {ref:g}", (pos, 1.05), ha="center", fontsize=8.5,
                    color="tab:red")

    ax.axhline(1.0, color="tab:red", ls="--", lw=1.2)
    ax.annotate("root LP bound / optimum", (len(instances) - 0.5, 1.0),
                textcoords="offset points", xytext=(-4, -14), ha="right",
                fontsize=8.5, color="tab:red")
    ax.set_xticks(range(len(instances)))
    ax.set_xticklabels(instances)
    # 留出顶部空间给图例，否则它会压住第一个实例的 "optimum = ..." 标注
    ax.set_ylim(0, 1.42)
    ax.set_ylabel("root LP bound / optimum")
    ax.set_title("A stronger formulation is visible at the root node\n"
                 "the same problem, three ways to write the ordering constraints",
                 fontsize=11)
    ax.legend(fontsize=8.5, loc="upper left")
    ax.grid(alpha=0.25, axis="y")
    fig.tight_layout()
    fig.savefig(FIGDIR / "root_lp_bounds.png", dpi=DPI)
    plt.close(fig)
    for inst in instances:
        line = []
        for method in methods:
            hit = [r for r in rows if r["instance"] == inst and r["method"] == method]
            if hit:
                line.append(f"{method}={as_float(hit[0]['best_bound'])}")
        print(f"root_lp_bounds.png  {inst}: optimum={refs.get(inst)} {' '.join(line)}")


# --------------------------------------------------------------------------
# 13. 分支定界：脚本自己跑一棵树（Week 2 Day 4）
# --------------------------------------------------------------------------
def bnb_lp(box_x: tuple[float, float], box_y: tuple[float, float]
           ) -> tuple[bool, float, float, float]:
    """求解 LP：min x + y, 2x + 2y >= 3, x/y 各自落在给定的盒子里。

    二维 LP 的顶点只可能出现在「盒子的角」或「盒边与那条直线的交点」，
    所以枚举这些候选点再筛可行就够了——不需要通用 LP 求解器，
    这样图上的每个界都能被人手复核。
    """
    (lx, ux), (ly, uy) = box_x, box_y
    cand = [(lx, ly), (ux, ly), (lx, uy), (ux, uy)]
    for xv in (lx, ux):
        yv = (3.0 - 2.0 * xv) / 2.0
        if ly - 1e-9 <= yv <= uy + 1e-9:
            cand.append((xv, yv))
    for yv in (ly, uy):
        xv = (3.0 - 2.0 * yv) / 2.0
        if lx - 1e-9 <= xv <= ux + 1e-9:
            cand.append((xv, yv))
    feasible = [(x, y) for x, y in cand if 2 * x + 2 * y >= 3 - 1e-9]
    if not feasible:
        return False, float("nan"), float("nan"), float("nan")
    x, y = min(feasible, key=lambda p: p[0] + p[1])
    return True, x + y, x, y


def bnb_integer_feasible(box_x: tuple[float, float], box_y: tuple[float, float]
                         ) -> tuple[int, int] | None:
    """盒子里有没有满足约束的整数点（本例只有 0/1 两种取值）。"""
    for xv in (0, 1):
        for yv in (0, 1):
            if (box_x[0] - 1e-9 <= xv <= box_x[1] + 1e-9
                    and box_y[0] - 1e-9 <= yv <= box_y[1] + 1e-9
                    and 2 * xv + 2 * yv >= 3 - 1e-9):
                return xv, yv
    return None


def bnb_search() -> dict:
    """深度优先的分支定界，边跑边记录节点，供绘图使用。

    与第 4 章 4.8 的教学模型一致：min x+y, 2x+2y>=3, x,y in {0,1}。
    """
    root_box = {"x": (0.0, 1.0), "y": (0.0, 1.0)}
    incumbent = bnb_integer_feasible(root_box["x"], root_box["y"])
    inc_value = float(incumbent[0] + incumbent[1]) if incumbent else float("inf")

    nodes: list[dict] = []
    edges: list[tuple[int, int, str]] = []

    def recurse(box: dict, parent: int | None, label: str) -> None:
        nonlocal incumbent, inc_value
        index = len(nodes)
        ok, value, xv, yv = bnb_lp(box["x"], box["y"])
        record = {"index": index, "box": dict(box), "parent": parent, "label": label,
                  "bounds": [box["x"][0], box["x"][1], box["y"][0], box["y"][1]],
                  "children": []}
        if parent is not None:
            edges.append((parent, index, label))
        nodes.append(record)

        if not ok:
            record.update(status="infeasible", lp=None, note="no feasible point in this box")
            return

        # 先判「松弛解本身是不是整数点」：是的话这个节点已经走到头，
        # 不必再分。这一支和「按界剪枝」是两种不同的结束方式，
        # 图上要能分开——它们的证据强度不一样。
        if abs(xv - round(xv)) < 1e-9 and abs(yv - round(yv)) < 1e-9:
            better = value < inc_value - 1e-9
            if better:
                incumbent = (int(round(xv)), int(round(yv)))
                inc_value = value
            record.update(status="integral", lp=value, x=xv, y=yv,
                          note=f"LP optimum is integral, obj {value:g}"
                               + ("" if better else f"; no better than incumbent {inc_value:g}"))
            return

        if value >= inc_value - 1e-9:
            record.update(status="pruned_by_bound", lp=value, x=xv, y=yv,
                          note=f"bound {value:g} >= incumbent {inc_value:g}")
            return

        # 取最接近整数的那条盒边来分支？这里按第 4 章的顺序：先 y 后 x。
        for var in ("y", "x"):
            lo, hi = box[var]
            if hi - lo > 1e-6:  # 还可以分
                frac = (xv if var == "x" else yv)
                if abs(frac - round(frac)) > 1e-9:  # 这个变量在当前 LP 解里是小数
                    left = dict(box)
                    left[var] = (lo, float(np.floor(frac)))
                    right = dict(box)
                    right[var] = (float(np.ceil(frac)), hi)
                    record.update(status="branched", lp=value, x=xv, y=yv,
                                  branch_var=var, branch_at=frac,
                                  note=f"LP optimum {value:g} at (x={xv:g}, y={yv:g}); "
                                       f"{var} = {frac:g} is fractional")
                    recurse(left, index, f"{var} <= {int(np.floor(frac))}")
                    recurse(right, index, f"{var} >= {int(np.ceil(frac))}")
                    return

        record.update(status="integral", lp=value, x=xv, y=yv, note="LP optimum is integral")

    recurse(root_box, None, "root")
    return {"nodes": nodes, "edges": edges, "incumbent": incumbent, "inc_value": inc_value}


def fig_branch_and_bound() -> None:
    """把分支定界画成树：每个节点标出 LP 界，被剪掉的理由写在节点里。

    这棵树是脚本现跑的，不是照抄正文；节点的三种归宿（不可行、按界剪、
    整数最优）都能在图上一眼分辨。
    """
    tree = bnb_search()
    nodes, edges = tree["nodes"], tree["edges"]

    # 深搜时先走的子树放左边，所以按发现顺序分配横坐标即可
    depth = {}
    def measure(idx: int, d: int) -> None:
        depth[idx] = d
        for a, b, _ in edges:
            if a == idx:
                measure(b, d + 1)
    measure(0, 0)

    leaves = [n["index"] for n in nodes if not any(a == n["index"] for a, _, _ in edges)]
    slots = {leaf: pos for pos, leaf in enumerate(sorted(leaves))}
    xpos: dict[int, float] = {}

    def place(idx: int) -> float:
        kids = [b for a, b, _ in edges if a == idx]
        if not kids:
            xpos[idx] = float(slots[idx])
        else:
            xpos[idx] = sum(place(k) for k in kids) / len(kids)
        return xpos[idx]
    place(0)

    style = {
        "infeasible": ("tab:red", "infeasible"),
        "pruned_by_bound": ("tab:orange", "pruned by bound"),
        "branched": ("tab:blue", "branched"),
        "integral": ("tab:green", "integer optimum"),
    }

    fig, ax = plt.subplots(figsize=(10.6, 5.4))
    ypos = {idx: -d for idx, d in depth.items()}
    for a, b, label in edges:
        ax.annotate("", (xpos[b], ypos[b]), (xpos[a], ypos[a]),
                    arrowprops={"arrowstyle": "-|>", "lw": 1.3, "color": "#666666",
                                "shrinkA": 26, "shrinkB": 26})
        ax.annotate(label, ((xpos[a] + xpos[b]) / 2, (ypos[a] + ypos[b]) / 2),
                    ha="center", va="center", fontsize=8.5, color="#333333",
                    bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "none"})

    for node in nodes:
        color, _ = style[node["status"]]
        body = f"LP bound {node['lp']:g}" if node["lp"] is not None else "no LP"
        ax.annotate(f"{body}\n{node['note']}", (xpos[node["index"]], ypos[node["index"]]),
                    ha="center", va="center", fontsize=8,
                    bbox={"boxstyle": "round,pad=0.42", "fc": "white", "ec": color, "lw": 1.8})

    handles = [Patch(facecolor="white", edgecolor=c, label=lab)
               for c, lab in style.values()]
    ax.legend(handles=handles, fontsize=8.5, loc="lower left", ncols=2)
    ax.set_xlim(-0.7, max(xpos.values()) + 0.7)
    ax.set_ylim(-max(depth.values()) - 0.55, 0.55)
    ax.axis("off")
    ax.set_title(f"Branch and bound: min x + y, 2x + 2y >= 3, x,y in {{0,1}}\n"
                 f"optimum {tree['inc_value']:g} at {tree['incumbent']}; "
                 "three ways a node dies, only one of them is 'no solution'",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGDIR / "branch_and_bound_tree.png", dpi=DPI)
    plt.close(fig)
    for node in nodes:
        print(f"branch_and_bound_tree.png  node{node['index']} d={depth[node['index']]} "
              f"{node['status']:<16} {node['note']}")


# --------------------------------------------------------------------------
# 14. 换写法省下的不是几毫秒，是几个数量级（Week 2 Day 6）
# --------------------------------------------------------------------------
def fig_formulation_effort() -> None:
    """limit 组：同一实例、同一时间预算，三种写法的搜索量。

    注意单机 C：紧/松两种写法在 10 秒内都没证完（状态 FEASIBLE，目标
    732 / 720，最优是 657），time-indexed 0 个节点就证完了。这是「模型写法
    属于建模决策、不属于调参」最直接的证据。
    """
    rows = [r for r in load_csv(W2 / "results.csv") if r["group"] == "limit"]
    instances = sorted({r["instance"] for r in rows})
    methods = ["milp_tight", "milp_loose", "milp_alt"]
    colors = {"milp_tight": "tab:blue", "milp_loose": "tab:orange", "milp_alt": "tab:green"}

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.8))
    width = 0.26
    # 同 fig_root_lp_bounds：图例按方法标，不要按第一个实例标
    labeled: set[str] = set()
    for pos, inst in enumerate(instances):
        for k, method in enumerate(methods):
            hit = [r for r in rows if r["instance"] == inst and r["method"] == method]
            if not hit:
                continue
            row = hit[0]
            xpos = pos + (k - 1) * width
            nodes = float(row["nodes"] or 0)
            axes[0].bar(xpos, max(nodes, 1.0), width * 0.92, color=colors[method],
                        label=method if method not in labeled else None)
            labeled.add(method)
            axes[0].annotate(f"{row['status']}\n{int(nodes)}", (xpos, max(nodes, 1.0)),
                             textcoords="offset points", xytext=(0, 4), ha="center",
                             fontsize=7.5, rotation=90)
            obj = as_float(row["objective"])
            ref = as_float(row["reference"])
            if obj is not None and ref:
                axes[1].bar(xpos, obj / ref, width * 0.92, color=colors[method])
                axes[1].annotate(f"{obj:g}", (xpos, obj / ref), textcoords="offset points",
                                 xytext=(0, 4), ha="center", fontsize=7.5, rotation=90)

    axes[0].set_yscale("log")
    axes[0].set_ylim(0.8, max(6e4, 1) * 3)
    axes[0].set_ylabel("branch-and-bound nodes (log scale, 0 drawn as 1)")
    axes[0].set_title("How much search the time limit allowed\n"
                      "0 nodes means the root relaxation already proved optimality",
                      fontsize=10)
    axes[0].legend(fontsize=8.5, loc="upper left")

    axes[1].axhline(1.0, color="tab:red", ls="--", lw=1.2)
    axes[1].annotate("optimum", (len(instances) - 0.55, 1.0), textcoords="offset points",
                     xytext=(-4, 5), ha="right", fontsize=8.5, color="tab:red")
    axes[1].set_ylim(0, 1.35)
    axes[1].set_ylabel("objective / optimum")
    axes[1].set_title("What it cost in solution quality\n"
                      "an unscaled axis would hide the time-indexed result at 1.0",
                      fontsize=10)

    for ax in axes:
        ax.set_xticks(range(len(instances)))
        ax.set_xticklabels(instances)
        ax.grid(alpha=0.25, axis="y")

    fig.suptitle("Same problem, same 10-second budget, different formulation",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(FIGDIR / "formulation_effort.png", dpi=DPI)
    plt.close(fig)
    for inst in instances:
        for method in methods:
            hit = [r for r in rows if r["instance"] == inst and r["method"] == method]
            if hit:
                row = hit[0]
                print(f"formulation_effort.png  {inst:<12}{method:<12}"
                      f"status={row['status']:<9} obj={row['objective']:<7}"
                      f"nodes={row['nodes']:<7}solve={row['solve_time']}")


# --------------------------------------------------------------------------
# 15. 约束传播：没试任何组合，域就窄了（Week 3 Day 1）
# --------------------------------------------------------------------------
def fig_interval_propagation() -> None:
    """第 5 章 5.1 的两步传播，画成域一步步收窄的过程。

    给定 S_B >= S_A + 3 且 S_B <= 5：先由 S_A >= 0 得 S_B >= 3，
    再由 S_B <= 5 得 S_A <= 2。两个不等式，两次收窄，一次搜索都没有。
    """
    steps = [
        ("initial domains", 0, 10, 0, 10),
        ("from S_B >= S_A + 3:\nS_A >= 0 so S_B >= 3", 0, 10, 3, 10),
        ("from S_B <= 5:\nS_A <= S_B - 3 = 2", 0, 2, 3, 5),
    ]
    fig, ax = plt.subplots(figsize=(9.6, 4.6))
    for pos, (label, a_lo, a_hi, b_lo, b_hi) in enumerate(steps):
        y = len(steps) - pos
        ax.barh(y + 0.18, a_hi - a_lo, left=a_lo, height=0.3, color="tab:blue")
        ax.barh(y - 0.18, b_hi - b_lo, left=b_lo, height=0.3, color="tab:orange")
        ax.annotate(f"[{a_lo}, {a_hi}]", (a_hi, y + 0.18), textcoords="offset points",
                    xytext=(6, -4), fontsize=9, color="tab:blue")
        ax.annotate(f"[{b_lo}, {b_hi}]", (b_hi, y - 0.18), textcoords="offset points",
                    xytext=(6, -4), fontsize=9, color="tab:orange")
        ax.annotate(label, (0, y + 0.62), fontsize=9, color="#333333", va="bottom")
        if pos > 0:
            old = steps[pos - 1]
            removed_a = (old[1], old[2]) != (a_lo, a_hi)
            removed_b = (old[3], old[4]) != (b_lo, b_hi)
            for lo, hi, ok, color, yy in ((a_lo, a_hi, removed_a, "tab:blue", y + 0.18),
                                          (b_lo, b_hi, removed_b, "tab:orange", y - 0.18)):
                if ok:
                    ax.annotate("", (lo, yy), (steps[pos - 1][1] if color == "tab:blue"
                                               else steps[pos - 1][3], yy),
                                arrowprops={"arrowstyle": "-|>", "color": color, "lw": 1.6})

    ax.axvline(5, color="gray", ls=":", lw=1.1)
    ax.annotate("S_B <= 5", (5, 3.6), fontsize=8.5, color="gray", ha="left")
    ax.set_yticks([])
    ax.set_xlim(-0.4, 12.2)
    ax.set_ylim(0.35, 4.15)
    ax.set_xlabel("start time")
    ax.set_title("Constraint propagation removes values, it does not try them\n"
                 "blue = domain of S_A, orange = domain of S_B",
                 fontsize=11)
    ax.grid(alpha=0.22, axis="x")
    fig.tight_layout()
    fig.savefig(FIGDIR / "interval_propagation.png", dpi=DPI)
    plt.close(fig)
    print("interval_propagation.png  S_A [0,10]->[0,2], S_B [0,10]->[3,5]")


# --------------------------------------------------------------------------
# 16. 可选区间：候选可以先画出来，再决定选哪个（Week 3 Day 2）
# --------------------------------------------------------------------------
def fig_parallel_optional() -> None:
    """3 个作业 2 台机器，每个作业为两台机器各建一个可选区间。

    被选中的候选画成实心，被拒绝的画成浅色——它们**仍然在模型里**，
    只是不参与对应机器上的 NoOverlap。
    """
    jobs = ["J1", "J2", "J3"]
    proc = {"J1": (3, 3), "J2": (2, 2), "J3": (2, 2)}
    chosen = {"J1": 0, "J2": 1, "J3": 1}
    starts = {"J1": 0, "J2": 0, "J3": 2}
    palette = {"J1": "tab:blue", "J2": "tab:orange", "J3": "tab:green"}

    fig, ax = plt.subplots(figsize=(9.4, 4.4))
    for machine in (0, 1):
        for job in jobs:
            start = starts[job]
            duration = proc[job][machine]
            active = chosen[job] == machine
            ax.barh(machine + (0.16 if job == "J1" else -0.16 if job == "J3" else 0.0),
                    duration, left=start, height=0.28 if active else 0.22,
                    color=palette[job], alpha=1.0 if active else 0.22,
                    edgecolor=palette[job], lw=1.2,
                    label=f"{job} on M{machine + 1}" if not active else None)
            ax.annotate(f"{job}", (start + duration / 2, machine),
                        ha="center", va="center", fontsize=9,
                        color="white" if active else palette[job],
                        fontweight="bold" if active else "normal")

    ax.axvline(4, color="tab:red", ls="--", lw=1.4)
    ax.annotate("Cmax = 4", (4.06, 1.55), color="tab:red", fontsize=10)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["M1", "M2"])
    ax.set_xticks(range(0, 6))
    ax.set_xlim(-0.4, 5.6)
    ax.set_ylim(-0.65, 1.85)
    ax.set_xlabel("time   (pale bars = rejected candidates, still present as variables)")
    ax.set_title("Optional intervals: one interval per (job, eligible machine)\n"
                 "total processing 7 over 2 machines, so Cmax >= ceil(7/2) = 4",
                 fontsize=11)
    ax.grid(alpha=0.25, axis="x")
    fig.tight_layout()
    fig.savefig(FIGDIR / "parallel_optional.png", dpi=DPI)
    plt.close(fig)
    print("parallel_optional.png  chosen=" + str(chosen) + " starts=" + str(starts) + " Cmax=4")


# --------------------------------------------------------------------------
# 17. Cumulative：容量不是「总需求够小」，是「任何时刻都够小」（Week 3 Day 4）
# --------------------------------------------------------------------------
def cumulative_profile(placements: list[tuple[str, int, int, int]]
                       ) -> tuple[list[int], list[int]]:
    """把 (任务, 开始, 结束, 需求) 折成每单位时间的总需求。"""
    last = max(e for _, _, e, _ in placements)
    times = list(range(last))
    totals = [sum(q for _, s, e, q in placements if s <= t < e) for t in times]
    return times, totals


def fig_cumulative_profile() -> None:
    """第 5 章 5.7 的两组排程：容量 3 时，第一组的 [2,3) 段超载。

    超载不是「总需求大于容量」，而是**某个区间上**的并发达标。把这一格
    画出来，比一句「违反容量」清楚得多。
    """
    capacity = 3
    bad = [("A", 0, 3, 2), ("B", 1, 4, 1), ("C", 2, 4, 2)]
    good = [("A", 0, 3, 2), ("B", 1, 4, 1), ("C", 3, 5, 2)]
    palette = {"A": "tab:blue", "B": "tab:orange", "C": "tab:green"}

    fig, axes = plt.subplots(2, 1, figsize=(9.8, 6.4), sharex=True)

    for ax, placements, title in ((axes[0], bad, "as written: C runs [2,4)"),
                                  (axes[1], good, "after moving C to [3,5)")):
        times, totals = cumulative_profile(placements)
        # 任务条画在剖面**上方**，否则色块会压住那条阶梯线
        strip = max(max(totals), capacity) + 0.55
        for job, start, end, demand in placements:
            ax.barh(strip, end - start, left=start, height=0.42,
                    color=palette[job], edgecolor="white")
            ax.annotate(f"{job}\nq={demand}", (start + (end - start) / 2, strip),
                        ha="center", va="center", color="white", fontsize=8.5)
        ax.step(times + [times[-1] + 1], totals + [totals[-1]], where="post",
                color="#17324d", lw=2, label="profile: sum of q_i running at t")
        ax.axhline(capacity, color="tab:red", ls="--", lw=1.6)
        ax.annotate(f"capacity Q = {capacity}", (0.04, capacity + 0.12), fontsize=9,
                    color="tab:red")
        for t, total in zip(times, totals):
            if total > capacity:
                ax.axvspan(t, t + 1, color="tab:red", alpha=0.18)
                ax.annotate(f"overloaded: {total} > {capacity}", (t + 0.5, total + 0.22),
                            ha="center", fontsize=8.5, color="tab:red")
        ax.set_ylim(0, strip + 0.55)
        ax.set_yticks(range(0, int(strip) + 1))
        ax.legend(fontsize=8, loc="upper right")
        ax.set_ylabel("resource used")
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.22, axis="x")

    axes[1].set_xlabel("time")
    fig.suptitle("Cumulative: q_i summed over every moment, not over the whole horizon\n"
                 "sum q_i = 5 > Q = 3 for both solvers -- only the bad one overlaps",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGDIR / "cumulative_profile.png", dpi=DPI)
    plt.close(fig)
    for name, placements in (("bad", bad), ("good", good)):
        times, totals = cumulative_profile(placements)
        print(f"cumulative_profile.png  {name}: profile={list(zip(times, totals))} "
              f"peak={max(totals)}")


# --------------------------------------------------------------------------
# 18. 求解器报的每一个数字，含义都不一样（Week 3 Day 5 / Day 6）
# --------------------------------------------------------------------------
def fig_search_evidence() -> None:
    """同一个最优值，四种方法的「代价」与「证据强度」完全不同。

    w3_single_8 所有精确方法都拿到 85；w3_single_12 里只有 time-indexed
    证出了最优，CP-SAT 拿到了同样的目标值但没有证明它。
    """
    rows = load_csv(W3 / "results.csv")
    picks = [("w3_single_8", ["milp_tight", "milp_loose", "milp_alt", "cpsat_jsp"]),
             ("w3_single_12", ["milp_tight", "milp_loose", "milp_alt", "cpsat_jsp"])]
    colors = {"milp_tight": "tab:blue", "milp_loose": "tab:orange",
              "milp_alt": "tab:green", "cpsat_jsp": "tab:purple"}

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.9))
    for panel, (instance, methods) in enumerate(picks):
        sub = [r for r in rows if r["instance"] == instance and r["method"] in methods]
        ref = as_float(sub[0]["batch_reference"]) if sub else None
        for pos, method in enumerate(methods):
            hit = [r for r in sub if r["method"] == method]
            if not hit:
                continue
            row = hit[0]
            obj = as_float(row["objective"]) or 0.0
            axes[panel].bar(pos, obj, 0.62, color=colors[method],
                            hatch="" if row["status"] == "OPTIMAL" else "//",
                            edgecolor="white")
            axes[panel].annotate(f"{obj:g}\n{row['status']}\n{int(float(row['iterations'] or 0))} conflicts",
                                 (pos, obj), textcoords="offset points", xytext=(0, 5),
                                 ha="center", fontsize=8)
        if ref is not None:
            axes[panel].axhline(ref, color="tab:red", ls="--", lw=1.4)
            axes[panel].annotate(f"proven optimum {ref:g}", (len(methods) - 0.55, ref),
                                 textcoords="offset points", xytext=(-4, 6), ha="right",
                                 fontsize=8.5, color="tab:red")
        axes[panel].set_xticks(range(len(methods)))
        axes[panel].set_xticklabels([m.replace("_", "\n") for m in methods], fontsize=8.5)
        axes[panel].set_ylim(0, max(as_float(r["objective"]) or 0 for r in sub) * 1.42)
        axes[panel].set_ylabel("total tardiness")
        axes[panel].set_title(f"{instance}\n"
                              "hatched = the value is not proven optimal",
                              fontsize=10)
        axes[panel].grid(alpha=0.25, axis="y")

    fig.suptitle("A number in the objective column is not the same thing as a proof",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(FIGDIR / "search_evidence.png", dpi=DPI)
    plt.close(fig)
    for instance, methods in picks:
        for method in methods:
            hit = [r for r in rows if r["instance"] == instance and r["method"] == method]
            if hit:
                row = hit[0]
                print(f"search_evidence.png  {instance:<14}{method:<12}"
                      f"status={row['status']:<9} obj={row['objective']:<7}"
                      f"bound={row['best_bound']:<20} it={row['iterations']}")


# --------------------------------------------------------------------------
# 19. 初解与「改问题」：目标值为什么会变差（Week 4 Day 2）
# --------------------------------------------------------------------------
def fig_warmstart_ablation() -> None:
    """五种用法在同一实例上的目标值。

    hint_only / cutoff_only / cutoff_and_hint 都拿到 271；一旦固定前缀或
    固定全部（fix_prefix_3 / fix_all），返回的是 283——不是求解失败，
    而是**问题已经被改小**，这个 283 只属于受限子问题。
    """
    rows = load_csv(W4 / "results.csv")
    target = "sgl_10x1_seed_suboptimal"
    order = ["hint_only", "cutoff_only", "cutoff_and_hint", "fix_prefix_3", "fix_all"]
    labels = {"hint_only": "hint only\n(direction)", "cutoff_only": "cutoff only\n(bound)",
              "cutoff_and_hint": "cutoff + hint", "fix_prefix_3": "fix prefix of 3\n(CHANGES the problem)",
              "fix_all": "fix everything\n(CHANGES the problem)"}
    picks = {r["variant"]: r for r in rows
             if r["instance"] == target and r["group"] == "warmstart_ablation"}
    values = [float(picks[v]["objective"]) for v in order if v in picks]
    optimum = min(values)

    fig, ax = plt.subplots(figsize=(10.2, 4.9))
    colors = ["tab:blue"] * 3 + ["tab:red"] * 2
    bars = ax.bar(range(len(values)), values, 0.6, color=colors)
    for bar, value, variant in zip(bars, values, order):
        ax.annotate(f"{value:g}", (bar.get_x() + bar.get_width() / 2, value),
                    textcoords="offset points", xytext=(0, 5), ha="center", fontsize=10)
    ax.axhline(optimum, color="tab:green", ls="--", lw=1.4)
    # 标注放左边：右边两根柱子会把标签压掉
    ax.annotate(f"best value found = {optimum:g}", (0.0, optimum),
                textcoords="offset points", xytext=(4, 8), ha="left",
                fontsize=9, color="tab:green")
    ax.axvspan(2.5, len(values) - 0.5, color="tab:red", alpha=0.07)
    ax.annotate("these two report the optimum of a\n*restricted* problem, not of the original",
                (3.5, max(values) * 0.62), ha="center", fontsize=9, color="tab:red",
                bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": "tab:red"})
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels([labels[v] for v in order if v in picks], fontsize=8.5)
    ax.set_ylim(0, max(values) * 1.22)
    ax.set_ylabel("objective (total tardiness)")
    ax.set_title(f"{target}: all five runs return status OPTIMAL\n"
                 "the difference is whether the model is still the model you wrote",
                 fontsize=11)
    ax.grid(alpha=0.25, axis="y")
    fig.tight_layout()
    fig.savefig(FIGDIR / "warmstart_ablation.png", dpi=DPI)
    plt.close(fig)
    for variant in order:
        if variant in picks:
            row = picks[variant]
            print(f"warmstart_ablation.png  {variant:<18}obj={row['objective']:<7}"
                  f"status={row['status']:<9}bound={row['best_bound']:<7}"
                  f"solve={row['solve_time']}")


# --------------------------------------------------------------------------
# 20. 冲突诊断：允许的松弛越大，报出来的集合越大（Week 4 Day 3）
# --------------------------------------------------------------------------
def fig_diagnosis_conflict() -> None:
    """三种 slack 下报出的冲突集合与极小化步数。

    slack 越大，被牵连进来的作业越多；reduction_steps 说明「报出来的
    集合」还要再经一步收缩才拿到极小的那个。
    """
    rows = [r for r in load_csv(W4 / "results.csv")
            if r["group"] == "infeasibility_diagnosis"]
    rows.sort(key=lambda r: float(r["variant"].split("_")[1]))
    slack = [float(r["variant"].split("_")[1]) for r in rows]
    reported = [len((r["reported_conflict"] or "").split("|")) for r in rows]
    minimal = [len((r["minimal_conflict"] or "").split("|")) for r in rows]
    steps = [int(float(r["reduction_steps"] or 0)) for r in rows]

    fig, ax = plt.subplots(figsize=(9.6, 4.8))
    width = 0.36
    xpos = np.arange(len(rows))
    ax.bar(xpos - width / 2, reported, width, color="tab:orange", label="reported conflict")
    ax.bar(xpos + width / 2, minimal, width, color="tab:green", label="minimal conflict")
    for pos, row, rep, mini, step in zip(xpos, rows, reported, minimal, steps):
        ax.annotate((row["reported_conflict"] or "").replace("|", "\n"),
                    (pos - width / 2, rep), textcoords="offset points", xytext=(0, 5),
                    ha="center", fontsize=8, color="tab:orange")
        ax.annotate((row["minimal_conflict"] or "").replace("|", "\n"),
                    (pos + width / 2, mini), textcoords="offset points", xytext=(0, 5),
                    ha="center", fontsize=8, color="tab:green")
        ax.annotate(f"reduction steps: {step}", (pos, 0.18), ha="center", fontsize=8.5,
                    color="#333333")

    ax.set_xticks(xpos)
    ax.set_xticklabels([f"allowed slack {s:g}" for s in slack])
    ax.set_ylim(0, max(reported + minimal) * 1.5)
    ax.set_ylabel("jobs named in the conflict")
    ax.set_title("Infeasibility diagnosis on the same model, three relaxations\n"
                 "a bigger allowance drags more jobs into the explanation",
                 fontsize=11)
    ax.legend(fontsize=8.5, loc="upper left")
    ax.grid(alpha=0.25, axis="y")
    fig.tight_layout()
    fig.savefig(FIGDIR / "diagnosis_conflict.png", dpi=DPI)
    plt.close(fig)
    for row in rows:
        print(f"diagnosis_conflict.png  {row['variant']:<10}reported={row['reported_conflict']:<20}"
              f"minimal={row['minimal_conflict']:<20}steps={row['reduction_steps']}")


# --------------------------------------------------------------------------
# 21. 时间预算买到了什么，没买到什么（Week 4 Day 4）
# --------------------------------------------------------------------------
def fig_time_limit_scan() -> None:
    """同一实例，预算 1s / 3s / 10s。

    目标值从 1519 降到 968 就停住了；上界几乎没动（65.13 → 65.51）。
    多出来的时间全用在**搜索**上，没有用在**证明**上。
    """
    rows = [r for r in load_csv(W4 / "results.csv") if r["group"] == "time_limit_scan"]
    rows.sort(key=lambda r: float(r["variant"].split("_")[1].rstrip("s")))
    budgets = [float(r["variant"].split("_")[1].rstrip("s")) for r in rows]
    obj = [float(r["objective"]) for r in rows]
    bound = [float(r["best_bound"]) for r in rows]
    iters = [float(r["iterations"]) for r in rows]

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.3))

    axes[0].plot(budgets, obj, marker="o", color="tab:blue", label="incumbent (best found)")
    axes[0].plot(budgets, bound, marker="s", color="tab:orange", label="best bound")
    axes[0].fill_between(budgets, bound, obj, color="tab:red", alpha=0.10)
    axes[0].annotate("this gap does not close\nthe bound barely moves",
                     (budgets[-1], (obj[-1] + bound[-1]) / 2), ha="right", fontsize=8.5,
                     color="tab:red")
    axes[0].set_yscale("log")
    axes[0].set_xticks(budgets)
    axes[0].set_xlabel("time limit (s)")
    axes[0].set_ylabel("objective (log scale)")
    axes[0].set_title("incumbent and bound over the budget", fontsize=10)
    axes[0].legend(fontsize=8, loc="center left")
    axes[0].grid(alpha=0.25)

    axes[1].bar(range(len(budgets)), iters, 0.55, color="tab:purple")
    for pos, value in zip(range(len(budgets)), iters):
        axes[1].annotate(f"{int(value)}", (pos, value), textcoords="offset points",
                         xytext=(0, 5), ha="center", fontsize=9)
    axes[1].set_xticks(range(len(budgets)))
    axes[1].set_xticklabels([f"{b:g}s" for b in budgets])
    axes[1].set_yscale("symlog", linthresh=1)
    axes[1].set_xlabel("time limit (s)")
    axes[1].set_ylabel("conflicts (symlog)")
    axes[1].set_title("search effort grows with the budget", fontsize=10)
    axes[1].grid(alpha=0.25, axis="y")

    axes[2].plot(budgets, [o / obj[-1] for o in obj], marker="o", color="tab:blue",
                 label="incumbent / best known")
    axes[2].plot(budgets, [b / obj[-1] for b in bound], marker="s", color="tab:orange",
                 label="bound / best known")
    axes[2].axhline(1.0, color="tab:green", ls="--", lw=1.1)
    axes[2].set_xticks(budgets)
    axes[2].set_xlabel("time limit (s)")
    axes[2].set_ylabel("ratio to the best value found")
    axes[2].set_title("normalised: what the budget bought", fontsize=10)
    axes[2].legend(fontsize=8)
    axes[2].grid(alpha=0.25)

    fig.suptitle("A time limit is a stopping rule, not a quality guarantee", fontsize=12)
    fig.tight_layout()
    fig.savefig(FIGDIR / "time_limit_scan.png", dpi=DPI)
    plt.close(fig)
    for row, b in zip(rows, budgets):
        print(f"time_limit_scan.png  {b:g}s status={row['status']:<9} obj={row['objective']:<7}"
              f"bound={float(row['best_bound']):.4f} conflicts={row['iterations']}")


# --------------------------------------------------------------------------
# 22. 各方法相对参考值的差距（报告 §6 主结果）
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
    # Week 1：LP、单纯形、运输、对偶、敏感性、容差
    fig_feasible_region()
    fig_simplex_pivot_path()
    fig_transport_network()
    fig_duality_certificate()
    fig_complementarity()
    fig_tolerance_band()
    fig_shadow_price()
    # Week 2：顺序变量、Big-M、LP 松弛、分支定界、换写法
    fig_single_machine_orders()
    fig_bigm_geometry()
    fig_root_lp_bounds()
    fig_branch_and_bound()
    fig_formulation_effort()
    # Week 3：传播、可选区间、累计资源、求解证据
    fig_interval_propagation()
    fig_parallel_optional()
    fig_cumulative_profile()
    fig_search_evidence()
    # Week 4：强化、初解、诊断、预算、方法质量
    fig_symmetry_ablation()
    fig_symmetry_scale()
    fig_warmstart_ablation()
    fig_diagnosis_conflict()
    fig_time_limit_scan()
    fig_bound_vs_time()
    fig_method_quality()
    print(f"done: {len(list(FIGDIR.glob('*.png')))} PNG figures in {FIGDIR}")


if __name__ == "__main__":
    main()
