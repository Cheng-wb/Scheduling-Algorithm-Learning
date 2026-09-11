# 单机与并行机调度建模

[项目总览](../README.md) · [学习路线](../../LEARNING_PLAN.md)

`scheduling/` 包含模型、规则、MILP、指标、校验、实例生成和甘特图。 `experiments/` 负责配置、运行、比较和保存结果，`results/` 保存实验批次。算法代码按功能命名，与学习日编号解耦。

## 实验入口

| 文件（experiments/） | 来源 |
| --- | --- |
| `model_basics.py` | 原 day1 实验，按功能保留 |
| `parallel_milp.py` | 原 day2 实验，按功能保留 |
| `single_machine_milp.py` | 原 day3 实验，按功能保留 |
| `tardiness.py` | 原 day4 实验，按功能保留 |
| `dispatching_rules.py` | 原 day5 实验，按功能保留 |
| `parallel_comparison.py` | 原 day6 实验，按功能保留 |
| `benchmark_suite.py` | 原 day7 实验，按功能保留 |

## 运行

仓库根目录运行：

```powershell
python run.py basics model_basics
python run.py basics parallel_comparison
python run.py basics benchmark_suite --skip-milp --no-plots --seeds 1
```

也可直接运行 `python projects/scheduling_basics/experiments/model_basics.py`，或进入本目录运行对应 `python -m experiments.模块名`。不同项目的同名包由独立进程隔离。

MILP 与甘特图依赖见 `requirements.txt`，仓库根目录安装：`python -m pip install -r projects/scheduling_basics/requirements.txt`。仅规则/搜索实验可使用标准库；具体参数见入口 `--help`。

## 笔记与实验记录

笔记已移入 [第一个月的主题周](../../Month_01_调度基础与算法/README.md)，完整旧日编号映射见 [迁移说明](../../MIGRATION.md)。原始结果与生成数据保留；旧批次内部环境路径不重写。

运行结束后的新数据仍写入本项目目录。搜索实验的计数比较并不等于硬等预算实验；精确模型的限时可行解、下界与状态表达按第 02/04 周任务完善，不因迁移改变算法结论。
