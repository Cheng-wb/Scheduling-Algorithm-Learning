# 第 4 月：高级运筹优化与分解方法

本月目标：建立从普通 OR 工程师向更高上限发展的理论基础，掌握网络优化、路由问题与分解方法。

## 周计划

| 周次 | 学习内容 | 编码与实验任务 | 验收 |
|---|---|---|---|
| Week 1 | 最短路、最大流、最小费用流、匹配、指派；network simplex 基本思想 | 实现 assignment、min-cost flow、workforce/resource matching | 识别「看似调度、实则可转网络流」的结构 |
| Week 2 | TSP formulation、子回路、MTZ、CVRP、容量、VRPTW、软/硬时间窗 | 实现最近邻、savings、insertion、2-opt；用 OR-Tools Routing 建 VRPTW | 约束校验通过；与贪心基线对比 |
| Week 3 | Lagrangian Relaxation：难约束、松弛、乘子、次梯度、分解直觉 | 对一个小 scheduling/assignment 模型做 constraint relaxation | 解释「拆问题」为何常比扩大求解时间更重要 |
| Week 4 | Dantzig-Wolfe、Column Generation、Benders；master/subproblem、pricing | 推导小规模 column generation 示例；实现 cutting stock / set partitioning 小例子 | 理解 crew scheduling / VRP 为何适合 column generation |

## 每周 7 天执行清单

| 天 | 固定任务 |
|---|---|
| Day 1 | 阅读本周理论，写出变量、约束或算法流程草图 |
| Day 2 | 完成最小可运行代码，并准备一个手算小例子 |
| Day 3 | 加入边界条件和输入校验，记录一次运行结果 |
| Day 4 | 扩展到 10 个以上实例，保存参数与随机种子 |
| Day 5 | 与基线或枚举结果对拍，定位差异并修复 |
| Day 6 | 绘制指标图，分析质量、速度和失败案例 |
| Day 7 | 写一页周报：结论、证据、问题、下周改进 |

不要求完整实现 Branch-and-Price，但 Week 4 需有可运行的 column generation 示例或 Benders 技术报告。

## 月末交付

**Project 4：Advanced OR Lab**——network optimization + TSP/VRPTW + Lagrangian 示例 + Column Generation demo + Benders demo 或技术报告。
