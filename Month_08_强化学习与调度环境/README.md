# 第 8 月：强化学习基础与 Scheduling Environment

本月目标：完整建立 RL 理论和工程基础，并把 Month 6 的仿真器封装成可训练的调度环境。

## 周计划

| 周次 | 学习内容 | 编码与实验任务 | 验收 |
|---|---|---|---|
| Week 1 | MDP、Bellman 方程、policy/value/Q-value、DP、Monte Carlo、TD、Q-learning | 实现 GridWorld 与 tabular Q-learning | 禁止直接调用 RL library 完成全部逻辑 |
| Week 2 | replay buffer、target network、epsilon greedy、bootstrapping、不稳定性 | 实现 DQN（Double DQN 选做） | 解决一个简单 resource-allocation environment |
| Week 3 | REINFORCE、advantage、baseline、actor-critic、entropy、GAE、PPO | 实现 REINFORCE 与 PPO | 真正理解 PPO clip objective |
| Week 4 | 基于 Month 6 Simulator 封装 reset/step/observation/action/reward/done/info/action_mask | state=机器可用/队列/工时/剩余工序/交期/优先级/WIP；action=选工序/选机器/dispatch | 可复现、可 vectorize、带 action masking、随机实例生成器 |

## 每周 7 天执行清单

| 天 | 固定任务 |
|---|---|
| Day 1 | 阅读本周理论，写出 MDP 或网络结构草图 |
| Day 2 | 完成最小可运行训练/环境脚本 |
| Day 3 | 加入随机种子、日志与一次完整运行 |
| Day 4 | 扩展到多实例/多环境，保存超参 |
| Day 5 | 与经典规则基线对拍，定位训练问题 |
| Day 6 | 绘制 reward / 收敛曲线，分析失败案例 |
| Day 7 | 写一页周报：结论、证据、问题、下周改进 |

Week 4 需比较 sparse reward、dense reward、delta objective reward 三种奖励设计。

## 月末交付

**Project 8：Scheduling RL Environment**——可复现、可 vectorize、带 action masking、随机实例生成器、train/test 分布分离。
