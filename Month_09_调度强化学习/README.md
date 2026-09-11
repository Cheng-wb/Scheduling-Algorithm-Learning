# 第 9 月：RL for Scheduling

本月目标：不是「让 PPO 跑起来」，而是回答 RL 在什么时候比规则或 OR 更有价值。

## 周计划

| 周次 | 学习内容 | 编码与实验任务 | 验收 |
|---|---|---|---|
| Week 1 | Dynamic JSP/FJSP 的 dispatching；基线 FIFO/SPT/EDD/ATC/critical ratio | 实现 DQN 或 PPO dispatcher | 比较训练稳定性与 KPI |
| Week 2 | invalid action mask、变长动作空间、reward/observation 归一化、entropy 控制 | 做 reward ablation；研究 reward hacking、退化策略、policy collapse | 写出 reward ablation 报告 |
| Week 3 | JSP Graph → GNN Encoder → Operation Embedding → Policy Head | 比较 MLP-PPO 与 GNN-PPO | 报告训练效率、泛化、决策延迟 |
| Week 4 | 泛化与鲁棒性 | 训练 20×5，测试 30×5 / 50×8 / 不同工时分布 / 不同故障率 / 不同交期紧张度 | 必须做 OOD evaluation |

## 每周 7 天执行清单

| 天 | 固定任务 |
|---|---|
| Day 1 | 阅读本周理论，写出 state/action/reward 或网络草图 |
| Day 2 | 完成最小可运行训练脚本 |
| Day 3 | 加入随机种子、归一化与一次完整训练 |
| Day 4 | 扩展到多实例/多随机种子，保存超参 |
| Day 5 | 与规则基线对拍，定位训练不稳定 |
| Day 6 | 绘制 KPI / 收敛曲线，分析失败案例 |
| Day 7 | 写一页周报：结论、证据、问题、下周改进 |

## 月末交付

**Project 9：RL Scheduler**——报告中必须回答：RL 赢了哪些 baseline、输了哪些、为什么、训练成本、inference 延迟、泛化能力。
