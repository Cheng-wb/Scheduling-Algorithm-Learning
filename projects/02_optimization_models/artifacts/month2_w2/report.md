# M2 Week 2 实验汇总（脚本生成）

两个 formulation 的对照必须分成**两类指标**看：

- `root_lp` 组 = 只解 LP relaxation，回答**松弛强度**（root bound）；
- `limit` 组 = 同一时间预算解 MIP，回答**搜索行为**（incumbent / nodes / gap）。

时间受限时 `limit` 组的 `best_bound` 是随搜索爬升的**进度值**，不是强度指标。

## 实例 `single_a`（total_tardiness）

生成参数 `{"seed": 50, "jobs": 8, "machines": 1}`，时间预算 10.0s，参考类型 `optimum`，参考值 85.0。

| 方法 | 组 | 状态 | 目标值 | best bound | gap | nodes | 建模(s) | 求解(s) | 变量 | 约束 | 非零元 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `milp_tight` | root_lp | `UNKNOWN` | - | 0.0000 | - | None | 0.0041 | 0.002 | 44 | 64 | 192 |
| `milp_tight` | limit | `OPTIMAL` | 85.00 | 85.0000 | 0.0000 | 130 | 0.0024 | 1.480 | 44 | 64 | 192 |
| `milp_loose` | root_lp | `UNKNOWN` | - | 0.0000 | - | None | 0.0027 | 0.001 | 44 | 64 | 192 |
| `milp_loose` | limit | `OPTIMAL` | 85.00 | 85.0000 | 0.0000 | 124 | 0.0024 | 1.439 | 44 | 64 | 192 |
| `milp_alt` | root_lp | `UNKNOWN` | - | 83.9347 | - | None | 0.0274 | 0.013 | 475 | 85 | 4366 |
| `milp_alt` | limit | `OPTIMAL` | 85.00 | 85.0000 | 0.0000 | 0 | 0.0228 | 0.183 | 475 | 85 | 4366 |

## 实例 `single_c`（total_tardiness）

生成参数 `{"seed": 60, "jobs": 15, "machines": 1}`，时间预算 10.0s，参考类型 `proven_by_solver`，参考值 657.0。

| 方法 | 组 | 状态 | 目标值 | best bound | gap | nodes | 建模(s) | 求解(s) | 变量 | 约束 | 非零元 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `milp_tight` | root_lp | `UNKNOWN` | - | 0.0000 | - | None | 0.0120 | 0.003 | 135 | 225 | 675 |
| `milp_tight` | limit | `FEASIBLE` | 732.00 | 60.3039 | 0.9176 | 32501 | 0.0185 | 10.657 | 135 | 225 | 675 |
| `milp_loose` | root_lp | `UNKNOWN` | - | 0.0000 | - | None | 0.0088 | 0.003 | 135 | 225 | 675 |
| `milp_loose` | limit | `FEASIBLE` | 720.00 | 57.6507 | 0.9199 | 58397 | 0.0120 | 10.086 | 135 | 225 | 675 |
| `milp_alt` | root_lp | `UNKNOWN` | - | 656.0508 | - | None | 0.1561 | 0.172 | 2413 | 204 | 30574 |
| `milp_alt` | limit | `OPTIMAL` | 657.00 | 657.0000 | 0.0000 | 0 | 0.1775 | 0.517 | 2413 | 204 | 30574 |

## 实例 `parallel_a`（makespan）

生成参数 `{"seed": 52, "jobs": 8, "machines": 3}`，时间预算 10.0s，参考类型 `proven_by_solver`，参考值 29.0。

| 方法 | 组 | 状态 | 目标值 | best bound | gap | nodes | 建模(s) | 求解(s) | 变量 | 约束 | 非零元 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `milp_alt` | root_lp | `UNKNOWN` | - | 25.0000 | - | None | 0.0954 | 0.012 | 1774 | 274 | 19539 |
| `milp_alt` | limit | `OPTIMAL` | 29.00 | 29.0000 | 0.0000 | 11 | 0.1176 | 0.925 | 1774 | 274 | 19539 |
| `heur_parallel_lpt` | root_lp | `FEASIBLE` | 31.00 | - | - | None | 0.0000 | 0.000 | None | None | None |
| `heur_parallel_lpt` | limit | `FEASIBLE` | 31.00 | - | - | None | 0.0000 | 0.000 | None | None | None |

## 读表要点

1. `milp_tight` 与 `milp_loose` 的 **root LP bound 完全相同**：两者都松到同一个
   退化点（LP 用分数 `x_jk` 让所有工序在释放时间上并行开工），Big-M 的大小在
   这个区间里改变不了松弛值。
2. 真正拉开 root bound 的是 **formulation 的变量定义**：`milp_alt` 的
   time-indexed 模型用时间格点 + 容量约束表达互斥，根节点界高出一个量级。
3. `milp_alt` 的代价在模型规模：变量数随 ``H = max r + Σp`` 线性增长，
   建模时间明显高于 sequence 模型。松弛强 ≠ 一定更快，要连规模一起看。
4. 每个返回的排程都过了 M1 的独立验证器；`INVALID_SOLUTION` 表示求解器给的解
   被独立验证器拒绝，比 `FAILED` 更严重。
