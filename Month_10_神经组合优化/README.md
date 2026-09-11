# 第 10 月：Neural Combinatorial Optimization

本月目标：进入 AI4CO / Neural Solver，重点是建立方法论而不是论文复现数量。

## 周计划

| 周次 | 学习内容 | 编码与实验任务 | 验收 |
|---|---|---|---|
| Week 1 | Pointer Network 思想、autoregressive construction、REINFORCE、rollout baseline、Attention Model | 从 TSP 学（资料最成熟） | 理解 Encoder/Decoder/Sampling/Rollout/Policy Gradient |
| Week 2 | multi-start、symmetry exploitation、POMO 思想 | 实现或复现 TSP/CVRP neural solver | 目标不是追 SOTA，是吃透训练流程 |
| Week 3 | learned local search、move selection、improvement policy、destroy/repair selection | 用模型预测 ALNS operator / neighborhood | 完成一个 neural improvement 实验 |
| Week 4 | Graph Encoder + Attention Decoder | 迁移回 JSP/FJSP：dispatch / machine selection / initial solution 三选一 | 比较手工初始化 vs 学习初始化 vs CP-SAT vs ALNS |

## 每周 7 天执行清单

| 天 | 固定任务 |
|---|---|
| Day 1 | 阅读本周理论，写出网络或采样流程草图 |
| Day 2 | 完成最小可运行训练脚本 |
| Day 3 | 加入随机种子、baseline 与一次完整训练 |
| Day 4 | 扩展到多实例，保存超参与 checkpoint |
| Day 5 | 与经典 solver 对拍，定位训练/评估问题 |
| Day 6 | 绘制 objective / gap 曲线，分析失败案例 |
| Day 7 | 写一页周报：结论、证据、问题、下周改进 |

## 月末交付

**Project 10：Neural CO Lab**——Pointer Network / POMO / Neural Improvement 至少其一，附与 CP-SAT / ALNS 的公平对比。
