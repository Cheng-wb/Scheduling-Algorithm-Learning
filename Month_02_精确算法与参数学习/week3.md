# M2 Week 3 周总结：CP-SAT 区间模型

> 笔记：[Day1](Week_3/Day1.md) · [Day2](Week_3/Day2.md) · [Day3](Week_3/Day3.md) · [Day4](Week_3/Day4.md) · [Day5](Week_3/Day5.md) · [Day6](Week_3/Day6.md) · [Day7](Week_3/Day7.md)

## 1. 本周目标与成果

本周把调度问题从 MILP 的「变量 + 线性约束」搬到 CP-SAT 的「区间 + 全局约束」上：用 `IntervalVar` / `OptionalIntervalVar` 表示工序占用，用 `AddNoOverlap` 表示机器互斥，用 `AddExactlyOne` 表示选机，用 `AddCumulative` 表示有限容量资源，并在同一套 `Instance` / `Objective` / `Schedule` 接口下与 Week 2 的 MILP 做了对照。

落地三件事：建模件 [cpsat_models.py](../projects/02_optimization_models/opt_models/cpsat_models.py) 注册了 `cpsat_parallel`、`cpsat_jsp`、`cpsat_cumulative` 三个方法；测试件 [test_cpsat_models.py](../projects/02_optimization_models/tests/test_cpsat_models.py) 用手算最优值与 M1 的 oracle 交叉验证；跑批件 [w3_cpsat.py](../projects/02_optimization_models/opt_experiments/w3_cpsat.py) 产出 `artifacts/month2_w3/`（29 次运行、0 失败）。

本周最重要的两个认识：**状态与目标值必须一起读**（`FEASIBLE` 与 `OPTIMAL` 可能有相同目标值，Day 5）；**CP 的传播与 MILP 的松弛是两种形状完全不同的推理**，强弱由建模结构决定而不是范式新旧（Day 7）。

## 2. 核心概念

| 概念 | 一句话定义 | 读它回答的问题 |
|---|---|---|
| `IntervalVar` | 由 `start` / `size` / `end` 三个表达式约束的区间变量 | 这道工序占用哪一段时间 |
| `OptionalIntervalVar` | 带 `is_present` 文字的区间，缺席时区间不存在 | 这道工序到底做不做、在哪台机器做 |
| `AddExactlyOne` | 一组布尔文字恰好一个为真 | 每道工序恰好选一台机器 |
| `AddNoOverlap` | 一组区间两两不重叠 | 一台机器同一时刻只能做一件事 |
| `AddCumulative` | 一组区间在每时刻的用量之和不超过容量 | 有限容量资源（人力、模具）的占用 |
| 域传播 | 沿约束删去变量域中不可能取的值 | 为什么有些矛盾在搜索前就被发现 |
| `best_bound` | 搜索中得到的「最优值不会低于它」的证明 | 证明推进到哪（`None` 表示该方法不提供） |
| `FEASIBLE` | 找到可行解，未证明最优 | 解可用，但结论不能写「最优」 |
| `MODEL_INVALID` | 模型本身被求解器拒绝 | 是建模错误，不是问题不可行 |
| 整数时间缩放 | 用 `time_scale` 把浮点时间转成整数 | CP-SAT 只接受整数域 |

`Operation.eligible_machine_ids` 是**允许范围**（约束），`is_present` 与 `start` 是**实际决策**（结果）——与 M1 的输入 / 结果分离是同一条原则。

## 3. 三条注册方法

| 方法 | 建模要点 | 适用实例 | 状态能力 |
|---|---|---|---|
| `cpsat_parallel` | `OptionalIntervalVar` + 每工序 `AddExactlyOne` + 每机器 `AddNoOverlap` | 同质并行机、可含 release time / due date | 五种状态全部可达 |
| `cpsat_jsp` | 固定路由下的区间 + 工序间优先级 + 每机器 `AddNoOverlap` | 小型 job shop、含柔性路由 | 同上 |
| `cpsat_cumulative` | `AddCumulative` + `AddNoOverlap` 语义对照 | 有限容量资源、容量不可行检测 | 同上 |

三条方法共用 [cpsat_models.py](../projects/02_optimization_models/opt_models/cpsat_models.py) 里同一份区间建模与读解逻辑，差异只在「加了哪几条约束」——`cpsat_jsp` 在 `cpsat_parallel` 的基础上加了工序间的优先级，`cpsat_cumulative` 把「机器互斥」这一条从 `AddNoOverlap` 换成 `AddCumulative`。

## 4. 接口约定（API Contract）

