# Day 4：交期、延期与加权延期

## 1. 学习目标

前一天的 Big-M 模型已经能够决定单机任务的顺序，并优化 Makespan 或总完工时间。今天把交期真正接入模型，回答三个问题：

- 一个任务提前、准时或延期，如何用数学指标表示？
- 如何在 MILP 中表示延期而不直接使用 `max()`？
- 为什么最小化 Makespan、总延期和加权延期会得到不同的顺序？

今天的代码入口是 [day4_tardiness.py](../experiments/day4_tardiness.py)，核心模型在 [single_machine.py](../scheduling/exact/single_machine.py)。

## 2. 基本概念

对任务 $i$，设：

- $S_i$：开始时间
- $p_i$：加工时间
- $C_i=S_i+p_i$：完工时间
- $d_i$：交期
- $w_i$：延期权重

### Lateness

$$
L_i=C_i-d_i
$$

Lateness 是带符号的交期偏差：

| 情况 | 条件 | 含义 |
| --- | --- | --- |
| 提前 | $L_i<0$ | 完工早于交期 |
| 准时 | $L_i=0$ | 完工时刻等于交期 |
| 延期 | $L_i>0$ | 完工晚于交期 |

### Tardiness

$$
T_i=\max(0,C_i-d_i)=\max(0,L_i)
$$

Tardiness 只记录延期，不会因为提前完成而出现负值。比如 $d_i=10$ 时，$C_i=8$ 得到 $L_i=-2,T_i=0$；$C_i=12$ 得到 $L_i=2,T_i=2$。

## 3. 今天使用的评价指标

对整个 `Schedule`，项目中的 `metrics.py` 提供：

| 指标 | 公式 | 关注点 |
| --- | --- | --- |
| 总延期 | $\sum_i T_i$ | 所有延期时间的总和 |
| 最大延期 | $\max_i T_i$ | 最严重的单个延期 |
| 迟交任务数 | $\sum_i\mathbf{1}(T_i>0)$ | 有多少订单延期 |
| 加权延期 | $\sum_i w_iT_i$ | 重要订单的延期代价 |

权重可以表示客户优先级、订单价值或延期罚金。两个订单都延期 2 个时间单位时，权重为 1 的订单贡献 2，权重为 10 的订单贡献 20。因此加权目标会更重视高优先级订单。

本项目约定：`due_date=None` 表示不评价该任务的交期，Lateness 和 Tardiness 按 0 处理；这不是说任务真实偏差为 0，而是表示当前模型没有交期评价数据。

## 4. 三种目标的区别

今天使用同一批任务分别求解三个模型：

### 目标 A：最小化 Makespan

$$
\min C_{\max},\qquad C_{\max}\ge C_i
$$

它关心最后一个任务何时完成，不直接惩罚延期。

### 目标 B：最小化总延期

$$
\min\sum_iT_i
$$

它关心所有订单一共晚了多少时间。

### 目标 C：最小化加权延期

$$
\min\sum_iw_iT_i
$$

它在总延期之外区分订单重要性。高权重任务延期 1 个单位，可能比普通任务延期多个单位更值得避免。

这三个目标没有绝对的“全面最好”：一个方案可能总延期较小，但延期订单更多；另一个方案可能保护了 VIP 订单，却让普通订单更晚。

## 5. Tardiness 的 MILP 建模

单机排序模型仍使用 Day 3 的变量：

- $S_i$：连续开始时间变量
- $y_{ij}\in\{0,1\}$：任务 $i$ 和 $j$ 的先后关系
- $M$：Big-M 常数

仍然使用非重叠约束：

$$
S_i+p_i\le S_j+M(1-y_{ij})
$$

$$
S_j+p_j\le S_i+My_{ij}
$$

新增延期变量 $T_i\ge0$，并添加：

$$
T_i\ge C_i-d_i
$$

由于 $C_i=S_i+p_i$，代码中写成：

$$
T_i\ge S_i+p_i-d_i
$$

这里没有直接写 `max()`。为什么两个不等式加上最小化目标就够了？

- 如果 $C_i-d_i=3$，则 $T_i\ge3$，最小化目标会使 $T_i=3$。
- 如果 $C_i-d_i=-2$，则 $T_i\ge-2$，再结合 $T_i\ge0$，最小值为 $T_i=0$。

因此：

$$
T_i\ge C_i-d_i,\qquad T_i\ge0
$$

在正权重的最小化目标下，等价于：

$$
T_i=\max(0,C_i-d_i)
$$

这是一种常见的线性建模技巧：用下界和目标函数共同实现一个 `max` 关系。

## 6. 代码职责

### `models.py`

`Job` 保存 `due_date` 和 `weight`；`ScheduledJob` 根据完工时间提供 `lateness`、`tardiness` 等任务级属性。

