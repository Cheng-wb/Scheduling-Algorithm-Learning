# 第 5 月：元启发式与混合优化

对齐依据：[全年计划](../LEARNING_PLAN.md)「M5」月度周次。周主题与顺序以全年计划为准，下面的任务与验收是执行细化；周号仅使用本月 Week 1–4。

本月目标：在 M1 搜索基础与 M3 工业 FJSP 模型上，提高邻域评价效率，构建 ALNS 与精确修复混合求解器。

## 周计划

| 周次 | 全年周主题 | 学习内容 | 编码与实验任务 | 验收 |
|---|---|---|---|---|
| Week 1 | 问题相关邻域与增量评估 | 问题相关邻域与增量评估；关键路径/关键块、swap、insert、机器重指派、瓶颈/迟交/setup-aware move | 实现 FJSP 邻域与 incremental evaluation；profiler 测候选生成和评价吞吐量 | 增量目标与完整评价自动 cross-check，报告每种邻域吞吐量 |
| Week 2 | ILS / VNS / Tabu | ILS / VNS / Tabu；扰动、restart、禁忌记忆、自适应参数与多样化 | 深入实现 ILS 或 VNS，实现 Tabu 基线；复用 M1 LS/SA 对比 | 同实例、同墙钟预算、多种子比较 LS/SA/ILS或VNS/Tabu |
| Week 3 | LNS / ALNS | LNS / ALNS；destroy/repair、算子评分、自适应权重、SA 接受准则 | 实现 random/worst/related/critical/bottleneck removal 和 greedy/regret-2/regret-3 repair | ALNS 可运行，记录算子使用、成功率、权重及目标轨迹 |
| Week 4 | Hybrid Solver（CP/MILP repair、fix-and-optimize、消融） | Hybrid Solver；CP/MILP repair、fix-and-optimize、ruin-and-recreate | 结合初解、ALNS、局部搜索和精确修复；消融 local search、adaptive weight、CP repair、critical removal | 同墙钟预算完成混合求解器比较、消融、统计汇总和失败分析 |

## 每周 7 天执行清单

| 天 | 固定任务 |
|---|---|
| Day 1 | 定义本周邻域、接受准则或混合接口，写算法草图 |
| Day 2 | 实现最小版本，准备手算和边界小例子 |
| Day 3 | 校验候选可行性、增量评价及随机种子复现 |
| Day 4 | 扩展到多实例与多种子，保存参数和 profiler 记录 |
| Day 5 | 在相同墙钟预算下与既有基线对比 |
| Day 6 | 分析质量、吞吐量、消融和失败案例 |
| Day 7 | 写周报，记录结论、证据与下周改进 |

GA 与 bandit 算子选择可作为扩展，不替代上述四周核心任务。

## 月末交付

**Project 5：Industrial Hybrid Solver**——100+ jobs 可运行，多实例、多随机种子、同墙钟预算比较，附增量评价对拍、profiler、消融和失败案例分析。