```python
# opt_models/cpsat_models.py —— 建模层
cpsat_parallel(instance, spec) -> SolveResult
cpsat_jsp(instance, spec) -> SolveResult
cpsat_cumulative(instance, spec) -> SolveResult

# spec 支持的字段
#   objective    : str   —— M2_OBJECTIVES 里的目标名
#   time_limit   : float —— 墙钟秒数，传给 parameters.max_time_in_seconds
#   seed         : int   —— random_seed
#   time_scale   : int   —— 整数时间缩放（默认 1）
#   capacity     : int   —— 仅 cpsat_cumulative：资源容量
#   demand       : int   —— 仅 cpsat_cumulative：每工序占用

# SolveResult 的关键字段（顺序即读表顺序）
#   status       : str   —— 五种 CP-SAT 状态之一，1:1 映射，不替换
#   objective    : float | None
#   best_bound   : float | None   —— CP-SAT 不提供可比值时为 None，绝不用目标值顶替
#   schedule     : Schedule | None
#   build_time   : float —— 建模耗时（与 solve_time 分开记录）
#   solve_time   : float
#   iterations   : int | None —— 分支数 / 冲突数（可用时才填）
#   detail       : dict  —— 含 capacity / demand / objective_divisor 等回溯信息
```

## 5. 关键数值证据：MILP 与 CP-SAT 的对照

以下全部来自 [m2w3d6_milp_vs_cpsat.py](../projects/02_optimization_models/examples/m2w3d6_milp_vs_cpsat.py) 的实测（同一台机器、`time_limit = 5.0` 秒、`seed = 0`）；表里的目标值与跑批件 [w3_cpsat.py](../projects/02_optimization_models/opt_experiments/w3_cpsat.py) 的 `results.csv` 逐行一致，耗时是墙钟量，两次运行会有小幅波动：

| 实例 | 目标 | 最好目标值 | MILP 结果 | CP-SAT 结果 | MILP 证明用时 (s) | CP-SAT 证明用时 (s) |
|---|---|---|---|---|---|---|
| `single_8`（8 工序 / 1 机） | `total_tardiness` | 85 | `milp_tight` / `milp_loose` / `milp_alt` 三个都 OPTIMAL | `cpsat_parallel` / `cpsat_jsp` 都 OPTIMAL | 1.4698 / 1.4284 / 0.1280 | 0.1432 / 0.1663 |
| `single_12`（12 工序 / 1 机） | `total_tardiness` | 532 | `milp_alt` OPTIMAL 532；`milp_tight` FEASIBLE 543、`milp_loose` FEASIBLE 573 | `cpsat_parallel` FEASIBLE 532（未证明，`bound` 仅 1） | 0.6216（`milp_alt`） | 未证明（用满 5 秒） |
| `parallel_8`（8 工序 / 3 机） | `makespan` | 29 | `milp_alt` OPTIMAL | `cpsat_parallel` / `cpsat_jsp` 都 OPTIMAL | 0.8145 | 0.0088 / 0.0105 |
| `parallel_12`（12 工序 / 3 机） | `makespan` | 39 | `milp_alt` OPTIMAL | `cpsat_parallel` / `cpsat_jsp` 都 OPTIMAL | 1.6458 | 0.0324 / 0.0255 |

三条观察（**限定在这四个实例、这两个目标、这个 5 秒预算之内**）：

1. **四个实例上 MILP 与 CP-SAT 的最好目标值完全相同**（85 / 532 / 29 / 39）。不同建模方式、不同搜索机制给出同一批最优值，是本周最硬的一条交叉验证。
2. **`single_12` 上 CP-SAT 找到了最优解 532 但没证明它**（状态 `FEASIBLE`、`bound = 1`、`gap = 0.9981`）。这一行的 `gap` 接近 1 衡量的是**证明进度**，不是解的质量——读表时最容易在这里出错。
3. **`single_12` 上同一个 MILP 范式内部就分岔了**：`milp_alt` 证完了，`milp_tight` / `milp_loose` 两个都没证完。所以「MILP 行不行」不能按范式回答，只能按「实例 + 建模方式 + 预算」回答。

补充一次长预算观察：`single_12` 上把 CP-SAT 的预算抬到 20 秒与 60 秒，目标值仍是 532（状态始终 `FEASIBLE`），界只从 1 抬到 2.0 与 9.0（分支数在二十万与五十万量级，且墙钟限制下计数不可复现）——**它从未证明 532 最优**，而 `milp_alt` 在同一实例上用约 0.6 秒就证完了。反方向的例子是 `parallel_8` / `parallel_12`：CP-SAT 的证明时间比 `milp_alt` 少两个数量级（0.0088 s 对 0.8145 s、0.0324 s 对 1.6458 s）。**两个方向都存在，谁也不是全面占优。**

