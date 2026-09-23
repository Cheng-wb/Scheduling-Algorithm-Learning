# Week 2 · Day 2：逻辑约束与线性化：先判断方向，再写不等式

> **先读教材正文**：[第 3 章：0-1 规划](../教材/03_零一规划与逻辑建模.md)、[第 4 章：MILP 与调度](../教材/04_混合整数规划与调度.md)。本页用于读后的复习和项目实验，不能代替零基础教材中的完整推导。

[月度索引](../README.md) · [本周知识主线](../week2.md) · [前一天](Day1.md) · [后一天](Day3.md)

## 1. 单向蕴含与等价必须分开

指示约束 $z=1\Rightarrow a^Tx\le b$ 表示 z 为真时约束生效。z 为假时，这条指示约束不再限制 x；**不表示 $a^Tx\le b$ 必须为假**。原生 indicator 和 CP-SAT 的 `OnlyEnforceIf` 都不能直接理解为“当且仅当”。[Gurobi 指示约束定义](https://docs.gurobi.com/projects/optimizer/en/current/concepts/modeling/constraints.html)

若真的需要 $z=1\Leftrightarrow x\le5$，且 x 是整数，还应表达 $z=0\Rightarrow x\ge6$。连续变量的否定是严格不等式 $x>5$，普通闭线性约束不能直接精确表达；必须结合业务精度重新定义边界。

## 2. Big-M 从禁用分支推出来

要表达 $z=1\Rightarrow a^Tx\le b$，可写：

$$a^Tx\le b+M(1-z).$$

z=1 时恢复原式；z=0 时应不排除允许的 x，因此需要：

$$M\ge\max_{x\in X}(a^Tx-b).$$

这里 X 是其余约束和有效变量界定义的区域。利用变量上下界得到一个安全上界通常比精确求这个最大值便宜。M 是推导结果，不是“尽量选一个很大的数”。

排序式 $S_k\ge C_j-M_{jk}(1-y)$ 中，若 $C_j\le U_j,S_k\ge L_k$，可取 $M_{jk}=\max(0,U_j-L_k)$。

## 3. 二元变量乘连续变量

设 $w=zx,z\in\{0,1\},L\le x\le U$，其精确线性化为：

$$Lz\le w\le Uz,$$
$$x-U(1-z)\le w\le x-L(1-z).$$

代入 z=0：前两界强制 w=0，其余约束等价于已知变量界；代入 z=1：后两界强制 w=x，前两界仍符合 x 的范围。因此两种离散情况都被准确表达。

如果 x 可以为负，不能随意用只适用于 $L=0$ 的简化式。若 z 也连续，这四条通常只构成双线性项的凸松弛，而非 w=zx 的精确表达。

## 4. 逻辑不一定需要 Big-M

二元变量 a、b 满足“a 为真则 b 为真”，直接写 $a\le b$。恰好一个选择为 $\sum_i z_i=1$；至多一个为 $\sum_i z_i\le1$；两个二元量的乘积 $w=ab$ 可写 $w\le a,w\le b,w\ge a+b-1,w\ge0$。

先找这些简单线性表达，再考虑 Big-M。原生 indicator 也值得尝试，但其后端处理和性能不是统一保证，仍要比较模型规模、界和耗时。

## 5. 实验与自测

给每个逻辑约束写一个真值表，并在小范围内枚举检查“该允许的点未被删除、该禁止的点确实被禁止”。随机测试有帮助，但不替代上面的分情况证明。

1. $z=0$ 时原不等式可以碰巧成立吗？可以。
2. $U_j=20,L_k=7$，排序式可取多少 M？13。
3. $x\in[-2,5]$ 时，线性化中的下界可以写成 $w\ge0$ 吗？不能，z=1、x=-2 时 w 必须是 -2。

## 配套代码入口

从仓库根目录运行（需先按[项目指南](../../projects/02_optimization_models/PROJECT_GUIDE.md)配置环境）：

```powershell
python projects/02_optimization_models/examples/m2w2d2_big_m_linearization.py
```

[阅读示例源码](../../projects/02_optimization_models/examples/m2w2d2_big_m_linearization.py)。先完成正文手算，再用脚本核对项目实例；记录实例、状态、约束检查与目标，不把一次运行耗时作为固定结论。实现与数学语义的区别见[概念勘误](../CONCEPT_CORRECTIONS.md)。
