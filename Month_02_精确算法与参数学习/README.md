# 第 2 月：MILP、CP-SAT 与 Solver Engineering

对齐依据：[全年计划](../LEARNING_PLAN.md)「M2」月度周次。周主题与顺序以全年计划为准，下面的任务与验收是执行细化；周号仅使用本月 Week 1–4。

本月目标：从 LP 与对偶建立精确建模基础，再实现 MILP、CP-SAT，理解模型质量、bound、gap 和求解器诊断。承接 M1 的规则基线与独立验证器，不假定 M1 已实现 MILP。

## Week 1：LP、对偶与建模基本功

全年主题：Week 1 LP、对偶与建模基本功。

| 天 | 任务 | 产出 |
|---|---|---|
| Day 1 | 学习 LP 标准型、可行域、极点与 slack；先写集合、参数、变量、目标、约束 | 生产计划数学模型 |
| Day 2 | 使用 LP 求解器实现生产计划，读取 primal solution、slack、reduced cost | 可运行 LP、结果解释 |
| Day 3 | 建立运输与指派模型，比较网络结构和一般 LP | 两个模型与手算小例子 |
| Day 4 | 推导对偶，理解弱/强对偶、互补松弛和影子价格 | 原始—对偶对照表 |
| Day 5 | 扰动产能、需求与成本，核验影子价格的局部解释范围 | 敏感性实验 |
| Day 6 | 核对小实例的原始/对偶目标、约束残差和互补松弛 | 对拍、数值容差记录 |
| Day 7 | 总结建模步骤、对偶解释与局限 | `week1.md` |

## Week 2：MILP 深化

全年主题：Week 2 MILP 深化（Big-M、线性化、branch-and-bound）。

| 天 | 任务 | 产出 |
|---|---|---|
| Day 1 | 建立首个单机调度 MILP：二元排序变量、时间变量、释放时间和迟交约束 | 数学模型、可运行实现 |
| Day 2 | 推导 indicator logic、Big-M 与乘积线性化，核对逻辑方向及变量界 | 线性化例子、约束测试 |
| Day 3 | 由有效时间界构造 loose/tight Big-M，求解 LP relaxation | 两种 formulation、root LP bound |
| Day 4 | 手工走 branch-and-bound 小例子，区分 incumbent、best bound、gap、nodes、presolve | 搜索树、日志解读 |
| Day 5 | 实现一种替代 formulation，用枚举验证表达等价 | 替代模型、正确性证据 |
| Day 6 | 同实例同预算比较 loose/tight Big-M 和替代模型的 bound、nodes、runtime、gap | formulation comparison |
| Day 7 | 解释模型快慢与松弛强弱，分析变量定义和约束表达的影响 | `week2.md` |

## Week 3：CP-SAT 区间模型

全年主题：Week 3 CP-SAT 区间模型。

| 天 | 任务 | 产出 |
|---|---|---|
| Day 1 | 学习 domain、propagation、IntervalVar、OptionalIntervalVar 与整数时间缩放 | 概念笔记、单位约定 |
| Day 2 | 用可选区间、ExactlyOne、NoOverlap 表达并行机选择与互斥 | CP-SAT 并行机模型 |
| Day 3 | 用 precedence 和 NoOverlap 建立小型 JSP | JSP 模型、独立校验结果 |
| Day 4 | 用 Cumulative 建有限容量资源小例子，对比 NoOverlap 语义 | 容量约束实验 |
| Day 5 | 区分 FEASIBLE、OPTIMAL、UNKNOWN、INFEASIBLE、MODEL_INVALID；记录时间限制及参数 | 状态测试、参数配置 |
| Day 6 | 在共同支持的同一实例集上比较 MILP 与 CP-SAT，独立校验返回解 | 质量、bound、gap、耗时对比 |
| Day 7 | 解释 CP 传播与 MILP 松弛/分支机制的差别及表达边界 | `week3.md` |

## Week 4：高级 Solver Engineering

全年主题：Week 4 高级 Solver Engineering（对称破缺、warm start、不可行诊断）。

| 天 | 任务 | 产出 |
|---|---|---|
| Day 1 | 识别同质机器对称性，实验 symmetry breaking、冗余约束、有效不等式 | 强化模型、正确性核验 |
| Day 2 | 使用 M1 规则解构造 warm start/MIP start 或 hint，比较 variable fixing | 初解与固定变量实验 |
| Day 3 | 检查 numerical scaling，构造不可行实例并按求解器能力定位冲突 | 不可行诊断报告 |
| Day 4 | 配置时间限制、workers 和种子，分别记录建模/求解时间及终止原因 | time limit strategy、参数实验 |
| Day 5 | 统一 MILP/CP-SAT/Heuristic 输出 status、solution、objective、best_bound、gap、build_time、solve_time | 统一结果接口；无 bound 时明确为空 |
| Day 6 | 同实例同预算比较三类方法，分析强化、初解及参数的成本与收益 | 选择矩阵、性能分布 |
| Day 7 | 汇总 LP/MILP/CP-SAT 模型、formulation comparison 和诊断结论 | Optimization Model Lab、Month 2 报告 |

## 月末验收

- 完成生产计划、运输、指派 LP，能解释对偶、互补松弛与影子价格。
- 完成 loose/tight Big-M、替代 formulation 对比，以及至少两项工程手段实验；无改进也如实分析。
- 返回解通过独立验证，能解释目标、bound、gap、时间限制和不可行冲突。
- MILP、CP-SAT 和启发式使用共同实例与相同时间预算比较，分别记录 build_time 与 solve_time。
