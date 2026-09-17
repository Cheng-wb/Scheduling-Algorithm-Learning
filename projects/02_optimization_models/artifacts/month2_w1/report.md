# M2 Week 1 实验汇总（脚本生成）

容差 `TOLERANCE = 1e-09`。空值表示**该方法不提供**这个量，
不是 0——本文件里没有任何一个 `0.0` 是「没测」的意思。

## 1. 场景与目标值

`primal` 与 `dual` 是**两次独立求解**（对偶模型由 `build_dual` 构造），
两者相等是强对偶的数值对拍。`dual_involution_ok` 检查「对偶的对偶」
是否回到原问题的目标值。

| 场景 | 类型 | 状态 | 变量 | 约束 | primal | dual | \|gap\| | 对偶的对偶 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| prod_2d | `production` | OPTIMAL | 2 | 2 | 2200 | 2200 | 4.55e-13 | 是 |
| prod_base | `production` | OPTIMAL | 3 | 5 | 2300 | 2300 | 0 | 是 |
| prod_infeasible | `production` | INFEASIBLE | 3 | 6 | — | — | — | — |
| transport_base | `transportation` | OPTIMAL | 6 | 5 | 180 | 180 | 0 | 是 |
| assign_base | `assignment` | OPTIMAL | 9 | 6 | 9 | 9 | 0 | 是 |
| cap_M_60 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 1600 | 1600 | 0 | 是 |
| cap_M_70 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 1800 | 1800 | 0 | 是 |
| cap_M_80 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2000 | 2000 | 0 | 是 |
| cap_M_90 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2150 | 2150 | 0 | 是 |
| cap_M_100 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2300 | 2300 | 0 | 是 |
| cap_M_110 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2450 | 2450 | 0 | 是 |
| cap_M_120 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2600 | 2600 | 0 | 是 |
| cap_M_130 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2600 | 2600 | 0 | 是 |
| cap_M_140 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2600 | 2600 | 0 | 是 |
| cap_L_40 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 1600 | 1600 | 0 | 是 |
| cap_L_50 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 1850 | 1850 | 0 | 是 |
| cap_L_60 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2100 | 2100 | 0 | 是 |
| cap_L_70 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2200 | 2200 | 0 | 是 |
| cap_L_80 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2300 | 2300 | 0 | 是 |
| cap_L_90 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2400 | 2400 | 4.55e-13 | 是 |
| cap_L_100 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2466.666667 | 2466.666667 | 4.55e-13 | 是 |
| cap_L_110 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2533.333333 | 2533.333333 | 0 | 是 |
| cap_L_120 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2600 | 2600 | 0 | 是 |
| cap_L_130 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2650 | 2650 | 4.55e-13 | 是 |
| cap_L_140 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2700 | 2700 | 4.55e-13 | 是 |
| cap_L_150 | `sensitivity_capacity` | OPTIMAL | 3 | 5 | 2750 | 2750 | 0 | 是 |
| profit_P2_25 | `sensitivity_profit` | OPTIMAL | 3 | 5 | 2300 | 2300 | 0 | 是 |
| profit_P2_30 | `sensitivity_profit` | OPTIMAL | 3 | 5 | 2300 | 2300 | 0 | 是 |
| profit_P2_35 | `sensitivity_profit` | OPTIMAL | 3 | 5 | 2300 | 2300 | 0 | 是 |
| profit_P2_40 | `sensitivity_profit` | OPTIMAL | 3 | 5 | 2400 | 2400 | 4.55e-13 | 是 |
| profit_P2_45 | `sensitivity_profit` | OPTIMAL | 3 | 5 | 2500 | 2500 | 9.09e-13 | 是 |
| demand_P1_10 | `sensitivity_demand` | OPTIMAL | 3 | 5 | 2150 | 2150 | 0 | 是 |
| demand_P1_15 | `sensitivity_demand` | OPTIMAL | 3 | 5 | 2225 | 2225 | 0 | 是 |
| demand_P1_20 | `sensitivity_demand` | OPTIMAL | 3 | 5 | 2300 | 2300 | 0 | 是 |
| demand_P1_25 | `sensitivity_demand` | OPTIMAL | 3 | 5 | 2300 | 2300 | 0 | 是 |
| demand_P1_30 | `sensitivity_demand` | OPTIMAL | 3 | 5 | 2300 | 2300 | 0 | 是 |
| demand_P1_40 | `sensitivity_demand` | OPTIMAL | 3 | 5 | 2300 | 2300 | 0 | 是 |

## 2. 数值对拍

`max_constraint_residual` 是原始可行性残差（由本模块按系数**重算**，
不是抄求解器的活动值）；`max_reduced_cost_identity` 检查
`reduced_cost = c_j - Σ a_ij y_i` 这条符号约定；`max_complementarity`
是全部 `\|x*rc\|` 与 `\|slack*y\|` 的最大值。

