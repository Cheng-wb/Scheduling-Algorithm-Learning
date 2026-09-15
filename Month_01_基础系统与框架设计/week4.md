# Week 4 周报：Benchmark 与科研式实验

## 本周内容

JSON 配置、六个保存输入、162 次运行记录、结构化结果/排程/轨迹、均值/中位数/标准差汇总、质量/收敛/甘特图、SA 敏感性分析和逐运行复现脚本。

笔记：[Day1](Week_4/Day1.md) · [Day2](Week_4/Day2.md) · [Day3](Week_4/Day3.md) · [Day4](Week_4/Day4.md) · [Day5](Week_4/Day5.md) · [Day6](Week_4/Day6.md) · [Day7](Week_4/Day7.md)。

## 验证与结论

主实验 108 次＋敏感性 54 次，正式批次零失败；失败注入测试确认异常不会被当作零目标计入平均。tiny_single 的枚举 optimum=36，tiny_parallel optimum=38。其他实例仅记录本批次 best-known。

敏感性没有统一赢家：single_12 快冷却均值较好，parallel_24 低温均值较好，routes_12 高温明显变差。样本量小且未留独立测试集，不能把这些观察写成普遍参数建议。

## 复现入口

[项目 README](../projects/01_scheduling_core/PROJECT_GUIDE.md) 提供安装、测试、基准、逐次复现命令；[MONTH1_REPORT.md](MONTH1_REPORT.md) 提供最终模型、数据、结果与局限。

## 后续学习

M2 加入求解器 bound/optimum 证据，并继续复用同一验证器。本月不涉及 MILP/CP-SAT，不把有限预算启发式的 best-known gap 写成求解器 gap。
