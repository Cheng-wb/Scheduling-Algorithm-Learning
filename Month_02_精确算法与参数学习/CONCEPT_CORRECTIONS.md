# 概念勘误与当前实现的阅读边界

[返回月度索引](README.md)

本次重写聚焦学习笔记，修正原笔记中的不严谨概括；没有修改求解器源码或重新生成历史实验。以下问题用于防止把旧输出、代码注释或实现限制当作一般理论。

| 旧表述或易误读点 | 正确理解 | 详细笔记 |
|---|---|---|
| LP 最优解总在极点 | 需要可行域结构及最优解存在条件；最优面可能包含非极点 | [W1D1](Week_1/Day1.md) |
| 全幺模只需基行列式为 ±1 | 所有方形子矩阵行列式都在 −1、0、1 中 | [W1D3](Week_1/Day3.md) |
| 一次返回整数说明一般 LP 都有整数解 | 运输、指派依靠特定结构与整数数据；额外约束可能破坏性质 | [W1D3](Week_1/Day3.md) |
| 单次后端返回状态证明所有版本对无界都报不可行 | 状态应按版本、原始日志和模型核查 | [W1D2](Week_1/Day2.md) |
| indicator 是当且仅当 | 通常是单向蕴含，反方向要额外建模 | [W2D2](Week_2/Day2.md) |
| regular 目标总存在非延迟最优排程 | 有释放时间时可能值得主动等待；H 的证明应固定顺序左移 | [W2D3](Week_2/Day3.md) |
| tight M 必然提高 LP bound | 可能收紧可行域而不改变该目标的松弛最优值 | [W2D3](Week_2/Day3.md) |
| 可选区间缺席时结束时间自动为零 | 缺席不自动固定辅助时间；求和设计需要另加条件 | [W3D1](Week_3/Day1.md) |
| CP-SAT 完全不支持浮点目标 | 整数变量与整数约束不排除现代版本的浮点线性目标 | [W3D1](Week_3/Day1.md) |
| 机器置换会改变总迟交 | 真正的同质机器重编号保留全部完工时间与迟交量 | [W4D1](Week_4/Day1.md) |
| 有效不等式就是已有可行解给出的目标截断 | 有效不等式对目标可行集的所有点成立；截断通常删除劣解但保留最优解 | [W4D1](Week_4/Day1.md) |
| 几次开关实验目标相等就证明强化普遍正确 | 实验用于发现错误；一般合法性需要数学论证 | [W4D1](Week_4/Day1.md) |
| 固定变量后的 OPTIMAL / bound 属于原问题 | 通常只属于受限子问题，不能冒充原问题最优证书 | [W4D2](Week_4/Day2.md) |
| SetHint 成功意味着 CBC 使用了初解 | 需核对后端与日志，不能只看调用完成 | [W4D2](Week_4/Day2.md) |
| 删除过滤必得最少条数冲突 | 完整可判定检查至多保证包含极小；UNKNOWN 会中断该证明 | [W4D3](Week_4/Day3.md) |
| 最小化下界绝不能上取整 | 严格整数目标的有效下界可上取整加强，但必须处理数值误差 | [W4D5](Week_4/Day5.md) |
| 所有 gap 都用同一个分母 | 项目与后端可能不同，须说明公式、单位及问题范围 | [W4D5](Week_4/Day5.md) |

## 哪些源码需要带着这些区别阅读

- [milp_scheduling.py](../projects/02_optimization_models/opt_models/milp_scheduling.py)：时间界仍须在具体假设下解释，注释中的“非延迟最优”不是一般定理。
- [strengthening.py](../projects/02_optimization_models/opt_models/strengthening.py)：总迟交的对称性判断、目标截断命名、固定变量后的界及取整注释需要按上述概念辨析。
- [cpsat_models.py](../projects/02_optimization_models/opt_models/cpsat_models.py)：时间和权重缩放是实现选择；舍入、解码和 bound 的换算都需验证。
- [result.py](../projects/02_optimization_models/opt_solvers/result.py)：工程状态词表并非全部是 CP-SAT 原生状态；`proven_optimal` 的状态判断本身不表达证书范围或容差终止细节。
- [diagnostics.py](../projects/02_optimization_models/opt_models/diagnostics.py)：应区分假设集合内极小冲突与整个系统的 IIS，并检查子求解是否真正得到结论。

这些是本次阅读中识别的边界，不表示已经完成源码修复或全部实现审计。学习数学定义以重写后的正文为准；复用代码或发布实验结论前，应针对实际用途处理相应实现问题。
