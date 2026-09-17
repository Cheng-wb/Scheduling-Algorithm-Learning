# M2 实验汇总（脚本生成）

`gap`=(objective−best_bound)/max(1,|objective|)：相对**求解器自己的界**。
`gap_to_reference`=(objective−reference)/max(1,|reference|)：相对**该实例的参考值**。
启发式没有 bound，两者都为空，**不能当作 0**。

## 实例参考值

| 实例 | 参考类型 | 参考值 |
|---|---|---:|
| parallel_12 | `proven_by_solver` | 39 |
| parallel_24 | `proven_by_solver` | 71 |
| parallel_8 | `proven_by_solver` | 29 |
| routes_10 | `best-known` | 71 |
| routes_6 | `proven_by_solver` | 56 |
| single_12 | `proven_by_solver` | 532 |
| single_20 | `proven_by_solver` | 903 |
| single_8 | `optimum` | 85 |

`optimum` 来自独立枚举，`proven_by_solver` 来自某个求解器在预算内的证明，
`best-known` 只是本批见过的最好可行解——**不是最优性证书**。

## 逐方法汇总

| 实例 | 组 | 方法 | 成功/失败 | 已证明最优 | 均值 | 平均 gap | 平均 ref gap | 平均耗时(s) | 平均迭代 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| parallel_12 | main | cpsat_parallel | 1/0 | 1 | 39.000 | 0.0000 | 0.0000 | 0.021 | 687.0 |
| parallel_12 | main | cpsat_symmetry | 1/0 | 1 | 39.000 | 0.0000 | 0.0000 | 0.096 | 3513.0 |
| parallel_12 | main | heur_parallel_lpt | 1/0 | 0 | 46.000 | — | 0.1795 | 0.000 | — |
| parallel_12 | main | milp_alt | 1/0 | 1 | 39.000 | 0.0000 | 0.0000 | 1.422 | 8.0 |
| parallel_12 | tl_3 | cpsat_parallel | 1/0 | 1 | 39.000 | 0.0000 | 0.0000 | 0.021 | 687.0 |
| parallel_12 | tl_30 | cpsat_parallel | 1/0 | 1 | 39.000 | 0.0000 | 0.0000 | 0.019 | 687.0 |
| parallel_24 | main | cpsat_parallel | 1/0 | 0 | 71.000 | 0.6620 | 0.0000 | 10.003 | 49641.0 |
| parallel_24 | main | cpsat_symmetry | 1/0 | 1 | 71.000 | 0.0000 | 0.0000 | 0.467 | 10644.0 |
| parallel_24 | main | heur_parallel_lpt | 1/0 | 0 | 75.000 | — | 0.0563 | 0.000 | — |
| parallel_24 | main | milp_alt | 1/0 | 0 | 73.000 | 0.4110 | 0.0282 | 10.173 | 28.0 |
| parallel_24 | tl_3 | cpsat_parallel | 1/0 | 0 | 71.000 | 0.6620 | 0.0000 | 3.004 | 17206.0 |
| parallel_24 | tl_30 | cpsat_parallel | 1/0 | 0 | 71.000 | 0.6620 | 0.0000 | 30.003 | 142997.0 |
| parallel_8 | main | cpsat_parallel | 1/0 | 1 | 29.000 | 0.0000 | 0.0000 | 0.012 | 227.0 |
| parallel_8 | main | cpsat_symmetry | 1/0 | 1 | 29.000 | 0.0000 | 0.0000 | 0.018 | 336.0 |
| parallel_8 | main | heur_parallel_lpt | 1/0 | 0 | 31.000 | — | 0.0690 | 0.000 | — |
| parallel_8 | main | milp_alt | 1/0 | 1 | 29.000 | 0.0000 | 0.0000 | 0.753 | 11.0 |
| parallel_8 | tl_3 | cpsat_parallel | 1/0 | 1 | 29.000 | 0.0000 | 0.0000 | 0.008 | 227.0 |
| parallel_8 | tl_30 | cpsat_parallel | 1/0 | 1 | 29.000 | 0.0000 | 0.0000 | 0.009 | 227.0 |
| routes_10 | main | cpsat_jsp | 1/0 | 0 | 71.000 | 0.4789 | 0.0000 | 10.003 | 67970.0 |
| routes_10 | main | cpsat_parallel | 1/0 | 0 | 71.000 | 0.4789 | 0.0000 | 10.004 | 67536.0 |
| routes_10 | tl_3 | cpsat_parallel | 1/0 | 0 | 71.000 | 0.4789 | 0.0000 | 3.003 | 24580.0 |
| routes_10 | tl_30 | cpsat_parallel | 1/0 | 0 | 71.000 | 0.4789 | 0.0000 | 30.004 | 183430.0 |
| routes_6 | main | cpsat_jsp | 1/0 | 1 | 56.000 | 0.0000 | 0.0000 | 0.033 | 903.0 |
| routes_6 | main | cpsat_parallel | 1/0 | 1 | 56.000 | 0.0000 | 0.0000 | 0.033 | 903.0 |
| routes_6 | tl_3 | cpsat_parallel | 1/0 | 1 | 56.000 | 0.0000 | 0.0000 | 0.030 | 903.0 |
| routes_6 | tl_30 | cpsat_parallel | 1/0 | 1 | 56.000 | 0.0000 | 0.0000 | 0.036 | 903.0 |
| single_12 | main | heur_edd | 1/0 | 0 | 543.000 | — | 0.0207 | 0.000 | — |
| single_12 | main | heur_lpt | 1/0 | 0 | 719.000 | — | 0.3515 | 0.000 | — |
| single_12 | main | heur_spt | 1/0 | 0 | 532.000 | — | 0.0000 | 0.000 | — |
| single_12 | main | heur_wspt | 1/0 | 0 | 568.000 | — | 0.0677 | 0.000 | — |
| single_12 | main | milp_alt | 1/0 | 1 | 532.000 | 0.0000 | 0.0000 | 0.512 | 0.0 |
| single_12 | main | milp_fixing | 1/0 | 1 | 532.000 | 0.0000 | 0.0000 | 0.012 | 0.0 |
| single_12 | main | milp_loose | 1/0 | 0 | 573.000 | 0.9044 | 0.0771 | 10.616 | 116335.0 |
| single_12 | main | milp_tight | 1/0 | 0 | 543.000 | 0.8984 | 0.0207 | 10.077 | 81379.0 |
| single_12 | main | milp_warmstart | 1/0 | 1 | 532.000 | 0.0000 | 0.0000 | 0.032 | 0.0 |
| single_12 | tl_3 | milp_tight | 1/0 | 0 | 543.000 | 0.8984 | 0.0207 | 3.022 | 291.0 |
| single_12 | tl_30 | milp_tight | 1/0 | 0 | 543.000 | 0.8984 | 0.0207 | 30.663 | 404653.0 |
| single_20 | main | heur_edd | 1/0 | 0 | 922.000 | — | 0.0210 | 0.000 | — |
| single_20 | main | heur_lpt | 1/0 | 0 | 2094.000 | — | 1.3189 | 0.000 | — |
| single_20 | main | heur_spt | 1/0 | 0 | 903.000 | — | 0.0000 | 0.000 | — |
| single_20 | main | heur_wspt | 1/0 | 0 | 1003.000 | — | 0.1107 | 0.000 | — |
| single_20 | main | milp_alt | 1/0 | 1 | 903.000 | 0.0000 | 0.0000 | 0.675 | 0.0 |
| single_20 | main | milp_fixing | 1/0 | 1 | 903.000 | 0.0000 | 0.0000 | 0.023 | 0.0 |
| single_20 | main | milp_loose | 1/0 | 0 | 1089.000 | 0.9384 | 0.2060 | 10.042 | 1139.0 |
| single_20 | main | milp_tight | 1/0 | 0 | 968.000 | 0.9323 | 0.0720 | 10.048 | 817.0 |
| single_20 | main | milp_warmstart | 1/0 | 1 | 903.000 | 0.0000 | 0.0000 | 0.052 | 0.0 |
| single_20 | tl_3 | milp_tight | 1/0 | 0 | 968.000 | 0.9323 | 0.0720 | 3.040 | 31.0 |
| single_20 | tl_30 | milp_tight | 1/0 | 0 | 968.000 | 0.9323 | 0.0720 | 30.048 | 3794.0 |
| single_8 | main | heur_edd | 1/0 | 0 | 85.000 | — | 0.0000 | 0.000 | — |
| single_8 | main | heur_lpt | 1/0 | 0 | 195.000 | — | 1.2941 | 0.000 | — |
| single_8 | main | heur_spt | 1/0 | 0 | 85.000 | — | 0.0000 | 0.000 | — |
| single_8 | main | heur_wspt | 1/0 | 0 | 101.000 | — | 0.1882 | 0.000 | — |
| single_8 | main | milp_alt | 1/0 | 1 | 85.000 | 0.0000 | 0.0000 | 0.213 | 0.0 |
| single_8 | main | milp_fixing | 1/0 | 1 | 85.000 | 0.0000 | 0.0000 | 0.012 | 0.0 |
| single_8 | main | milp_loose | 1/0 | 1 | 85.000 | 0.0000 | 0.0000 | 1.165 | 124.0 |
| single_8 | main | milp_tight | 1/0 | 1 | 85.000 | 0.0000 | 0.0000 | 1.187 | 130.0 |
| single_8 | main | milp_warmstart | 1/0 | 1 | 85.000 | 0.0000 | 0.0000 | 0.013 | 0.0 |
| single_8 | tl_3 | milp_tight | 1/0 | 1 | 85.000 | 0.0000 | 0.0000 | 1.247 | 130.0 |
| single_8 | tl_30 | milp_tight | 1/0 | 1 | 85.000 | 0.0000 | 0.0000 | 1.155 | 130.0 |

同一实例跨方法汇总。时间预算相同不代表实际耗时相同；
`OPTIMAL` 只说明求解器证明了自己的模型最优，排程可行性另由独立验证器判定。
