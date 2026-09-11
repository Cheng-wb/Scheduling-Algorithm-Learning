# 第 3 月：JSP / FJSP 与工业级排程

本月目标：从「算法题」转向「真实生产调度」，把 Flow Shop / Job Shop 推进到 Flexible Job Shop，并叠加真实业务约束。

## 周计划

| 周次 | 学习内容 | 编码与实验任务 | 验收 |
|---|---|---|---|
| Week 1 | Flow Shop、Johnson 规则、NEH；JSP 析取图、关键路径、关键块 | 读 FT/LA/ABZ 标准实例；实现 Flow Shop baseline 与 CP-SAT JSP；输出甘特图 | 独立验证器通过；提交关键路径与瓶颈分析 |
| Week 2 | FJSP 的机器选择、按机器变化的工时、机器指派 | 实现 FJSP Decoder / Validator / CP-SAT / 启发式 | 比较随机指派、最短工时机器、负载均衡、CP-SAT |
| Week 3 | 释放时间、交期、加权迟交、sequence-dependent setup、机器日历、计划维护 | 目标从 min Cmax 扩展为 α·Cmax + β·总迟交 + γ·setup 成本 | 给出多目标归一化与权重敏感性分析 |
| Week 4 | 机器资质、次生资源、工人、工装、批处理、WIP、锁定工序、紧急订单 | 建立 Order/ProcessRoute/Operation/Machine/Calendar/Qualification/Resource 数据模型 | 至少 5 种真实约束、JSON 输入输出、多目标 KPI |

## 每周 7 天执行清单

| 天 | 固定任务 |
|---|---|
| Day 1 | 阅读本周理论，写出变量、约束或算法流程草图 |
| Day 2 | 完成最小可运行代码，并准备一个手算小例子 |
| Day 3 | 加入边界条件和输入校验，记录一次运行结果 |
| Day 4 | 扩展到 10 个以上实例，保存参数与随机种子 |
| Day 5 | 与基线或枚举结果对拍，定位差异并修复 |
| Day 6 | 绘制指标图，分析质量、速度和失败案例 |
| Day 7 | 写一页周报：结论、证据、问题、下周改进 |

每周的 Day 2–Day 6 必须围绕上方周计划主题完成一个可运行实验，不能只提交阅读笔记。

## 月末交付

**Project 3：Industrial FJSP Solver v1**——CP-SAT baseline + 启发式 baseline + 独立验证器 + 甘特图 + 多目标 KPI + JSON 输入输出。
