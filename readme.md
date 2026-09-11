# 通用调度算法与运筹优化 · 六个月学习框架

默认掌握 Python、数据结构与基本开发工具。以“问题定义 → 数学建模 → 求解算法 → 合法性校验 → 实验评测 → 项目交付”为主线，按 6 个月、24 个主题周组织。

## 学习入口

- [六个月总计划](LEARNING_PLAN.md)：范围、已有内容折算、工具与学习规则。
- [代码项目](projects/README.md)：长期项目边界、运行方式与后续扩展。
- [旧材料迁移表](MIGRATION.md)：原三周笔记和代码的新位置。

| 月份 | 任务大纲 |
| --- | --- |
| 第 1 月 · 第 01～04 周 | [调度基础、建模与搜索闭环](Month_01_调度基础与算法/README.md) |
| 第 2 月 · 第 05～08 周 | [运筹优化与精确求解](Month_02_运筹优化与数学建模/README.md) |
| 第 3 月 · 第 09～12 周 | [JSP / FJSP 生产调度](Month_03_JSP与FJSP生产调度/README.md) |
| 第 4 月 · 第 13～16 周 | [网络优化与车辆路径](Month_04_图优化与车辆调度/README.md) |
| 第 5 月 · 第 17～20 周 | [邻域设计与混合优化](Month_05_启发式与大规模优化/README.md) |
| 第 6 月 · 第 21～24 周 | [动态优化与综合交付](Month_06_动态调度与工程化/README.md) |

## 已有内容如何接续

原三周约折合三周主题学习量，重新分配到第一个月：规则与指标、MILP、基础搜索、评测四个主题。移除基础 Python 练习与旧版副本，保留整理后的算法；补齐 LP 松弛、限时求解语义和硬预算实验后进入后续内容。

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
projects/      # 可运行实验与持续扩展的领域项目
run.py         # 按项目隔离运行已有实验
LEARNING_PLAN.md # 六个月总计划
MIGRATION.md   # 旧位置与新位置映射
```

六个月都使用相同的 `Week_1`～`Week_4` 层级。月度 README 展开每周的学习、实践、实验与验收要求；每周 README 列出 Day 1～Day 7 的具体任务和交付标准。只保留已学内容的主题笔记，不预建每日笔记。命名参考 [AI_Infra_Learning](https://github.com/Cheng-wb/AI_Infra_Learning)。

## 运行已有项目

```powershell
python run.py --list
python run.py basics parallel_comparison
python run.py search integrated_demo
```

使用现有虚拟环境时将 `python` 换为 `.\.venv\Scripts\python.exe`。MILP/绘图依赖按 [基础项目说明](projects/scheduling_basics/README.md) 安装；搜索项目仅依赖标准库。未来月份先提供明确任务与项目说明，未实现的算法不放空壳，也不出现在可运行列表。
