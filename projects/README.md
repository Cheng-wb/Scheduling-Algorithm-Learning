# 项目与每周代码入口

前三周的代码、笔记与实验已放回 [第一个月](../Month_01_调度基础与算法/README.md) 的周目录。

| 位置 | 内容 |
| --- | --- |
| [Week_1](../Month_01_调度基础与算法/Week_1/README.md) | 模型、指标、规则与并行机列表调度 |
| [Week_2](../Month_01_调度基础与算法/Week_2/README.md) | 单机/并行机 MILP、松弛、求解状态与枚举 |
| [Week_3](../Month_01_调度基础与算法/Week_3/README.md) | 邻域、LS、Multi-start、SA、比较与整合 |
| [optimization_models](optimization_models/README.md) | 后续 LP/MILP/CP 模型项目 |
| [shop_scheduling](shop_scheduling/README.md) | 后续 JSP/FJSP 项目 |
| [routing](routing/README.md) | 后续网络优化与车辆路径项目 |
| [dynamic_scheduling](dynamic_scheduling/README.md) | 后续滚动调度综合项目 |

每周 `note/` 保存 Day1～Day7 笔记，`experiments/` 保存每日实验。第一、二周使用本周 `scheduling/`，第三周按 `models/scheduling/evaluation/search` 分层。各周独立运行，不在同一进程混用同名包；未来项目不直接把不同问题的数据模型视为同一类型。

```powershell
python run.py --list
python run.py week1 day3_dispatching
python run.py week2 day5_lp_relaxation
python run.py week3 day7_integration
```

`experiments.json` 注册实际存在的入口，`run.py` 使用当前解释器启动独立进程，也可进入周目录使用 `python -m experiments.模块名`。第一、三周仅需标准库；第二周依赖见本周 `requirements.txt`。

模型、算法与指标负责计算，每日脚本负责实验，独立校验负责检查排程。结果保存在对应周 `results/`；原始实例、配置和历史结果保留，历史环境路径不重写。不新增 tests 目录。
