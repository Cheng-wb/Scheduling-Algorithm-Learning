# Day 3：局部搜索 Local Search

[周计划](../README.md)

## 学习目标

理解从一层邻域比较到重复改进的过程，实现 Best Improvement 与 First Improvement，记录搜索路径，并区分局部最优和资源上限导致的停止。

## 前置知识

规则生成初始任务排列，Move 产生邻居，`build_schedule()` 根据排列重新计算排程，`objective()` 返回待最小化的标量。实验继续使用单机、不可抢占、任务可自由排序、$r_i=0$ 的条件。

目标为总延期：

$$
f(\pi)=\sum_i\max(0,C_i(\pi)-d_i).
$$

## Local Search 基本思想

```text
初始解 → 枚举当前邻域 → 选择严格改进 → 更新当前解
                          ↑                │
                          └────────────────┘
                没有严格改进时停止
```

每次接受新解后，必须围绕新解重新生成邻域。只检查一次邻域是候选比较，反复更新当前解才是局部搜索。

## 核心变量

| 变量 | 含义 |
| --- | --- |
| Initial | 搜索起点，算法保留其原始排列 |
| Current | 当前所在的排列 |
| Current Score | 当前排列解码后的目标值 |
| Neighbor | 当前排列的一次 Move 结果 |
| Best Neighbor | 当前邻域中目标值最小的邻居，未必严格优于 Current |
| Local Optimum | 当前邻域中不存在严格更优邻居的解 |

严格下降搜索中，Current 同时也是迄今最好的已访问解。允许接受较差解的算法需要另外保存历史最佳解。

## 手算一轮搜索

沿用六任务实例，$p=[8,3,6,2,7,4]$、$d=[12,7,20,15,14,10]$，任务按 J1～J6 编号。

SPT 初始解为 J4 → J2 → J6 → J3 → J5 → J1，完工时间依次为 $[2,5,9,15,22,30]$，总延期为 $8+18=26$。

第一轮扫描 15 个 Swap 邻居，其中 2 个改进、2 个持平、11 个更差。最佳邻居由 `swap(3,4)` 得到：

```text
J4 → J2 → J6 → J5 → J3 → J1
```

完工时间为 $[2,5,9,16,22,30]$，总延期为 $2+2+18=22$。因为 $22<26$，接受该排列作为新 Current。

第二轮围绕新 Current 再扫描 15 个邻居，没有严格改进，于是停止。`history=[26,22]`，成功更新次数为 1，邻居评价次数为 30。终止前的最后一次完整扫描也有计算成本。

## Best Improvement 实现

```python
current = list(initial_solution)
current_score = objective(build_schedule(current))

while iterations < max_iterations:
    chosen = None
    chosen_score = current_score
    for neighbor in neighbors(current):
        score = objective(build_schedule(neighbor))
        if score < chosen_score:
            chosen, chosen_score = neighbor, score
    if chosen is None:
        break
    current, current_score = chosen, chosen_score
    iterations += 1
```

`chosen_score` 从当前值开始，只保留严格改进。同分不覆盖已选候选，因此确定的枚举顺序也决定 Best Improvement 的并列选择。当前排列与目标值必须一起更新。

## 局部最优与停止条件

对最小化问题，局部最优满足：

