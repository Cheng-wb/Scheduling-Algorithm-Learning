# Day 3：swap、insert 与机器指派邻域

> 目标：明确每一种移动改变什么，以及边界如何处理。建议 3 小时。

## 1. 邻域不是算法

邻域 N(x) 是当前候选解 x 附近允许考察的一组解。First、Best、SA 都可使用相同移动，却用不同方式选下一步。

| 操作 | ABCD 的示例 | 保持不变 |
|---|---|---|
| swap(0,2) | CBAD | 机器指派 |
| insert(0,2) | BCAD | 机器指派 |
| reassign(op_index,machine) | order 不变 | 其余工序机器 |

insert 的 j 指移除后插入的最终索引，不是“原索引 j 前面”。重新指派的 index 指 instance.operations 中的位置。

## 2. 边界与可行性

实现位于 [solution.py](../../../projects/01_scheduling_core/scheduling_core/solution.py)。swap/insert 拒绝负数和越界；i=j 返回等值候选解。reassign 只允许 eligible 集合中的机器。交换优先级可能把后继放在前面，但 decoder 会等待前驱，不等于 precedence 违规。

完整邻域按固定顺序扫描 swap、insert、机器替换，用集合去重并排除自身。swap 有 n(n−1)/2 个位置对，insert 原始有 n(n−1) 个有向移动；相邻交换会与 insert 重合，不能把两者简单相加当作去重后大小。

## 3. 实验

项目目录执行 `python -m pytest tests/test_month1.py -k moves -v`。测试验证交换两次恢复、insert 方向、非法资格、边界和每个邻居的独立可行性。

手算：ABC 的去重排列邻居是 BAC、CBA、ACB、BCA、CAB，恰好覆盖其余五种排列。若 A 只能 M0，B/C 各有两台资格，则还多两个单独改变指派的候选解。

## 4. 搜索意义与练习

只改变顺序可能无法缓解机器负载不均；只改变机器可能无法改善交期顺序。邻域的组合决定搜索能走到哪里。当前完整邻域的存储与评估成本随 n² 增长，SA 使用随机移动，不先生成整个邻域。

练习：禁用 reassign 再对并行机实例运行搜索，记录目标变化。此为可选扩展，月度已运行的敏感性实验聚焦温度和冷却率，不能把未执行的邻域消融写成结论。
