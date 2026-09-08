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

## 项目结构

```text
Week 2/
├── README.md
├── requirements.txt          # Python 依赖
├── note/                     # 学习笔记与手算过程
│   ├── Day1.md
│   ├── Day2.md
│   └── Day3.md
├── scheduling/               # 可复用的调度核心代码
│   ├── __init__.py
│   ├── models.py             # Job、ScheduledJob、Schedule 数据模型
│   ├── scheduler.py          # 根据给定顺序生成单机排程
│   ├── metrics.py            # 计算各项调度指标
│   ├── evaluator.py          # 校验排程并汇总评价结果
│   └── exact/                # 精确优化模型
│       ├── __init__.py
│       ├── parallel_machine.py  # 相同并行机 MILP
│       └── single_machine.py    # 单机排序与 Big-M
└── experiments/              # 每日题目、实验与结果输出
    ├── __init__.py
    ├── day1_basics.py
    ├── day2_milp.py
    └── day3_big_m.py
```

核心数据流：

```text
任务数据 → 调度算法 → Schedule → Evaluator → 指标结果
```

所有算法统一输出 `Schedule`，共用指标计算与评价模块。`experiments` 负责准备数据、调用算法和输出结果，`note` 记录概念、公式和分析。

扩展模块按职责划分为 `heuristics/`（启发式）、`exact/`（精确求解）、`generators/`（数据生成）和 `visualization/`（可视化），每日实验统一放在 `experiments/`。

## 运行

使用 Python 3.10+；MILP 实验依赖 OR-Tools 和其 SCIP 后端。在 Week 2 目录安装依赖并运行：

```powershell
python -m pip install -r requirements.txt
python -m experiments.day1_basics
python -m experiments.day2_milp
python -m experiments.day2_milp --scale
python -m experiments.day3_big_m
```

从仓库根目录先进入本目录，再运行实验：

```powershell
cd "Month_1st_Foundation/Week 2"
python -m experiments.day1_basics
```

Day 1 实验输出给定方案的调度指标；Day 2 实验求解三个并行机题目，`--scale` 增加固定随机种子的规模实验。IDE 应选择已安装依赖的解释器；使用仓库虚拟环境时选择 `.venv/Scripts/python.exe`。

Day 3 实验比较单机的 Makespan 与总完工时间目标，并观察 Big-M 取值、释放时间和主动空闲的影响。

详细概念、数学模型和实验分析见 [Day 1 笔记](note/Day1.md)、[Day 2 笔记](note/Day2.md) 与 [Day 3 笔记](note/Day3.md)。
