# Week 1：调度定义、指标与规则基线（全程第 01 周）

[月度大纲](../README.md) · [六个月总览](../../LEARNING_PLAN.md)

## 学习内容

三字段表示法；单机与同质并行机；释放时间、交期、权重；Cmax、总完工、延期；SPT/EDD/WSPT/LPT 的适用条件。

## 项目任务

复用任务模型、解码器、指标、规则与并行机列表调度；整理一页“问题假设—目标—规则适用性”对照。

代码归属：scheduling_basics、search_lab。项目目录见 [projects](../../projects/README.md)。

## 实验任务

手算 4～6 个任务；同一实例比较 FCFS/SPT/EDD/WSPT；并行机比较 Greedy/LPT，核对负载下界。

每项实验保存问题假设、实例或生成种子、算法参数、预算、合法性结果、目标值与运行成本。笔记记录概念、公式、结果及限制，不记录学习时长或日程口号。

## 验收标准

能区分 lateness 与 tardiness；逐任务时间与指标一致；不把 SPT 的总完工最优性套到总延期。

## 材料衔接

已有主体材料：原第二周的概念、规则、并行机实验，以及原第三周的规则初始解。按主题复核，不重新按七天学习。

## 主题笔记

- [调度规则与启发式算法](notes/dispatching_rules.md)
- [调度规则与初始解](notes/initial_solutions.md)
- [并行机调度——Greedy、LPT 与 MILP](notes/parallel_machines.md)
- [调度问题的数学描述与核心概念](notes/scheduling_concepts.md)
