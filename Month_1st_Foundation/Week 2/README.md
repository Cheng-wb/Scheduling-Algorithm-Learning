# Week 2：调度建模与实验框架

围绕任务分配、任务排序和时间安排，学习 MILP 与调度规则，并通过统一的校验、指标和实验流程比较算法。

## 学习大纲

| 学习日 | 主题 |
| --- | --- |
| [Day 1](note/Day1.md) | 调度的数学描述、数据模型与核心指标 |
| [Day 2](note/Day2.md) | MILP 基础与相同并行机任务分配 |
| [Day 3](note/Day3.md) | 单机排序、Big-M 与总完工时间 |
| [Day 4](note/Day4.md) | 交期、总延期与加权延期 |
| [Day 5](note/Day5.md) | FCFS、SPT、LPT、EDD、WSPT 与释放时间 |
| [Day 6](note/Day6.md) | 并行机 Greedy、LPT 与 MILP 比较 |
| [Day 7](note/Day7.md) | 可复现实例、批量 Benchmark、甘特图与总结 |

## 项目结构

```text
Week 2/
├── README.md
├── requirements.txt
├── note/                         # Day1.md ～ Day7.md
├── data/generated/               # 按运行批次保存实例与生成参数
├── results/                      # CSV、配置、排程 JSON、甘特图
├── scheduling/
│   ├── models.py                 # Job / ScheduledJob / Schedule
│   ├── scheduler.py              # 按指定顺序生成单机排程
│   ├── validation.py             # 排程与原始任务核对
│   ├── metrics.py                # 单项指标
│   ├── evaluator.py              # 汇总指标
│   ├── bounds.py                 # 并行机 Makespan 下界
│   ├── benchmark.py              # 算法接口、统一运行与分组统计
│   ├── exact/
│   │   ├── single_machine.py     # 单机各目标的独立 MILP 函数
│   │   └── parallel_machine.py   # 相同并行机 MILP
│   ├── heuristics/
│   │   ├── rules.py              # 排序键
│   │   ├── single_machine.py     # 静态与动态调度规则
│   │   └── parallel_machine.py   # 列表扫描实现 Greedy / LPT
│   ├── generators/
│   │   └── job_generator.py      # 带随机种子的数据生成
│   └── visualization/
│       └── gantt.py              # 算法无关的甘特图
└── experiments/
    ├── day1_basics.py
    ├── day2_milp.py
    ├── day3_big_m.py
    ├── day4_tardiness.py
    ├── day5_dispatching_rules.py
    ├── day6_parallel_machine.py
    └── day7_benchmark.py
```

核心接口：`algorithm(jobs) → Schedule`，之后调用 `validate_schedule(schedule, jobs)`、`evaluate(schedule)` 和 `plot_gantt(schedule)`。核心模块返回数据，实验入口负责配置、打印与保存结果。

## 运行

在仓库根目录使用项目虚拟环境安装依赖，再运行实验；IDE 也应选择同一解释器：

```powershell
.\.venv\Scripts\python.exe -m pip install -r "Month_1st_Foundation/Week 2/requirements.txt"
.\.venv\Scripts\python.exe "Month_1st_Foundation/Week 2/experiments/day7_benchmark.py"
```

也可以进入 Week 2，在已安装依赖的 Python 环境中使用模块入口：

```powershell
cd "Month_1st_Foundation/Week 2"
python -m experiments.day1_basics
python -m experiments.day2_milp
python -m experiments.day3_big_m
python -m experiments.day4_tardiness
python -m experiments.day5_dispatching_rules
python -m experiments.day6_parallel_machine --scale
python -m experiments.day7_benchmark --scale --seeds 20
```

第七天默认运行固定实例和种子 1～5 的批量比较；单机规则组使用 20 个任务，单机 MILP 组使用 6 个任务，并行机使用 20 个任务、3 台机器。不同组分别统计，不互相计算 Gap。

| 参数 | 作用 |
| --- | --- |
| `--seeds N` | 批量使用种子 1～N，默认 5 |
| `--scale` | 增加 10/20/50/100 个任务、5 台机器的并行机实验 |
| `--time-limit-ms N` | 每次 MILP 的时间上限，默认 5000 毫秒 |
| `--skip-milp` | 仅运行规则与启发式，无最优基准时 Gap 留空 |
| `--no-plots` | 不生成图片；与 `--skip-milp` 一起使用时只需标准库 |

每次运行创建独立目录。`data/generated/day7_时间戳/` 保存输入；`results/day7_时间戳/` 保存明细表、汇总表、环境配置、排程和 PNG 甘特图。

`benchmark.csv` 包含指标、运行时间、状态和错误原因；`summary.csv` 包含均值、最大 Gap、成功数及 Gap 样本数。MILP 未证明最优时记录失败，保留其他算法结果，最优值 Gap 留空。单机 MILP 的比较目标是加权延期，并行机为 Makespan。
