# 并行机调度——Greedy、LPT 与 MILP

[周任务](../README.md) · [对应项目](../../../projects/scheduling_basics/README.md)

> 来源：原第二周 Day 6。按主题归档；旧实验数字仍对应文中配置，不代表新计划的未完成验收已通过。

## 1. 问题与机器负载

$P_m\mid\mid C_{\max}$ 表示 m 台相同并行机，目标为最小化最大完工时间。相同机器意味着同一个任务在任意机器上的加工时间都为 $p_i$。

模型假设：所有任务及机器在时刻 0 可用；每个任务只在一台机器上完整加工，不可拆分、不可抢占；无换型、维护和工序先后约束。交期和权重不参与优化。

令机器 j 的任务集合为 $A_j$，负载为：

$$
\ell_j=\sum_{i\in A_j}p_i.
$$

各机器从 0 连续加工时，机器负载等于最后完工时刻，因此：

$$
C_{\max}=\max_j\ell_j.
$$

不同机器可以同时加工；同机任务不能重叠。分配确定后，同机内部顺序不影响该机器最终负载，但会影响总完工时间和延期等其他指标。

## 2. Greedy / List Scheduling

按输入任务顺序，每次把任务分给当前负载最小的机器。

1. 初始化 `machine_loads = [0.0] * m`。
2. 扫描全部机器，选择负载最小的机器 j。
3. 令 $S_i=\ell_j$、$C_i=S_i+p_i$。
4. 记录任务分配，更新 $\ell_j=C_i$。

```python
machine_id = min(range(num_machines), key=lambda j: machine_loads[j])
```

负载并列时选择编号最小的机器。分配逻辑使用列表扫描，时间复杂度为 $O(nm)$，机器负载数组空间为 $O(m)$，排程输出空间为 $O(n)$。项目最后的 `Schedule.validate()` 还会排序校验，产生额外 $O(n\log n)$ 开销。

Greedy 依赖输入顺序，局部选择最小负载并不保证最终最大负载最小。

## 3. LPT + List Scheduling

LPT 先按加工时间降序排列任务，再复用相同的最小负载分配过程：

$$
\text{LPT}=\text{加工时间降序}+\text{List Scheduling}.
$$

先分配长任务可以降低“最后剩下一个长任务，导致某台机器负载突然增大”的风险。并行机 LPT 包括任务排序和机器选择；单机 LPT 只有排序。

排序与分配的复杂度为 $O(n\log n+nm)$。实现复用 `lpt_key()`，相同加工时间时按任务 ID 排序；在任务及 ID 不变时，反转输入列表不改变 LPT 的结果。排序生成新列表，不修改输入。

LPT 通常是较好的基准算法，但不保证最优，也不保证在每个实例上优于任意输入顺序的 Greedy。例如 `[8,7,6,5,4]` 分到两台机器：

| 方法 | 负载分组 | Makespan |
| --- | --- | ---: |
| LPT | 8+5+4；7+6 | 17 |
| 最优分配 | 8+7；6+5+4 | 15 |

## 4. MILP 与理论下界

复用并行机分配模型：

$$
x_{ij}\in\{0,1\},\qquad \sum_jx_{ij}=1\quad\forall i
$$

$$
C_{\max}\ge\sum_i p_ix_{ij}\quad\forall j,\qquad \min C_{\max}.
$$

任务不能被漏排或重复分配。求解后把同机任务串行展开，返回与启发式相同的 Schedule。

任意可行方案都满足：

$$
LB=\max\left(\frac{\sum_i p_i}{m},\max_i p_i\right)\le C_{\max}^*.
$$

加工时间全为整数时，可将平均负载向上取整；小数加工时间不能直接取整。下界是任务实例的性质，不是某个 Schedule 的指标，所以本实验将计算函数放在实验模块中。

若启发式结果为 20、下界为 18，则 $18\le C_{\max}^*\le20$，其绝对误差至多为 2。达到下界即可证明最优；没达到这个简单下界，不代表方案一定非最优。

在上述经典假设下，列表调度与 LPT 有最坏情况近似保证：

$$
\frac{C_{\max}^{LS}}{C_{\max}^*}\le2-\frac1m,\qquad
\frac{C_{\max}^{LPT}}{C_{\max}^*}\le\frac43-\frac{1}{3m}.
$$

