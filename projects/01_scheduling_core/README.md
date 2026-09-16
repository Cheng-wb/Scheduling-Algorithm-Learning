# 01_scheduling_core：调度核心与实验框架（M1）

[学习路线](../../LEARNING_PLAN.md)

对应第 1 月（M1）。本目录逐步实现 M1 的调度核心：统一输入模型、经典规则、解码器、独立验证器、目标评估器与可复现 Benchmark。

## 当前进度

**M1 四周全部完成。** 已实现不可变输入模型、解析与独立输入校验、六种目标指标、单机与并行机规则基线、候选解与追加式解码器、swap/insert/reassign 邻域、独立排程验证器、随机实例生成器、极小实例枚举 oracle、五种搜索方法（Random / First / Best / Multi-start / SA）、JSON 配置驱动的可复现 Benchmark 与逐运行复现脚本。

月末产出为 **Scheduling Core & Search Lab**：一个月度报告、四个周报、28 篇日笔记、正式批次 162 次运行（108 主实验 + 54 敏感性实验，零失败）。入口见 [月度索引](../../Month_01_基础系统与框架设计/README.md) 与 [月度报告](../../Month_01_基础系统与框架设计/MONTH1_REPORT.md)。

## 目录结构

```text
01_scheduling_core/
├── scheduling_core/
│   ├── __init__.py
│   ├── models.py            # 不可变输入数据模型
│   ├── validation.py        # 输入校验（fail-fast）
│   ├── schedule.py          # 排程结果的最小表示
│   ├── schedule_validation.py  # 排程可行性独立验证
│   ├── solution.py          # 候选解（Candidate）不可变表示与合法性校验
│   └── objective.py         # 统一目标评估器
├── scheduling_io/
│   ├── __init__.py
│   ├── parser.py            # JSON/CSV → Instance
│   ├── generator.py         # 局部 RNG 随机实例生成
│   └── export.py            # Schedule → Gantt rows / CSV
├── scheduling_algorithms/
│   ├── __init__.py
│   ├── rules.py             # 单机 SPT/EDD/WSPT/LPT + 并行 LPT 与 P||Cmax 下界
│   ├── decoder.py           # Candidate → Schedule（machine_ready 推进）
│   ├── neighborhoods.py     # 交换/插入/选机邻域，只产生新候选解
│   ├── oracle.py            # 单工序极小实例穷举（独立于 decoder 证明最优）
│   └── search.py            # 统一评价预算的局部搜索与模拟退火
├── scheduling_experiments/
│   ├── __init__.py
│   └── benchmark.py         # 可复现 benchmark CLI（--config）
├── configs/
│   └── month1.json          # 实验配置：6 实例 × 6 方法 × 3 seed + 3 组 SA 敏感性
├── artifacts/
│   ├── month1_refactored/   # 当前正式批次（月度报告与复现命令指向它）
│   ├── month1/              # 重构前正式批次
│   └── month1_initial/      # 首轮开发归档，不用于最终验收
├── notes/
│   ├── rules_cheatsheet.md  # 规则最优性速查卡
│   └── counterexamples.md   # 四个失效反例库
├── tests/
│   ├── test_models.py       # 模型与不可变性的单元测试
│   ├── test_parser.py       # 解析的单元测试
│   ├── test_validation.py   # 校验规则的单元测试
│   ├── test_objective.py    # 目标公式的手算对拍
│   ├── test_rules.py        # 单机规则 + 并行 LPT / 下界
│   ├── test_export.py       # Gantt 导出的单元测试
│   ├── test_month1.py       # 跨模块验收：手算、枚举、破坏排程、预算与复现
│   └── test_week1_review.py # Week 1 四个失效反例的可执行断言
├── examples/
│   ├── small_instance.json
│   ├── m1w1d2_exercises.py      # W1D2 实验作业（练习 1、练习 2）
│   ├── m1w1d3_pipeline.py       # W1D3 JSON→解析→校验→排程→指标
│   ├── m1w1d4_rules.py          # W1D4 四条单机规则对比基线
│   ├── m1w1d5_parallel.py       # W1D5 并行 LPT + 下界 + Gantt 导出
│   ├── m1w1d7_review.py         # W1D7 规则最优性表 + 四个失效反例
│   ├── m1w2d1_candidate.py      # W2D1 候选解表示与表示冗余
│   ├── m1w2d2_decoder.py        # W2D2 三条精确解码轨迹
│   ├── m1w2d3_neighborhoods.py  # W2D3 swap / insert / reassign 邻域
│   ├── m1w2d4_validator.py      # W2D4 九类破坏排程的诊断
│   ├── m1w2d5_generator.py      # W2D5 实例生成器与输入质量
│   ├── m1w2d6_verification.py   # W2D6 解码 / 枚举 / 可行性验收
│   ├── m1w2d7_review.py         # W2D7 表示、验证与测试边界复盘
│   ├── m1w3d1_random.py         # W3D1 搜索契约与 Random Search
│   ├── m1w3d2_first.py          # W3D2 First Improvement
│   ├── m1w3d3_best.py           # W3D3 Best Improvement 与扫描成本
│   ├── m1w3d4_multistart.py     # W3D4 Multi-start 与预算分配
│   ├── m1w3d5_sa.py             # W3D5 模拟退火与接受率
│   ├── m1w3d6_search.py         # W3D6 五种搜索方法对比
│   ├── m1w3d7_review.py         # W3D7 搜索方法复盘与默认参数
│   ├── m1w4d1_benchmark.py      # W4D1 benchmark 入口
│   ├── m1w4d2_instances.py      # W4D2 基准实例集与输入 SHA-256
│   ├── m1w4d3_schema.py         # W4D3 结果 schema 与可追溯性
│   ├── m1w4d4_reproduce.py      # W4D4 逐运行复现与核对
│   ├── m1w4d5_stats.py          # W4D5 统计表、收敛图与甘特图数据
│   ├── m1w4d6_sensitivity.py    # W4D6 温度敏感性分析
│   └── m1w4d7_review.py         # W4D7 月度复盘与验收对应
└── pyproject.toml            # pytest 配置
```

