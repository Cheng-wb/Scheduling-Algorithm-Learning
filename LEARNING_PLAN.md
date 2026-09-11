# 十二个月学习计划：高上限调度算法 / AI4OR 工程师

## 目标岗位

十二个月后能够独立完成一个中等复杂度的调度项目完整闭环，并具备 AI4OR / 强化学习增强能力：理解业务、抽象建模、在 MILP / CP-SAT / 启发式 / 元启发式 / 分解方法之间选型、用历史数据估计参数、构建离散事件仿真环境、实现 RL / GNN 调度策略，并交付一个带超时回退、监控和容器化部署的智能调度服务（Intelligent APS）。

默认已经掌握 Python、Git 和基本软件开发。不安排 Python 语法学习，把时间放在运筹优化、AI4OR 和工程交付上。

核心原则：**OR 是主干，复杂业务建模是核心，启发式与混合优化负责规模，RL / GNN / LLM 负责增强，工程化负责落地。**

## 学习节奏

- 每周 15–20 小时：理论 3–4 小时，编码 7–8 小时，实验与复盘 4–6 小时，数学补充 2 小时。
- 每周 7 天都要有记录：Day 1–5 学习和编码，Day 6 对比实验，Day 7 写周报。
- 所有实验固定随机种子，保存输入实例、配置、求解状态、目标值、运行时间、gap 和失败原因。
- 月份与周次只用本地编号：每个月固定 Week 1–Week 4，不使用跨月份的全局周号。

## 阶段划分

| 阶段 | 月份 | 核心目标 |
|---|---|---|
| Phase I | M1–M2 | 调度基础、数学建模、Solver Engineering |
| Phase II | M3–M4 | 工业排程、高级运筹优化、分解方法 |
| Phase III | M5–M6 | 大规模启发式、混合优化、动态调度与仿真 |
| Phase IV | M7–M8 | PyTorch、GNN、强化学习基础 |
| Phase V | M9–M10 | RL for Scheduling、Neural Combinatorial Optimization |
| Phase VI | M11–M12 | Hybrid OR+AI、LLM/Agent、工业级综合项目 |

## 月度路线

| 月份 | 重点能力 | 月末作品 |
|---|---|---|
| 1 | 调度建模、规则基线、统一实验框架 | Scheduling Core & Search Lab |
| 2 | LP / MILP / CP-SAT、求解器诊断 | Optimization Model Lab |
| 3 | JSP / FJSP、工业约束 | Industrial FJSP Solver v1 |
| 4 | 网络优化、TSP/VRP、分解方法 | Advanced OR Lab |
| 5 | 邻域设计、ILS/VNS/Tabu、ALNS、混合求解 | Industrial Hybrid Solver |
| 6 | 动态调度、离散事件仿真、服务化 | Dynamic APS v1 |
| 7 | PyTorch、Attention、GNN、Learning-to-Rank | Learning for OR Lab |
| 8 | MDP、DQN、PPO、Scheduling Gym | Scheduling RL Environment |
| 9 | Dispatching RL、GNN Policy、泛化 | RL Scheduler |
| 10 | Pointer Network、POMO、Neural Improvement | Neural CO Lab |
| 11 | Learned Warm Start、RL-guided ALNS、LLM/Agent | Hybrid OR + AI Solver |
| 12 | 系统设计、多算法决策、Benchmark、发布 | Intelligent APS |

## 月度周次

### M1：调度基础与实验框架
Week 1 调度问题语言与经典规则（`1||Cmax`、`1||ΣCj`、SPT/EDD/WSPT/LPT）；Week 2 解表示、邻域与独立验证器；Week 3 局部搜索与模拟退火；Week 4 Benchmark 与科研式实验。

### M2：精确求解与 Solver Engineering
Week 1 LP、对偶与建模基本功；Week 2 MILP 深化（Big-M、线性化、branch-and-bound）；Week 3 CP-SAT 区间模型；Week 4 高级 Solver Engineering（对称破缺、warm start、不可行诊断）。

### M3：工业排程与柔性车间
Week 1 Flow Shop 与 JSP；Week 2 FJSP；Week 3 工业约束 I（release/due/setup/calendar/maintenance）；Week 4 工业约束 II（qualification/worker/batching/WIP/urgent order）。

### M4：高级运筹与分解方法
Week 1 网络优化（最短路/最大流/最小费用流/匹配）；Week 2 TSP/CVRP/VRPTW；Week 3 Lagrangian Relaxation；Week 4 Dantzig-Wolfe / Column Generation / Benders。

### M5：元启发式与混合求解
Week 1 问题相关邻域与增量评估；Week 2 ILS / VNS / Tabu；Week 3 LNS / ALNS；Week 4 Hybrid Solver（CP/MILP repair、fix-and-optimize、消融）。

### M6：动态调度与仿真交付
Week 1 动态调度模型（滚动时域、事件重排）；Week 2 离散事件仿真；Week 3 动态优化 KPI（稳定性、响应时间）；Week 4 服务化（FastAPI/Docker/超时/回退）。

### M7：机器学习与运筹
Week 1 PyTorch 基础；Week 2 Embedding / Attention / Transformer；Week 3 GNN（GCN/GAT）；Week 4 Learning-to-Rank / Imitation Learning。

