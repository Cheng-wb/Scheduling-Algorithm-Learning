# M2 Week 4 实验汇总（脚本生成）

空值表示**该方法不提供**这个量，不是 0。

## 1. 强化消融（同质并行机，Cmax）

| 实例 | 变体 | 状态 | 目标 | 界 | 冲突 | 耗时(s) |
|---|---|---|---:|---:|---:|---:|
| par_6x3 | `sym=0_red=0` | OPTIMAL | 27 | 27 | 190 | 0.020 |
| par_6x3 | `sym=0_red=1` | OPTIMAL | 27 | 27 | 370 | 0.020 |
| par_6x3 | `sym=1_red=0` | OPTIMAL | 27 | 27 | 377 | 0.029 |
| par_6x3 | `sym=1_red=1` | OPTIMAL | 27 | 27 | 529 | 0.045 |
| par_10x3 | `sym=0_red=0` | OPTIMAL | 29 | 29 | 898 | 0.040 |
| par_10x3 | `sym=0_red=1` | OPTIMAL | 29 | 29 | 701 | 0.035 |
| par_10x3 | `sym=1_red=0` | OPTIMAL | 29 | 29 | 1461 | 0.058 |
| par_10x3 | `sym=1_red=1` | OPTIMAL | 29 | 29 | 1574 | 0.048 |

**判据**：同一实例的四个变体目标值必须完全相同。不同即说明强化改变了最优值，
那是建模错误，不是性能差异。

## 2. warm start 消融（单机，ΣT）

| 实例 | 变体 | 状态 | 目标 | 相对规则初解 | 耗时(s) |
|---|---|---|---:|---:|---:|
| sgl_8x1 | `hint_only` | OPTIMAL | 85 | +0 | 0.010 |
| sgl_8x1 | `cutoff_only` | OPTIMAL | 85 | +0 | 0.012 |
| sgl_8x1 | `cutoff_and_hint` | OPTIMAL | 85 | +0 | 0.009 |
| sgl_8x1 | `fix_prefix_3` | OPTIMAL | 85 | +0 | 0.008 |
| sgl_8x1 | `fix_all` | OPTIMAL | 85 | +0 | 0.008 |
| sgl_12x1 | `hint_only` | OPTIMAL | 532 | +0 | 0.044 |
| sgl_12x1 | `cutoff_only` | OPTIMAL | 532 | +0 | 0.035 |
| sgl_12x1 | `cutoff_and_hint` | OPTIMAL | 532 | +0 | 0.032 |
| sgl_12x1 | `fix_prefix_3` | OPTIMAL | 532 | +0 | 0.014 |
| sgl_12x1 | `fix_all` | OPTIMAL | 532 | +0 | 0.014 |
| sgl_10x1_seed_suboptimal | `hint_only` | OPTIMAL | 271 | -12 | 0.020 |
| sgl_10x1_seed_suboptimal | `cutoff_only` | OPTIMAL | 271 | -12 | 0.039 |
| sgl_10x1_seed_suboptimal | `cutoff_and_hint` | OPTIMAL | 271 | -12 | 0.041 |
| sgl_10x1_seed_suboptimal | `fix_prefix_3` | OPTIMAL | 283 | +0 | 0.016 |
| sgl_10x1_seed_suboptimal | `fix_all` | OPTIMAL | 283 | +0 | 0.015 |

`fix_all` 必然等于规则初解本身——它是把解空间缩到一个点，不是强化。

## 3. 时间预算扫描（20 作业单机，ΣT）

| 预算(s) | 状态 | 目标 | 界 | gap | 节点 | 建模(s) | 求解(s) |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | FEASIBLE | 1519 | 65.130 | 0.9571 | 0 | 0.016 | 1.018 |
| 3 | FEASIBLE | 968 | 65.509 | 0.9323 | 4 | 0.014 | 3.046 |
| 10 | FEASIBLE | 968 | 65.509 | 0.9323 | 597 | 0.016 | 10.037 |

## 4. 不可行诊断（slack 作为旋钮）

| slack | 状态 | 求解次数 | 极小冲突集 | 删除过滤步数 |
|---|---|---:|---|---:|
| 0.5 | INFEASIBLE | 4 | `J000` | 1 |
| 1 | INFEASIBLE | 6 | `J000|J001` | 2 |
| 2 | INFEASIBLE | 8 | `J000|J002|J004` | 3 |

冲突集是**相对这组假设**的极小集：slack 变化后，能各自达标的作业变了，
冲突集也跟着变。所以「冲突」不能脱离「相对哪组假设」单独讲。
