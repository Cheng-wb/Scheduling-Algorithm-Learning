# M2 Week 1 周总结：LP、对偶与建模基本功

> 笔记：[Day1](Week_1/Day1.md) · [Day2](Week_1/Day2.md) · [Day3](Week_1/Day3.md) · [Day4](Week_1/Day4.md) · [Day5](Week_1/Day5.md) · [Day6](Week_1/Day6.md) · [Day7](Week_1/Day7.md)

## 1. 本周目标与成果

本周建立了 LP 建模层（生产计划 / 运输 / 指派三个 builder，`GLOP` 后端）、对偶层（`build_dual` 由对偶表机械生成、独立求解验证强对偶）与核对层（约束残差、互补松弛、`rc` 恒等式、对偶可行性、`gap` 五条独立检查），并把影子价格与 `reduced cost` 从「求解器打印的数字」升级为「带区间的边际解释」。

七个可运行脚本对应七天：标准型与极点、求解器读数、两个网络模型、对偶推导、敏感性扫描、容差对拍、复盘总账。实验驱动 `opt_experiments/lp_experiments.py` 用 37 个场景（5 个核心 + 32 个敏感性）生成 `artifacts/month2_w1/` 的 `results.csv`、`sensitivity.csv`、`complementarity.csv`、`metadata.json` 与 `report.md`。

本周**不**注册 benchmark 方法：LP 结果没有 `Schedule`，硬塞进调度基准会让「规则 vs 精确算法」的对比失真。这是接口纪律，不是遗漏。

## 2. 核心概念

| 概念 | 一句话定义 | 读它回答的问题 |
|---|---|---|
| 标准型 | `max c'x, Ax <= b, x >= 0` | 把业务问题写成可套对偶表的形式 |
| 极点 | 可行域中不能表示为两个不同可行点凸组合的点 | LP 的最优解（若存在）必在极点上取到 |
| `slack` | `b_i - a_i'x`（不等式行） | 哪条约束被用满了 |
| `shadow price` | `y_i`，右端项增加 1 单位时最优值的变化率 | 哪条约束值得追加投入 |
| `reduced cost` | `rc_j = c_j - Σ_i a_ij y_i` | 哪个变量差一点就能进基（盈亏平衡价） |
| 弱对偶 | 任意双可行解满足 `c'x <= b'y` | 上界从哪来（`bound` 的依据） |
| 强对偶 | 两边都有最优解时最优值相等 | 对拍的前提 |
| 互补松弛 | `x_j·rc_j = 0` 且 `slack_i·y_i = 0` | 从「可行」推进到「最优」的最后一步 |
| 全幺模 | 约束矩阵的每个基行列式为 ±1 | 为什么网络 LP 的极点天然整数 |

**LP 最优解在极点上**是定理；**运输 / 指派的解恰好整数**在本周是「定理 + 本算例的观察」，两者分开写。

## 3. 三个模型与它们的对偶

| 模型 | 目标 | 约束结构 | 对偶的名字 | 对偶是否唯一 |
|---|---|---|---|---|
| 生产计划 | `max Σ 利润` | 资源行 `<=` + 需求行 `<=` | 影子价格 | 基准算例唯一；折点上不唯一 |
| 运输 | `min Σ c_ij x_ij` | 每节点一条流量守恒等式 | 位势 `u`、`v` | 不唯一（平移自由度） |
| 指派 | `min Σ c_ij x_ij` | 每人 / 每任务恰好一次 | 位势 `u`、`v` | 不唯一（取等约束少于变量数） |

产销平衡的运输问题里，`Σ supply = Σ demand` 使 `u + t, v - t` 不改变任何一条对偶约束，对偶目标变化量 `t·(Σa - Σb) = 0`（实测 `t = 0 / 1 / -2.5` 的目标都是 180.000000）。**对偶不唯一时能核验的是不变量，不是某一组数值。**

## 4. 接口约定（API Contract）

