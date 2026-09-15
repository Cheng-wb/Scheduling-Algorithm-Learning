# Day 1：统一搜索接口与 Random Search

> 目标：先建立可比较的搜索实验，再讨论智能策略。建议 2.5 小时。

## 1. 搜索契约

[search.py](../../projects/01_scheduling_core/scheduling_algorithms/search.py) 定义 `solve(instance, config, initial=None) -> SearchResult`。所有目标都最小化，支持 makespan、total_tardiness、weighted_completion_time。

SearchConfig 保存 algorithm、objective、budget、seed、temperature、cooling、restart_interval。SearchResult 返回历史最好 Candidate、Schedule、objective、evaluations、status、elapsed_seconds、trace。返回的是历史最好解，不一定是最后走到的解。

## 2. 一次评价到底是什么

一次评价包含完整解码、独立可行性验证和目标计算。初始解算 1 次，被拒绝候选也计数；同一个候选再次评价照样计数。预算为 1 时只能返回初始解。这样的上限比“迭代 100 次”更公平，因为 Best 一轮可能检查数百邻居。

默认初始解统一来自 LPT 优先级与贪心指派；所有算法使用相同实例和初始解。LPT 基线只用 1 次评价，不人为填满预算。

## 3. Random Search

每次随机打乱工序优先级，独立随机选择各工序合格机器，解码并比较目标；只在严格改善时更新当前最好解。局部 RNG 由算法种子初始化。抽样在编码空间进行，表示冗余使它并不等价于均匀抽样所有不同时间表。

例：初始值 30，候选依次 35、28、31，则 proposed 为 35、28、31，best 为 30、28、28。失败候选花掉评价预算，不能从统计中删除。

## 4. 实验

项目目录执行 `python -m examples.m1w3d6_search`，观察 random 相对初始基线是否改善。执行 `python -m pytest tests/test_month1.py -k search_budget -v`，验证预算 1、2、60 的边界和复现。

练习：用同一 config 连跑两次，目标、候选、排程与轨迹应一致，墙钟时间通常不同。验收：能解释为什么“同 seed”不能要求毫秒数完全相同。
