# Day 7：规则基线整合

[周计划](../README.md)



## 分层调用

`Job → Rule → Schedule → validate_schedule → evaluate`。

`scheduling/heuristics` 决定选择顺序，`scheduler.py` 展开时间，`metrics.py` 计算指标。实验组织数据与表格，不重复实现算法。

单机 SPT、EDD、WSPT 的经典最优性分别对应总完工时间、最大 lateness、加权总完工时间，成立条件是任务同时可用且无换型等附加约束。并行机 LPT 是启发式，不能把它的结果自动当成最优值。

比较必须固定输入、机器数和目标。独立校验任务覆盖、释放时间和机器互斥后，再解释质量与成本。

## 实验入口

在本周目录运行：

```powershell
python -m experiments.day7_baselines
```