```python
# opt_models/lp_models.py —— 建模层
build_production_lp(data) -> LPModel         # 上界一律写成行，不写成变量界
build_transportation_lp(data) -> LPModel     # 产销不平衡抛 ValueError
build_assignment_lp(data) -> LPModel         # 非方阵抛 ValueError
build_dual(model) -> LPModel                 # 自由/有界变量越界时抛 ValueError
solve_model(model) -> LPSolution

# 核对层（dual_available 为假时一律返回 None，不返回 0）
row_slack(row, activity) -> float
complementarity_rows(model, solution) -> list[dict]
max_complementarity_violation(model, solution) -> float | None
max_reduced_cost_identity_error(model, solution) -> float | None
dual_feasibility_violation(model, solution) -> float | None
duality_gap(primal_objective, dual_objective) -> float
enumerate_vertices_2d(model) -> list[...]    # 只支持两个变量

# 敏感性网格
production_capacity_grid(...) / production_profit_grid(...) / production_demand_grid(...)
```

```python
# opt_experiments/lp_experiments.py —— 驱动
run(output: Path) -> list[dict[str, Any]]    # 输出目录非空则抛 ValueError
main()                                       # 默认写 artifacts/month2_w1/
```

`LPSolution` 字段：`model, sense, status, objective, primal, reduced_cost, dual, activity, slack, dual_available, max_constraint_residual, solve_time`。**`None` 而不是 0**：没有最优解时 `objective`、`primal`、`dual`、`slack`、`dual_available` 全部为假值。

**命名派生规则**：对偶变量名 `y_<原约束名>`、对偶约束名 `d_<原变量名>`、对偶的对偶里的变量名 `y_d_<原变量名>`。名字对应而不是位置索引，是为了让「对照表」可以被机器生成。

## 5. 建模九步

```text
写模型：1 写集合 → 2 写参数（带单位）→ 3 写变量（先定取值范围）→ 4 写目标（无常数项）→ 5 写约束（上界写成行）
读模型：6 求解（先读状态）→ 7 读解（四个量一起读）→ 8 对拍（五条独立核对）→ 9 解释（带区间）
```

四条不可让步的规矩：

```text
上界写成行，不写成变量界       —— 否则 build_dual 抛 ValueError（对偶表会漏项）
状态不是 OPTIMAL 先别解释目标  —— GLOP 对无界 LP 也返回 INFEASIBLE
没有检查过就是 None，不是 0     —— 不可行算例的 objective/primal/dual/slack 全为 None
任何数字都要带区间与容差       —— cap_M ∈ [80, 120]；TOLERANCE = 1e-09
```

## 6. 关键数值证据

| 场景 | 规模 | 状态 | `primal` | `dual` | `\|gap\|` | 互补松弛 | 手算依据 |
|---|---:|---|---:|---:|---:|---:|---|
| `prod_2d` | 2×2 | OPTIMAL | 2200 | 2200 | 4.55e-13 | 2.37e-13 | 极点枚举 `(40, 20)`，`40*40 + 30*20` |
| `prod_base` | 3×5 | OPTIMAL | 2300 | 2300 | 0 | 2.13e-13 | `x = (20, 0, 60)`，逐项相乘相加 |
| `prod_infeasible` | 3×6 | INFEASIBLE | None | None | None | None | `x_P2 <= 50` 与 `x_P2 >= 60` 冲突 |
| `transport_base` | 6×5 | OPTIMAL | 180 | 180 | 0 | 0 | `4*15 + 6*5 + 4*15 + 3*10` |
| `assign_base` | 9×6 | OPTIMAL | 9 | 9 | 0 | 0 | `3! = 6` 种指派全枚举，最小 9 |

敏感性轴（Day 5 实测）：

| 轴 | 基准 | 读数 | 有效区间 | 区间外的实测反例 |
|---|---:|---:|---|---|
| `cap_M` | 100 | 15 | `[80, 120]` | 130 处预测 2750，实测 2600（多算 150） |
| `cap_L` | 80 | 10 | `[60, 90]` | 40 处预测 1900，实测 1600 |
| `P2` 单位利润 | 30 | `rc = -5` | 盈亏平衡价 35 | 25 / 30 处不投产、目标仍 2300 |
| `demand_P1` | 40 | 0 | `>= 20` 一侧成立 | 10 处预测 2300，实测 2150 |

折点上的对偶解不唯一：`cap_M = 80` 处左斜率 20、右斜率 15，求解器报 16.6667；`cap_L = 60` 处报 25（左斜率），`cap_L = 90` 处报 6.66667（右斜率）。

