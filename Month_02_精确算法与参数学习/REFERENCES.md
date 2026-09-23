# 第二个月阅读资料与使用顺序

[返回月度索引](README.md)

## 教材：按主题选读

| 资料 | 本月读什么 | 对应笔记 |
|---|---|---|
| Hillier、Lieberman：Introduction to Operations Research | 线性规划、对偶、敏感性、运输与指派、整数规划 | Week 1、Week 2 |
| H. Paul Williams：Model Building in Mathematical Programming，第 5 版 | 第 3、4、6 章补充 LP；第 8–10 章重点练整数建模 | Week 1、Week 2 |
| Dominik Krupke：The CP-SAT Primer | 基础建模、高级建模、参数、日志、代码组织与 benchmark | Week 3、Week 4 |

书籍各版本章节编号可能不同，Hillier 按主题查目录；Williams 上述编号对应第 5 版。无需本月通读整本。

- [Hillier / Lieberman 出版社书目与目录](https://www.mheducation.com/highered/product/Introduction-to-Operations-Research-Hillier.html)
- [Williams 第 5 版出版社目录](https://bcs.wiley.com/he-bcs/Books?action=contents&bcsId=8095&itemId=1118443330)
- [CP-SAT Primer 免费在线全文](https://d-krupke.github.io/cpsat-primer/)

## 官方资料：遇到接口语义时查阅

- [CP-SAT 状态与基础用法](https://developers.google.com/optimization/cp/cp_solver)：Week 3 Day 1、Day 5。
- [Google Job Shop 示例](https://developers.google.com/optimization/scheduling/job_shop)：Week 3 Day 3，先读约束再读代码。
- [OR-Tools 官方模型协议](https://github.com/google/or-tools/blob/stable/ortools/sat/cp_model.proto)：核对可选约束、区间和浮点目标等细节；注意底层协议与高级 API 的职责不同。
- [Gurobi 约束与 indicator 定义](https://docs.gurobi.com/projects/optimizer/en/current/concepts/modeling/constraints.html)：Week 2 Day 2，核对单向逻辑。
- [Gurobi 数值容差与缩放](https://docs.gurobi.com/projects/optimizer/en/current/concepts/numericguide/tolerances_scaling.html)：Week 1 Day 6、Week 4 Day 3。
- [Gurobi MIP start](https://doc.gurobi.com/projects/optimizer/en/current/features/warmstart.html)：Week 4 Day 2，理解初解及其开销。
- [Gurobi 不可行性分析](https://docs.gurobi.com/projects/optimizer/en/current/features/infeasibility.html)：Week 4 Day 3，区分冲突诊断与可行性松弛。

这些资料用于定义和方法学习。项目使用的 GLOP、CBC、CP-SAT 后端并不共享所有功能；Gurobi 的 API 和行为不能直接当作 CBC 的能力承诺。在线文档可能更新，运行时以锁定的依赖版本为准。

## 读完一节后做什么

先不看源码写一遍模型，再做一个可手算例子；运行项目对应示例后，解释每个变量和约束。若只是复现输出而不能解释其条件，应回到正文中的推导，暂不增加模型复杂度。
