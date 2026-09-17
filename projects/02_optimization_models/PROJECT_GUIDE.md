# Optimization Model Lab（M2）

本项目包含：LP 与对偶、单机与并行机 MILP、CP-SAT 区间模型、模型强化与求解器诊断，以及跨方法的可复现比较框架。

入口：[月度学习索引](../../Month_02_精确算法与参数学习/README.md) · [全年计划](../../LEARNING_PLAN.md) · [M1 项目](../01_scheduling_core/PROJECT_GUIDE.md)。

## 安装与验证

从仓库根目录进入项目：

```powershell
cd projects/02_optimization_models
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

> **当前环境的已知状态**：本仓库的 `.venv` 里**没有** `ruff` / `black` / `mypy` / `pre-commit`（M1 的记录里有，之后被移除）。因此本月的证据只包含 `pytest`；`requirements-dev.txt` 仍然声明它们，装上之后即可补跑 lint 与类型检查。精确包版本见 `requirements-lock.txt`。

## 一条命令重跑跨方法实验

仓库根目录：

```powershell
python projects/02_optimization_models/examples/m2_month2_benchmark.py --output projects/02_optimization_models/artifacts/month2
```

项目目录等价命令：

```powershell
python -m opt_experiments.benchmark --config configs/month2.json --output artifacts/month2
```

输出目录必须为空或不存在；每次重跑换一个名字，保护旧记录。同一实例上的所有方法共享**逐字节相同**的输入（先落盘 `instances/*.json` 再求解）。

各周的独立实验分别写入 `artifacts/month2_w1/` … `artifacts/month2_w4/`，与月末统一批次互不覆盖。

## 代码地图

```text
02_optimization_models/
├── opt_common/          # 复用 M1：路径装配与领域接口重导出
│   └── bridge.py
├── opt_solvers/         # 求解器包装层
│   ├── result.py        # 统一 SolveResult（status/objective/best_bound/gap/build_time/solve_time）
│   ├── registry.py      # 方法注册表：@register(name) → solve_fn(instance, spec)
│   └── heuristics.py    # M1 规则接入统一接口（bound 恒为 None）
├── opt_models/          # 模型层（按周组织）
│   ├── lp_models.py         # W1 生产计划 / 运输 / 指派 LP + 对偶信息
│   ├── milp_scheduling.py   # W2 单机与并行机 MILP（tight/loose/替代 formulation）
│   ├── cpsat_models.py      # W3 区间模型（并行机 / JSP / Cumulative）
│   ├── strengthening.py     # W4 对称破缺 / warm start / variable fixing
│   └── diagnostics.py       # W4 不可行诊断
├── opt_experiments/     # 实验编排
│   ├── benchmark.py         # 跨方法批次（配置驱动）
│   ├── lp_experiments.py    # W1
│   ├── w2_formulations.py   # W2
│   ├── w3_cpsat.py          # W3
│   └── w4_engineering.py    # W4
├── configs/month2.json  # 月末跨方法比较的实例与方法表
├── examples/            # 按学习日组织的运行入口
├── tests/               # 自动化验收
└── artifacts/           # 实际输入、运行记录与汇总
```

依赖方向：`opt_models` 依赖 `opt_solvers` 与 `opt_common`；`opt_experiments` 依赖前两者；`opt_common` 不依赖任何 M2 模块。**周模块不得互相导入**——四周共享的是注册表与结果接口，不是彼此的实现。

| 模块 | 职责 | 学习日 |
|---|---|---|
| `opt_common/bridge.py` | 复用 M1 的 Instance/Schedule/验证器/Objective/规则 | 全月 |
| `opt_solvers/result.py` | 统一结果接口：无 bound 时明确为空 | W4D5 |
| `opt_solvers/registry.py` | 方法注册表 | 全月 |
| `opt_solvers/heuristics.py` | M1 规则作为对照基线 | W4D6 |
| `opt_models/lp_models.py` | 生产计划 / 运输 / 指派 LP 与对偶 | W1D1–D6 |
| `opt_models/milp_scheduling.py` | 单机 MILP、Big-M 强弱、替代 formulation | W2D1–D6 |
| `opt_models/cpsat_models.py` | OptionalInterval / NoOverlap / Cumulative | W3D1–D6 |
| `opt_models/strengthening.py` | 对称破缺、warm start、variable fixing | W4D1–D2 |
| `opt_models/diagnostics.py` | 不可行诊断与冲突定位 | W4D3 |
| `opt_experiments/benchmark.py` | 跨方法批次、参考值分档、独立验证 | W4D4–D6 |

## 输出文件

| 文件 | 内容 |
|---|---|
| `config.json` / `metadata.json` | 参数、环境、**M2 与 M1 两组源码的联合 hash**、时间预算 |
| `instances/*.json` | 五个实际输入及其 SHA-256 |
| `results.csv` | 每次求解一行：状态、目标、bound、gap、迭代数、建模/求解耗时、独立验证诊断 |
| `runs/*.json` | 该次的配置、求解细节、完整排程与验证结果 |
| `failures.json` | 失败与「返回解不可行」的行 |
| `summary.csv` / `report.md` | 每实例每方法的汇总；参考值分档表 |

## 关键约定与限制

- **不使用 M2 自造的问题定义**：`Instance`、`Schedule`、独立验证器、Objective 全部来自 M1。
- **`best_bound` 没有就写 `None`**，绝不填 0 或目标值。`gap` 随之也为 `None`。写成 0 会伪造「已证明最优」。
- **`build_time` 与 `solve_time` 分开记**。建模慢与求解慢是两种问题。
- **求解器说 `OPTIMAL` 不等于解可行**：每个返回排程都过 M1 的 `schedule_errors`，诊断落在 `validation` 列。
- **参考值分三档**：`optimum`（独立枚举，不依赖被测求解器）/ `proven_by_solver`（求解器在预算内证明）/ `best-known`（本批最好可行解，**不是证书**）。本批 `single_8` 有独立枚举的最优值。
- **时间预算必须进结果行**：求解器有终止条件，「谁更快」离开预算无从谈起。
- 失败留痕：失败行保留，空值不写成 0；批次末尾若存在失败，CLI 以非零状态退出。
- 不覆盖非空输出目录——旧批次被覆盖就失去了证据。
- 当 `best_bound` 高于独立枚举的最优值时，结果行会带上告警（这是对求解器正确性的交叉检查）。
