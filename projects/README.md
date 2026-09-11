# 项目目录与代码边界

学习大纲位于 [六个月总计划](../LEARNING_PLAN.md)，代码按问题持续维护。月份和周目录只存学习任务、笔记与报告入口。

| 项目 | 用途 | 对应周 |
| --- | --- | --- |
| [scheduling_basics](scheduling_basics/README.md) | 单机/并行机规则、MILP、指标与基础评测 | 01～02、04 |
| [search_lab](search_lab/README.md) | 排列邻域、LS、Multi-start、SA 与搜索评测 | 03～04 |
| [optimization_models](optimization_models/README.md) | LP/MILP/CP 模型、求解状态与比较 | 05～08 |
| [shop_scheduling](shop_scheduling/README.md) | Flow Shop、JSP/FJSP、RCPSP 案例 | 09～12、17～20 可选 |
| [routing](routing/README.md) | 网络模型、TSP/CVRP/VRPTW | 13～16、17～20 可选 |
| [dynamic_scheduling](dynamic_scheduling/README.md) | 滚动时域、事件回放与综合交付 | 21～24 |

前两个项目为已有实现的迁移，其余项目先明确任务与边界，不放无法运行的空 Solver。新增方法进入所属领域项目，不再建 WeekN 的基础模型副本。

## 运行与隔离

在仓库根目录执行 `python run.py --list` 查看可运行实验。`run.py` 使用同一 Python 解释器启动独立进程，以项目为工作目录，避免两个历史项目的 `scheduling`、`experiments` 同名包相互覆盖。

基础建模项目返回 Schedule，搜索项目返回包含排列与统计的字典；两套 Job/排程定义存在差异，不能只改 import 就当成同一种模型。当前保留独立边界与明确运行入口，不强行合并。跨问题扩展时在边界显式转换，稳定后再抽取确实相同的组件。

## 新项目约定

数据模型、实例读取、排程或路线解码、独立校验、算法、评价与实验分别承担职责。只在有实现时创建对应模块，不预建空类和复杂继承。实验只做配置、调用、汇总和导出；算法不写报表。

后续统一结果至少说明 `status / solution / objective / runtime / evaluations / seed`；精确求解器另带 `best_bound / gap`，不同内部求解器的 evaluations 不强行伪造可比值。已完成接口不冒充后续契约全部实现。

实验输出放所属项目 `results/`，实例及生成参数随批次保留；笔记引用具体批次和配置。历史结果路径字符串是运行当时的环境记录，不因目录迁移改写原始实验数据。

验证用手算、小实例枚举、独立合法性检查、固定种子复现和可运行实验完成，不新建 tests 目录。依赖按项目安装，运行成本按问题与预算解释。