| 场景 | 可行性残差 | rc 恒等式误差 | 互补松弛 | 对偶可行违反 | 互补松弛通过 |
|---|---:|---:|---:|---:|---:|
| prod_2d | 0 | 0 | 2.37e-13 | 7.11e-15 | 是 |
| prod_base | 0 | 0 | 2.13e-13 | 0 | 是 |
| transport_base | 0 | 0 | 0 | 0 | 是 |
| assign_base | 0 | 0 | 0 | 0 | 是 |
| cap_M_60 | 0 | 0 | 1.42e-13 | 0 | 是 |
| cap_M_70 | 0 | 0 | 2.13e-13 | 0 | 是 |
| cap_M_80 | 0 | 0 | 0 | 7.11e-15 | 是 |
| cap_M_90 | 0 | 0 | 0 | 0 | 是 |
| cap_M_100 | 0 | 0 | 2.13e-13 | 0 | 是 |
| cap_M_110 | 0 | 0 | 4.26e-13 | 0 | 是 |
| cap_M_120 | 0 | 0 | 0 | 0 | 是 |
| cap_M_130 | 0 | 0 | 0 | 0 | 是 |
| cap_M_140 | 0 | 0 | 0 | 0 | 是 |
| cap_L_40 | 0 | 0 | 0 | 0 | 是 |
| cap_L_50 | 0 | 0 | 0 | 0 | 是 |
| cap_L_60 | 0 | 0 | 1.78e-13 | 0 | 是 |
| cap_L_70 | 0 | 0 | 2.13e-13 | 0 | 是 |
| cap_L_80 | 0 | 0 | 2.13e-13 | 0 | 是 |
| cap_L_90 | 0 | 0 | 2.37e-13 | 7.11e-15 | 是 |
| cap_L_100 | 0 | 0 | 2.37e-13 | 7.11e-15 | 是 |
| cap_L_110 | 0 | 0 | 2.37e-13 | 7.11e-15 | 是 |
| cap_L_120 | 0 | 0 | 1.42e-13 | 7.11e-15 | 是 |
| cap_L_130 | 0 | 0 | 2.84e-13 | 0 | 是 |
| cap_L_140 | 0 | 0 | 2.84e-13 | 0 | 是 |
| cap_L_150 | 0 | 0 | 3.55e-13 | 0 | 是 |
| profit_P2_25 | 0 | 0 | 2.13e-13 | 0 | 是 |
| profit_P2_30 | 0 | 0 | 2.13e-13 | 0 | 是 |
| profit_P2_35 | 0 | 0 | 2.13e-13 | 0 | 是 |
| profit_P2_40 | 0 | 0 | 3.79e-13 | 0 | 是 |
| profit_P2_45 | 2.84e-14 | 0 | 5.68e-13 | 7.11e-15 | 是 |
| demand_P1_10 | 0 | 0 | 0 | 0 | 是 |
| demand_P1_15 | 0 | 0 | 0 | 0 | 是 |
| demand_P1_20 | 0 | 0 | 0 | 0 | 是 |
| demand_P1_25 | 0 | 0 | 0 | 0 | 是 |
| demand_P1_30 | 0 | 0 | 2.13e-13 | 0 | 是 |
| demand_P1_40 | 0 | 0 | 2.13e-13 | 0 | 是 |

## 3. 生产计划的影子价格（`prod_base`）

| 约束 | 影子价格 |
|---|---:|
| `cap_M` | 15 |
| `cap_L` | 10 |
| `demand_P1` | 0 |
| `demand_P2` | 0 |
| `demand_P3` | 0 |

三条需求上限都没顶住（松弛量大于 0），所以它们的影子价格是 0——
**不是**「这些约束没用」，而是「在现在这个解上，放松一单位不会让目标变大」。

## 4. 敏感性：影子价格的局部有效范围（Day 5）

两类扰动用**两条不同的预测规则**，混用会得出错误结论：

* `rhs_linear`（扰动产能、需求上限）：预测 = 基准目标 + 基准影子价格 x `delta`，
  只在基不变的区间内成立，跨过折点立刻失效；
* `reduced_cost_breakeven`（扰动单位利润）：reduced cost 不是斜率而是**盈亏平衡价**，
  在利润升到 `break_even` 之前 `x_j` 保持为 0、目标值不变。把 rc 当斜率用会
  预测出「降价反而多赚」这种明显的错。

