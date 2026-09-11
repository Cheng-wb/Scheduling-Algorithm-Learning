# 学习路线与目录迁移说明

改版日期：2026-09-11。方向为通用调度算法与运筹优化，默认具备 Python 与数据结构基础。

## 旧目录到新目录

| 原位置 | 新位置 |
| --- | --- |
| Month_1st_Foundation/Week 1 | 基础练习移除，历史可查 Git |
| Month_1st_Foundation/Week 2 的代码与数据 | projects/scheduling_basics |
| Month_1st_Foundation/Week 3 的代码与数据 | projects/search_lab |
| 原第二、三周 note | Month_01_调度基础与算法/Week_1～Week_4/notes |
| 原根 readme.md | 改为新路线入口，旧计划不保留副本 |

## 主题笔记映射

| 原材料 | 新周任务 | 笔记 |
| --- | --- | --- |
| 原 Week 2 / Day 1 | 第 01 周 | [scheduling_concepts](Month_01_调度基础与算法/Week_1/notes/scheduling_concepts.md) |
| 原 Week 2 / Day 5 | 第 01 周 | [dispatching_rules](Month_01_调度基础与算法/Week_1/notes/dispatching_rules.md) |
| 原 Week 2 / Day 6 | 第 01 周 | [parallel_machines](Month_01_调度基础与算法/Week_1/notes/parallel_machines.md) |
| 原 Week 2 / Day 2 | 第 02 周 | [parallel_milp](Month_01_调度基础与算法/Week_2/notes/parallel_milp.md) |
| 原 Week 2 / Day 3 | 第 02 周 | [single_machine_milp](Month_01_调度基础与算法/Week_2/notes/single_machine_milp.md) |
| 原 Week 2 / Day 4 | 第 02 周 | [tardiness](Month_01_调度基础与算法/Week_2/notes/tardiness.md) |
| 原 Week 2 / Day 7 | 第 04 周 | [scheduling_benchmark](Month_01_调度基础与算法/Week_4/notes/scheduling_benchmark.md) |
| 原 Week 3 / Day 1 | 第 01 周 | [initial_solutions](Month_01_调度基础与算法/Week_1/notes/initial_solutions.md) |
| 原 Week 3 / Day 2 | 第 03 周 | [neighborhoods](Month_01_调度基础与算法/Week_3/notes/neighborhoods.md) |
| 原 Week 3 / Day 3 | 第 03 周 | [local_search](Month_01_调度基础与算法/Week_3/notes/local_search.md) |
| 原 Week 3 / Day 4 | 第 03 周 | [multi_start](Month_01_调度基础与算法/Week_3/notes/multi_start.md) |
| 原 Week 3 / Day 5 | 第 03 周 | [simulated_annealing](Month_01_调度基础与算法/Week_3/notes/simulated_annealing.md) |
| 原 Week 3 / Day 6 | 第 04 周 | [algorithm_comparison](Month_01_调度基础与算法/Week_4/notes/algorithm_comparison.md) |
| 原 Week 3 / Day 7 | 第 04 周 | [project_integration](Month_01_调度基础与算法/Week_4/notes/project_integration.md) |

## 代码入口变更

- `scheduling_basics/experiments/day1_basics.py` → `scheduling_basics/experiments/model_basics.py`
- `scheduling_basics/experiments/day2_milp.py` → `scheduling_basics/experiments/parallel_milp.py`
- `scheduling_basics/experiments/day3_big_m.py` → `scheduling_basics/experiments/single_machine_milp.py`
- `scheduling_basics/experiments/day4_tardiness.py` → `scheduling_basics/experiments/tardiness.py`
- `scheduling_basics/experiments/day5_dispatching_rules.py` → `scheduling_basics/experiments/dispatching_rules.py`
- `scheduling_basics/experiments/day6_parallel_machine.py` → `scheduling_basics/experiments/parallel_comparison.py`
- `scheduling_basics/experiments/day7_benchmark.py` → `scheduling_basics/experiments/benchmark_suite.py`
- `search_lab/experiments/day1_dispatching.py` → `search_lab/experiments/initial_solutions.py`
- `search_lab/experiments/day2_neighborhood.py` → `search_lab/experiments/neighborhoods.py`
- `search_lab/experiments/day3_local_search.py` → `search_lab/experiments/local_search_comparison.py`
- `search_lab/experiments/day4_random_restart.py` → `search_lab/experiments/multi_start.py`
- `search_lab/experiments/day5_simulated_annealing.py` → `search_lab/experiments/annealing.py`
- `search_lab/experiments/day6_compare_algorithms.py` → `search_lab/experiments/algorithm_comparison.py`
- `search_lab/experiments/day7_project_integration.py` → `search_lab/experiments/integrated_demo.py`

所有新路径以 `projects/` 为根。IDE 原来打开的文件页需要从新路径重新打开。`python run.py --list` 提供统一入口，不再依赖带空格的月份/周工作目录。

这次迁移保留算法行为、未提交修改、实例与结果，不重算或改写历史结果中的参数/绝对路径。两套已有实验项目暂时独立：数据模型不同，统一启动入口不等于两套内部类型已经合并。后续按任务增量改进。

已有材料约相当于三周内容量，但覆盖新第 01～04 周的不同部分；验收状态以周大纲为准。第 02 周缺松弛/界与状态实验，第 04 周缺硬预算及严格多实例对照，不能直接标为全部完成。