## 6. 容量与状态：另外两组数值证据

`cpsat_cumulative` 的容量对照（实例 1：2 台机器、3 道各长 5 的工序；实例 2：3 台机器、4 道各长 4 的工序）。峰值由独立的 [cumulative_profile](../projects/02_optimization_models/opt_models/cpsat_models.py) 扫描返回的排程得到，不复用求解器的自述：

| 实例 | 容量设置 | `floor(capacity / demand)` | Cmax | 峰值消耗 | 状态 |
|---|---|---|---|---|---|
| 实例 1（2 机、3 道 p=5） | 无容量（占用 1） | —— | 10 | 2 | OPTIMAL |
| 实例 1 | 容量 1 / 占用 1 | 1 | 15 | 1 | OPTIMAL |
| 实例 1 | 容量 2 / 占用 1 | 2 | 10 | 2 | OPTIMAL |
| 实例 1 | 容量 1 / 占用 2 | 0 | —— | —— | INFEASIBLE |
| 实例 2（3 机、4 道 p=4） | 无容量（占用 1） | —— | 8 | 2 | OPTIMAL |
| 实例 2 | 容量 3 / 占用 2 | 1 | 16 | 2 | OPTIMAL |
| 实例 2 | 容量 4 / 占用 2 | 2 | 8 | 4 | OPTIMAL |

结论：**`NoOverlap` 不会替代 `Cumulative`**。容量 2 与无容量约束结果相同（容量不紧，Cmax 都是 10），容量 1 时 Cmax 从 10 涨到 15（容量收紧最优值），而「容量 1 + 占用 2」直接不可行。五组带容量参数的数据里「有效并发度 = `floor(capacity / demand)`」全部成立：实例 2 的容量 3 / 占用 2 只允许 1 道工序同时进行（Cmax 回到 16 = 4 × 4），容量 4 / 占用 2 允许 2 道（Cmax 8）。

五种状态的实测落点（Day 5 脚本）：

| 状态 | 触发条件 | `objective` / `best_bound` | 关键计数 |
|---|---|---|---|
| `OPTIMAL` | 小实例证完 | 6.0 / 6.0 | 分支与冲突正常累加 |
| `FEASIBLE` | 超时但有解 | 610.0 / 0.0（平凡界） | —— |
| `UNKNOWN` | 超时且无可解 | `None` / `None`（`raw_best_bound = 0.0`） | —— |
| `INFEASIBLE` | 容量或窗口矛盾 | `None` / `None` | 分支 0、冲突 0 |
| `MODEL_INVALID` | 模型被求解器拒绝 | `None` / `None` | —— |

`INFEASIBLE` 的分支数与冲突数都是 0：矛盾在**传播阶段**就被发现，求解器根本没进搜索树——这是 LP 松弛做不到的一类推理。

## 7. 机制结论（CP 传播 vs MILP 松弛）

| 维度 | CP 的传播 | MILP 的线性松弛 |
|---|---|---|
| 动的是什么 | 变量的域（端点） | 变量的取值范围（整数性） |
| 一次操作给出 | 一批被排除的取值 | 一个下界值 |
| 下界与预算的关系 | 随搜索推进收紧 | 一次算出，与预算无关 |
| 失效场景 | 只有局部互斥信息时推不动全局量（`NoOverlap` 只能给 `H - p`） | 结构高度非凸时太松（并行机 makespan 丢掉了不可抢占性） |

实测的 LP 松弛（`root_lp=True`，time-indexed 模型）：

| 实例 | root LP | 整数最优 | LP gap |
|---|---|---|---|
| `single_8` | 83.9347 | 85 | 0.0125 |
| `single_12` | 529.0987 | 532 | 0.0055 |
| `parallel_8` | 25.0000 | 29 | 0.1379 |
| `parallel_12` | 28.9645 | 39 | 0.2573 |

**同一个范式、同一个模型、同一个实例生成器，只换机器数与目标类型，LP gap 从 0.55% 变到 25.73%**——界强度是建模结构的函数，不是范式的函数。`parallel_8` 的 LP 值 25.0000 甚至低于「总加工时间 / 机器数」这个平凡下界（总工时 76，$\lceil 76/3 \rceil = 26$），因为 LP 下「每道工序恰好选一个（机器，开工时刻）」的等式允许把归属按小数摊到多台机器上。

由此得到一条可用的判据：目标含交期惩罚这一类分段线性成本结构时优先 MILP，机器互斥 / 选机 / 容量是主导约束时优先 CP-SAT；**但不要用 LP gap 预测 CP-SAT 的表现**——LP gap 最大的 `parallel_12` 上 CP-SAT 反而 0.0324 秒证明了最优。

