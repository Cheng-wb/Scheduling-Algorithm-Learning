# M2 Week 2 周总结：MILP 深化 —— Big-M、线性化与分支定界

> 笔记：[Day1](Week_2/Day1.md) · [Day2](Week_2/Day2.md) · [Day3](Week_2/Day3.md) · [Day4](Week_2/Day4.md) · [Day5](Week_2/Day5.md) · [Day6](Week_2/Day6.md) · [Day7](Week_2/Day7.md)

## 1. 本周目标与成果

本周把「整数变量」这件事从「加一个 `IntVar`」推进到**能说明为什么某个模型更慢**：建立了单机 sequence（disjunctive）MILP 的 tight / loose 两个 Big-M 变体与本模块第一个替代 formulation（time-indexed），并把 `branch-and-bound` 的读数（`incumbent`、`best bound`、`gap`、`node`）与 `LP relaxation` 的强度区分开。

- **三个注册方法**（`opt_solvers.registry.available()` 确认）：`milp_tight`、`milp_loose`、`milp_alt`。
- **七个可运行脚本**：`examples/m2w2d1_sequence_milp.py` … `m2w2d7_why_models_differ.py`，逐日一个。
- **实验驱动**：`opt_experiments/w2_formulations.py`（`root_lp` 组 + 限时组，生成对照表与报告）；**测试**：`tests/test_milp_scheduling.py` 新增 42 个用例全部通过，本仓全套 `python -m pytest -q` 为 `232 passed`。

本周最需要记住的结论（三条，都来自本周自己的实测）：

```text
1. Big-M 的紧度 ≠ 松弛强度：tight 与 loose 的 root LP bound 完全相同（本实例族 + ΣTj 下都是 0）；
   紧度改的是矩阵系数与限时搜索里的 incumbent / node，不是界。
2. 改强度的是变量定义：time-indexed 的 root bound 达到最优值的 98.75%–99.97%，代价是变量数随时间界线性增长。
3. 强度看 root LP bound，搜索行为看 incumbent / node / runtime / gap —— 限时后的 best bound 是进度值，不是强度值。
```

## 2. 核心概念

| 概念 | 一句话定义 | 读它回答的问题 |
|---|---|---|
| 序对二元变量 | `x_jk = 1` 表示 `j` 先于 `k` | 谁先加工 |
| `Big-M` | `s_k >= s_j + p_j - M_jk(1 - x_jk)` 里的 `M_jk` | 约束被放松时允许的最大「逆序幅度」 |
| `indicator` 约束 | 「当且仅当 `x = 1` 时该式成立」的等价写法 | 为什么 `M` 必须足够大才合法 |
| tight / loose `M` | 逐对 `H - r_k` / 全局 `n·H` | 系数能写多紧 |
| `LP relaxation` | 把整数限制放开后的 LP | 界从哪来 |
| `root bound` | 根节点 LP 松弛的目标值（最小化问题里是下界） | 搜索树的地板有多高 |
| `incumbent` / `best bound` | 目前最好的可行解目标值 / 未探索节点界的最小值 | 找到了多好的解 / 还有多少可能更好 |
| `gap` | `\|incumbent - best bound\| / \|incumbent\|` | 离「证明最优」还有多远 |
| `node` | 搜索树里被求解过一次 LP 的节点 | 爬了多少步（**不可复现读数**） |
| `presolve` / `root cuts` / `strong branching` | 求解器在根节点做的三层额外处理 | 为什么日志里的「根界」可能不是纯 LP 界 |
| `precedence` | 同一 job 内后道工序开工 ≥ 前道完工 | 多工序实例的连接约束 |
| time-indexed | `y[工序][机器][时刻] = 1` 表示该工序在该时刻在该机器开工 | 换变量定义换强度 |

**区分纪律**：`root bound` 是定理级读数（确定性）；`incumbent` / `best bound` / `gap` 是搜索状态；`node` 与 `solve_time` 是运行读数（**不可复现**，见第 7 节）。

## 3. 三个 formulation 与规模

