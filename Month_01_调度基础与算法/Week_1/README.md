# Week 1：调度定义、指标与规则基线（全程第 01 周）

[月度大纲](../README.md) · [六个月总览](../../LEARNING_PLAN.md)

## 学习内容

三字段表示法；单机与同质并行机；释放时间、交期、权重；Cmax、总完工、延期；SPT/EDD/WSPT/LPT 的适用条件。

## 每日计划

| 日期 | 主题 | 学习与实践任务 | 交付 / 完成标准 |
| --- | --- | --- | --- |
| Day 1 | 问题定义与调度表示 | 整理 Job、Machine、释放时间、交期和权重；用三字段描述单机与同质并行机问题 | 一页问题假设与符号表 |
| Day 2 | 时间与评价指标 | 手算 4～6 个任务的开始、完工、lateness、tardiness 与 Cmax，实现并核对指标函数 | 手算与程序逐项一致 |
| Day 3 | 单机派工规则 | 在同一实例运行 FCFS、SPT、EDD、WSPT；说明排序依据与目标适用条件 | 规则、假设、适用目标对照表 |
| Day 4 | 释放时间与排程解码 | 比较固定排列等待与动态选择已释放任务；复核顺序、时间和合法性 | 一个能区分两种调度方式的实例 |
| Day 5 | 并行机列表调度 | 运行 Greedy/LPT，用列表扫描选最早空闲机器；核对机器负载 | 每项任务恰分配一次，排程无重叠 |
| Day 6 | 下界与规则比较 | 计算最大任务时长、平均负载下界；比较 Greedy/LPT 并分析非最优反例 | 同实例目标值、下界与差距表 |
| Day 7 | 规则基线整合 | 组合模型、校验、指标和实验，归纳单机与并行机结论 | 可运行基线及适用范围总结 |

## 项目任务

复用任务模型、解码器、指标、规则与并行机列表调度；整理一页“问题假设—目标—规则适用性”对照。

代码位于本周目录，模型和算法按功能命名；实验按 Day 编号组织。

## 实验任务

手算 4～6 个任务；同一实例比较 FCFS/SPT/EDD/WSPT；并行机比较 Greedy/LPT，核对负载下界。

每项实验保存问题假设、实例或生成种子、算法参数、预算、合法性结果、目标值与运行成本。笔记记录概念、公式、结果及限制，不记录学习时长或日程口号。

## 验收标准

能区分 lateness 与 tardiness；逐任务时间与指标一致；不把 SPT 的总完工最优性套到总延期。

## 本周目录与运行

```text
Week_1/
├── README.md
├── note/          # Day1.md～Day7.md
├── experiments/   # 每日实验和公共输出工具
├── scheduling/    # 模型、指标、规则
└── results/       # 需要保存的运行产物
```

| 日期 | 笔记 | 实验 |
| --- | --- | --- |
| Day 1 | [Day1.md](note/Day1.md) | [day1_models.py](experiments/day1_models.py) |
| Day 2 | [Day2.md](note/Day2.md) | [day2_metrics.py](experiments/day2_metrics.py) |
| Day 3 | [Day3.md](note/Day3.md) | [day3_dispatching.py](experiments/day3_dispatching.py) |
| Day 4 | [Day4.md](note/Day4.md) | [day4_release_times.py](experiments/day4_release_times.py) |
| Day 5 | [Day5.md](note/Day5.md) | [day5_parallel_rules.py](experiments/day5_parallel_rules.py) |
| Day 6 | [Day6.md](note/Day6.md) | [day6_bounds.py](experiments/day6_bounds.py) |
| Day 7 | [Day7.md](note/Day7.md) | [day7_baselines.py](experiments/day7_baselines.py) |

在本周目录运行 `python -m experiments.day1_models`，或在仓库根目录运行 `python run.py week1 day1_models`。支持 IDE 直接运行实验文件。
