# Week 2：调度建模与评价框架

本周围绕“理解调度问题 → 数学建模 → 生成排程 → 评价与比较”，逐步建立可复用的调度项目。

## 学习内容

| 学习日 | 主题 | 实践内容 |
| --- | --- | --- |
| Day 1 | 调度基本概念与数学描述 | 理解任务、资源、时间、约束和目标，建立数据模型与评价体系 |
| Day 2 | MILP 基础 | 学习决策变量、约束和目标函数，建立简单并行机模型 |
| Day 3 | Big-M 与排序决策 | 表达任务先后关系和单机不重叠约束 |
| Day 4 | 交期与延期目标 | 学习总延期、加权延期等目标，比较调度结果 |
| Day 5 | 启发式调度规则 | 实现和比较 FCFS、SPT、LPT、EDD、WSPT |
| Day 6 | 并行机调度 | 学习任务分配，比较贪心、LPT 与精确方法 |
| Day 7 | 综合实验 | 生成可复现的数据，汇总指标与运行时间，绘制甘特图 |

当前已完成 Day 1 的基础模块和题目实验，其余内容随学习进度添加。

## 项目结构

```text
Week 2/
├── README.md
├── note/                     # 学习笔记与手算过程
│   └── Day1.md
├── scheduling/               # 可复用的调度核心代码
│   ├── __init__.py
│   ├── models.py             # Job、ScheduledJob、Schedule 数据模型
│   ├── scheduler.py          # 根据给定顺序生成单机排程
│   ├── metrics.py            # 计算各项调度指标
│   └── evaluator.py          # 校验排程并汇总评价结果
└── experiments/              # 每日题目、实验与结果输出
    ├── __init__.py
    └── day1_basics.py
```

核心数据流：

```text
任务数据 → 调度算法 → Schedule → Evaluator → 指标结果
```

所有算法统一输出 `Schedule`，共用指标计算与评价模块。`experiments` 负责准备数据、调用算法和输出结果，`note` 记录概念、公式和分析。

后续在 `scheduling` 中按需增加 `heuristics/`（启发式）、`exact/`（精确求解）、`generators/`（数据生成）和 `visualization/`（可视化）。

## 运行

Python 3.10+，仅使用标准库。在本目录运行：

```powershell
python -m experiments.day1_basics
```

从仓库根目录先进入本目录，再运行实验：

```powershell
cd "Month_1st_Foundation/Week 2"
python -m experiments.day1_basics
```

`experiments/day1_basics.py` 是实验入口，输出两组四任务方案及三组六任务方案。学习笔记统一放在 `note/` 中。

详细概念、手算结果和接口说明见 [Day 1 笔记](note/Day1.md)。
