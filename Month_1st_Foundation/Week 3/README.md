# Week 3：初始解与搜索基础

从单机任务排列出发，学习用调度规则构造初始解，再围绕明确的目标函数理解邻域与局部搜索。第一天聚焦规则、任务顺序、排程和评价之间的关系。

## 学习主线

```text
派工规则 → 初始任务顺序 → 排程与目标值 → 邻域修改 → 局部搜索
```

| 学习内容 | 主题 |
| --- | --- |
| [Day 1](note/Day1.md) | FCFS、SPT、LPT、EDD 与初始解评价 |
| [Day 2](note/Day2.md) | Swap、Insert、Reverse、生成器与一层邻域比较 |
| [Day 3](note/Day3.md) | Best / First Improvement、停止条件与搜索路径 |

后续通过不同起点与 Random Restart 比较多个局部最优。

## 项目结构

```text
Week 3/
├── README.md
├── note/
│   ├── Day1.md                    # 规则与初始解
│   ├── Day2.md                    # 邻域、Move 与实验结论
│   └── Day3.md                    # 局部搜索与搜索路径
├── data/
│   └── instances.py               # 例题与随机任务生成
├── models/
│   ├── job.py                     # Job 与任务属性检查
│   └── machine.py                 # Machine 与机器标识检查
├── scheduling/
│   ├── dispatching.py             # 四种规则：Jobs → 新的 list[Job]
│   ├── schedule.py                # ScheduledJob / Schedule / build_schedule
│   └── validation.py              # 核对输入完整性与排程合法性
├── evaluation/
│   ├── metrics.py                 # 单项指标函数
│   ├── evaluate.py                # evaluate：汇总评价
│   └── objective.py               # 最小总延期目标
├── search/
│   ├── neighborhood.py            # Move 与邻域生成器
│   └── local_search.py            # Best / First Improvement
└── experiments/
    ├── __init__.py
    ├── day1_dispatching.py        # 规则初始解比较
    ├── day2_neighborhood.py       # Move 与一层邻域比较
    └── day3_local_search.py       # 起点、邻域与搜索策略比较
```

数据模型、校验和评价基础沿用第二周代码，复制为本周独立版本；第三周补充平均完工时间和最大 lateness。各周独立运行，避免跨目录导入同名 `scheduling` 包。

## 接口约定

```python
sequence = dispatch(jobs, rule="spt")
schedule = build_schedule(sequence)
validate_schedule(schedule, jobs)
result = evaluate(schedule)
```

规则不修改输入，不计算时间和指标。FCFS 同时到达时保留输入顺序；其他规则同优先级时按 `job_id` 字典序排序。EDD 将无交期任务放在最后。

`build_schedule` 严格执行给定顺序，遇到未释放任务时等待；它不是动态地从已释放任务中重新选择的派工算法。

## 运行

使用 Python 3.10+，实验只依赖标准库。在仓库根目录运行：

```powershell
python "Month_1st_Foundation/Week 3/experiments/day1_dispatching.py"
python "Month_1st_Foundation/Week 3/experiments/day2_neighborhood.py"
python "Month_1st_Foundation/Week 3/experiments/day3_local_search.py"
```

也可以在 Week 3 目录运行：

```powershell
python -m experiments.day1_dispatching --seed 7
python -m experiments.day2_neighborhood
python -m experiments.day2_neighborhood --neighborhood insert
python -m experiments.day2_neighborhood --neighborhood reverse
python -m experiments.day3_local_search
python -m experiments.day3_local_search --seed 7 --max-iterations 1000
```

`day2_neighborhood.py` 默认运行六任务 Swap 实验，输出 SPT 初始解、单次 Move 示例、全部邻居的总延期、最佳邻居及改善比例。`--neighborhood` 可选 `swap`、`insert`、`reverse`；`--seed` 控制随机 Swap 示例。只检查同一初始解的一层邻域，不迭代更新当前解。

`day1_dispatching.py` 运行规则比较，打印任务属性、四种顺序、各任务起止时间和指标表，并列出每项指标的全部并列最优规则。随机作业默认种子为 42，生成 10 个任务，加工时间在 `[1,20]`、交期在 `[10,80]`，释放时间均为零。

第一天评价表展示 Makespan、平均完工时间、总延期和最大 lateness。`max_lateness` 保留负值，只统计有交期的任务；无有效交期时约定返回 0。空排程的平均完工时间约定为 0。

`day3_local_search.py` 先运行六任务手算例，再用同一十任务实例比较 SPT/EDD、Swap/Insert 和 Best/First 的全部组合。输出初始与最终排列、目标值历史、更新次数、邻居评价次数、改善比例、耗时和停止原因，并复核最终邻域是否仍有改进。

`--max-iterations` 限制每次搜索成功接受的次数，默认 1000，允许为 0。达到上限时返回当前解并标记 `max_iterations`；完整扫描后没有严格改进才标记 `no_improvement`。搜索模块接收解码器、目标与邻域函数，不依赖具体初始规则。
