# Week 1 周报：调度语言与规则

## 本周内容

本周学习单机规则、并行机 LPT、CSV 解析和甘特数据，并用十例手算核对结果。数据模型继续采用不可变实体与 ID 引用。

笔记：[Day1](Week_1/Day1.md) · [Day2](Week_1/Day2.md) · [Day3](Week_1/Day3.md) · [Day4](Week_1/Day4.md) · [Day5](Week_1/Day5.md) · [Day6](Week_1/Day6.md) · [Day7](Week_1/Day7.md)。

## 验证与结论

十个不同手算实例同时检查规则时间线和四个目标，覆盖单机排序、释放空闲、缺失交期、平局、权重与并行机。Day 4 练习中 WSPT=28 已修正为 43；带释放时间时 Cmax 等于总工时的表述补充无空闲条件。

单机规则增加机器资格拒绝，避免指定一台不合格机器后返回非法排程。规则最优性必须附带模型条件；EDD 对 Lmax 的保证不能迁移成总迟交保证。

## 复跑

项目目录：`python -m pytest tests/test_month1.py -k hand -v`；原有 examples/m1w1d4_rules.py 保持可运行。

## 待个人完成

闭卷推导 SPT/WSPT 的相邻交换证明，重做释放时间反例。
