# M2 Week 3：CP-SAT 区间模型实验（脚本生成）

统一时间预算：每次求解 `5` 秒，`num_search_workers=1`、`random_seed=0`。
`gap`=(objective−best_bound)/max(1,|objective|)，`gap_to_reference` 相对该实例的参考值。
参考值分两档：`hand_computed` 是手算时间线推出的最优；`solver_proven` 是另一组同语义设置给出的可证最优。
启发式没有 bound，`gap` 一律留空——**空不是 0**。

## 1. 实例与参考值

| 实例 | 组 | 目标 | 参考类型 | 参考值 |
|---|---|---|---|---:|
| w3_parallel_small | `main` | `makespan` | `hand_computed` | 6 |
| w3_parallel_small | `scale_4` | `makespan` | `hand_computed` | 6 |
| w3_parallel_tight | `main` | `makespan` | `hand_computed` | 13 |
| w3_single_8 | `main` | `total_tardiness` | `cross_checked` | — |
| w3_single_12 | `main` | `total_tardiness` | `cross_checked` | — |
| w3_parallel_8 | `main` | `makespan` | `cross_checked` | — |
| w3_parallel_12 | `main` | `makespan` | `cross_checked` | — |
| w3_jsp_2x2 | `main` | `makespan` | `hand_computed` | 7 |
| w3_routes_6 | `main` | `makespan` | `cross_checked` | — |
| w3_cumulative_small | `no_capacity` | `makespan` | `per_group` | 10 |
| w3_cumulative_small | `cap_1` | `makespan` | `per_group` | 15 |
| w3_cumulative_small | `cap_2` | `makespan` | `per_group` | 10 |
| w3_cumulative_small | `infeasible_demand_2` | `makespan` | `per_group` | — |

## 2. 逐次运行

