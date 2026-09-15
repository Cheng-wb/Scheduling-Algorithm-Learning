# Day 6：搜索对比与收敛曲线

> 目标：用真实运行记录判断方法差异。建议 3 小时。

## 1. 最小对比实验

仓库根目录执行：

```powershell
python projects/01_scheduling_core/examples/m1w3d6_search.py
```

实例固定 seed=20、12 个单机作业，目标 total_tardiness；搜索 seed=0、预算 150。输出包括 lpt、random、first、best、multistart、sa 的目标值、实际评价数、状态和时间。

LPT 在这里仅作为共享初始基线，不是单机迟交问题的理论最佳规则。SPT/EDD/WSPT 的规则对照仍在 Week 1 脚本中；不能把没有纳入本批次的规则写成被所有方法击败。

## 2. 扩展为逐次记录

完整基准在 Week 4 执行，落盘 `runs/*.trace.csv`，列出 evaluation、proposed、current、best、accepted、temperature。算法返回最好值必须等于轨迹最末 best，并且对应 Schedule 的重新计算目标。

收敛图以评价数为横轴。不同算法可能提前停止，因此曲线长短不同；不能把提前停止误画成完成了全部预算。运行时间比较另看 elapsed_seconds，包含该次搜索的解码、验证与邻居开销，不含写文件和绘图。

## 3. 差异分析框架

先看可行性与失败，再看质量，最后看成本。对每个实例比较初始值、最好值、达到改善的评价位置、是否平台。若 First 三个种子完全一样，原因可能只是它没有用 RNG；若 SA 波动较大，需多种子和分布描述。

本月真实数值与限制集中在 [月度报告](../MONTH1_REPORT.md)，避免把示意数字写成测量值。

练习：选一个 SA 轨迹，找到一处 accepted=True 且 proposed>之前 current 的行，确认历史 best 没有回升。验收：能从原始记录解释图上一个具体拐点。
