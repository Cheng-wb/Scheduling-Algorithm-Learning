# Industrial FJSP Solver v1（M3）

本项目包含：Flow Shop 基线（Johnson / NEH）、析取图与关键路径、JSP 与 FJSP 的 CP-SAT 模型、工业约束（换型/日历/维护/资质/资源/WIP/紧急订单）、独立验证器、多目标 KPI 与 JSON 输入输出。

入口：[月度学习索引](../../Month_03_工业排程与柔性车间/README.md) · [全年计划](../../LEARNING_PLAN.md) · [M1 项目](../01_scheduling_core/PROJECT_GUIDE.md) · [M2 项目](../02_optimization_models/PROJECT_GUIDE.md)。

## 安装与验证

```powershell
cd projects/03_industrial_fjsp
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

> **当前环境的已知状态**：本仓库的 `.venv` 里**没有** `ruff` / `black` / `mypy` / `pre-commit`（M1 的记录里有，之后被移除）。因此本月的证据只包含 `pytest`；`requirements-dev.txt` 仍然声明它们，装上之后即可补跑 lint 与类型检查。精确包版本见 `requirements-lock.txt`。

## 一条命令重跑跨方法实验

仓库根目录：

```powershell
python projects/03_industrial_fjsp/examples/m3_month3_benchmark.py --output projects/03_industrial_fjsp/artifacts/month3
```

项目目录等价命令：

```powershell
python -m fjsp_experiments.benchmark --config configs/month3.json --output artifacts/month3
```

输出目录必须为空或不存在；同一实例上的所有方法共享**逐字节相同**的输入（先落盘 `instances/*.json` 再求解）。各周的独立实验分别写入 `artifacts/month3_w1/` … `artifacts/month3_w4/`。

## 代码地图

```text
03_industrial_fjsp/
├── fjsp_core/          # 领域模型、输入校验、独立验证器、目标、统一结果
│   ├── models.py            # Job / Operation / Machine / Calendar / Maintenance
│   │                        #   / Qualification / Worker / Setup / FJSPInstance / Schedule
│   ├── validation.py        # 输入校验（fail-fast）
│   ├── schedule_validation.py  # 独立排程验证器（11 项检查）
│   ├── objective.py         # Cmax / ΣT / weighted / setup / weighted_sum + Weights
│   └── result.py            # 统一 ShopResult（含 breakdown）
├── fjsp_shop/          # 模型与算法（按周组织）
│   ├── registry.py          # 方法注册表
│   ├── flowshop.py          # W1 Johnson / NEH
│   ├── jsp.py               # W1 优先级派工 + JSP CP-SAT
│   ├── graph.py             # W1 析取图、关键路径、关键块
│   ├── gantt.py             # W1 甘特图数据与 CSV
│   ├── fjsp.py              # W2 解码器与三种指派启发式
│   ├── cpsat_fjsp.py        # W2 FJSP CP-SAT
│   ├── oracle.py            # W2 小实例穷举（独立于解码器）
│   ├── industrial.py        # W3 换型 / 日历维护 / 多目标
│   └── constraints2.py      # W4 资质与资源 / 全约束模型
├── fjsp_io/            # 实例生成、JSON 读写、标准格式解析、KPI
├── fjsp_experiments/   # 跨方法批次与各周驱动
├── configs/month3.json
├── examples/           # 按学习日组织的运行入口
├── tests/              # 自动化验收（含 tests/data/ 手写标准格式实例）
└── artifacts/          # 实际输入、运行记录与汇总
```

依赖方向：`fjsp_shop` 依赖 `fjsp_core` 与 `fjsp_io`；`fjsp_experiments` 依赖前三者；`fjsp_core` 不依赖任何上层。**周模块之间尽量不互相导入**——四周共享的是注册表、领域模型与结果接口。

| 模块 | 职责 | 学习日 |
|---|---|---|
| `fjsp_core/models.py` | 三层数据模型（订单/工序/资源） | W1D1、W3D1、W3D4、W4D1–W4D3 |
| `fjsp_core/schedule_validation.py` | 11 项独立检查 | 全月 |
| `fjsp_core/objective.py` | 单目标 + 多目标加权和与分量 | W3D2–W3D3 |
| `fjsp_core/result.py` | 统一结果接口 | 全月 |
| `fjsp_shop/flowshop.py` | Johnson / NEH | W1D1–W1D2 |
| `fjsp_shop/graph.py` | 析取图与关键路径 | W1D3 |
| `fjsp_shop/fjsp.py` | 解码器与指派启发式 | W2D1–W2D3 |
| `fjsp_shop/cpsat_fjsp.py` | FJSP CP-SAT | W2D4 |
| `fjsp_shop/oracle.py` | 小实例穷举参考 | W2D5 |
| `fjsp_shop/industrial.py` | 换型 / 日历维护 / 多目标 | W3D2–W3D6 |
| `fjsp_shop/constraints2.py` | 资质、资源、全约束 | W4D1–W4D6 |

## 输出文件

| 文件 | 内容 |
|---|---|
| `config.json` / `metadata.json` | 参数、环境、源码 hash、运行前的工作区状态 |
| `instances/*.json` | 实际输入及其 SHA-256 |
| `results.csv` | 每次求解一行：状态、目标、bound、gap、迭代数、建模/求解耗时、三个目标分量、独立验证诊断 |
| `runs/*.json` | 该次的配置、求解细节、完整排程与验证结果 |
| `failures.json` | 失败与「返回解不可行」的行 |
| `summary.csv` / `report.md` | 每实例每方法的汇总；参考值分档表 |

## 每日实验入口

以下路径从仓库根目录执行，也支持 IDE 直接运行。每个脚本对应一天的学习笔记，其预期输出写在笔记的「实验」一节。

```powershell
# Week 1：Flow Shop 与 JSP
python projects/03_industrial_fjsp/examples/m3w1d1_flowshop_rules.py          # Johnson 规则
python projects/03_industrial_fjsp/examples/m3w1d2_flowshop_baseline.py       # NEH 基线
python projects/03_industrial_fjsp/examples/m3w1d3_disjunctive_graph.py       # 析取图、关键路径、关键块
python projects/03_industrial_fjsp/examples/m3w1d4_jsp_cpsat.py               # JSP 的 CP-SAT
python projects/03_industrial_fjsp/examples/m3w1d5_baseline_vs_enumeration.py # 与枚举对拍
python projects/03_industrial_fjsp/examples/m3w1d6_gantt_bottleneck.py        # 甘特图与瓶颈分析
python projects/03_industrial_fjsp/examples/m3w1d7_week1_review.py            # 第一周复盘

# Week 2：FJSP
python projects/03_industrial_fjsp/examples/m3w2d1_machine_choice.py          # 机器选择与 p_ij
python projects/03_industrial_fjsp/examples/m3w2d2_decoder.py                 # FJSP 解码器
python projects/03_industrial_fjsp/examples/m3w2d3_assignments.py             # 三种指派启发式
python projects/03_industrial_fjsp/examples/m3w2d4_cpsat.py                   # FJSP 的 CP-SAT
python projects/03_industrial_fjsp/examples/m3w2d5_oracle.py                  # 小实例穷举 oracle
python projects/03_industrial_fjsp/examples/m3w2d6_compare.py                 # 四方法对比
python projects/03_industrial_fjsp/examples/m3w2d7_week2_wrapup.py            # 第二周复盘

# Week 3：工业约束 I
python projects/03_industrial_fjsp/examples/m3w3d1_release_and_due.py         # 释放时间与交期
python projects/03_industrial_fjsp/examples/m3w3d2_weighted_multiobj.py       # 加权多目标
python projects/03_industrial_fjsp/examples/m3w3d3_normalization_sensitivity.py # 归一化与权重敏感性
python projects/03_industrial_fjsp/examples/m3w3d4_setup_gaps.py              # sequence-dependent setup
python projects/03_industrial_fjsp/examples/m3w3d5_calendar_maintenance.py    # 日历与计划维护
python projects/03_industrial_fjsp/examples/m3w3d6_model_comparison.py        # 带约束模型的对比
python projects/03_industrial_fjsp/examples/m3w3d7_week3_summary.py           # 第三周复盘

# Week 4：工业约束 II
python projects/03_industrial_fjsp/examples/m3w4d1_qualified.py               # 资质与次生资源
python projects/03_industrial_fjsp/examples/m3w4d2_batching.py                # 批处理与工序族
python projects/03_industrial_fjsp/examples/m3w4d3_locked.py                  # WIP 与锁定工序
python projects/03_industrial_fjsp/examples/m3w4d4_urgency.py                 # 紧急订单与优先级
python projects/03_industrial_fjsp/examples/m3w4d5_kpi_bundle.py              # 多目标 KPI 与 JSON 往返
python projects/03_industrial_fjsp/examples/m3w4d6_failures.py                # 全约束端到端与失败分析
python projects/03_industrial_fjsp/examples/m3w4d7_review.py                  # 月度复盘
```

各周的独立实验驱动（写入 `artifacts/month3_wN/`）：

```powershell
python -m fjsp_experiments.week1_gantt          # Week 1（项目目录）
python -m fjsp_experiments.weight_sensitivity   # Week 3
python -m fjsp_experiments.w4_industrial        # Week 4
```

## 如何验证一批结果是否可信

```text
1. metadata.json 的 source_sha256 是否等于当前源码重算的 source_hash()
2. working_tree_dirty 是否为 False，git_commit 是否指向一个真实提交
3. 重跑一次，比较 (status, objective, best_bound, gap, validation) 是否逐行一致
```

这三步是 M2 补上的教训：`fjsp_experiments/benchmark.py` 在**创建输出目录之前**捕获 git 状态，否则刚写进输出目录的 `config.json` 会让 `working_tree_dirty` 恒为 True、这个标记彻底失效（M1 的批次正是栽在这里）。

## 关键约定与限制

- **不使用 M2/M1 自造的问题定义**：M3 的 `FJSPInstance` 自带机器相关工时；复用的是纪律而非代码。
- **`best_bound` 没有就写 `None`**（启发式），绝不填 0 或目标值。`gap` 随之也为 `None`。
- **每次求解都要填 `breakdown`**：目标可能是加权和，只报一个数会让分量取舍不可见。
- **求解器说 `OPTIMAL` 不等于解可行**：每个返回排程都过 11 项独立检查，诊断落在 `validation` 列。
- **参考值分三档**：`optimum`（独立枚举）/ `proven_by_solver`（求解器在预算内证明）/ `best-known`（本批最好可行解，**不是证书**）。`oracle.py` 拒绝它无法表示约束的实例——受限枚举不能冒充更大问题的最优值。
- **半开区间 `[start, end)`**：相接合法；资源占用相接也不算超容量。
- **换型只在实例定义了 `setups` 时才检查**；只给工序族而不给换型矩阵，可能是把族用于资质或批处理分组。
- **批处理用工序族编码**：同族连续加工免换型，异族付换型时间——它能表达「同族成组更省」，但不表达「一个批次有容量上限」。
- 失败留痕：失败行保留，空值不写成 0；批次末尾若存在失败，CLI 以非零状态退出。
- 不覆盖非空输出目录——旧批次被覆盖就失去了证据。