| run | 状态 | 目标 | bound | gap | 参考 | ref gap | 建模(s) | 求解(s) | 分支 | 峰值资源 | 独立校验 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| w3_parallel_small / cpsat_parallel / main | `OPTIMAL` | 6.000 | 6.000 | 0.0000 | 6.000 | 0.0000 | 0.0085 | 0.0083 | 96 | 2 | 通过 |
| w3_parallel_small / cpsat_parallel / scale_4 | `OPTIMAL` | 6.000 | 6.000 | 0.0000 | 6.000 | 0.0000 | 0.0009 | 0.0050 | 96 | 2 | 通过 |
| w3_parallel_tight / cpsat_parallel / main | `OPTIMAL` | 13.000 | 13.000 | 0.0000 | 13.000 | 0.0000 | 0.0011 | 0.0042 | 66 | 2 | 通过 |
| w3_parallel_tight / heur_parallel_lpt / main | `FEASIBLE` | 13.000 | — | — | 13.000 | 0.0000 | 0.0000 | 0.0014 | — | 2 | 通过 |
| w3_single_8 / milp_tight / main | `OPTIMAL` | 85.000 | 85.000 | 0.0000 | — | — | 0.0030 | 1.3744 | 130 | 1 | 通过 |
| w3_single_8 / milp_loose / main | `OPTIMAL` | 85.000 | 85.000 | 0.0000 | — | — | 0.0028 | 1.4642 | 124 | 1 | 通过 |
| w3_single_8 / milp_alt / main | `OPTIMAL` | 85.000 | 85.000 | 0.0000 | — | — | 0.0218 | 0.1487 | 0 | 1 | 通过 |
| w3_single_8 / cpsat_jsp / main | `OPTIMAL` | 85.000 | 85.000 | 0.0000 | — | — | 0.0020 | 0.1602 | 4495 | 1 | 通过 |
| w3_single_8 / cpsat_parallel / main | `OPTIMAL` | 85.000 | 85.000 | 0.0000 | — | — | 0.0014 | 0.1369 | 4495 | 1 | 通过 |
| w3_single_8 / heur_edd / main | `FEASIBLE` | 85.000 | — | — | — | — | 0.0000 | 0.0001 | — | 1 | 通过 |
| w3_single_12 / milp_tight / main | `FEASIBLE` | 543.000 | 55.173 | 0.8984 | — | — | 0.0056 | 5.0263 | 430 | 1 | 通过 |
| w3_single_12 / milp_loose / main | `FEASIBLE` | 573.000 | 54.798 | 0.9044 | — | — | 0.0081 | 5.3771 | 14380 | 1 | 通过 |
| w3_single_12 / milp_alt / main | `OPTIMAL` | 532.000 | 532.000 | 0.0000 | — | — | 0.1266 | 0.5933 | 0 | 1 | 通过 |
| w3_single_12 / cpsat_jsp / main | `FEASIBLE` | 532.000 | 1.000 | 0.9981 | — | — | 0.0014 | 5.0174 | 74393 | 1 | 通过 |
| w3_single_12 / cpsat_parallel / main | `FEASIBLE` | 532.000 | 1.000 | 0.9981 | — | — | 0.0018 | 5.0182 | 73501 | 1 | 通过 |
| w3_single_12 / heur_edd / main | `FEASIBLE` | 543.000 | — | — | — | — | 0.0000 | 0.0001 | — | 1 | 通过 |
| w3_parallel_8 / milp_alt / main | `OPTIMAL` | 29.000 | 29.000 | 0.0000 | — | — | 0.0914 | 0.7622 | 11 | 3 | 通过 |
| w3_parallel_8 / cpsat_parallel / main | `OPTIMAL` | 29.000 | 29.000 | 0.0000 | — | — | 0.0011 | 0.0106 | 227 | 3 | 通过 |
| w3_parallel_8 / heur_parallel_lpt / main | `FEASIBLE` | 31.000 | — | — | — | — | 0.0000 | 0.0002 | — | 3 | 通过 |
| w3_parallel_12 / milp_alt / main | `OPTIMAL` | 39.000 | 39.000 | 0.0000 | — | — | 0.2260 | 1.5602 | 8 | 3 | 通过 |
| w3_parallel_12 / cpsat_parallel / main | `OPTIMAL` | 39.000 | 39.000 | 0.0000 | — | — | 0.0016 | 0.0250 | 687 | 3 | 通过 |
| w3_parallel_12 / heur_parallel_lpt / main | `FEASIBLE` | 46.000 | — | — | — | — | 0.0000 | 0.0003 | — | 3 | 通过 |
| w3_jsp_2x2 / cpsat_jsp / main | `OPTIMAL` | 7.000 | 7.000 | 0.0000 | 7.000 | 0.0000 | 0.0008 | 0.0019 | 5 | 2 | 通过 |
| w3_routes_6 / cpsat_jsp / main | `OPTIMAL` | 56.000 | 56.000 | 0.0000 | — | — | 0.0020 | 0.0388 | 903 | 3 | 通过 |
| w3_routes_6 / cpsat_parallel / main | `OPTIMAL` | 56.000 | 56.000 | 0.0000 | — | — | 0.0017 | 0.0382 | 903 | 3 | 通过 |
| w3_cumulative_small / cpsat_parallel / no_capacity | `OPTIMAL` | 10.000 | 10.000 | 0.0000 | 10.000 | 0.0000 | 0.0024 | 0.0032 | 24 | 2 | 通过 |
| w3_cumulative_small / cpsat_cumulative / cap_1 | `OPTIMAL` | 15.000 | 15.000 | 0.0000 | 15.000 | 0.0000 | 0.0011 | 0.0032 | 23 | 1 | 通过 |
| w3_cumulative_small / cpsat_cumulative / cap_2 | `OPTIMAL` | 10.000 | 10.000 | 0.0000 | 10.000 | 0.0000 | 0.0011 | 0.0041 | 24 | 2 | 通过 |
| w3_cumulative_small / cpsat_cumulative / infeasible_demand_2 | `INFEASIBLE` | — | — | — | — | — | 0.0014 | 0.0003 | 0 | — | 通过 |

## 3. 第 6 天：同实例集、同预算的 MILP × CP-SAT 对照

MILP 方法可用：`milp_tight`, `milp_loose`, `milp_alt`。

同一实例、同一时间预算、同一独立验证器。`参考` 一列是该实例在**本批次**里
已经证明最优的最小目标值（`proven_by_solver`），不是独立枚举的证书。