## 运行示例

无需安装本项目或手动设置环境变量。可以在 IDE 中直接“运行 Python 文件”，
也可以从仓库根目录执行。每天都有对应的实验脚本，命名规则为 `m{月}w{周}d{日}_主题.py`：

```powershell
python projects/01_scheduling_core/examples/m1w1d5_parallel.py     # 并行 LPT + 下界 + Gantt
python projects/01_scheduling_core/examples/m1w2d2_decoder.py     # 三条精确解码轨迹
python projects/01_scheduling_core/examples/m1w2d4_validator.py   # 九类破坏排程诊断
python projects/01_scheduling_core/examples/m1w3d5_sa.py          # 模拟退火与接受率
python projects/01_scheduling_core/examples/m1w4d5_stats.py       # 统计表与图表数据
```

完整脚本清单见上面的目录结构；每个脚本的预期输出写在对应的 Day 笔记里。

在项目目录下，两种方式都支持：

```powershell
cd projects/01_scheduling_core
python examples/m1w1d5_parallel.py
python -m examples.m1w1d5_parallel
```

直接运行时，脚本会根据自身位置自动将项目目录加入 `sys.path`，不依赖当前工作目录。
`-m` 按模块运行时，Python 会从当前工作目录查找 `scheduling_core`。

## 运行测试

在本目录下：

```bash
python -m pytest
```

## 设计约定

- 输入实体用 `@dataclass(frozen=True, slots=True)`，集合用 `tuple`，保证不可变。
- 关系使用稳定 ID（`Job.operation_ids`、`Operation.job_id`、`Operation.eligible_machine_ids`），不用对象嵌套。
- 输入与求解结果分离：`start_time / machine_id / completion_time` 等不属于输入模型，由 Schedule / Objective 层表达。
- Parser 只做读取/结构/类型转换，Validator 只做合法性判断，Objective 只做指标计算，三者各司其职。
- 领域模型与展示模型分离：`Schedule` 是最小结果表示，Gantt rows 是展示用的宽表（`scheduling_io/export.py` 派生 `job_id`、`duration` 等字段）。
- 时间单位由 Instance 统一约定；`due_date=None` 表示无交期。

## 命名约定

- 项目目录 `NN_slug` 中的 `NN` 对应月份：`01_scheduling_core` = 第 1 个月的项目。
- 稳定的工程代码（`models.py`、`parser.py`、`test_parser.py` 等）不带日期——它们属于项目本身，后续每天在这上面累加。
- 实验作业脚本用 `m{n}w{n}d{n}_主题.py` 命名，例如 `m1w1d5_parallel.py` = 第 1 月第 1 周第 5 天。
- 学习笔记按时间组织在 `Month_XX/Week_X/DayX.md`，代码按项目组织在 `projects/`，两者靠月份编号 + 本 README 对应。
