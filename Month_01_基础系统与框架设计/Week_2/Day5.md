# Day 5：随机实例与输入质量

> 目标：可复现地产生不同规模的输入，理解生成分布的局限。建议 2.5 小时。

## 1. 生成器参数

[generator.py](../../projects/01_scheduling_core/scheduling_io/generator.py) 使用局部 `Random(seed)`，不修改 Python 全局 RNG。

| 参数 | 含义 | 默认值 |
|---|---|---:|
| seed | 实例种子，与算法种子分开 | 必填 |
| jobs | 作业数 | 12 |
| machines | 同质机器数 | 3 |
| operations_per_job | 每个作业链长度 | 1 |
| release_max | 释放时刻均匀整数范围上界 | 10 |
| due_factor | 交期相对自身总工时的系数 | 1.5 |

加工时间从 1…20 抽取，权重从 1…5 抽取。`due=r+int(sum(p)*due_factor)`。因此交期主要相对作业自身工时定义，繁忙单机上容易大量迟交，不能认为它代表所有工厂订单。

## 2. 正例与负例分工

生成器负责合法正例，所有工序默认可上全部机器。资格受限的案例另用手工测试覆盖。输入验证器处理负工时、重复 ID、引用不存在、空工序链、非有限权重等；排程验证器处理结果错误。两个验证器不要混为一谈。

已有 Day 3 的 JSON 读取增加了 CSV 三表入口：machines.csv、jobs.csv、operations.csv；列表字段用 `|` 分隔，交期空字符串转换为 None。JSON 浮点工时不再被 int 静默截断，而由校验器拒绝。

## 3. 实验

项目目录执行：

```powershell
python -m pytest tests/test_month1.py -k 'roundtrip or invalid_inputs or corruption' -v
```

JSON 往返测试确认保存后再读得到相同 Instance；CSV 测试确认空交期和工时解析。Week 4 还会将实际生成输入落盘并计算 SHA-256，而不是只保存随机种子。

练习：比较 jobs=6 和 jobs=24 的总工时，注意“大实例的目标更大”不等于“算法更差”。自测：生成器种子与 SA 种子相同是否表示同一个随机过程？答案：不，它们是独立 RNG，各自描述数据生成和搜索动作。
