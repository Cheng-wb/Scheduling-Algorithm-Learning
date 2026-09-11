# 第 7 月：Machine Learning for OR

对齐依据：[全年计划](../LEARNING_PLAN.md)「M7」月度周次。周主题与顺序以全年计划为准，下面的任务与验收是执行细化；周号仅使用本月 Week 1–4。

本月目标：把深度学习底层能力补齐，为后续 RL / Neural CO 打基础。

## 周计划

| 周次 | 全年周主题 | 学习内容 | 编码与实验任务 | 验收 |
|---|---|---|---|---|
| Week 1 | PyTorch 基础 | tensor、autograd、nn.Module、optimizer、loss、DataLoader、checkpoint、GPU、混合精度 | 实现 MLP 做 regression / classification | 自己写训练循环，不依赖高级 Trainer |
| Week 2 | Embedding / Attention / Transformer | embedding、query/key/value、self-attention、positional encoding、encoder/decoder、masking | 实现 sequence encoder 与 attention model | 说清组合优化里为何常用 Attention |
| Week 3 | GNN（GCN/GAT） | 图表示、message passing、GCN、GAT、GraphSAGE | 把 JSP 表示为 Operation Nodes + Precedence Edges + Machine Conflict Edges | 做 schedule-quality / dispatch-score 预测小项目 |
| Week 4 | Learning-to-Rank / Imitation Learning | 用 CP-SAT / ALNS 生成 expert 数据；Learning-to-Rank、Imitation Learning | 训练模型预测 dispatch priority / machine selection / move score | 比较手工启发式 vs 有监督学习启发式 |

## 每周 7 天执行清单

| 天 | 固定任务 |
|---|---|
| Day 1 | 阅读本周理论，写出网络结构或数据流草图 |
| Day 2 | 完成最小可运行训练脚本，准备一个小例子 |
| Day 3 | 加入数据切分、随机种子和 checkpoint，记录一次训练 |
| Day 4 | 扩展到完整数据，保存超参与版本 |
| Day 5 | 与基线对拍，检查过拟合与数据泄漏 |
| Day 6 | 绘制 loss / 指标曲线，分析失败案例 |
| Day 7 | 写一页周报：结论、证据、问题、下周改进 |

## 月末交付

**Project 7：Learning for OR Lab**——PyTorch pipeline + GNN 模型 + expert 数据生成 + train/valid/test 分离 + 实验记录。
