# Day 1：候选解表示与接口约定

> 目标：区分 Instance、Candidate、Schedule；建议 2.5 小时。

## 1. 为什么需要第三种对象

Instance 是不随搜索改变的业务输入。Schedule 是已经落到时间轴的输出。直接移动 Schedule 中的时间戳很容易破坏释放时间和机器容量，因此引入 Candidate：它描述决策，由解码器重新计算时间。

定义见 [solution.py](../../../projects/01_scheduling_core/scheduling_core/solution.py)：

```python
Candidate(order=("A", "B", "C"), assignments=("M0", "M1", "M0"))
```

order 是所有工序 ID 的优先级排列，必须恰好出现一次；assignments 的位置始终对应 `instance.operations`，不是 order 的位置。元组加 frozen dataclass 保证邻域操作不意外修改父解。

## 2. 三个编码例子

设 instance.operations 顺序为 A,B,C，A→B 属于同一作业，C 独立。

| order | assignments | 含义 |
|---|---|---|
| A,B,C | M0,M1,M0 | A 在 M0、B 在 M1、C 在 M0 |
| B,C,A | M0,M1,M0 | 只改变优先级，机器指派不变；B 要等 A 排定 |
| B,C,A | M0,M0,M1 | B 改到 M0、C 改到 M1 |

这里 order 不必是前驱在前的拓扑序；解码器扫描时跳过前驱尚未排定的工序。不同 order 可能得到相同 Schedule，这叫表示冗余。搜索空间计数不能直接等同于不同可行时间表的数量。

## 3. 接口与错误边界

`validate_candidate` 拒绝缺失、重复、未知工序、指派长度不符和不合格机器。`decode` 先检查 Instance，再检查 Candidate。不要在邻域里偷偷修复坏输入；那会令错误难以定位。

实验：项目目录运行 `python -m pytest tests/test_month1.py -k 'decoder or moves' -v`。三类编码都被参数化测试覆盖，下一天逐步解释时间轨迹。

练习：交换 A、C 的优先级时，是否也应交换 assignments？答案：不应；如果交换，就同时改变了机器决策。验收：能写出三例每道工序的机器，并能解释 B 在 order 第一位为何仍不会早于 A 加工。
