# 01_scheduling_core：调度核心与实验框架（M1）

[学习路线](../../LEARNING_PLAN.md)

对应第 1 月（M1）。本目录逐步实现 M1 的调度核心：统一输入模型、经典规则、解码器、独立验证器、目标评估器与可复现 Benchmark。

## 当前进度

Week 1 Day 4 —— 单机 SPT/EDD/WSPT/LPT 规则与释放时间处理。

## 目录结构

```text
01_scheduling_core/
├── scheduling_core/
│   ├── __init__.py
│   ├── models.py        # 不可变输入数据模型
│   ├── parser.py        # JSON → Instance
│   ├── validation.py    # 输入校验（fail-fast）
│   ├── schedule.py      # 排程结果的最小表示
│   ├── objective.py     # 统一目标评估器
│   └── rules.py         # 单机 SPT/EDD/WSPT/LPT 规则 + 释放时间处理
├── tests/
│   ├── test_models.py       # 模型与不可变性的单元测试
│   ├── test_parser.py       # 解析的单元测试
│   ├── test_validation.py   # 校验规则的单元测试
│   ├── test_objective.py    # 目标公式的手算对拍
│   └── test_rules.py        # 单机规则的顺序/目标/释放时间/错误处理
├── examples/
│   ├── small_instance.json      # 小示例实例（2 机器 / 2 作业 / 3 工序）
│   ├── m1w1d2_exercises.py      # M1W1D2 实验作业（练习 1、练习 2）
│   ├── m1w1d3_pipeline.py       # M1W1D3 实验：JSON→解析→校验→排程→指标
│   └── m1w1d4_rules.py          # M1W1D4 实验：四条单机规则对比基线
└── pyproject.toml            # pytest 配置
```

## 运行示例

无需安装本项目或手动设置环境变量。可以在 IDE 中直接“运行 Python 文件”，
也可以从仓库根目录执行：

```powershell
python projects/01_scheduling_core/examples/m1w1d3_pipeline.py
python projects/01_scheduling_core/examples/m1w1d4_rules.py
```

在项目目录下，两种方式都支持：

```powershell
cd projects/01_scheduling_core
python examples/m1w1d3_pipeline.py
python -m examples.m1w1d3_pipeline
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
- 输入与求解结果分离：`start_time / assigned_machine / completion_time` 等不属于输入模型，由 Schedule / Objective 层表达。
- Parser 只做读取/结构/类型转换，Validator 只做合法性判断，Objective 只做指标计算，三者各司其职。
- 时间单位由 Instance 统一约定；`due_date=None` 表示无交期。

## 命名约定

- 项目目录 `NN_slug` 中的 `NN` 对应月份：`01_scheduling_core` = 第 1 个月的项目。
- 稳定的工程代码（`models.py`、`parser.py`、`test_parser.py` 等）不带日期——它们属于项目本身，后续每天在这上面累加。
- 实验作业脚本用 `m{n}w{n}d{n}_主题.py` 命名，例如 `m1w1d3_pipeline.py` = 第 1 月第 1 周第 3 天。
- 学习笔记按时间组织在 `Month_XX/Week_X/DayX.md`，代码按项目组织在 `projects/`，两者靠月份编号 + 本 README 对应。
