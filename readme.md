# 调度算法工程师 · 6个月学习路线

> **目标：** 用 6 个月建立「编程基础 → 运筹优化 → 调度建模 → 求解器 → 启发式算法 → 工程化」的完整知识体系，并完成可用于实践和求职的调度算法项目。

## 学习路线

```text
Python & 算法基础
        ↓
运筹学 & MILP
        ↓
JSP / FJSP
        ↓
TSP / VRP
        ↓
LNS / ALNS
        ↓
动态调度 & 工程化
```

---

## Month 1：Python 与算法基础

### 学习内容

* Python 基础与面向对象
* NumPy / Pandas / Matplotlib
* 常见数据结构：栈、队列、哈希表、堆、图
* 常见算法：排序、二分、DFS、BFS、贪心、动态规划
* 图算法：最短路、拓扑排序
* 调度基本概念：Job、Operation、Machine、Makespan、Due Date

### 实践

* 实现 FCFS / SPT / EDD 等简单调度规则
* 使用 Matplotlib 绘制甘特图

**目标：能够使用 Python 独立实现基础算法和简单调度程序。**

---

## Month 2：运筹优化与数学建模

### 学习内容

* 线性规划 LP
* 整数规划 IP
* 混合整数规划 MILP
* 决策变量、目标函数、约束条件
* 0-1 变量与 Big-M
* Branch & Bound 基本原理
* Gurobi / OR-Tools 基础

### 实践

完成几个经典优化模型：

* Knapsack Problem
* Assignment Problem
* Transportation Problem
* 简单生产计划模型

**目标：能够把简单业务问题转换成数学优化模型并使用 Solver 求解。**

---

## Month 3：JSP / FJSP 生产调度

### 学习内容

重点学习生产调度：

* Job Shop Scheduling Problem（JSP）
* Flexible Job Shop Scheduling Problem（FJSP）
* 工序先后约束
* 机器互斥约束
* Makespan Optimization
* Constraint Programming
* OR-Tools CP-SAT

### 项目

**Project 01：JSP / FJSP 生产排程**

```text
订单数据
   ↓
调度模型
   ↓
CP-SAT
   ↓
排程结果
   ↓
Gantt Chart
```

**目标：能够独立建立并求解一个基本的生产调度模型。**

---

## Month 4：图优化与车辆调度

### 学习内容

图优化：

* Shortest Path
* Bipartite Matching
* Maximum Flow
* Minimum Cost Flow

车辆调度：

* TSP
* VRP
* CVRP
* VRPTW
* Capacity Constraint
* Time Window

### 项目

**Project 02：VRPTW 车辆调度**

实现：

* 多车辆
* 容量约束
* 客户时间窗
* 路径优化
* 调度结果可视化

**目标：理解物流调度问题，并能够使用 OR-Tools 求解 VRP/VRPTW。**

---

## Month 5：启发式与大规模优化

### 学习内容

* Greedy
* Local Search
* Simulated Annealing
* Tabu Search
* Genetic Algorithm
* Large Neighborhood Search（LNS）
* Adaptive Large Neighborhood Search（ALNS）

重点学习：

```text
Initial Solution
      ↓
Local Search
      ↓
Destroy
      ↓
Repair
      ↓
Acceptance
      ↓
Repeat
```

### 实践

选择 JSP / FJSP / VRPTW 中的一个问题：

* 实现 Greedy 初始解
* 实现 Local Search
* 实现 LNS / ALNS
* 与 CP-SAT / MILP 进行效果和求解时间对比

**目标：能够处理 Solver 难以快速求解的大规模组合优化问题。**

---

## Month 6：工业调度与工程化

### 学习内容

工业调度：

* 订单约束
* 设备约束
* 人员 / 物料约束
* Setup / 换型
* Due Date
* 多目标优化
* 紧急插单
* 机器故障
* 动态重调度

工程能力：

* Git
* Linux
* SQL
* FastAPI
* Docker

### 项目

**Project 03：动态生产调度系统**

```text
订单
 ↓
初始排程
 ↓
CP-SAT / MILP / ALNS
 ↓
机器故障 / 紧急插单
 ↓
动态重调度
 ↓
Gantt Chart / API
```

**目标：从“会写调度算法”提升到“能够实现一个完整的调度系统”。**

---

# 6个月项目成果

| 项目         | 核心内容            |
| ---------- | --------------- |
| Project 01 | JSP / FJSP 生产排程 |
| Project 02 | VRPTW 车辆调度      |
| Project 03 | 动态生产调度系统        |

最终形成以下能力：

```text
数学建模
   +
LP / MILP / CP
   +
Gurobi / OR-Tools
   +
JSP / FJSP / VRP
   +
Local Search / LNS / ALNS
   +
动态调度
   +
工程化
```

## 最终目标

6个月后能够：

> 面对一个实际调度问题，分析业务规则，建立数学模型，选择合适的 MILP / CP-SAT / 启发式算法进行求解，并完成结果可视化与基础工程化。

**核心原则：不要只学算法，要持续完成「理论 → 建模 → 编码 → 实验 → 项目」的闭环。**
