# 第 1 月：调度基础与实验框架

对齐依据：[全年计划](../LEARNING_PLAN.md)「M1」月度周次。周主题与顺序以全年计划为准，下面的任务与验收是执行细化；周号仅使用本月 Week 1–4。

本月目标：建立统一输入模型、经典规则、解码器、独立验证器和目标评估器，实现局部搜索与模拟退火，并完成可复现的 Benchmark。MILP / CP-SAT 在 M2 学习，本月不涉及。月末作品为 **Scheduling Core & Search Lab**。

## Week 1：调度问题语言与经典规则

全年主题：Week 1 调度问题语言与经典规则（`1||Cmax`、`1||ΣCj`、SPT/EDD/WSPT/LPT）。

| 天 | 任务 | 产出 |
|---|---|---|
| Day 1 | 学习三字段表示法与问题分类，列出订单、工序、机器、交期等字段 | 领域词汇表与问题分类 |
| Day 2 | 设计 Job、Operation、Machine、Instance 数据结构与不可变输入模型 | `scheduling_core` 数据模型 |
| Day 3 | 实现 JSON/CSV 解析、字段校验与独立 objective 模块 | 输入校验器与目标评估器 |
| Day 4 | 实现单机 SPT/EDD/WSPT/LPT 规则及释放时间处理 | 单机规则基线 |
| Day 5 | 实现 LPT 并行机基线与最小选机表示，输出 Schedule/Gantt 数据 | 并行机基线与 Gantt 数据 |
| Day 6 | 用 ≥10 个手算实例对拍规则与指标，记录规则对比 | 对拍断言与规则对比 |
| Day 7 | 汇总规则最优性条件、失效反例与本周问题 | `week1.md` |

## Week 2：解表示、邻域与独立验证器

全年主题：Week 2 解表示、邻域与独立验证器。

| 天 | 任务 | 产出 |
|---|---|---|
| Day 1 | 约定候选解字段与 permutation 表示，编码三个小例子 | 解表示约定 |
| Day 2 | 实现 decoder 并手算三类解码轨迹 | decoder 与确定性测试 |
| Day 3 | 实现 swap、insert、机器指派邻域与边界处理 | 邻域模块 |
| Day 4 | 实现独立 schedule validator 与违规诊断样例 | 独立验证器 |
| Day 5 | 实现随机实例生成器与五类负例测试 | 实例生成器 |
| Day 6 | 对 ≥5 个小实例做枚举对拍与自动测试 | 对拍案例与自动测试 |
| Day 7 | 固化接口约定、测试覆盖与待解决问题 | `week2.md` |

## Week 3：局部搜索与模拟退火

全年主题：Week 3 局部搜索与模拟退火。

| 天 | 任务 | 产出 |
|---|---|---|
| Day 1 | 统一搜索接口与评价计数，实现 Random Search | 统一搜索入口 |
| Day 2 | 实现 First Improvement 与停止条件测试 | First Improvement |
| Day 3 | 实现 Best Improvement，对比 First/Best 扫描计数 | Best Improvement |
| Day 4 | 实现 Multi-start 与种子、预算分配 | Multi-start |
| Day 5 | 实现 Simulated Annealing 与温度/接受率轨迹 | SA |
| Day 6 | 记录逐次运行与搜索曲线，做差异分析 | 可复现搜索记录 |
| Day 7 | 总结算法差异与默认配置 | `week3.md` |

## Week 4：Benchmark 与科研式实验

全年主题：Week 4 Benchmark 与科研式实验。

| 天 | 任务 | 产出 |
|---|---|---|
| Day 1 | 统一实验入口、配置与可复现运行命令 | 实验入口 |
| Day 2 | 准备基准输入、实例参数表与种子 | 基准实例集 |
| Day 3 | 定义结构化结果格式与排程/轨迹文件 | 结果 schema |
| Day 4 | 批量运行并记录缺失、失败与复现结果 | 完整运行记录 |
| Day 5 | 生成统计表、图表与汇总脚本 | 统计表与图 |
| Day 6 | 做敏感性实验与案例分析，记录必要修复 | 敏感性表 |
| Day 7 | 完成月度报告：模型、方法、验证、实验、结论、局限与复现 | Scheduling Core & Search Lab、Month 1 报告 |

## 月末验收

- 规则与目标评估器通过 ≥10 个手算实例核对，注明每种规则的适用条件。
- 独立验证器拒绝 precedence 违规、机器重叠、非法指派、工序缺失和重复。
- Random Search、LS、Multi-start、SA 使用统一实例、种子和评价预算公平比较。
- 一条命令重跑基准并生成统计表与图；失败单独记录，best-known 不标成 optimum。
