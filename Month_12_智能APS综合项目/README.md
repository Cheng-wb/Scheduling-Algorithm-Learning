# 第 12 月：工业级 Intelligent APS 综合项目

本月目标：把全年能力收敛到一个可展示、可部署、可面试的系统。

## 周计划

| 周次 | 学习内容 | 编码与实验任务 | 验收 |
|---|---|---|---|
| Week 1 | 系统设计：Data Layer → Domain Model → Instance Builder → Solver Registry → MILP/CP-SAT/ALNS/RL → Validator → Simulation → KPI → API | 设计数据库表（orders/operations/routes/machines/machine_calendars/qualifications/maintenance/wip/schedules/schedule_operations/events/solver_runs） | 产出架构图、数据库 schema、API contract、solver interface |
| Week 2 | 工业约束整合：FJSP + release/due/setup/calendar/maintenance/qualification/urgent/breakdown/WIP/frozen（选做 workers/tools/batching/material） | 把约束接进统一数据模型与 validator | 每条约束都有可行性与违规检查 |
| Week 3 | 多算法决策系统：Rule（SPT/EDD/ATC）+ Exact（CP-SAT/MILP）+ Metaheuristic（ALNS/ALNS+CP repair）+ AI（PPO/GNN/learned warm start/RL-guided ALNS） | 统一接口 `solver.solve(instance, config)` | 各算法在同一接口下可替换 |
| Week 4 | Benchmark、验收、发布 | 建立 benchmark matrix（Jobs 20/50/100/200 × Machines 5/10/20 × 交期 × 故障 × setup × 动态到达）；指标含 makespan/tardiness/utilization/throughput/setup/stability/latency/gap/feasibility | 100+ 自动实验、ablation、OOD、profiler、failure case、README、架构图、demo、技术报告、Docker |

## 每周 7 天执行清单

| 天 | 固定任务 |
|---|---|
| Day 1 | 设计/梳理本周模块接口与数据流 |
| Day 2 | 完成最小可运行实现 |
| Day 3 | 接入校验器与日志，跑通一次 |
| Day 4 | 扩展到全约束/全算法，保存版本与配置 |
| Day 5 | 与基线对拍，定位正确性/性能问题 |
| Day 6 | 跑 benchmark，分析指标与失败案例 |
| Day 7 | 写周报，更新 README 与架构图 |

## 月末交付

**Project 12：Intelligent APS**——一个可部署的智能调度平台，附带完整 benchmark 报告与演示。
