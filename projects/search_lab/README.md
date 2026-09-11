# 排列搜索与算法评测

[项目总览](../README.md) · [学习路线](../../LEARNING_PLAN.md)

`models/` 定义任务；`scheduling/` 排序与解码；`evaluation/` 计算目标与指标；`search/` 保存邻域、LS、Multi-start 与 SA。 `experiments/` 负责配置、运行、比较和保存结果，`results/` 保存实验批次。算法代码按功能命名，与学习日编号解耦。

## 实验入口

| 文件（experiments/） | 来源 |
| --- | --- |
| `initial_solutions.py` | 原 day1 实验，按功能保留 |
| `neighborhoods.py` | 原 day2 实验，按功能保留 |
| `local_search_comparison.py` | 原 day3 实验，按功能保留 |
| `multi_start.py` | 原 day4 实验，按功能保留 |
| `annealing.py` | 原 day5 实验，按功能保留 |
| `algorithm_comparison.py` | 原 day6 实验，按功能保留 |
| `integrated_demo.py` | 原 day7 实验，按功能保留 |

## 运行

仓库根目录运行：

```powershell
python run.py search initial_solutions
python run.py search local_search_comparison
python run.py search integrated_demo
python run.py search algorithm_comparison
```

也可直接运行 `python projects/search_lab/experiments/initial_solutions.py`，或进入本目录运行对应 `python -m experiments.模块名`。不同项目的同名包由独立进程隔离。

只依赖 Python 标准库；使用仓库现有 Python 3.10+ 环境。

## 笔记与实验记录

笔记已移入 [第一个月的主题周](../../Month_01_调度基础与算法/README.md)，完整旧日编号映射见 [迁移说明](../../MIGRATION.md)。原始结果与生成数据保留；旧批次内部环境路径不重写。

运行结束后的新数据仍写入本项目目录。搜索实验的计数比较并不等于硬等预算实验；精确模型的限时可行解、下界与状态表达按第 02/04 周任务完善，不因迁移改变算法结论。
