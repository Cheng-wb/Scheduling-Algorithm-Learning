# Week 3：邻域、局部搜索与随机搜索（全程第 03 周）

[月度大纲](../README.md) · [六个月总览](../../LEARNING_PLAN.md)

## 学习内容

Solution 与 Schedule；Swap/Insert；Best/First Improvement；局部最优；Multi-start；SA 的 current/best、温度和接受。

## 项目任务

复用 search_lab，整理初始化、目标、邻域和停止接口；保留随机种子、搜索历史及实际评价计数。

代码归属：scheduling_basics、search_lab。项目目录见 [projects](../../projects/README.md)。

## 实验任务

同一总延期目标比较 SPT/EDD 起点、Swap/Insert、LS/Multi-start/SA；检查多种子复现和输入不变。

每项实验保存问题假设、实例或生成种子、算法参数、预算、合法性结果、目标值与运行成本。笔记记录概念、公式、结果及限制，不记录学习时长或日程口号。

## 验收标准

能手算一轮搜索；严格下降 LS 停止正确；SA 返回历史最好解，固定配置与种子可复现。

## 材料衔接

已有邻域、LS、Multi-start、SA 与实验；按四个主题复盘，完成验收后直接进入下一周。

## 主题笔记

- [局部搜索 Local Search](notes/local_search.md)
- [局部最优、随机初始解与 Multi-start](notes/multi_start.md)
- [邻域、Move 与邻域生成](notes/neighborhoods.md)
- [Simulated Annealing（模拟退火）](notes/simulated_annealing.md)