## 7. 测试证据

`tests/test_lp_models.py` 用**显式手算的期望值**对拍（`expected` 不来自被测函数）：

```text
test_production_2d_hand_computed_optimum / _shadow_prices / _vertices_are_hand_enumerated
test_production_base_hand_computed_solution / _duals_and_reduced_cost
test_shadow_price_equals_hand_computed_objective_difference / _is_only_locally_valid
test_reduced_cost_is_a_break_even_price_not_a_slope
test_transportation_hand_computed_solution / _duals / _rejects_unbalanced_instance
test_assignment_matches_brute_force_permutations / _dual_is_not_unique_but_satisfies_hand_checks
test_assignment_rejects_non_square_instance
test_complementary_slackness_hand_pairs_on_production_base
test_numerical_invariants_on_every_model（参数化）
test_dual_of_dual_returns_the_primal_objective · test_build_dual_rejects_bounded_variables
test_infeasible_production_lp_is_detected · test_status_code_alone_is_not_a_proof
test_vertex_enumeration_rejects_models_with_more_than_two_variables
```

复跑命令（在项目目录下运行）：

```bash
python -m pytest -q
```

## 8. 确定性契约

```text
相同数据 + 相同容差  ->  相同 primal / dual / 状态
容差：TOLERANCE = 1e-09（比实测噪声 2e-13 宽约 4 个数量级，比求解器容差 1e-8 严一个数量级）
折点上的对偶解：求解器返回哪一个次梯度不作保证 —— 依赖它的断言必须写成区间或不等式
求解器：OR-Tools pywraplp / GLOP，版本记在 metadata.json 里
```

**「折点上的对偶解不作保证」是本周确定性契约里最重要的一条**：它把「数值可以复现」与「最优点不唯一」分开写，避免后续把某一次的具体读数当成规格。

## 9. 已知局限

```text
状态码：GLOP 对无界 LP 也返回 INFEASIBLE(2)，UNBOUNDED(3) 不出现 —— 状态 2 只能读作「没有最优解」
build_dual：不支持带有限上界的变量（会抛 ValueError），所有上界必须写成行
enumerate_vertices_2d：只支持两个变量，超过两个抛 ValueError
shadow price：只在最优基不变的区间内有效，折点上只是众多次梯度之一
对偶解：运输有平移自由度、指派有退化带来的自由度 —— 能核验的只有不变量
容差探针：只能回答「多严算太严」，「多松算太松」要靠喂已知错误的输入来验证
```

## 10. 遗留问题

| # | 问题 | 状态 |
|---|---|---|
| 1 | 区间端点由哪条约束决定？ | 已由 Day 5 手算给出（`cap_M` 的 80 由 `x_P1 >= 0`、120 由 `demand_P1`） |
| 2 | 折点上该报左斜率还是右斜率？ | 不报单一值：脚本同时打印两侧斜率与求解器读数 |
| 3 | 整数解是定理还是巧合？ | 定理（全幺模 / Birkhoff–von Neumann）+ 本算例的观察，两者分开写 |
| 4 | 区间外怎么办？ | 重新求解并重新读影子价格，不做外推 |
| 5 | 不可行 / 无界怎么区分？ | 手算、加人工界、换后端三者之一；状态码不提供该信息 |
| 6 | LP 表达不了的问题怎么办？ | Week 2 MILP（半连续、固定成本）、Week 3 CP-SAT（顺序与资源不重叠） |
| 7 | 求解时间与最优性如何权衡？ | Week 4（时间限制、`bound`、`gap` 的工程取舍） |

## 11. 待个人完成

闭卷重做两件事：一是 `prod_2d` 的对偶最优解手算（解 `2y_M + y_L = 40`、`y_M + 2y_L = 30` 得 `50/3`、`20/3`，目标 2200），二是 `cap_M ∈ [80, 120]` 与 `cap_L ∈ [60, 90]` 两个区间的推导（从顶点族 `V = 15·cap_M + 10·cap_L` 出发，代入需求与非负条件）。两件事都不看笔记写出来，才算把本周的核心推导收进自己的手里。
