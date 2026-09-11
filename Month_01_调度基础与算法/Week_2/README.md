# Week 2：MILP 入门与单机/并行机模型（全程第 02 周）

[月度大纲](../README.md) · [六个月总览](../../LEARNING_PLAN.md)

## 学习内容

参数、变量、线性约束；分配与排序变量；Big-M 来源；可行解、下界、最优值、求解状态。

## 每日计划

| 日期 | 主题 | 学习与实践任务 | 交付 / 完成标准 |
| --- | --- | --- | --- |
| Day 1 | 参数、变量与约束 | 从并行机问题区分输入参数、分配变量、机器负载与目标 | 数学模型与业务语义逐条对应 |
| Day 2 | 并行机分配 MILP | 复核每任务唯一分配与负载上界约束，运行小实例 | 模型、可行排程和 Cmax 一致 |
| Day 3 | 单机排序与 Big-M | 写排序变量和非重叠约束，从时间上界推导有效 M | 说明每种排序取值对应的约束 |
| Day 4 | 交期与延期目标 | 建立总延期和加权延期，保留不同目标的独立求解函数 | 两种目标下排程与指标对照 |
| Day 5 | LP 松弛与上下界 | 放松分配变量，比较松弛目标、整数可行解与最优值 | 一例可解释的松弛界与整数差距 |
| Day 6 | 求解状态与 M 的影响 | 比较合理 M 与过松 M；记录限时状态、可行解及 best bound | 超时有解与无解分别表达，不伪称最优 |
| Day 7 | 枚举核对与模型复盘 | 对 4～7 任务枚举合法方案，交叉核对 MILP 并整理假设 | 小实例最优值一致，模型限制明确 |

按上述顺序推进；已有实现用于复核和补缺，不重复编写。每日交付记录在相应实验或主题笔记中，笔记已按每日主题整理到 `note/`。

## 项目任务

整理并行机分配、单机排序和加权延期模型；补一例 LP 松弛；分别保留不同目标的求解函数。

代码位于本周目录，模型和算法按功能命名；实验按 Day 编号组织。

## 实验任务

4～7 任务用枚举交叉核对 MILP；比较合理 M 与过松 M；记录时间限制下的 incumbent、bound 与状态。

每项实验保存问题假设、实例或生成种子、算法参数、预算、合法性结果、目标值与运行成本。笔记记录概念、公式、结果及限制，不记录学习时长或日程口号。

## 验收标准

每条约束对应业务语义；能推出有效 M；区分 FEASIBLE 与 OPTIMAL，不能把超时等同无解。

## 材料衔接

单机/并行机 MILP 与 Big-M 代码按天整理；Day 5～7 补充 LP 松弛、M 与限时状态、小实例枚举核对。原精确求解函数只返回最优排程，分析接口另行保留限时状态与界，二者不混用。


## 本周目录与运行

```text
Week_2/
├── README.md
├── note/          # Day1.md～Day7.md
├── experiments/   # 每日实验和公共输出工具
├── scheduling/    # 模型、指标、规则与 MILP
└── results/       # 需要保存的运行产物
```

| 日期 | 笔记 | 实验 |
| --- | --- | --- |
| Day 1 | [Day1.md](note/Day1.md) | [day1_formulation.py](experiments/day1_formulation.py) |
| Day 2 | [Day2.md](note/Day2.md) | [day2_parallel_milp.py](experiments/day2_parallel_milp.py) |
| Day 3 | [Day3.md](note/Day3.md) | [day3_big_m.py](experiments/day3_big_m.py) |
| Day 4 | [Day4.md](note/Day4.md) | [day4_tardiness.py](experiments/day4_tardiness.py) |
| Day 5 | [Day5.md](note/Day5.md) | [day5_lp_relaxation.py](experiments/day5_lp_relaxation.py) |
| Day 6 | [Day6.md](note/Day6.md) | [day6_solver_status.py](experiments/day6_solver_status.py) |
| Day 7 | [Day7.md](note/Day7.md) | [day7_enumeration.py](experiments/day7_enumeration.py) |

在本周目录运行 `python -m experiments.day1_formulation`，或在仓库根目录运行 `python run.py week2 day1_formulation`。支持 IDE 直接运行实验文件。

MILP 实验依赖 `requirements.txt`，在本周目录执行 `python -m pip install -r requirements.txt`。