| 场景 | 轴 | 取值 | delta | 影子价格(基准) | 盈亏平衡值 | 规则 | 实测目标 | 预测目标 | 预测误差 | 预测成立 |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| cap_M_60 | `capacity_M` | 60 | -40 | 15 | — | `rhs_linear` | 1600 | 1700 | 100 | 否 |
| cap_M_70 | `capacity_M` | 70 | -30 | 15 | — | `rhs_linear` | 1800 | 1850 | 50 | 否 |
| cap_M_80 | `capacity_M` | 80 | -20 | 15 | — | `rhs_linear` | 2000 | 2000 | 0 | 是 |
| cap_M_90 | `capacity_M` | 90 | -10 | 15 | — | `rhs_linear` | 2150 | 2150 | 0 | 是 |
| cap_M_100 | `capacity_M` | 100 | +0 | 15 | — | `rhs_linear` | 2300 | 2300 | 0 | 是 |
| cap_M_110 | `capacity_M` | 110 | +10 | 15 | — | `rhs_linear` | 2450 | 2450 | 0 | 是 |
| cap_M_120 | `capacity_M` | 120 | +20 | 15 | — | `rhs_linear` | 2600 | 2600 | 0 | 是 |
| cap_M_130 | `capacity_M` | 130 | +30 | 15 | — | `rhs_linear` | 2600 | 2750 | 150 | 否 |
| cap_M_140 | `capacity_M` | 140 | +40 | 15 | — | `rhs_linear` | 2600 | 2900 | 300 | 否 |
| cap_L_40 | `capacity_L` | 40 | -40 | 10 | — | `rhs_linear` | 1600 | 1900 | 300 | 否 |
| cap_L_50 | `capacity_L` | 50 | -30 | 10 | — | `rhs_linear` | 1850 | 2000 | 150 | 否 |
| cap_L_60 | `capacity_L` | 60 | -20 | 10 | — | `rhs_linear` | 2100 | 2100 | 0 | 是 |
| cap_L_70 | `capacity_L` | 70 | -10 | 10 | — | `rhs_linear` | 2200 | 2200 | 0 | 是 |
| cap_L_80 | `capacity_L` | 80 | +0 | 10 | — | `rhs_linear` | 2300 | 2300 | 0 | 是 |
| cap_L_90 | `capacity_L` | 90 | +10 | 10 | — | `rhs_linear` | 2400 | 2400 | 4.55e-13 | 是 |
| cap_L_100 | `capacity_L` | 100 | +20 | 10 | — | `rhs_linear` | 2466.666667 | 2500 | 33.3 | 否 |
| cap_L_110 | `capacity_L` | 110 | +30 | 10 | — | `rhs_linear` | 2533.333333 | 2600 | 66.7 | 否 |
| cap_L_120 | `capacity_L` | 120 | +40 | 10 | — | `rhs_linear` | 2600 | 2700 | 100 | 否 |
| cap_L_130 | `capacity_L` | 130 | +50 | 10 | — | `rhs_linear` | 2650 | 2800 | 150 | 否 |
| cap_L_140 | `capacity_L` | 140 | +60 | 10 | — | `rhs_linear` | 2700 | 2900 | 200 | 否 |
| cap_L_150 | `capacity_L` | 150 | +70 | 10 | — | `rhs_linear` | 2750 | 3000 | 250 | 否 |
| profit_P2_25 | `profit_P2` | 25 | -5 | -5 | 35 | `reduced_cost_breakeven` | 2300 | 2300 | 0 | 是 |
| profit_P2_30 | `profit_P2` | 30 | +0 | -5 | 35 | `reduced_cost_breakeven` | 2300 | 2300 | 0 | 是 |
| profit_P2_35 | `profit_P2` | 35 | +5 | -5 | 35 | `reduced_cost_breakeven` | 2300 | 2300 | 0 | 是 |
| profit_P2_40 | `profit_P2` | 40 | +10 | -5 | 35 | `reduced_cost_breakeven` | 2400 | — | — | 是 |
| profit_P2_45 | `profit_P2` | 45 | +15 | -5 | 35 | `reduced_cost_breakeven` | 2500 | — | — | 是 |
| demand_P1_10 | `max_demand_P1` | 10 | -30 | 0 | — | `rhs_linear` | 2150 | 2300 | 150 | 否 |
| demand_P1_15 | `max_demand_P1` | 15 | -25 | 0 | — | `rhs_linear` | 2225 | 2300 | 75 | 否 |
| demand_P1_20 | `max_demand_P1` | 20 | -20 | 0 | — | `rhs_linear` | 2300 | 2300 | 0 | 是 |
| demand_P1_25 | `max_demand_P1` | 25 | -15 | 0 | — | `rhs_linear` | 2300 | 2300 | 0 | 是 |
| demand_P1_30 | `max_demand_P1` | 30 | -10 | 0 | — | `rhs_linear` | 2300 | 2300 | 0 | 是 |
| demand_P1_40 | `max_demand_P1` | 40 | +0 | 0 | — | `rhs_linear` | 2300 | 2300 | 0 | 是 |

## 5. 求解器状态码的一条实测限制

`prod_infeasible` 的状态是 `INFEASIBLE`，但**这个状态码不能证明可行域为空**：
本环境的 GLOP 后端对无界 LP 也返回同一个状态码（实测 `min -x, x >= 0`
同样返回 2）。该算例「真的不可行」是靠手算确认的——
`x_P2 <= 50` 与 `x_P2 >= 60` 直接冲突。

## 6. 复现

在项目目录下运行：

```bash
python -m opt_experiments.lp_experiments
```

输出目录必须为空或不存在；重跑前请先自行移走旧目录。
