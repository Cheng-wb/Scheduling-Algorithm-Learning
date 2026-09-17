# 02_optimization_models：LP / MILP / CP-SAT 模型库（M2）

[学习路线](../../LEARNING_PLAN.md) · [月度学习索引](../../Month_02_精确算法与参数学习/README.md)

对应第 2 月（M2，Week 1–4）。承接 M1 的规则基线与独立验证器，把「找到一个好解」升级为「**证明一个解有多好**」：建立 LP 与对偶的基本功、实现单机与并行机的 MILP / CP-SAT 模型、理解 Big-M 与松弛强弱、读懂 bound / gap / nodes，并把不可行诊断、对称破缺、warm start 这些 Solver Engineering 手段做成可比较的实验。

**不重新定义调度语义**：`Instance`、`Schedule`、独立验证器、Objective 全部复用 M1（见 [bridge.py](opt_common/bridge.py)）。否则「MILP 的解」和「启发式的解」就不是在同一个问题上比较。

## 求解器依赖

全部使用 **OR-Tools 9.15**，一个依赖覆盖三类后端：

| 后端 | 用途 | 入口 |
|---|---|---|
| GLOP | 连续 LP、对偶与影子价格 | `pywraplp.Solver.CreateSolver("GLOP")` |
| CBC | MILP、branch-and-bound、bound 与 nodes | `...CreateSolver("CBC_MIXED_INTEGER_PROGRAMMING")` |
| CP-SAT | 区间变量、NoOverlap、Cumulative、传播 | `ortools.sat.python.cp_model` |

## 目录结构

```text
02_optimization_models/
├── opt_common/
│   └── bridge.py            # 复用 M1：路径装配 + 重导出 Instance/Schedule/验证器/Objective/规则
├── opt_solvers/
│   ├── result.py            # 统一 SolveResult：status/objective/best_bound/gap/build_time/solve_time
│   ├── registry.py          # 方法注册表：名字 → 求解函数
│   └── heuristics.py        # M1 规则接入统一接口（bound 恒为 None）
├── opt_models/              # 模型层：LP / MILP / CP-SAT / 强化与 warm start
├── opt_experiments/
│   └── benchmark.py         # 配置驱动的可复现批次
├── configs/month2.json      # 月末跨方法比较的实例与方法表
├── examples/                # 按学习日组织的运行入口（m2wXdY_主题.py）
├── tests/                   # 自动化验收
└── artifacts/               # 实际输入、运行记录与汇总
```

## 统一结果接口（全月的主线）

任何方法都返回同一个 `SolveResult`：

```python
SolveResult(method, status, objective, best_bound, schedule,
            build_time, solve_time, iterations, detail)
```

三条纪律，贯穿全月：

1. **没有 bound 就写 `None`。** 启发式没有下界，`best_bound` 必须是 `None`，`gap` 也是 `None`。填 0 或填目标值会让 gap 恒为 0，看起来「已证明最优」——这是求解器实验里最严重的伪证据。
2. **`build_time` 与 `solve_time` 分开记。** 建模慢和求解慢是两种问题，混成一个数就无法归因。
3. **求解器说 `OPTIMAL` 不等于解可行。** 每个返回的排程都要过 M1 的独立验证器（`validate_result`）。

状态词表：`OPTIMAL` / `FEASIBLE` / `INFEASIBLE` / `UNKNOWN` / `MODEL_INVALID` / `FEASIBLE_OR_UNKNOWN` / `FAILED` / `NOT_SOLVED`。

## 方法注册表（周模块的接口契约）

周模块在自己文件里注册方法名，benchmark 只认识名字：

```python
from opt_solvers.registry import register
from opt_solvers.result import SolveResult

@register("milp_tight", "tight Big-M 的单机 MILP")
def milp_tight(instance, spec) -> SolveResult: ...
```

统一签名 `solve_fn(instance, spec) -> SolveResult`，`spec` 含 `objective`、`time_limit`、`seed` 及方法特有参数。调度类方法必须带 `schedule`；纯参数模型（LP）允许 `schedule=None`。

`configs/month2.json` 引用的方法名必须全部注册，否则该行记为 `FAILED`（批次继续，不中断）。

## 运行

在项目目录下：

```bash
python -m pytest -q
python -m opt_experiments.benchmark --config configs/month2.json --output artifacts/month2
python -m examples.m2w1d2_lp_production
```

或从仓库根目录：

```bash
python projects/02_optimization_models/examples/m2w1d2_lp_production.py
```

输出目录必须为空或不存在——否则会覆盖旧批次的证据。

## 设计约定

- 输入实体、结果结构、验证器、目标函数**一律复用 M1**，不在 M2 重写。
- 模型层只负责「把问题写成 LP/MILP/CP-SAT」，不负责计时、记录与比较；那些属于 `opt_experiments`。
- 时间预算必须进结果行：求解器有终止条件，「谁更快」离开预算就无从谈起。
- 参考值分三档且必须标注——`optimum`（独立枚举）/ `proven_by_solver`（求解器证明）/ `best-known`（本批最好可行解，**不是证书**）。
- 失败留痕：失败行保留在结果里，空值不写成 0。

## 与 M1 的关系

| 复用（不重写） | M2 新增 |
|---|---|
| `Instance` / `Job` / `Operation` / `Machine` | LP / MILP / CP-SAT 模型 |
| `Schedule` / `ScheduledOperation` | Big-M 强弱与替代 formulation |
| `validate_schedule`（独立验证器） | bound / gap / nodes / 终止原因 |
| `objective`（六种指标） | 对偶、互补松弛、影子价格 |
| `spt` / `edd` / `wspt` / `parallel_lpt`（作为 warm start 与对照） | 对称破缺、warm start、不可行诊断 |
| `exhaustive_optimum`（小实例真最优参考） | 统一跨方法比较与时间预算实验 |
