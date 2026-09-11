# Day 2：并行机分配 MILP

[周计划](../README.md)

## 完整数学模型

任务集合 $I=\{1,\ldots,n\}$，机器集合 $M=\{1,\ldots,m\}$，已知加工时间 $p_i>0$。

**变量：**

$$
x_{ij}\in\{0,1\},\qquad C_{\max}\ge0.
$$

$x_{ij}=1$ 表示任务 $i$ 分配给机器 $j$。$C_{\max}$ 是连续辅助变量。

**目标与约束：**

$$
\min C_{\max}
$$

$$
\sum_{j\in M}x_{ij}=1\qquad \forall i\in I
$$

$$
C_{\max}\ge\sum_{i\in I}p_ix_{ij}\qquad \forall j\in M.
$$

第一组约束要求每个任务恰好分配一次；改成 $\le1$ 会允许漏排，改成 $\ge1$ 会允许重复分配。

令机器负载为 $\ell_j=\sum_i p_ix_{ij}$。第二组约束使 $C_{\max}$ 不小于任一机器负载，再通过最小化把它压到 $\max_j\ell_j$。使用 $\ell_j$ 表示负载，以区别 Day 1 中的 Lateness $L_i$。

原始模型有 $nm$ 个二进制变量、1 个连续变量，以及 $n+m$ 条主要约束，不计变量界。求解器预处理后的规模可能不同。
## 从数学模型到项目代码

算法位于 [parallel_machine.py](../scheduling/exact/parallel_machine.py)，沿用原先的建模步骤：

| 数学或工程步骤 | 对应代码 |
| --- | --- |
| 创建求解引擎 | `pywraplp.Solver.CreateSolver("CBC")` |
| 二进制分配变量 | `solver.BoolVar(...)` |
| 连续 Cmax | `solver.NumVar(0, solver.infinity(), "cmax")` |
| 每个任务恰好一次 | `solver.Add(sum(...) == 1)` |
| 机器负载上界 | `solver.Add(machine_load <= cmax)` |
| 最小化目标 | `solver.Minimize(cmax)` |
| 求解与状态检查 | `status = solver.Solve()` |

接口为 `solve_parallel_machine_milp(jobs, num_machines, time_limit_ms=30_000) -> Schedule`。先检查机器数、时间限制、重复 ID 和释放时间；空任务集返回空排程。

提取方案时用 `solution_value() > 0.5` 判断二进制分配，避免直接比较浮点数是否等于 1，并核对每个任务恰好选中一台机器。每台机器上的任务按原输入顺序从 0 串行展开，生成 `ScheduledJob`。最后检查排程可行性，并核对实际最大完工时间与求解器目标值一致。

`ScheduledJob` 的单任务时间指标仍使用你写的属性；没有交期时，属性返回 None，指标汇总层将其视为零贡献。这里只表示没有交期评价要求。

算法不打印结果，不测量整体运行时间；[day2_parallel_milp.py](../experiments/day2_parallel_milp.py) 负责实例、求解调用、评价和输出。实验的 Runtime 用 `perf_counter()` 包围整个算法调用，包含建模、求解、提取和内部校验，不包含后续评价与打印。
## 实验与结果

基础题目运行结果：

| 加工时间 | 机器数 | 简单下界 | 最优 Makespan | 一种机器负载分配 |
| --- | ---: | ---: | ---: | --- |
| 3, 7, 2, 8, 4, 6 | 2 | 15 | 15 | 3+2+4+6；7+8 |
| 3, 7, 2, 8, 4, 6 | 3 | 10 | 10 | 3+7；2+8；4+6 |
| 6, 6, 6, 6, 6 | 2 | 15 | 18 | 6+6+6；6+6 |

机器编号和具体分配可能不同，只要完整、可行且目标相同即可。多种 Makespan 最优方案可能具有不同的总完工时间。

规模实验使用 `random.Random(42)` 生成 100 个 1～20 的整数加工时间，再取前 n 个任务，均使用 3 台机器。本次运行均返回 OPTIMAL：

| n | 变量数 | 约束数 | 简单下界 | Makespan |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 31 | 13 | 27 | 27 |
| 20 | 61 | 23 | 57 | 57 |
| 50 | 151 | 53 | 158 | 158 |
| 100 | 301 | 103 | 322 | 322 |

运行时间以脚本现场输出为准，受硬件和求解器版本影响；这组样例不能说明所有同规模实例都容易求解。



## 实验入口

在本周目录运行：

```powershell
python -m experiments.day2_parallel_milp
```