| formulation | 变量 | 约束 | `M` | 本实例族的 root LP bound |
|---|---|---|---|---|
| `milp_tight` | `n` 个 `s` + `n` 个 `T` + `C(n,2)` 个 `x`（`2n + C(n,2)`） | 每条 disjunction 2 条（`2·C(n,2)`）+ `n` 条 `T` 定义 | 逐对 `H - r_k` | `0.0000` |
| `milp_loose` | 同上 | 同上（只换系数） | 全局 `n·H` | `0.0000` |
| `milp_alt` | `n` 个 `T` + `Σ_工序 (H - p_o - r_o + 1)` 个 `y` | `n` 条 assignment + `n` 条 `T` 定义 + 每时刻一条容量 | 无 | 最优值的 `98.75%`–`99.97%` |

规模随时间界的实测增长（`seed = 50`，单机，`ΣTj`）：

| `n` | `H` | seq 变量 | alt 变量 | alt/seq | seq 约束 | alt 约束 |
|---|---|---|---|---|---|---|
| 8 | 71 | 44 | 475 | 10.8 | 64 | 85 |
| 12 | 113 | 90 | 1206 | 13.4 | 144 | 137 |
| 16 | 138 | 152 | 2017 | 13.3 | 256 | 170 |
| 20 | 180 | 230 | 3343 | 14.5 | 400 | 220 |
| 40 | 380 | 860 | 14692 | 17.1 | 1600 | 460 |

`M` 的两个度量（8 job 实例）：tight 的 56 个方向之和 `3640`，loose 为 `n·H = 568` 每方向、合计 `31808` —— **`M` 相差近 `9` 倍，root LP bound 完全相同。**

## 4. 接口约定（API Contract）

```python
# opt_models/milp_scheduling.py —— 建模层
FORMULATIONS = ("milp_tight", "milp_loose", "milp_alt")
SOLVER_ID = "CBC_MIXED_INTEGER_PROGRAMMING"      # Cbc 2.10.12
MAX_TIME_INDEXED_VARS = 400_000                  # 规模闸门，超过直接拒绝建模
class InfeasibleModelError(ValueError)           # 截止期不可行在建模型时抛出
time_horizon(instance) -> int                    # H = max r_j + Σ p_j
pair_big_m(instance, horizon) -> dict            # tight：M_jk = H - r_k
loose_big_m(instance, horizon) -> int            # loose：M = n·H
earliest_start_bounds(instance) -> dict          # 前道工序累计推移后的最早开工
build_sequence_model(instance, spec) -> _BuiltModel
build_time_indexed_model(instance, spec) -> _BuiltModel
build_model(instance, spec) -> _BuiltModel       # 按 spec["method"] 分派
model_stats(instance, spec) -> dict              # 只建模不求解：变量/约束/非零/建模时间
trivial_lower_bound(instance, objective_name) -> float | None

# 注册方法（spec 支持 objective / time_limit / seed / root_lp）
milp_tight(instance, spec) -> SolveResult
milp_loose(instance, spec) -> SolveResult
milp_alt(instance, spec) -> SolveResult

# opt_experiments/w2_formulations.py —— 驱动
build_instances() / collect(...) / compare_models(...) / run(output) / main()
```

`SolveResult` 字段（`opt_solvers/result.py`）：`method, status, objective, best_bound, schedule, build_time, solve_time, iterations, detail`。三条纪律：

```text
objective 来自独立重算（不是求解器读数），solver_objective 另存 detail；best_bound=None 表示「不提供下界」，不是 0；
iterations = solver.nodes()，配 iterations_kind="branch_and_bound"；
只解 LP 时 status="UNKNOWN"、objective=None、iterations=None、detail["bound_kind"]="lp_relaxation"。
```

## 5. 关键数值证据

**强度（`root LP bound`，与预算无关的确定性测量）**：

| `n` | seq root bound | alt root bound | 最优值（来源） | alt bound / 最优 |
|---|---|---|---|---|
| 8 | 0.0000 | 83.9347 | 85（alt 证明） | 98.75% |
| 12 | 0.0000 | 293.0900 | 294（alt 证明） | 99.69% |
| 16 | 0.0000 | 542.7683 | 543（alt 证明） | 99.96% |
| 20 | 0.0000 | 911.7667 | 912（alt 证明） | 99.97% |

