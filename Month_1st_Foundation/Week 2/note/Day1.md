# Day 1：调度问题的数学描述与核心概念

## 1. 学习目标

对应学习路线中“调度基本概念”与“理论 → 建模 → 编码 → 实验”的闭环，为后续 MILP 建模准备评价工具。今天重点是把实际问题翻译成数学语言，并手算、验证一个给定调度方案。

## 2. 调度的基本对象

调度决定：**什么任务，在什么资源上，什么时间执行。**

| 概念 | 符号 | 含义与例子 |
| --- | --- | --- |
| Job（作业/任务） | $J_i$ | 待安排的基本任务，如一张生产订单 |
| Operation（工序） | $O_{ik}$ | 作业 $i$ 的第 $k$ 道工序，如切割、钻孔、喷漆 |
| Machine（机器/资源） | $M_j$ | 执行任务的有限资源，如机床、CPU 核心 |
| Processing time | $p_i$ | 单工序任务需要的加工时长 |
| Release time | $r_i$ | 任务最早可以开始的时刻，属于输入参数 |
| Due date | $d_i$ | 期望完成时刻，通常允许延期并计入惩罚 |
| Weight | $w_i$ | 任务重要性或单位延期惩罚权重 |

一个 Job 可以含多道 Operation。加工时间 $p_{ij}$ 也可能表示任务 $i$ 在机器 $j$ 上的加工时间，必须先明确下标含义。

今天代码限定：一台机器、每个任务一道工序、不可抢占、无换型时间、机器从时刻 0 可用。不可抢占表示任务开始后连续加工到完成；可抢占则允许暂停后继续。

## 3. 时间与评价指标

| 名称 | 公式 | 含义 |
| --- | --- | --- |
| 开始时间 | $S_i\ge r_i$ | 不能在任务释放前加工 |
| 完工时间 | $C_i=S_i+p_i$ | 适用于这里的单工序、连续加工假设 |
| Lateness（带符号的交期偏差） | $L_i=C_i-d_i$ | 提前为负、准时为零、迟交为正 |
| Tardiness（延期时间） | $T_i=\max(0,C_i-d_i)$ | 只统计迟交，永不为负 |
| Waiting time | $W_i=S_i-r_i$ | 释放后到开始加工的等待时间 |
| Flow time | $F_i=C_i-r_i=W_i+p_i$ | 任务在系统中的停留时长 |
| Makespan | $C_{\max}=\max_i C_i$ | 最后一个任务完成的时刻 |
| 总完工时间 | $\sum_i C_i$ | 各任务完工时刻之和，不是加工总时长 |
| 总延期 | $\sum_i T_i$ | 所有任务的延期时长之和 |
| 加权总延期 | $\sum_i w_iT_i$ | 考虑任务重要性的延期代价 |

例如 $d_i=10$：当 $C_i=8$ 时，$L_i=-2,T_i=0$；当 $C_i=12$ 时，$L_i=T_i=2$。提前完成不会抵消其他任务的延期。

Due date 不自动意味着 $C_i\le d_i$ 必须成立。如果业务要求绝不能迟交，才将它写为硬约束。$C_i$ 是时刻，$F_i$ 是时长；当 $r_i\ne0$ 时不能混用。

对本例单机，以 $[0,C_{\max}]$ 为观察窗口：

$$
B=\sum_i p_i,\qquad I=C_{\max}-B,\qquad U=\frac{B}{C_{\max}}.
$$

其中 $B$ 是忙碌时间，$I$ 是空闲时间（包含首次开工前的空闲），$U$ 是利用率。空任务集的汇总指标在代码中约定为 0。利用率取决于观察窗口；零空闲也不能保证延期指标最优。

## 4. 数学建模：参数、变量、约束、目标

场景：一台机床加工若干订单，材料到齐后才能开工，一次只能加工一个订单，允许迟交，希望减少加权延期。

**参数：** 任务集合 $\mathcal J$、加工时间 $p_i$、释放时间 $r_i$、交期 $d_i$、权重 $w_i$。

**决策：** 加工顺序和开始时间 $S_i$。完工时间 $C_i$ 与延期 $T_i$ 可作为辅助变量。

**约束：**

$$
S_i\ge r_i,\qquad C_i=S_i+p_i \quad (i\in\mathcal J)
$$

$$
C_i\le S_j\quad\text{或}\quad C_j\le S_i\quad (i\ne j)
$$

第二条表示同机任务不得重叠，前一个任务完工时下一个可以立即开始。这是逻辑约束，尚不是完整的线性化 MILP。

