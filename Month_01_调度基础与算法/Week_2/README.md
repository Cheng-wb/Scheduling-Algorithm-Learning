# Week 2：MILP 入门与单机/并行机模型（全程第 02 周）

[月度大纲](../README.md) · [六个月总览](../../LEARNING_PLAN.md)

## 学习内容

参数、变量、线性约束；分配与排序变量；Big-M 来源；可行解、下界、最优值、求解状态。

## 项目任务

整理并行机分配、单机排序和加权延期模型；补一例 LP 松弛；分别保留不同目标的求解函数。

代码归属：scheduling_basics、search_lab。项目目录见 [projects](../../projects/README.md)。

## 实验任务

4～7 任务用枚举交叉核对 MILP；比较合理 M 与过松 M；记录时间限制下的 incumbent、bound 与状态。

每项实验保存问题假设、实例或生成种子、算法参数、预算、合法性结果、目标值与运行成本。笔记记录概念、公式、结果及限制，不记录学习时长或日程口号。

## 验收标准

每条约束对应业务语义；能推出有效 M；区分 FEASIBLE 与 OPTIMAL，不能把超时等同无解。

## 材料衔接

已有单机/并行机 MILP 与 Big-M 代码；仍需补 LP 松弛、M 的紧度实验和限时可行解/下界的完整结果表达。

## 主题笔记

- [MILP 基础与相同并行机调度](notes/parallel_milp.md)
- [任务排序、非重叠约束与 Big-M](notes/single_machine_milp.md)
- [交期、延期与加权延期](notes/tardiness.md)
