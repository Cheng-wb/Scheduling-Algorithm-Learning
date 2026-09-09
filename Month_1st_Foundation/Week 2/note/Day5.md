# Day 5：调度规则与启发式算法

## 1. 优先级规则与排程

调度规则（Dispatching Rule）通过优先级选择下一个任务。启发式通常能快速生成可行方案，但最优性取决于具体规则、目标和问题假设。MILP 搜索满足约束的方案，只有获得最优性证明后，才能作为最优值基准。

规则与排程生成的职责不同：

```text
Job → 优先级 key → 选择顺序 → 生成起止时间 → Schedule → evaluate
```

优先级 key 越小越先加工。规则只决定选择偏好，释放时间、机器可用时刻和不可抢占要求由调度器处理。

## 2. 五种规则及其目标

| 规则 | 主排序键 | 含义 | 经典性质或用途 |
| --- | --- | --- | --- |
| FCFS | $r_i$ | 先到先服务 | 按到达顺序服务的基准规则 |
| SPT | $p_i$ | 最短加工时间优先 | 最小化 $\sum C_i$ |
| LPT | $-p_i$ | 最长加工时间优先 | 常用于并行机列表调度；单机实验中的对照规则 |
| EDD | $d_i$ | 最早交期优先 | 最小化最大交期偏差 $L_{\max}=\max_i(C_i-d_i)$ |
| WSPT | $p_i/w_i$ | 加权最短加工时间优先 | 最小化 $\sum w_iC_i$ |

表中 SPT、EDD、WSPT 的最优性成立于单机、任务同时可用、不可抢占、无换型等经典假设；WSPT 的比例形式要求正权重，EDD 的经典结论要求交期已定义。

### SPT 与总完工时间

若相邻任务满足 $p_i>p_j$，把 j 放到 i 前，会使两者完工时间之和减少 $p_i-p_j$，且不影响后续任务的完工时刻。因此加工时间升序最优。

### WSPT 与加权总完工时间

比较相邻的 i → j 与 j → i，前者更优或相同的条件为：

$$
w_jp_i\le w_ip_j
\quad\Longleftrightarrow\quad
\frac{p_i}{w_i}\le\frac{p_j}{w_j}.
$$

加权完工时间 $\sum w_iC_i$ 与加权延期 $\sum w_i\max(0,C_i-d_i)$ 不同。WSPT 不使用交期，因此不保证加权延期最优；EDD 也不保证总延期最优。

### 并列优先级与缺失值

- FCFS 按释放时间排序；同时释放时保留输入顺序，不按任务 ID 重新排列。
- SPT、LPT、EDD、WSPT 的主键相同时，依次比较释放时间和任务 ID。ID 按字符串顺序比较，例如 J10 在 J2 前。
- EDD 将无交期任务的主键设为正无穷，排在有交期任务之后；动态模式下只在已释放集合中比较。
- Job 允许零权重，但本项目的 WSPT 接口要求权重严格为正，零权重输入报错。这是接口约定；扩展实现也可以把零权重任务排到正权重任务之后。

## 3. 静态排序与动态派工

### 静态模式

对全部任务排序一次，然后严格按该顺序执行：

$$
S_i=\max(t,r_i),\qquad C_i=S_i+p_i,\qquad t\leftarrow C_i.
$$

轮到的任务未释放时，机器等待它，即使其他任务已可用也不跳过。该方案可行，但等待可能不必要。排序与展开的总复杂度为 $O(n\log n)$。

### 动态模式

机器空闲时，先构造可用集合：

$$
A(t)=\{i\mid i\text{ 尚未加工且 }r_i\le t\}.
$$

若集合非空，从中选取优先级最小的任务并加工到完成；若集合为空，将时钟跳到剩余任务的最早释放时刻。新任务到达时不会中断正在加工的任务。

这里的“动态”表示每次决策重新检查可用任务，不表示实时接收外部订单。实现采用列表扫描，复杂度为 $O(n^2)$；优先级只依赖不可变的 Job，因此可预先计算。

动态模式在有任务可用时立即加工，属于非延迟派工；最优排程却可能主动空闲。因此它不保证在有释放时间时优于所有静态方案，也不保证最优。

**反例：** Long 的 p=10、r=0；Short 的 p=1、r=1。

| 方案 | 加工区间 | 总完工时间 |
| --- | --- | ---: |
| 动态 SPT | Long [0,10]，Short [10,11] | 21 |
| 主动等待 | Short [1,2]，Long [2,12] | 14 |

第二个方案的 Makespan 更大，但总完工时间更小。

## 4. 项目接口

| 模块 | 职责 |
| --- | --- |
| [heuristics/rules.py](../scheduling/heuristics/rules.py) | 五种排序键与优先级类型 |
| [heuristics/single_machine.py](../scheduling/heuristics/single_machine.py) | 静态、动态排程以及规则便捷入口 |
| [heuristics/__init__.py](../scheduling/heuristics/__init__.py) | 导出调用接口 |
| [day5_dispatching_rules.py](../experiments/day5_dispatching_rules.py) | 数据集、规则比较、打印、MILP 基准 |

