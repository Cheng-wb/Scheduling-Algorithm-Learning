# 第 11 月：Hybrid OR + AI + LLM / Agent

对齐依据：[全年计划](../LEARNING_PLAN.md)「M11」月度周次。周主题与顺序以全年计划为准，下面的任务与验收是执行细化；周号仅使用本月 Week 1–4。

本月目标：形成差异化路线。核心思想是「不追求 AI 替代 Solver，而是让 AI 帮 Solver 做更好的决策」。

## 周计划

| 周次 | 全年周主题 | 学习内容 | 编码与实验任务 | 验收 |
|---|---|---|---|---|
| Week 1 | Learned Warm Start | Learned Warm Start | 训练模型预测 operation priority / machine assignment / initial permutation，交给 CP-SAT / ALNS | 比较 random / heuristic / learned start 的初始目标、首个可行时间、最终目标、达到目标 gap 时间 |
| Week 2 | RL-guided ALNS | RL-guided ALNS | RL state=当前目标/改进历史/算子成功率/实例特征/温度/停滞；action=选 destroy/repair/邻域大小 | 形成 RL Controller → Operator Selection → Hybrid Solver |
| Week 3 | Learning to Repair / Solver Control | Learning to Repair / Solver Control | 研究 learned repair / learned candidate ranking / learned restart / solver selection | Problem Features → Meta Model → 选 CP-SAT / ALNS / RL |
| Week 4 | LLM / Agent for Optimization | LLM / Agent for Optimization（LLM 不当 optimizer） | 三选一：NL→约束草稿 / Solver 诊断 Agent / 实验 Agent | LLM 输出始终经过 deterministic validator |

## 每周 7 天执行清单

| 天 | 固定任务 |
|---|---|
| Day 1 | 阅读本周理论，写出混合框架或 Agent 流程草图 |
| Day 2 | 完成最小可运行脚本 |
| Day 3 | 加入随机种子、validator 与一次完整运行 |
| Day 4 | 扩展到多实例，保存超参与配置 |
| Day 5 | 与纯 OR / 纯 AI 基线对拍，定位瓶颈 |
| Day 6 | 绘制提升 / 耗时曲线，分析失败案例 |
| Day 7 | 写一页周报：结论、证据、问题、下周改进 |

## 月末交付

**Project 11：Hybrid OR + AI Solver**——learned warm start + RL-guided ALNS（或 learned neighborhood）+ deterministic validator + hybrid solver benchmark。这是全年最值得写论文 / 技术博客的部分。