**搜索行为（限时组，实例各自预算）**：

| 实例 | 方法 | 状态 | incumbent | final bound | gap | nodes | 求解 |
|---|---|---|---|---|---|---|---|
| single_a（8 job，5s） | tight / loose / alt | `OPTIMAL` ×3 | 85.0 | 85.0000 | 0.0000 | 130 / 124 / 0 | 1.544 / 1.527 / 0.204 |
| single_c（15 job，5s） | tight | `FEASIBLE` | 732.0 | 60.3039 | 0.9176 | 305 | 5.042 |
| single_c | loose | `FEASIBLE` | 720.0 | 57.6507 | 0.9199 | 13010 | 5.205 |
| single_c | alt | `OPTIMAL` | 657.0 | 657.0000 | 0.0000 | 0 | 0.625 |
| single_d（20 job，10s） | tight | `FEASIBLE` | 981.0 | 63.0999 | 0.9357 | 207 | 10.081 |
| single_d | loose | `FEASIBLE` | 1019.0 | 58.8305 | 0.9423 | 580 | 10.034 |
| single_d | alt | `OPTIMAL` | 912.0 | 912.0000 | 0.0000 | 0 | 0.810 |

**「换系数救不回松弛」的证据（8 job，五种写法）**：纯 LP 上 `现状 / tight + disjunction 等式 / 逐对最小可行 M / 逐对最小可行 M + 等式 / loose + 等式` 的界全部是 `0.0000`；穷举 `40320` 个顺序得到逐对最小可行 `M ∈ [61, 66]`，而 `M/2 = 30.5` 仍大于 `p_max = 16`，所以 `x = 0.5` 时工序照样能两两重叠。

**分支定界的手算对拍（Day 4）**：3 job 实例的两棵树各 `7` 个节点、叶子 `0` 与 `2`；4 job 实例 `23` 个节点、`11 + 1` 次剪枝。CBC 日志里同一实例出现 `47 / 65 / 107` 三个数而 `SolveResult` 报 `85` —— 日志数字必须与 `SolveResult` 对账（`107` 属于更强的构造值，不等于最终 `best_bound`）。

**规模劣势会不会翻盘（40 job，`H = 380`，10s 预算）**：`milp_alt` 用 `0.980s + 4.467s` 解到 `OPTIMAL 4488`（`0` 个分支节点）；`milp_tight` 烧完 `10.213s` 只给出 `FEASIBLE 7325` 与 `135.2009` 的界。**alt 的变量是 sequence 的 `17.1` 倍，但「省下整棵搜索树」的收益远大于「建模与每节点 LP 变大」的代价。**

## 6. 测试证据

`tests/test_milp_scheduling.py` 共 42 个用例，分五类：

| 类别 | 代表用例 |
|---|---|
| 手算对拍 | `test_three_job_hand_computed_tardiness` / `_makespan`、`test_parallel_hand_computed_makespan`、`test_precedence_hand_computed_completion_time` |
| 跨 formulation 一致性 | `test_three_formulations_agree`、`test_loose_and_tight_agree_on_a_larger_instance`、`test_enumeration_equivalence_single_machine` / `_parallel` / `_four_jobs_with_release_dates` |
| Big-M 合法性 | `test_big_m_never_cuts_off_feasible_schedules`、`test_big_m_matches_the_proved_time_bounds` |
| 松弛强度 | `test_root_lp_bound_not_above_integer_optimum`、`test_root_lp_reports_bound_without_a_schedule`、`test_time_indexed_relaxation_is_strictly_stronger_here` |
| 状态与契约 | `test_infeasible_deadline_returns_infeasible` / `_below_processing_time_is_certified_at_build_time`、`test_sequence_model_declines_parallel_instances`、`test_unknown_objective_is_failed`、`test_statuses_and_timings_are_well_formed`、`test_every_returned_schedule_passes_independent_validator`、`test_solver_objective_matches_recomputed_objective` |