## 8. 测试证据

[tests/test_cpsat_models.py](../projects/02_optimization_models/tests/test_cpsat_models.py) 共 63 个测试，覆盖：

```text
手算最优值        —— 2x2 JSP 的 Cmax = 7（含完整时间线）
与 M1 oracle 交叉 —— parallel_makespan_lower_bound 紧时取等、exhaustive_optimum 对拍
容量语义          —— 容量收紧最优值的实例、容量不可行返回 INFEASIBLE
状态能力          —— 五种状态各有一个最小可复现实例
模型错误          —— 畸形模型返回 MODEL_INVALID
整数时间缩放      —— time_scale 下目标值与时间轴一致缩放
排程合法性        —— 每一个返回的 schedule 都过 M1 的 validate_schedule
```

**求解器说 `OPTIMAL` 不等于排程合法**：所有返回的排程都必须过 M1 的独立验证器与 M1 的目标重算，求解器的自述只作为状态来源，不作为正确性的依据。

复跑命令（在项目目录下运行）：

```bash
python -m pytest -q
```

## 9. 确定性契约

```text
相同 Instance + 相同 spec（含 seed）  →  相同 objective

但：墙钟时间限制下，分支数与冲突数不保证可复现
    （NumBranches / NumConflicts 随机器负载波动）
```

因此测试只断言 `objective` 相等，不断言 `iterations` 相等。`num_search_workers = 1` 与固定 `seed` 能让目标值稳定，但**不能让搜索计数稳定**——这一点在 Day 5 的实测里被明确观察到（同一 spec 两次运行目标值相同、分支数不同）。零预算返回的那一档还要另说：`time_limit = 0.05` 时目标值本身也会在小范围内抖动，必须报成实验观察而不是契约。

## 10. 已知局限

```text
时间         ：CP-SAT 只接受整数域，浮点时间必须先缩放；缩放会放大时间轴与变量数
目标         ：只覆盖 M2_OBJECTIVES 里已有的目标，未新增目标函数
资源         ：Cumulative 只支持「每工序占用固定量」的同质容量，未做可分资源与交错资源
机器         ：只做同质并行机与小型 job shop，未做流水车间与柔性作业车间的完整建模
界           ：CP-SAT 的 best_bound 只在求解器提供时才有；多数时候接近平凡界
可复现性     ：分支/冲突计数在墙钟限制下不可复现（见第 9 节）
未做         ：不做 setup time、日历、工人等多资源耦合
```

## 11. 遗留问题

| # | 问题 | 状态 |
|---|---|---|
| 1 | 回填的域是不是最紧的？ | 不是。已验证 `end_0 >= 20` 可行、`>= 21` 不可行，而回填打印的是 25（Day 1 第 4.4 节） |
| 2 | `NoOverlap` 能不能替代 `Cumulative`？ | 不能。容量 1 时 Cmax 从 10 涨到 15，容量 1 / 占用 2 直接不可行（Day 4） |
| 3 | `FEASIBLE` 的目标值能当最优用吗？ | 不能。`single_12` 上 `FEASIBLE 532` 恰好是最优值，但这是结果不是保证 |
| 4 | 没有可用界时 `best_bound` 填什么？ | 填 `None`。既不能填 0（会伪装成平凡界），也不能填目标值（会伪装成已证明） |
| 5 | 超时未找到解该报 `UNKNOWN` 还是 `INFEASIBLE`？ | `UNKNOWN`。求解器没证明不可行，两者在证据上不等价 |
| 6 | 模型错误该报什么？ | `MODEL_INVALID`，并在映射层与 `FAILED` 区分开（Day 5 第 5 节） |
| 7 | 浮点时间怎么办？ | 整数时间缩放，缩放因子记进 `detail`，目标值按 `objective_divisor` 还原 |
| 8 | 跨范式比较谁更强？ | 不写「谁更强」。写「在这个实例集、这个目标、这个预算下观察到什么」（Day 6） |
| 9 | CP 的界为什么抬不起来？ | 传播是局部推理，交期惩罚这类线性成本结构对 LP 友好、对 CP 不友好（Day 7） |
| 10 | 更强的模型怎么加？ | 本周结束时仍是开放问题 |

## 12. 待个人完成

闭卷重做两件事：一是给出 `2x2 JSP` 的完整最优时间线与 Cmax = 7 的三条组合下界推导；二是手算 `NoOverlap` 与链在三个长 5 区间上的端点上界（25 与 15 / 20 / 25），并说清两者差的 10 来自哪条信息。完成后不看笔记写下「CP-SAT 的 `best_bound` 与 MILP 的 `best_bound` 在哪一种意义上可比」这一段。
