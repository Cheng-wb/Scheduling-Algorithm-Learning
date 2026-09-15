# Day 5：模拟退火、温度与接受率

> 目标：实现允许暂时变差的搜索，同时保留历史最好解。建议 3 小时。

## 1. 接受准则

当前目标 f(x)，候选 f(y)，令 Δ=f(y)−f(x)。如果 Δ≤0，接受；否则按 `exp(−Δ/T)` 的概率接受。每次提议后按 `T←cooling×T` 冷却。

当 Δ=5：T=10 时接受概率约 0.607；T=1 时约 0.0067。温度的量纲与目标差值相同，所以同一个 T 在 makespan 和总迟交上含义不同。

## 2. 三条轨迹必须分开

proposed 是候选目标；current 是接受/拒绝后的当前值；best 是历史最小值。current 可以上升，best 必须单调不增。最终返回 best 对应的排程，不能返回最后 current。

示例：当前 20、最好 18，接受候选 23 后 current=23，best 仍是 18。允许变差是搜索策略，不允许丢失历史最好是结果管理。

## 3. 实现选择

[search.py](../../../projects/01_scheduling_core/scheduling_core/search.py) 随机选 swap、insert、reassign 三种移动。允许 i=j 或原机器被再次抽到，此时 no-op 仍计预算；这避免单元素实例陷入“必须抽到不同解”的死循环。

温度必须有限且正，cooling 在 (0,1]。计算时用很小正数保护除零。这里只实现有限预算的几何降温启发式，不声称具有渐近全局最优保证。

## 4. 实验

运行 `python -m pytest tests/test_month1.py -k 'sa_accepts or search_budget' -v`。高温测试确认确实能接受坏解；复现测试核对逐评价轨迹。

接受率可按窗口统计 `accepted_count/proposals`，排除第一个初始化点。no-op 和等值接受也算接受，因此高接受率本身不证明探索有效。Week 4 的轨迹 CSV 包含温度、接受标记和三个目标序列，可逐行分析。

练习：固定实例与 seed，只改变初始温度，比较最终 best 而非最后 current。验收：能够解释“短期变差”和“最终返回质量不下降”如何同时成立。