$$
T_i\ge0,\qquad T_i\ge C_i-d_i
$$

**目标：**

$$
\min\sum_i w_iT_i.
$$

正权重下，最小化目标会将 $T_i$ 压到实际延期值；若 $w_i=0$，这些不等式不强制该辅助变量取最小值。评价器直接用 $\max$ 计算真实延期。

扩展到多机时，可以用 $x_{ij}\in\{0,1\}$ 表示任务 $i$ 是否分配给机器 $j$，并要求 $\sum_jx_{ij}=1$。顺序变量 $y_{ij}=1$ 可表示 $i$ 在 $j$ 前加工。多工序的先后约束形如 $S_{i,k+1}\ge C_{ik}$。这些扩展今天只理解含义。

目标必须根据业务明确：$\min C_{\max}$ 关注全部做完的时刻，$\min\sum C_i$ 关注整体尽早完工，$\min\sum T_i$ 关注交期，$\min\sum w_iT_i$ 还区分重要性。

## 5. 三字段表示法

$$
\alpha\mid\beta\mid\gamma
$$

| 字段 | 描述 | 常见取值 |
| --- | --- | --- |
| $\alpha$ | 机器环境 | $1$：单机；$P_m$：$m$ 台相同并行机 |
| $\beta$ | 额外条件 | $r_i$：释放时间；prec：先后约束；pmtn：允许抢占 |
| $\gamma$ | 优化目标 | $C_{\max}$、$\sum C_i$、$\sum w_iT_i$ |

- $1\mid\mid C_{\max}$：单机、无额外条件、最小化最大完工时间。
- $1\mid r_i\mid\sum C_i$：单机、有释放时间、最小化总完工时间。
- $P_m\mid\mid C_{\max}$：相同并行机、无额外条件、最小化最大完工时间。

空白的 $\beta$ 不表示没有机器容量等基本约束；在这里的经典模型中默认不可抢占、释放时间为 0。今日评价器可以评价 $1\mid r_i\mid\sum w_iT_i$ 的给定顺序，但不负责搜索最优顺序。

## 6. 四任务手算

输入数据：

| Job | $p_i$ | $r_i$ | $d_i$ | $w_i$ |
| --- | ---: | ---: | ---: | ---: |
| J1 | 4 | 0 | 6 | 1 |
| J2 | 2 | 0 | 8 | 1 |
| J3 | 5 | 0 | 10 | 1 |
| J4 | 1 | 0 | 5 | 1 |

顺序 A：J1 → J2 → J3 → J4。

| Job | $S_i$ | $C_i$ | $L_i$ | $T_i$ |
| --- | ---: | ---: | ---: | ---: |
| J1 | 0 | 4 | -2 | 0 |
| J2 | 4 | 6 | -2 | 0 |
| J3 | 6 | 11 | 1 | 1 |
| J4 | 11 | 12 | 7 | 7 |

顺序 B：J4 → J1 → J2 → J3。

| Job | $S_i$ | $C_i$ | $L_i$ | $T_i$ |
| --- | ---: | ---: | ---: | ---: |
| J4 | 0 | 1 | -4 | 0 |
| J1 | 1 | 5 | -1 | 0 |
| J2 | 5 | 7 | -1 | 0 |
| J3 | 7 | 12 | 2 | 2 |

| 顺序 | $C_{\max}$ | $\sum C_i$ | $\sum T_i$ |
| --- | ---: | ---: | ---: |
| A | 12 | 33 | 8 |
| B | 12 | 25 | 2 |

相同 Makespan 不意味着其他指标相同。这里所有任务时刻 0 释放，单机从 0 连续工作，因此任意无空闲排列的 Makespan 都等于 $\sum p_i=12$。

## 7. 六任务练习与比较

| Job | $p_i$ | $r_i$ | $d_i$ | $w_i$ |
| --- | ---: | ---: | ---: | ---: |
| J1 | 3 | 0 | 7 | 2 |
| J2 | 6 | 0 | 15 | 1 |
| J3 | 2 | 2 | 8 | 5 |
| J4 | 5 | 0 | 10 | 3 |
| J5 | 1 | 4 | 9 | 8 |
| J6 | 4 | 1 | 14 | 2 |

固定顺序的递推计算：设机器当前可用时刻为 $t=0$，依次取出任务 $i$：

$$
S_i=\max(t,r_i),\qquad C_i=S_i+p_i,\qquad t\leftarrow C_i.
$$