基础入口是 `schedule_static_rule(jobs, priority_fn)` 和 `schedule_dynamic_rule(jobs, priority_fn)`。`schedule_by_rule()` 负责模式选择；`fcfs()`、`spt()`、`lpt()`、`edd()`、`wspt()` 是指定优先级的便捷函数，共用上述排程逻辑。

```python
from scheduling.heuristics import spt
from scheduling.evaluator import evaluate

schedule = spt(jobs)                # 全局排序后按固定顺序加工
schedule = spt(jobs, dynamic=True)  # 每次只从已释放任务中选择
result = evaluate(schedule)
```

排程输入不被修改。动态调度的待处理列表保持输入顺序，保证相同 key 的选择稳定。实验用 `ExperimentResult` 分别保存 Schedule、指标字典和 Runtime，不把排程混入指标字典。

## 5. 同时释放的五规则实验

所有任务的 $r_i=0$：

| Job | p | d | w |
| --- | ---: | ---: | ---: |
| J1 | 3 | 10 | 2 |
| J2 | 6 | 15 | 1 |
| J3 | 2 | 6 | 5 |
| J4 | 7 | 20 | 3 |
| J5 | 4 | 9 | 4 |

| 规则 | 顺序（任务编号） | $\sum C_i$ | $\sum w_iC_i$ | $\sum T_i$ | $\sum w_iT_i$ |
| --- | --- | ---: | ---: | ---: | ---: |
| FCFS | 1 → 2 → 3 → 4 → 5 | 63 | 212 | 18 | 77 |
| SPT | 3 → 1 → 5 → 2 → 4 | 53 | 137 | 2 | 6 |
| LPT | 4 → 2 → 5 → 1 → 3 | 79 | 252 | 34 | 132 |
| EDD | 3 → 5 → 1 → 2 → 4 | 54 | 133 | 2 | 6 |
| WSPT | 3 → 5 → 1 → 4 → 2 | 55 | 122 | 7 | 7 |

所有方案从 0 连续工作，因此 Makespan 都为 22。SPT 的总完工时间为 53，与 MILP 最优值一致；WSPT 的加权总完工时间为 122，但加权延期为 7，高于这组数据中 SPT 和 EDD 的 6。

## 6. 同一组释放时间数据的模式对比

| Job | p | r | d | w |
| --- | ---: | ---: | ---: | ---: |
| J1 | 3 | 0 | 10 | 2 |
| J2 | 1 | 10 | 11 | 1 |
| J3 | 2 | 0 | 6 | 5 |
| J4 | 4 | 4 | 12 | 4 |
| J5 | 3 | 1 | 9 | 2 |

| 规则 | 静态 Cmax | 动态 Cmax | 静态 $\sum C_i$ | 动态 $\sum C_i$ | 静态空闲 | 动态空闲 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FCFS | 13 | 13 | 41 | 41 | 0 | 0 |
| SPT | 23 | 13 | 82 | 40 | 10 | 0 |
| LPT | 17 | 13 | 66 | 44 | 4 | 0 |
| EDD | 15 | 13 | 41 | 40 | 2 | 0 |
| WSPT | 17 | 13 | 52 | 41 | 4 | 0 |

静态 SPT 将 p=1 的 J2 排在最前，但 J2 到时刻 10 才释放，导致初始空闲 10。动态 SPT 在时刻 0 从 J1、J3 中选择 J3，无需等待 J2。FCFS 的固定顺序已经按释放时间排列，在一致的并列规则下两种模式相同。

## 7. 基准比较与运行

对相同实例、相同最小化目标，以已证明的最优值 $z^*$ 为基准：

$$
\mathrm{Gap}=\frac{z_h-z^*}{|z^*|}.
$$

$z^*=0$ 时不直接相除：启发式也为 0 则记为 0，否则记为无穷大。若 MILP 只有可行解，不能把这个比值解释成相对最优解的差距。

同时释放实验中，SPT 与 MILP 都是 53，Gap=0%；主动等待反例中，动态 SPT 为 21、MILP 为 14，Gap=50%。Runtime 在算法调用前后测量，不包含评价与打印；短小实例的一次计时不足以推断普遍性能。

在 Week 2 目录运行：

```powershell
python -m experiments.day5_dispatching_rules
```

只运行规则、无需 OR-Tools：

```powershell
python -m experiments.day5_dispatching_rules --skip-milp
```

从仓库根目录也可用 `.venv/Scripts/python.exe` 直接运行实验文件。完整实验依次输出同时释放规则比较、分批释放的静态/动态比较，以及两个总完工时间 MILP 基准。
