# Day 7：项目整合与端到端调度实验

[周计划](../README.md)

## 第三周知识链

```text
Jobs → 调度规则 → 初始排列 → 邻域 → 目标评价 → 搜索 → 最好排列
                                                       ↓
                                            排程 → 校验 → Benchmark
```

调度规则直接构造初始解；搜索算法通过邻域逐步修改已有解。Best / First Improvement 只接受严格改善，会停在给定邻域下的局部最优。Multi-start 用不同起点探索不同区域；SA 通过温度控制差解接受概率。两者扩大探索范围，但不保证全局最优。

SA 的当前解决定下一步从哪里搜索，历史最好解决定最终返回什么。评价实验则将目标值、计算成本与随机稳定性放在一起比较。

## Solution、Schedule 与模块职责

Solution 是任务排列，例如 `[J3, J1, J2]`；Schedule 是解码后的任务、机器、开始时间和完成时间。排列本身不含起止时间。

| 模块 | 职责 |
| --- | --- |
| `data/instances.py` | 根据实例种子生成任务 |
| `models/` | 任务与机器基础数据 |
| `scheduling/dispatching.py` | 规则排序、随机初始排列 |
| `scheduling/schedule.py` | 排程数据结构与排列解码 |
| `scheduling/validation.py` | 核对任务覆盖、属性与排程约束 |
| `evaluation/` | 单项指标、汇总指标与目标函数 |
| `search/` | 邻域、LS、Multi-start、SA |
| `experiments/benchmark.py` | Solver 适配、公共参数、计时计数与结果复核 |
| `experiments/tables.py` | 终端表格与结果文件输出 |
| `experiments/day7_integration.py` | 组织完整实验、比较方法、展示最好排程 |

实验入口负责配置数据、调用算法和展示结果。搜索逻辑位于 `search/`，指标公式位于 `evaluation/`。每日实验展示对应知识，整合实验复用公共报表与 Runner。

## 函数式 Solver 与组件组合

概念接口是 `Instance → Solution`。为保留搜索统计，项目采用以下函数式适配接口：

```python
solver(jobs, decode, score) -> result
```

调用者提供解码器和目标函数，返回值包括任务排列、目标值、迭代次数和停止原因。Runner 统一生成包含 `algorithm`、`objective`、`runtime`、`evaluations`、种子及状态的实验结果。

LS 和 SA 共享 `initializer(jobs)`，默认 SPT，可通过 `algorithm_table()` 的参数替换。Multi-start 刻意采用随机初始化，其核心函数支持 `initialize(jobs, rng)`，利用同一局部随机数生成器连续产生不同起点。

LS 接收枚举邻居的 `neighbors(solution)`，SA 接收抽取单个邻居的 `random_neighbor(solution, rng)`；两个接口用途不同。更换 Swap、Insert 等邻域不需要重写搜索更新逻辑。自定义初始化时，报表使用 `Initial+LS/SA`，避免误标为 SPT。

公共默认参数集中在 `DEFAULT_CONFIG`，实验使用副本覆盖指定参数。函数式接口已经足够表达这些组合；Solver Class 可以把参数保存在对象中，通过 `solve()` 调用，但当前不需要额外继承体系。

## 目标、合法性与统计口径

固定最小化总延期：

\[
f(S)=\sum_j\max(C_j-d_j,0).
\]

Objective 用于候选比较，Makespan 和平均完工时间用于描述结果。核心搜索函数接收目标函数，因此替换目标不需改写搜索算法；当前 Benchmark 的目标名称、复核与改善计算仍针对总延期，切换实验目标时也必须同步修改这些部分。

每次运行使用任务列表副本与不可变 Job。校验不仅检查任务数量，还检查标识、属性、重复、遗漏、释放时间与同机重叠。最终分数重新由返回的排程计算，避免错误解因漏任务获得虚假的改善。

评价次数包含每个起点及所有候选，不包含结果展示的复核。耗时包含初始化与搜索，不包含报表。LS 更新次数与 SA 候选次数含义不同；本实验没有强制统一时间或评价预算。

验证通过实验与临时检查完成，不新增 `tests/`。单项检查关注规则、Move 和指标；集成检查关注 `Jobs → SPT → LS → Schedule → Evaluate` 的连接，同时检查输入不变、最终目标不劣于初始目标、固定随机种子可复现。

## 完整 Demo

默认生成 20 个任务，加工时间取 `[1,20]`、交期取 `[20,150]`、释放时间均为零。实例种子为 100，算法种子为 0。LS 使用 Swap + Best、最多 1000 次更新；Multi-start 使用 20 个随机起点；SA 初温 100、降温率 0.95、最低温度 `1e-6`、候选上限 1000。

六种方法各自从同一实例运行，**不是把 LS 的结果依次传给 Multi-start 和 SA**。单次实际运行如下，时间仅反映运行环境。

| 方法 | 总延期 | 相对 SPT 改善率 | 评价次数 | 耗时 / s |
| --- | ---: | ---: | ---: | ---: |
| FCFS | 638 | -98.75% | 1 | 0.0006 |
| SPT | 321 | 0.00% | 1 | 0.0005 |
| EDD | 186 | 42.06% | 1 | 0.0004 |
| SPT + LS | 127 | 60.44% | 2471 | 0.5884 |
| Multi-start | 127 | 60.44% | 55880 | 12.7668 |
| SPT + SA | 155 | 51.71% | 361 | 0.0867 |

SPT + LS 与 Multi-start 并列最好，增加起点没有在该次运行中继续改善目标。展示按算法列表顺序选取的 SPT + LS 排程：

```text
J7 → J16 → J17 → J5 → J2 → J20 → J19 → J10 → J11 → J13
   → J9 → J8 → J3 → J18 → J12 → J1 → J6 → J14 → J4 → J15
```

总延期为 127，Makespan 为 177，平均完工时间为 86.75。完整任务起止时间和延期在终端表格及 `best_schedule.csv` 中展示。这里的“最好”仅指参与比较的有效结果，不是全局最优证明；随机稳定性另由第六天的多种子实验观察。

仓库根目录运行：

```powershell
python "Month_01_调度基础与算法/Week_3/experiments/day7_integration.py"
```

可通过 `--jobs`、`--instance-seed`、`--algorithm-seed`、`--restarts` 调整实验。`results/day7_时间戳/` 保存参数、实际实例、Benchmark 与最好排程，详细搜索轨迹不默认打印。

## 项目边界与后续方向

当前搜索面向单机、不可抢占的任务排列。解码器能按释放时间等待，但这不等于动态到达的在线派工；尚未表达工序优先关系、换型时间、机器故障与多机器分配。完整解码评价也没有使用增量更新。

从规则到搜索再到评测，统一的是问题表示、组件接口和结果口径。后续可在此基础上研究等预算比较、独立实例上的稳定性与增量评价，扩展复杂调度问题前需要重新明确解的表示和约束。


## 实验入口

在本周目录运行：

```powershell
python -m experiments.day7_integration
```
