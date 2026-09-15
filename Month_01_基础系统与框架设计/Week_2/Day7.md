# Day 7：表示、验证和测试边界复盘

> 目标：为所有搜索方法固定共同的接口。建议 1.5 小时复盘＋2 小时数学。

## 1. 固定接口

`Instance → Candidate → decode → Schedule → validate_schedule → objective`

输入与候选都不可变。邻域返回新 Candidate。每次完整评价必须走同一条链路；禁止某个算法略过验证或使用另一套目标公式，除非实验明确将其作为独立性能设置。

## 2. 本周证据

| 要求 | 证据 |
|---|---|
| 三类解表示/解码轨迹 | test_three_decoder_traces |
| swap/insert/指派 | test_moves_and_boundaries |
| 至少五类非法排程 | test_independent_validator_corruption，九类 |
| 可复现输入、CSV/JSON | test_roundtrip_and_csv |
| 至少五个小例枚举 | test_five_independent_enumerations，五个种子 |

周报：[week2.md](../week2.md)。测试代码位于 [test_month1.py](../../../projects/01_scheduling_core/tests/test_month1.py)。

## 3. 已知局限

优先级表示有冗余；追加解码不会自动填充已有空隙；生成器默认全机器资格；Oracle 只能证明单工序极小实例。它们都是明确的模型或实现边界，不能靠更多相同分布测试消除。

## 4. 数学补充与自测

练习理解有向无环图：当前作业链 A→B→C 不可能出现环，因为顺序来自不可重复的 operation_ids。若未来把 precedence 改成任意边集合，就必须新增环检测；当前结构合法不意味着未来任意图都合法。

问：解码产生可行解后为何仍要验证？答：独立模块能够发现实现错误，并验证外部导入排程。问：所有测试通过是否说明算法最优？答：不，正确性和解质量是两种问题。

下周将统一 SearchConfig、SearchResult 和完整评价计数；把“运行几轮”转换为可比较的计算预算。