若轮到的任务尚未释放，就等待它；不能偷偷跳过它，否则改变了待评价的顺序。

| 顺序 | 各任务开始时刻（按顺序） | 各任务完工时刻（按顺序） |
| --- | --- | --- |
| A：J1 → J2 → J3 → J4 → J5 → J6 | 0, 3, 9, 11, 16, 17 | 3, 9, 11, 16, 17, 21 |
| B：J1 → J3 → J5 → J4 → J6 → J2 | 0, 3, 5, 6, 11, 15 | 3, 5, 6, 11, 15, 21 |
| C：J5 → J3 → J1 → J6 → J4 → J2 | 4, 5, 7, 10, 14, 19 | 5, 7, 10, 14, 19, 25 |

| 顺序 | 各任务 $L_i$（按顺序） | 各任务 $T_i$（按顺序） |
| --- | --- | --- |
| A | -4, -6, 3, 6, 8, 7 | 0, 0, 3, 6, 8, 7 |
| B | -4, -3, -3, 1, 1, 6 | 0, 0, 0, 1, 1, 6 |
| C | -4, -1, 3, 0, 9, 10 | 0, 0, 3, 0, 9, 10 |

| 顺序 | $C_{\max}$ | $\sum C_i$ | $\sum T_i$ | $\sum w_iT_i$ | 空闲时间 | 利用率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 21 | 77 | 24 | 111 | 0 | 100% |
| B | 21 | 61 | 8 | 11 | 0 | 100% |
| C | 25 | 80 | 22 | 43 | 4 | 84% |

例如 B 的加权延期为 $3\times1+2\times1+1\times6=11$。C 为等待 J5 释放，最初空闲 4 个时间单位。B 在这三组方案的上述指标中最好或并列最好，但只比较三组顺序不能证明全局最优。A 与 C 的总完工时间、加权延期优劣相反，说明排序评价取决于目标。

## 8. 项目架构与题目运行

### 8.1 当前目录与模块职责

```text
Week 2/
├── README.md
├── note/
│   └── Day1.md               # 学习笔记
├── scheduling/
│   ├── __init__.py
│   ├── models.py             # Job、ScheduledJob、Schedule
│   ├── scheduler.py          # 固定顺序 → Schedule
│   ├── metrics.py            # 各项数学指标
│   └── evaluator.py          # Schedule → 指标汇总
└── experiments/
    ├── __init__.py
    └── day1_basics.py        # 题目数据、手工排程、运行和打印
```

`scheduling` 是可复用的核心包，`note` 保存学习笔记，`experiments` 保存题目数据与运行入口。

| 模块 | 职责 | 主要接口 |
| --- | --- | --- |
| [models.py](../scheduling/models.py) | 定义输入任务、单条分配和完整排程 | `Job`、`ScheduledJob`、`Schedule` |
| [scheduler.py](../scheduling/scheduler.py) | 根据给定顺序和释放时间生成排程 | `schedule_sequence(sequence, jobs)` |
| [metrics.py](../scheduling/metrics.py) | 独立计算每个指标 | `makespan`、`tardiness`、`weighted_tardiness` 等 |
| [evaluator.py](../scheduling/evaluator.py) | 校验排程并统一调用指标函数 | `evaluate(schedule)` |
| [day1_basics.py](../experiments/day1_basics.py) | 准备题目、组合调用、打印结果 | `main()` |

数据流：

```text
list[Job] + sequence → schedule_sequence() → Schedule
手工填写 ScheduledJob ────────────────────→ Schedule
                                              ↓
                                       evaluate(schedule)
                                              ↓ 调用
                                           metrics
                                              ↓
                                         汇总结果 dict
```

### 8.2 三个数据模型

- `Job(job_id, processing_time, release_time=0, due_date=None, weight=1)`：对应 $i,p_i,r_i,d_i,w_i$。只保存输入参数，使用不可变 dataclass，多个方案可以安全复用同一个任务。
- `ScheduledJob(job, machine_id, start_time, completion_time)`：保存一个任务的资源分配与起止时刻，不把结果写回 Job。机器编号从 0 开始。
- `Schedule(assignments, algorithm=None, machine_count=1)`：统一封装完整方案。`algorithm` 标记来源，`machine_count` 记录全部可用机器数量，包括未分到任务的机器。

`ScheduledJob` 检查释放时间和加工时长关系；`Schedule.validate()` 检查重复任务、机器编号和同机重叠。它没有原始任务全集，因此无法独自发现漏排任务；固定顺序构造器负责检查输入序列完整性。后续算法也需要保证每个输入任务恰好排一次。