| 实例 | 目标 | 方法 | 状态 | 目标值 | bound | gap | 建模(s) | 求解(s) | 相对参考 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| w3_single_8 | `total_tardiness` | `milp_tight` | `OPTIMAL` | 85.000 | 85.000 | 0.0000 | 0.0030 | 1.3744 | 0.0000 |
| w3_single_8 | `total_tardiness` | `milp_loose` | `OPTIMAL` | 85.000 | 85.000 | 0.0000 | 0.0028 | 1.4642 | 0.0000 |
| w3_single_8 | `total_tardiness` | `milp_alt` | `OPTIMAL` | 85.000 | 85.000 | 0.0000 | 0.0218 | 0.1487 | 0.0000 |
| w3_single_8 | `total_tardiness` | `cpsat_jsp` | `OPTIMAL` | 85.000 | 85.000 | 0.0000 | 0.0020 | 0.1602 | 0.0000 |
| w3_single_8 | `total_tardiness` | `cpsat_parallel` | `OPTIMAL` | 85.000 | 85.000 | 0.0000 | 0.0014 | 0.1369 | 0.0000 |
| w3_single_8 | `total_tardiness` | `heur_edd` | `FEASIBLE` | 85.000 | — | — | 0.0000 | 0.0001 | 0.0000 |
| w3_single_12 | `total_tardiness` | `milp_tight` | `FEASIBLE` | 543.000 | 55.173 | 0.8984 | 0.0056 | 5.0263 | 0.0207 |
| w3_single_12 | `total_tardiness` | `milp_loose` | `FEASIBLE` | 573.000 | 54.798 | 0.9044 | 0.0081 | 5.3771 | 0.0771 |
| w3_single_12 | `total_tardiness` | `milp_alt` | `OPTIMAL` | 532.000 | 532.000 | 0.0000 | 0.1266 | 0.5933 | 0.0000 |
| w3_single_12 | `total_tardiness` | `cpsat_jsp` | `FEASIBLE` | 532.000 | 1.000 | 0.9981 | 0.0014 | 5.0174 | 0.0000 |
| w3_single_12 | `total_tardiness` | `cpsat_parallel` | `FEASIBLE` | 532.000 | 1.000 | 0.9981 | 0.0018 | 5.0182 | 0.0000 |
| w3_single_12 | `total_tardiness` | `heur_edd` | `FEASIBLE` | 543.000 | — | — | 0.0000 | 0.0001 | 0.0207 |
| w3_parallel_8 | `makespan` | `milp_alt` | `OPTIMAL` | 29.000 | 29.000 | 0.0000 | 0.0914 | 0.7622 | 0.0000 |
| w3_parallel_8 | `makespan` | `cpsat_parallel` | `OPTIMAL` | 29.000 | 29.000 | 0.0000 | 0.0011 | 0.0106 | 0.0000 |
| w3_parallel_8 | `makespan` | `heur_parallel_lpt` | `FEASIBLE` | 31.000 | — | — | 0.0000 | 0.0002 | 0.0690 |
| w3_parallel_12 | `makespan` | `milp_alt` | `OPTIMAL` | 39.000 | 39.000 | 0.0000 | 0.2260 | 1.5602 | 0.0000 |
| w3_parallel_12 | `makespan` | `cpsat_parallel` | `OPTIMAL` | 39.000 | 39.000 | 0.0000 | 0.0016 | 0.0250 | 0.0000 |
| w3_parallel_12 | `makespan` | `heur_parallel_lpt` | `FEASIBLE` | 46.000 | — | — | 0.0000 | 0.0003 | 0.1795 |
| w3_routes_6 | `makespan` | `cpsat_jsp` | `OPTIMAL` | 56.000 | 56.000 | 0.0000 | 0.0020 | 0.0388 | 0.0000 |
| w3_routes_6 | `makespan` | `cpsat_parallel` | `OPTIMAL` | 56.000 | 56.000 | 0.0000 | 0.0017 | 0.0382 | 0.0000 |

### 3.1 交叉核对：两条独立技术路线给出同一个最优值

| 实例 | MILP 证明的最优 | CP-SAT 证明的最优 | 是否一致 |
|---|---:|---:|---|
| w3_single_8 | 85 | 85 | 一致 |
| w3_single_12 | 532 | — | 无双方同时证明最优的记录 |
| w3_parallel_8 | 29 | 29 | 一致 |
| w3_parallel_12 | 39 | 39 | 一致 |
| w3_routes_6 | — | 56 | 无双方同时证明最优的记录 |

## 4. Cumulative 与 NoOverlap 的语义对照

同一实例（2 台机器 × 3 个 p=5 的工序）在不同容量设置下的结果：

| 组 | 方法 | 容量 | 需求 | 状态 | Cmax | 峰值占用 |
|---|---|---:|---:|---|---:|---:|
| `no_capacity` | `cpsat_parallel` | — | — | `OPTIMAL` | 10.000 | 2 |
| `cap_1` | `cpsat_cumulative` | 1 | 1 | `OPTIMAL` | 15.000 | 1 |
| `cap_2` | `cpsat_cumulative` | 2 | 1 | `OPTIMAL` | 10.000 | 2 |
| `infeasible_demand_2` | `cpsat_cumulative` | 1 | 2 | `INFEASIBLE` | — | — |

## 5. 状态分布

| 状态 | 次数 |
|---|---:|
| `FEASIBLE` | 9 |
| `INFEASIBLE` | 1 |
| `OPTIMAL` | 19 |

平均求解耗时 0.9236 s（29 次成功求解）。