### `metrics.py`

只负责读取排程并计算指标：

- `total_tardiness(schedule)`
- `max_tardiness(schedule)`
- `weighted_tardiness(schedule)`
- `num_tardy_jobs(schedule)`

指标逻辑集中在这里，避免实验脚本重复计算。

### `evaluator.py`

`evaluate(schedule)` 先校验排程，再统一汇总 Makespan、总延期、最大延期、加权延期、迟交任务数等结果。它不负责排序，也不负责求解。

### `single_machine.py`

三个公开函数共用 `_build_model()` 的开始时间和 Big-M 非重叠约束，只改变目标：

```python
solve_single_machine_makespan(jobs)
solve_single_machine_total_tardiness(jobs)
solve_single_machine_weighted_tardiness(jobs)
```

`_add_tardiness()` 创建延期变量并添加交期约束。这样可以看到：同一组决策变量和可行域，仅改变目标函数，就可能得到不同调度。

## 7. Day 4 实验数据

实验使用完全相同的五个任务：

| Job | $p_i$ | $d_i$ | $w_i$ |
| --- | ---: | ---: | ---: |
| J1 | 4 | 6 | 1 |
| J2 | 2 | 8 | 5 |
| J3 | 5 | 10 | 2 |
| J4 | 1 | 5 | 8 |
| J5 | 3 | 12 | 1 |

其中 J4 加工时间短、交期早、权重高。在加权延期目标下，它通常值得优先保护，但具体顺序仍由整个模型共同决定。

实验流程：

```text
创建同一批 Job
    ↓
分别运行 Makespan、Total Tardiness、Weighted Tardiness
    ↓
提取 Schedule 并 validate()
    ↓
evaluate(schedule)
    ↓
打印任务级 S、C、Due、L、T、Weight、wT
    ↓
打印三种目标的比较表
```

运行命令，在 Week 2 目录执行：

```powershell
python -m experiments.day4_tardiness
```

若使用本项目的 Anaconda 环境：

```powershell
& D:\tools\anaconda\envs\schedule_venv\python.exe `
  "experiments/day4_tardiness.py"
```

## 8. 本次实验结果

求解器输出的具体最优顺序可能存在等价解，因此不要把某一个顺序当成唯一答案。本次运行得到：

| 目标 | 顺序 | $C_{\max}$ | $\sum T_i$ | $\sum w_iT_i$ | 最大延期 | 迟交任务数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Makespan | J5 → J4 → J3 → J2 → J1 | 15 | 12 | 24 | 9 | 2 |
| Total tardiness | J4 → J1 → J2 → J5 → J3 | 15 | 5 | 10 | 5 | 1 |
| Weighted tardiness | J1 → J4 → J2 → J3 → J5 | 15 | 5 | 7 | 3 | 2 |

观察：

1. 所有任务都在时刻 15 前完成，因此三个方案的 Makespan 相同。
2. Makespan 目标没有直接优化交期，所以 J1 和 J2 的延期较大。
3. 总延期目标把总延期从 12 降到 5，并且只让 J3 延期。
4. 加权延期目标进一步把加权延期降到 7，避免了高权重 J2、J4 的延期；它允许低权重的 J3、J5 承担延期。

任务级表格比只看目标值更有解释力，因为它能显示“到底是哪几个订单承担了延期”。

## 9. 实验验证清单

每个模型返回 `Schedule` 后，应检查：

- 每个输入任务恰好出现一次。
- 同一机器上的任务没有重叠。
- `completion_time = start_time + processing_time`。
- 开始时间不早于 `release_time`。
- `evaluate(schedule)` 计算出的延期指标与任务级表格一致。
- 求解器返回 `OPTIMAL` 时，才表示当前模型已证明最优；`FEASIBLE` 只表示找到了可行解。

尤其要验证：模型中的延期目标值与重新从 `Schedule` 计算的 `total_tardiness` 或 `weighted_tardiness` 一致。这可以发现提取排程、变量索引或目标函数接线错误。

## 10. 今天的总结

今天需要掌握的主线是：

$$
Due\ Date\rightarrow Completion\rightarrow Lateness\rightarrow Tardiness\rightarrow Weighted\ Tardiness
$$

以及三个层次的关系：

```text
MILP 求解器
    ↓
Schedule
    ↓
metrics.py
    ↓
evaluate()
    ↓
统一比较结果
```

最重要的结论是：

> 调度方案好不好，必须结合业务目标判断。减少最后完工时间、减少总延期、减少延期订单数量、保护高价值订单，并不是同一个问题。

下一天可以在这些精确模型之上加入 FCFS、SPT、EDD、WSPT 等规则，用启发式方案和 MILP 最优方案进行比较。
