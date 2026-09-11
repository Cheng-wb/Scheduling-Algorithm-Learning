# Week 3：邻域、局部搜索与随机搜索（全程第 03 周）

[月度大纲](../README.md) · [六个月总览](../../LEARNING_PLAN.md)

## 学习内容

Solution 与 Schedule；Swap/Insert；Best/First Improvement；局部最优；Multi-start；SA 的 current/best、温度和接受。

## 每日计划

| 日期 | 主题 | 学习与实践任务 | 交付 / 完成标准 |
| --- | --- | --- | --- |
| Day 1 | 解表示与目标解耦 | 区分任务排列与时间排程；复核 SPT/EDD 初始化和总延期评价 | 初始化、解码、目标接口清晰 |
| Day 2 | 邻域与 Move | 对同一排列生成 Swap/Insert，核对覆盖、重复与原输入不变 | 手算邻居与生成结果一致 |
| Day 3 | Best/First Improvement | 手算一轮局部搜索，运行两种改进策略并比较路径 | 严格改善与停止条件正确 |
| Day 4 | 随机重启 | 用局部随机数生成器产生多个起点，区分单次结果与历史最好值 | 重启历史和累计评价次数完整 |
| Day 5 | 模拟退火 | 复核 delta、差解接受、降温与 current/best，运行固定种子例子 | 返回历史最好解，可复现接受轨迹 |
| Day 6 | 搜索方法比较 | 同实例比较起点、邻域及 LS/Multi-start/SA，报告实际预算 | 对照表注明预算差异与种子 |
| Day 7 | 搜索模块整合 | 检查计数、历史、输入保护和排程合法性，整理已有主题笔记 | 已有算法可独立调用且实验跑通 |

按上述顺序推进；已有实现用于复核和补缺，不重复编写。每日交付记录在相应实验或主题笔记中，本计划不预建每日笔记文件。

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