对拍纪律：`test_enumeration_equivalence_*` 的期望值来自 M1 的独立穷举 oracle（另一条计算路径），不是来自被测函数；`test_every_returned_schedule_passes_independent_validator` 用独立验证器复核每一个返回的 `Schedule`。

复跑命令（在项目目录下运行）：

```bash
python -m pytest tests/test_milp_scheduling.py -q
python -m pytest -q
```

## 7. 确定性契约

```text
相同实例 + 相同目标  ->  相同 root LP bound（确定性，本周重复测量一致）
相同实例 + 相同预算  ->  incumbent 与 final bound 一致，但 nodes / solve_time 可以差一个数量级
                         （实测 single_c 上 tight 从 305 变 16500，约 54 倍）
限时语义：SetTimeLimit 在节点边界检查，单次重跑可能轻微超预算（实测 6.198s 对 5.0s 预算）
随机种子：CBC 经 pywraplp 不暴露，detail["seed_effective"] = False，无法固定搜索路径
求解器：OR-Tools 9.15.6755 / pywraplp / CBC_MIXED_INTEGER_PROGRAMMING（Cbc 2.10.12）；LP 走 GLOP
```

**「强度可复现、搜索行为不可复现」是本周契约里最重要的一条**：它决定了哪些数字能写成结论（root LP bound）、哪些只能写成「本轮实测」（node 数、限时 incumbent）。

## 8. 已知局限

```text
root bound 为 0：是「本实例族 + ΣTj 目标 + 单机单工序」的实测结论，不是普遍定律 —— 换 makespan 时界不为 0，
                实例的 r_j 更小 / p_j 更大时 M/2 > p_max 也可能不成立
alt 的规模天花板：MAX_TIME_INDEXED_VARS = 400_000，变量数随 H 线性增长，H 很大时首先被拒绝建模
tight vs loose：搜索行为互有胜负（8 job 上 loose 的 nodes 与时间都更小），不能外推成一般规律
CBC 日志：同一实例可能出现 47 / 65 / 107 三个不同层级的「界」，必须与 SolveResult 对账后再引用
模型范围：单机 / 单工序的 sequence 模型拒绝并行机实例（test_sequence_model_declines_parallel_instances）
oracle：exhaustive_optimum 只支持 makespan / total_tardiness / weighted_completion_time 三个目标
```

## 9. 遗留问题与衔接

| # | 问题 | 状态 |
|---|---|---|
| 1 | `M` 的取值除了合法性还有别的作用吗？ | 已测：只改变搜索路径与限时 incumbent，不改变 root bound |
| 2 | 更强的 formulation 有没有代价？ | 有：建模成本高一个量级、变量数线性于 `H`、有硬闸门 |
| 3 | 求解器的「根界」与纯 LP 界是同一个数吗？ | 不是：presolve / root cuts / strong branching 会抬高它（Day 4 的 0 / 47 / 65） |
| 4 | 限时结束后该报什么？ | `incumbent` + `best bound` + `gap`，并声明这是搜索进度而非强度 |
| 5 | 40 job 以上怎么办？ | 回到 sequence 模型或启发式；本周未测更大规模 |
| 6 | 更强 formulation / 工程取舍从哪来？ | Week 3（CP-SAT：顺序与资源不重叠的直接表达）、Week 4（时间限制、`bound`、`gap` 的取舍） |

## 10. 待个人完成

闭卷重做三件事：一是写出 sequence 模型的 `2n + C(n,2)` 与 time-indexed 模型的 `n + Σ_工序 (H - p_o - r_o + 1)` 两个规模公式并在 `n = 20` 上核对到 `230 / 3343`；二是手推 `x = 0.5` 时两条 disjunction 的放松形式，并解释为什么 `M/2 > p_max` 时界会掉到 `0`；三是在不看笔记的情况下复述「强度看 root LP bound，搜索行为看 incumbent / node / runtime / gap」这条口径，并各举一个本周的实测数字。
