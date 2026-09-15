# Week 3 周报：局部搜索与模拟退火

## 本周内容

统一 SearchConfig/SearchResult，Random、First、Best、Multi-start、SA，以及逐评价轨迹。LPT 初始基线作为额外方法保留。

笔记：[Day1](Week_3/Day1.md) · [Day2](Week_3/Day2.md) · [Day3](Week_3/Day3.md) · [Day4](Week_3/Day4.md) · [Day5](Week_3/Day5.md) · [Day6](Week_3/Day6.md) · [Day7](Week_3/Day7.md)。

## 验证与结论

预算 1/2/60、空/单元素输入、局部最优停止、SA 接受坏解和同 seed 轨迹重现均有测试。所有返回结果重新通过可行性检查，best 轨迹单调不增。

统一预算计算初始解、拒绝候选、no-op、重启评价。First/Best 可提前停机，Random/SA/Multi-start 消耗全部上限。公平性是同一个预算上限和相同评价过程，不是伪造相同实际评价数。

## 实验观察

主实验 single_12 中，初始总迟交 719；SA 三种子平均 261.67，Random 313，Multi-start 373，Best 529，First 575。routes_12 则 First/Best 平均 41，低于 SA 的 42。不存在本批次所有实例都领先的方法。

上述值来自月末完整批次，具体原始记录与参数见 [月度报告](MONTH1_REPORT.md)。复跑：`python projects/01_scheduling_core/examples/m1w3d6_search.py`（仓库根目录）。

## 局限与练习

完整邻域按顺序先扫描排列再扫描指派，小预算可能没走到选机邻域；报告排名受这个实现选择影响。个人练习：解释为何换扫描顺序可能改变 First 的最终值，但不改变每次候选的可行性。
