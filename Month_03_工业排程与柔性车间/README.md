# 第 3 月：JSP / FJSP 与工业级排程

对齐依据：[全年计划](../LEARNING_PLAN.md)「M3」月度周次。周主题与顺序以全年计划为准，下面的任务与验收是执行细化；周号仅使用本月 Week 1–4。

本月目标：从「算法题」转向「真实生产调度」，把 Flow Shop / Job Shop 推进到 Flexible Job Shop，并叠加真实业务约束。

## 教材正文

如果已经学过 M1 的输入模型和 M2 的 CP-SAT 基础，先按下表顺序阅读教材。每章从问题定义进入手算，再连接到 M3 项目代码与每日实验；章末有练习和解答。每日笔记仍可用于查看更细的推导与实际运行记录。

| 章节 | 内容 | 对应周次 |
|---|---|---|
| [第 0 章：从 M1 到工业排程](教材/00_从M1到工业排程.md) | Flow Shop、JSP、FJSP 的边界；数据与排程分层 | 预备 |
| [第 1 章：流水车间与构造规则](教材/01_流水车间与构造规则.md) | Johnson 规则、NEH、时刻表手算 | Week 1 |
| [第 2 章：作业车间与析取图](教材/02_作业车间与析取图.md) | 工艺边、机器边、关键路径与 JSP 模型 | Week 1 |
| [第 3 章：柔性车间的两维决策](教材/03_柔性车间的两维决策.md) | 选机、拓扑序、插入式解码与派工 | Week 2 |
| [第 4 章：精确模型与独立枚举](教材/04_精确模型与独立枚举.md) | FJSP CP-SAT、oracle、状态与上下界 | Week 2 |
| [第 5 章：交期换型与机器日历](教材/05_交期换型与机器日历.md) | 释放、迟交、多目标、换型、维护 | Week 3 |
| [第 6 章：资质资源与锁定工序](教材/06_资质资源与锁定工序.md) | 机器资质、工人、工序族、WIP、紧急订单 | Week 4 |
| [第 7 章：综合实训与核验](教材/07_综合实训与核验.md) | 完整算例、报告口径与批次复核 | 月末 |

阅读时先独立完成章末小题，再对照解答；需要重跑代码时按[项目指南](../projects/03_industrial_fjsp/PROJECT_GUIDE.md)配置环境和选择实验入口。

## 周计划

| 周次 | 全年周主题 | 学习内容 | 编码与实验任务 | 验收 |
|---|---|---|---|---|
| Week 1 | Flow Shop 与 JSP | Flow Shop、Johnson 规则、NEH；JSP 析取图、关键路径、关键块 | 读 FT/LA/ABZ 标准实例；实现 Flow Shop baseline 与 CP-SAT JSP；输出甘特图 | 独立验证器通过；提交关键路径与瓶颈分析 |
| Week 2 | FJSP | FJSP 的机器选择、按机器变化的工时、机器指派 | 实现 FJSP Decoder / Validator / CP-SAT / 启发式 | 比较随机指派、最短工时机器、负载均衡、CP-SAT |
| Week 3 | 工业约束 I（release/due/setup/calendar/maintenance） | 释放时间、交期、加权迟交、sequence-dependent setup、机器日历、计划维护 | 目标从 min Cmax 扩展为 α·Cmax + β·总迟交 + γ·setup 成本 | 给出多目标归一化与权重敏感性分析 |
| Week 4 | 工业约束 II（qualification/worker/batching/WIP/urgent order） | 机器资质、次生资源、工人、工装、批处理、WIP、锁定工序、紧急订单 | 建立 Order/ProcessRoute/Operation/Machine/Calendar/Qualification/Resource 数据模型 | 至少 5 种真实约束、JSON 输入输出、多目标 KPI |

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