### M8：强化学习与调度环境
Week 1 MDP 与 Value-based RL（Q-learning）；Week 2 DQN；Week 3 Policy Gradient / Actor-Critic / PPO；Week 4 Scheduling Gym Environment。

### M9：调度强化学习
Week 1 Dispatching RL（vs FIFO/SPT/EDD/ATC）；Week 2 PPO + Action Masking + reward ablation；Week 3 GNN Policy；Week 4 泛化与鲁棒性（OOD）。

### M10：神经组合优化
Week 1 Pointer Network / Attention Model；Week 2 POMO / Multi-start Neural Policy；Week 3 Neural Improvement；Week 4 迁移回 JSP/FJSP。

### M11：混合运筹与 AI
Week 1 Learned Warm Start；Week 2 RL-guided ALNS；Week 3 Learning to Repair / Solver Control；Week 4 LLM / Agent for Optimization。

### M12：智能 APS 综合项目
Week 1 系统设计与数据库 schema；Week 2 工业约束整合；Week 3 多算法决策系统（rule/exact/metaheuristic/AI）；Week 4 Benchmark、验收、发布。

## 贯穿线

### 数据驱动主线
每个项目都执行同一条链路：数据字典 → 质量检查 → 时间切分 → 预测基线 → 预测区间 → 优化参数 → 误差情景 → 离线回放 → 执行偏差 → 再训练或回退。工时、需求量、取消率和行驶时间预测服务于动态调度、warm start 特征与鲁棒回放；模型指标不能只看 MAE，还要看预测误差对迟交、里程、利用率和计划稳定性的影响。

### 工程规范
从第一天保持 type hints、tests、lint、formatter、deterministic seeds、config-driven experiments（pytest / ruff / black / mypy / pre-commit）。每个实验记录输入版本、随机种子、参数、状态、目标值、gap、运行时间和结论。

### SQL 与数据工程
掌握 SELECT / JOIN / GROUP BY / window function / CTE / 索引 / 事务基础，能把 ERP / MES 的脏业务数据变成可靠优化输入（Orders → Routes → Machines → Calendars → WIP → Instance Builder → 优化模型）。

### 性能工程
从 M5 起加入 cProfile / line_profiler / memory profiling / NumPy 向量化 / 增量评估；了解 Numba / Cython / pybind11。元启发式真正的瓶颈常是每秒能评价多少 candidate，而不是算法理论。

### 数学补充
每周额外 2 小时补线性代数、概率、凸优化、图论、动态规划、MDP、统计；目标是看论文不被基础符号卡死。

### 论文阅读
从 M4 起每两周精读一篇，按 Classic Scheduling → JSP/FJSP → ALNS/LNS → Matheuristics → Dynamic Scheduling → RL for Scheduling → Neural CO → Learning to Optimize 顺序。每篇只回答：问题、baseline、核心想法、为什么有效、实验是否公平、我能复现哪部分。

## 结业标准

1. 能把模糊业务需求抽象成集合、参数、决策变量、约束与目标函数，并写清变量、约束、目标和小实例对拍。
2. 能在 MILP、CP-SAT、启发式、元启发式、分解方法之间做方法选择，并读懂 bound、gap、超时和不可行冲突。
3. 能独立实现并验证 JSP、FJSP、VRP、动态重调度等典型模型。
4. 能处理 sequence-dependent setup、machine calendar、maintenance、batch、qualification、tool、worker、WIP、urgent order 等工业约束。
5. 能针对具体问题设计 neighborhood、destroy/repair、incremental evaluation 与 hybrid repair，并实现 LS、ILS/VNS、Tabu、LNS/ALNS 中至少四类算法做公平基准。
6. 能构建离散事件仿真环境，用于动态调度、回放评测和强化学习。
7. 能把 Scheduling 建模为 MDP，并用 PPO / DQN / Actor-Critic 构建调度策略，理解 action masking 与 reward 设计。
8. 能用 GNN / Attention 建模组合优化问题，完成 RL-guided ALNS、learned dispatching、neural warm start 等 AI+OR 融合实验。
9. 能交付一个带输入校验、超时回退、日志、指标、版本化输入和 Docker 配置的调度服务。
10. 能用严谨实验说明：方法为什么有效、在哪些实例上有效、什么时候不应该使用。

## 全年项目组合

```text
projects/
  01_scheduling_core      调度核心与搜索实验（M1）
  02_optimization_models  LP/MILP/CP-SAT 模型库（M2）
  03_industrial_fjsp      工业 FJSP 求解器（M3）
  04_advanced_or          网络优化与分解方法（M4）
  05_alns_hybrid_solver   混合求解器（M5）
  06_dynamic_aps          动态调度系统（M6）
  07_learning_for_or      机器学习与运筹（M7）
  08_scheduling_rl_env    调度强化学习环境（M8）
  09_rl_scheduler         调度强化学习策略（M9）
  10_neural_co            神经组合优化（M10）
  11_hybrid_or_ai         混合运筹与 AI（M11）
  12_intelligent_aps      智能 APS 综合项目（M12）
```

作品集重点展示：industrial_fjsp、alns_hybrid_solver、rl_scheduler、hybrid_or_ai、intelligent_aps。