$$
f(\pi)\le f(\pi'),\qquad \forall\pi'\in N(\pi).
$$

邻居可以与当前解同分，不要求当前解严格优于所有邻居。局部最优仅针对指定邻域，不等于全局最优。

- `no_improvement`：完整检查当前邻域，没有严格改进。
- `max_iterations`：成功更新次数达到上限，搜索没有继续检查最终邻域，不能仅据此宣称局部最优。

实验在搜索结束后独立扫描最终邻域，输出剩余改进邻居数，同时保留真实停止原因。上限为 0 时直接返回初始解。

有限排列空间中，只接受严格下降的确定性目标值就不会回到已访问解；接受等值移动可能造成循环。

## Best 与 First 对比

| 策略 | 选择方式 | 影响 |
| --- | --- | --- |
| Best Improvement | 扫描整层，选最大改进 | 每轮评价完整邻域，单步改善充分 |
| First Improvement | 遇到第一个严格改进立即接受 | 可能减少当轮评价，但路径依赖枚举顺序 |

例如当前值为 100，邻居依次为 105、97、80：Best 选择 80，First 选择 97。Best 的单步选择更好，不保证最终结果更好；First 的单轮评价可能更少，也不保证总耗时更低。

## Iterations 与 Search History

返回字典包含：

| 字段 | 定义 |
| --- | --- |
| `solution`、`score` | 最终排列和目标值 |
| `iterations` | 成功接受新 Current 的次数 |
| `history` | 初始值以及每次接受后的目标值 |
| `path` | 与 history 一一对应的排列快照 |
| `neighbor_evaluations` | 搜索期间评价的邻居总数，含终止扫描，不含初始解 |
| `stop_reason` | 无改进或达到迭代上限 |

`len(history) = iterations + 1`，相邻历史值严格下降。排列快照使用新列表，避免后续更新改变历史记录。

完整 Best 搜索若每层有 $k$ 个邻居、接受 $t$ 次改进，正常停止需要 $(t+1)k$ 次邻居评价。迭代少不等于计算量小，应结合评价次数和耗时比较。

## Objective 与搜索解耦

`search/local_search.py` 接收初始排列、解码器、目标函数和邻域生成器，不导入 SPT、EDD 或具体指标。

```python
result = best_improvement_local_search(
    initial, build_schedule, objective,
    generate_swap_neighbors, max_iterations=1000,
)
```

两个公开搜索函数共用内部迭代逻辑。搜索模块返回数据；实验模块负责计时、打印与排程复核。每个候选仍完整解码和评价，不使用增量计算。

## 不同 Initial Solution

在相同任务、目标、邻域及策略下比较 SPT 与 EDD 起点，才能观察初始解的影响。SPT 针对总完工时间，EDD 针对最大 lateness，两者都不保证总延期最优。

默认十任务实例中，SPT 初始总延期为 90，EDD 为 82；使用 Swap + Best 后分别停在 64 和 58，说明起点会影响最终结果。

## Search Path

同一十任务实例、SPT 起点、Swap 邻域：

```text
Best : 90 → 83 → 80 → 69 → 67 → 64
First: 90 → 88 → 84 → 80 → 76 → 65 → 58
```

两条路径都严格下降，却进入不同的局部最优。即使最终目标值相同，最终排列也可能不同；`path` 能显示这些区别，单独的 `history` 不能。

## 实验验证

实验执行时核对：初始排列保持不变；history 严格下降；每个排列包含全部任务且排程合法；重新评价与记录值一致；最终解与路径末项一致。正常停止后重新扫描同一邻域，确认不存在更好的邻居。

空排列、单任务、初始目标为零及迭代上限都需要明确处理。初始目标为零时，改善比例显示 `N/A`；相同目标值不触发更新。

## Swap 与 Insert 对比

10 个不同任务的 Swap 邻域有 45 个邻居，去重 Insert 邻域有 81 个邻居。

默认实例中，SPT + Swap + Best 返回值 64，虽然已无更好的 Swap 邻居，但其最佳 Insert 邻居为 58。这是“局部最优依赖邻域”的具体例子。

## 完整实验结果

使用 `homework_jobs(seed=42)`，10 个任务，$p_i\in[1,20]$、$d_i\in[10,80]$、$r_i=0$。所有组合使用相同数据，最大接受次数为 1000。

| 起点 | 邻域 | 策略 | 初始值 | 最终值 | 改善量 | 更新次数 | 邻居评价次数 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| SPT | — | 不搜索 | 90 | 90 | 0 | 0 | 0 |
| SPT | Swap | Best | 90 | 64 | 26 | 5 | 270 |
| SPT | Swap | First | 90 | 58 | 32 | 6 | 201 |
| SPT | Insert | Best | 90 | 58 | 32 | 4 | 405 |
| SPT | Insert | First | 90 | 58 | 32 | 7 | 389 |
| EDD | — | 不搜索 | 82 | 82 | 0 | 0 | 0 |
| EDD | Swap | Best | 82 | 58 | 24 | 3 | 180 |
| EDD | Swap | First | 82 | 58 | 24 | 4 | 148 |
| EDD | Insert | Best | 82 | 58 | 24 | 1 | 162 |
| EDD | Insert | First | 82 | 58 | 24 | 4 | 179 |

这些搜索均因无改进停止。58 是该实验得到的较好目标值，未证明为全局最优。运行时间由实验现场测量，包含搜索内的解码、校验和评价，不包含打印、历史复核及结束后的邻域比较。

## 项目结构

`search/local_search.py` 保存两种搜索入口；`search/neighborhood.py` 提供邻域；`evaluation/objective.py` 定义目标；`experiments/day3_local_search.py` 组合初始规则、邻域和策略，输出实验结果。实验按天存放，核心模块可复用。

## 核心结论

局部搜索通过“枚举、选择、更新、重复”改善初始解。严格接受规则决定目标值单调下降；起点、邻域、策略及并列处理共同决定路径和停止点。对结果的描述应同时说明目标、邻域和停止原因。

## 与 Random Restart 的衔接

当一次搜索停在局部最优时，可以从不同初始排列重新搜索，再比较各次结果。Random Restart 将初始解生成与单次局部搜索分开，复用已有搜索接口；多个起点提高探索机会，但仍不保证全局最优。


## 实验入口

在本周目录运行：

```powershell
python -m experiments.day3_local_search
```