### 8.3 指标与评价器的区别

`metrics.py` 的函数只读取排程。单任务函数包括 `lateness`、`tardiness`、`flow_time`、`waiting_time`；方案级函数包括 `makespan`、总完工时间、总延期、加权延期、迟交任务数等。

例如 `tardiness(item)` 复用 `lateness(item)`，`total_tardiness(schedule)` 和 `weighted_tardiness(schedule)` 再复用 `tardiness(item)`。数学公式只维护在指标层。

`evaluate(schedule)` 调用 `schedule.validate()` 后，把指标函数的返回值组织为字典，不排序、不生成开始时间。只需要一项指标时，直接调用 `makespan(schedule)` 即可；直接调用指标函数前，调用方应保证排程可行。

迟交任务数量为 $N_T=\sum_i\mathbf{1}(T_i>0)$，对应 `num_tardy_jobs()`。没有交期的任务，其 Lateness 和 Tardiness 在本项目中约定返回 0、也不计入迟交数量；这表示不评价交期，不代表真实交期偏差为零。

空排程各汇总指标约定为 0。单机利用率与第 3 节一致；当有 $m$ 台机器时，统一窗口为 $[0,C_{\max}]$：

$$
I_{\mathrm{total}}=mC_{\max}-\sum_i p_i,\qquad
U=\frac{\sum_i p_i}{mC_{\max}}.
$$

这里利用率是所有可用机器的平均值。后续添加并行机算法时，必须正确填写 `machine_count`。

### 8.4 运行今日题目

要求 Python 3.10 或更高版本，无第三方依赖。四任务题目手工构造两个 Schedule，六任务题目通过 `schedule_sequence()` 构造三组方案，统一输出 M、S、C、L、T、wT、W、F 和汇总指标。

在 `Week 2` 目录执行：

```powershell
python -m experiments.day1_basics
```

从仓库根目录先进入 Week 2，再运行实验：

```powershell
cd "Month 1st Foundation/Week 2"
python -m experiments.day1_basics
```

调用示例（在 Week 2 下）：

```python
from scheduling.models import Job
from scheduling.scheduler import schedule_sequence
from scheduling.evaluator import evaluate
from scheduling.metrics import makespan

jobs = [
    Job("J1", processing_time=4, due_date=6),
    Job("J2", processing_time=2, due_date=8),
    Job("J3", processing_time=5, due_date=10),
    Job("J4", processing_time=1, due_date=5),
]
schedule = schedule_sequence(["J4", "J1", "J2", "J3"], jobs)
result = evaluate(schedule)
print(schedule.assignments)
print(makespan(schedule))         # 单独计算一个指标：12
print(result["makespan"])         # 12
print(result["total_tardiness"])  # 2
```

与旧接口相比，输入任务由字典改成带 `job_id` 的 Job 列表；先生成 Schedule，再执行 `evaluate(schedule)`。逐任务数据从 `schedule.assignments` 读取，汇总字典不再混入排程数据。

序列必须完整覆盖全部任务且不能重复。加工时间必须为正，释放时间、权重非负，数值必须有限；允许小数时间。交期可为负，表示任务在观察起点前就已到期。

### 8.5 后续如何扩展

后续按学习内容逐步在 `scheduling` 中增加 `heuristics/`、`exact/`、`generators/`、`visualization/`，当前不创建尚未实现的算法占位文件。

- 启发式规则与精确算法统一返回 `Schedule`，复用现有评价器。
- 实例生成器返回 `list[Job]`，使用固定随机种子让不同算法比较同一批输入。
- 甘特图读取 `Schedule`，无需知道排程由哪种算法产生。
- 实验代码负责比较方案和测量求解耗时；runtime 用 `perf_counter()` 包围算法调用测得，不由排程指标推算。
- 当实验结果字段稳定后，可将评价器的 dict 升级为 `EvaluationResult` dataclass。

运行今日题目后，把结果与第 6、7 节手算表对照。日常练习仍以运行题目、输出结果为主。

## 9. 自检

1. 能否说明 Job 与 Operation 的区别？
2. 能否解释为什么 $S_i\ge r_i$，却不一定要求 $C_i\le d_i$？
3. 能否区分 $L_i$ 与 $T_i$、$C_i$ 与 $F_i$？
4. 能否解释两种顺序 Makespan 相同而总延期不同？
5. 面对新场景，能否依次列出任务、资源、加工时长、时间限制、业务约束、决策变量和目标？
6. 能否先手算一个序列，再用评价器核对？
