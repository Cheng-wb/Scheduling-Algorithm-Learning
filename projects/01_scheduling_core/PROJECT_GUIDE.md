# Scheduling Core & Search Lab（M1）

本项目包含：数据模型、JSON/CSV、规则、候选解与解码、独立验证、邻域、五种搜索和可复现实验。

入口：[月度学习索引](../../Month_01_基础系统与框架设计/README.md) · [月度报告](../../Month_01_基础系统与框架设计/MONTH1_REPORT.md) · [全年计划](../../LEARNING_PLAN.md)。

## 安装与验证

从仓库根目录进入项目；Python 3.11+（实际验证环境见 artifacts/month1_refactored/metadata.json）。

```powershell
cd projects/01_scheduling_core
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
python -m black --check .
python -m mypy
```

运行环境的精确依赖版本在 requirements-lock.txt，可在相同 Python/平台的隔离环境中安装。可选 Git 提交检查：从仓库根目录执行 `python -m pre_commit install --config projects/01_scheduling_core/.pre-commit-config.yaml`。

## 一条命令重跑全部实验

仓库根目录：

```powershell
python projects/01_scheduling_core/examples/m1w4d1_benchmark.py --output projects/01_scheduling_core/artifacts/my_run
```

项目目录等价命令：

```powershell
python -m scheduling_experiments.benchmark --config configs/month1.json --output artifacts/my_run
```

输出目录必须为空或不存在；每次重跑换一个名字，保护旧记录。六实例、三种子、六方法（包含 LPT 基线），加三个 SA 敏感性设置，共 162 次运行。

重算并核对已有实验记录（项目目录）：

```powershell
python examples/m1w4d4_reproduce.py artifacts/month1_refactored
```

复现检查输入与源码 hash、目标、状态、评价数、最好候选、排程、全部轨迹；不要求墙钟时间相同。代码改变后源码 hash 检查会拒绝，应先创建新批次。

## 代码地图

```text
01_scheduling_core/
├── scheduling_core/          # 领域模型、候选解、指标与独立验证
│   ├── models.py
│   ├── schedule.py
│   ├── solution.py           # Candidate + validate_candidate
│   ├── objective.py
│   ├── validation.py
│   └── schedule_validation.py
├── scheduling_algorithms/    # 如何产生、改进和求解排程
│   ├── decoder.py            # decode + initial_candidate
│   ├── neighborhoods.py      # swap / insert / reassign
│   ├── rules.py
│   ├── search.py
│   └── oracle.py
├── scheduling_io/            # 输入读写与实例生成
│   ├── parser.py
│   └── generator.py
├── scheduling_experiments/   # 实验编排、记录、汇总与绘图
│   └── benchmark.py
├── examples/                 # 按学习日组织的运行入口
├── tests/                    # 自动化验收
├── configs/                  # 实验配置
└── artifacts/                # 实际输入、运行记录与图表
```

依赖方向：算法层与 I/O 层分别依赖 core；实验层调用算法与 I/O。core 不导入算法、文件读写或绘图模块，算法不依赖实验层。包根目录只导出核心领域接口，避免为了方便导入造成循环依赖。

例如，`Candidate` 从 `scheduling_core.solution` 导入，`decode` 从 `scheduling_algorithms.decoder` 导入，`solve` 从 `scheduling_algorithms.search` 导入。原有按学习日运行的 examples 入口保留。

| 模块 | 职责 | 学习日 |
|---|---|---|
| models.py | 不可变 Job/Operation/Machine/Instance | W1D2 |
| scheduling_io/parser.py / scheduling_core/validation.py | JSON/CSV 与输入完整性 | W1D3、W2D5 |
| schedule.py / objective.py | 输出模型、六种指标 | W1D3 |
| rules.py | SPT/EDD/WSPT/LPT 与 parallel_lpt | W1D4–5 |
| scheduling_core/solution.py | Candidate 与候选解校验 | W2D1 |
| scheduling_algorithms/decoder.py / neighborhoods.py | 解码与 swap/insert/reassign | W2D2–3 |
| schedule_validation.py | 独立时间与资源检查 | W2D4 |
| scheduling_io/generator.py / scheduling_algorithms/oracle.py | 固定种子输入、极小实例枚举 | W2D5–6 |
| search.py | Random/First/Best/Multi-start/SA | W3D1–5 |
| benchmark.py | 批量运行、失败、汇总与图表 | W4 |

tests/test_month1.py 包含十个手算实例、三条解码轨迹、五个枚举对拍、九类损坏排程、预算/复现/失败注入测试；原有五个测试文件继续保留。

## 每周实验入口

以下路径从仓库根目录执行，也支持 IDE 直接运行：

```powershell
python projects/01_scheduling_core/examples/m1w1d2_exercises.py
python projects/01_scheduling_core/examples/m1w1d3_pipeline.py
python projects/01_scheduling_core/examples/m1w1d4_rules.py
python projects/01_scheduling_core/examples/m1w1d5_parallel.py
python projects/01_scheduling_core/examples/m1w2d6_verification.py
python projects/01_scheduling_core/examples/m1w3d6_search.py
```

## 输出文件

当前结构的实验记录：[artifacts/month1_refactored/report.md](artifacts/month1_refactored/report.md)。拆分前记录保留在 month1，首轮开发记录保留在 month1_initial；旧批次的源码 hash 对应旧结构。当前代码与复现默认使用 month1_refactored。

| 文件 | 内容 |
|---|---|
| config.json / metadata.json | 参数、环境、源码版本依据 |
| instances/*.json | 六个实际输入 |
| results.csv | 162 条运行及输入 hash、参考值/gap |
| runs/*.json | 配置、最好 Candidate 与完整 Schedule |
| runs/*.trace.csv | 每次评价的 proposed/current/best、接受事件与温度 |
| failures.json | 失败行（本批次为空） |
| summary.csv / report.md | 每实例每配置跨种子统计 |
| quality.png / convergence.png / gantt.png | 质量、收敛、排程图 |

## 关键约定与限制

- assignments 对齐 instance.operations；order 为工序优先级。多工序前驱就绪后才排入。
- 时间为非负整数、不可抢占，区间 [start,end)。每工序在所有合格机器上的工时相同。
- decoder 采用追加式构造，不插入已有空隙。无 setup、calendar、工人和动态事件。
- 独立验证器先验可行性，Objective 再计算指标；直接调用 Objective 不会自动验证坏排程。
- 每次完整解码＋验证＋评价计 1，包括初始化、拒绝解和重启。LS 可提前停机；预算是上限。
- Best 的 accepted 在扫描末表示是否移动，SA 的 accepted 表示该候选是否接受；计算接受率仅使用对应方法。
- tiny 的参考由独立枚举证明，其余是本批主实验＋敏感性实验的 best-known；gap 不混称数学最优差距。
- 同 seed 重现目标和轨迹，时间依赖机器和环境。三 seed、小合成数据只支持教学观察。

CSV 输入目录应有 machines.csv（id,name）、jobs.csv（id,operation_ids,release_time,due_date,weight）、operations.csv（id,job_id,processing_time,eligible_machine_ids）；列表字段用 `|` 分隔，空 due_date 表示 None。读取后调用 validate_instance。