这些是所有合法实例上的上界，不是每个实例的实际误差，也不能直接套用到带释放时间、换型或不同机器速度的模型。

## 5. Gap 与利用率

以已证明的最优值为基准，启发式 Gap 为：

$$
\mathrm{Gap}=\frac{C_{\max}^{heuristic}-C_{\max}^*}{C_{\max}^*}.
$$

它与求解器内部的 optimality gap 不同：后者比较当前可行解与搜索下界。只有 FEASIBLE 状态时不能把求解器结果当成最优值。实验中 MILP 未证明最优或未运行时，Gap 显示 N/A，继续展示启发式结果和简单下界。空实例最优值与启发式值均为 0 时，Gap 约定为 0。

在统一窗口 $[0,C_{\max}]$ 内：

$$
U_j=\frac{\ell_j}{C_{\max}},\qquad
U=\frac{\sum_i p_i}{mC_{\max}},\qquad
I_{total}=mC_{\max}-\sum_i p_i.
$$

没有分到任务的机器也计入 m。最后一个任务结束前，其余机器提前结束的时间计入空闲。对于固定工作量和机器数，最小化 Makespan 等价于最大化该窗口下的平均利用率。

## 6. 实验结果

所有方法在每个案例中使用同一批 Job 和相同机器数；各次运行的 MILP 均证明最优。

| 案例（按输入顺序列 p） | m | LB | Greedy | LPT | MILP | Greedy Gap | LPT Gap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3,7,2,8,4,6 | 2 | 15 | 17 | 15 | 15 | 13.33% | 0% |
| 3,7,2,8,4,6 | 3 | 10 | 13 | 10 | 10 | 30% | 0% |
| 8,7,6,5,4 | 2 | 15 | 17 | 17 | 15 | 13.33% | 13.33% |
| 9,8,7,6,5,4,3,2 | 3 | 15 | 16 | 16 | 15 | 6.67% | 6.67% |
| 基础案例反转输入、保留 ID | 2 | 15 | 15 | 15 | 15 | 0% | 0% |

第一组 Greedy 负载为 `[13,17]`，LPT 为 `[15,15]`。反转同一批任务后，Greedy 达到 15，表明输入顺序会影响结果。

纸笔案例的列表调度负载为 `[16,15,13]`；更优分配可以是 `8+7=15`、`9+4+2=15`、`6+5+3=14`，达到整数下界 15。

规模实验用 `random.Random(42)` 生成 100 个 1～20 的整数加工时间，分别取前 n 个任务：

| n | m | LB | Greedy | LPT | MILP | Greedy Gap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 3 | 27 | 33 | 27 | 27 | 22.22% |
| 30 | 5 | 57 | 61 | 57 | 57 | 7.02% |
| 100 | 10 | 97 | 103 | 97 | 97 | 6.19% |

这些实例中 LPT 均达到最优，不能据此认为 LPT 总是最优。Runtime 以脚本输出为准，包含算法调用及内部校验，不包含统一评价和打印；规模、数据、硬件及求解器都会影响计时。

## 7. 接口与运行

[heuristics/parallel_machine.py](../../../projects/scheduling_basics/scheduling/heuristics/parallel_machine.py) 提供三个接口：

```python
list_schedule(jobs, num_machines)
greedy_list_scheduling(jobs, num_machines)
lpt_list_scheduling(jobs, num_machines)
```

`list_schedule()` 实现一次分配逻辑，Greedy 保留输入顺序，LPT 先排序。所有接口返回 Schedule，保留全部机器数量，并检查机器数、重复 ID、释放时间和排程可行性。非零释放时间输入会报错，以保持与本次 MILP 模型一致。

[parallel_comparison.py](../../../projects/scheduling_basics/experiments/parallel_comparison.py) 负责案例、下界、调用、按机器打印加工区间、负载和比较表。默认每个 MILP 实例限时 5 秒，可通过参数调整。

在 scheduling_basics 项目目录 目录运行：

```powershell
python -m experiments.parallel_comparison
python -m experiments.parallel_comparison --scale
python -m experiments.parallel_comparison --skip-milp
python -m experiments.parallel_comparison --scale --time-limit-ms 30000
```

`--skip-milp` 只运行标准库实现的启发式，不依赖 OR-Tools。IDE 也可直接运行实验文件；完整比较需选择已安装 OR-Tools 的解释器。
