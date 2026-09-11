# 通用调度算法与运筹优化 · 六个月学习框架

默认掌握 Python、数据结构与基本开发工具。以“问题定义 → 数学建模 → 求解算法 → 合法性校验 → 实验评测 → 项目交付”为主线，按 6 个月、24 个主题周组织。

## 学习入口

- [六个月总计划](LEARNING_PLAN.md)：学习目标、知识主线、工具与任务安排。
- [代码项目](projects/README.md)：长期项目边界、运行方式与后续扩展。

| 月份 | 任务大纲 |
| --- | --- |
| 第 1 月 · 第 01～04 周 | [调度基础、建模与搜索闭环](Month_01_调度基础与算法/README.md) |
| 第 2 月 · 第 05～08 周 | [运筹优化与精确求解](Month_02_运筹优化与数学建模/README.md) |
| 第 3 月 · 第 09～12 周 | [JSP / FJSP 生产调度](Month_03_JSP与FJSP生产调度/README.md) |
| 第 4 月 · 第 13～16 周 | [网络优化与车辆路径](Month_04_图优化与车辆调度/README.md) |
| 第 5 月 · 第 17～20 周 | [邻域设计与混合优化](Month_05_启发式与大规模优化/README.md) |
| 第 6 月 · 第 21～24 周 | [动态优化与综合交付](Month_06_动态调度与工程化/README.md) |

## 目录

```text
Month_01_调度基础与算法/
Month_02_运筹优化与数学建模/
Month_03_JSP与FJSP生产调度/
Month_04_图优化与车辆调度/
Month_05_启发式与大规模优化/
Month_06_动态调度与工程化/
    README.md  # 每个月的主题、目标与里程碑
    Week_1/README.md
    Week_2/README.md
    Week_3/README.md
    Week_4/README.md
projects/      # 后续领域项目的任务框架及实验注册表
run.py         # 按周隔离运行实验
LEARNING_PLAN.md # 六个月总计划
```

六个月都使用相同的 `Week_1`～`Week_4` 层级。月度 README 展开每周的学习、实践、实验与验收要求；每周 README 列出 Day 1～Day 7 的具体任务和交付标准。笔记按天放在各周 `note/`，代码与每日实验也在相应周目录。

## 运行实验

```powershell
python run.py --list
python run.py week1 day6_bounds
python run.py week3 day7_integration
```

使用仓库虚拟环境时将 `python` 换为 `.\.venv\Scripts\python.exe`。MILP/绘图依赖按 [基础项目说明](Month_01_调度基础与算法/Week_2/README.md) 安装；搜索项目仅依赖标准库。未来月份先提供明确任务与项目说明，未实现的算法不放空壳，也不出现在可运行列表。
