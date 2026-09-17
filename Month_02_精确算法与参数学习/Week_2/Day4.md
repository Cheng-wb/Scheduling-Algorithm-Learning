# Day 4：手工走一遍 branch-and-bound，再读真实求解器的日志

> 当日主题：用 20 行伪代码自己实现一次 DFS branch-and-bound，然后把「incumbent / best bound / gap / node / presolve」这五个名词逐一对上真实输出
> 当日产出：**一棵可打印的搜索树** + **CBC 日志的逐行解读** + 一份「日志数字与 `SolveResult` 对账」的记录
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 写出 branch-and-bound 的五个基本动作：选节点、解节点 LP、剪枝判断、分支、更新 incumbent。
2. 说出三种剪枝各自的触发条件（按界剪枝、按不可行剪枝、按整数解更新 incumbent）。
3. 区分 `incumbent`、`best bound`、`gap`：谁是可交出去的答案、谁是搜索的下界、谁在衡量「还差多远」。
4. 说清「`node` 数」与「树的形状」的关系，并解释为什么节点数与叶节点数可以一增一减。
5. 解释 `presolve` 在日志里的位置与作用，并说明它为什么会让「根节点界」与「纯 LP 松弛界」不相等。
6. 读出真实 CBC 日志中的阶段顺序：presolve → 根节点 LP → 割平面 → 搜索 → 搜索结束。
7. 说清「日志里的数字必须与 `SolveResult` 对账」这条纪律，并能举出当天日志里出现的不一致数字。
8. 说清为什么「初始 incumbent 的质量」不改变最优值，却会改变搜索过程。

---

## 2. 为什么 Day 4 要自己走一遍

Day 1–3 得到的是一个精确的模型，以及一个残酷的观测：这个模型的 LP relaxation 在 `ΣTj` 上的界是 0。把界为 0 的模型交给求解器，求解器究竟在做什么？如果不知道，后面所有关于「哪个 formulation 更快」的比较都只能靠感觉。

所以今天不用求解器，用 20 行伪代码自己实现一次：

```text
为什么值得自己写一遍：
  1. 「界」这个概念只有在你亲手用它剪掉一个节点之后才变得具体；
  2. incumbent / best bound / gap 三者的关系，在教科书上是一段文字，
     在自己打印出的表格里是三个同步变化的列；
  3. 真实求解器还会做 presolve、割平面、强分支这些「额外动作」，
     先在纯手工版本里把主干走完，才知道那些额外动作在主干上加了什么。
```

知识链的位置：

```text
Day 3  量出这个模型的松弛强度：root bound = 0
Day 4  branch-and-bound 就是「界为 0 时该怎么办」的答案      ← 今天
Day 5  换一种 formulation，把界抬起来
Day 6  比较两种做法的总账
```

---

## 3. 概念：五个名词的定义与关系

### 3.1 定义

| 名词 | 定义 | 本日实例上的首次取值 |
|---|---|---|
| `incumbent` | 目前找到的最好**可行解**的目标值（最小化问题取最小） | hand 实例：SPT 给的 `1` |
| `best bound` | 所有未探索节点里最小的**下界**（即「还没排除的最好可能」） | hand 实例根节点：`0` |
| `gap` | `(incumbent - best bound) / |incumbent|`，衡量还有多远才能证明最优 | 根节点：`1.00` |
| `node` | 搜索树上一个「固定了部分决策」的子问题 | hand 实例共 `7` 个 |
| `presolve` | 求解前对模型的化简：删冗余行、收紧变量界、固定变量 | CBC 把 64 行 44 列缩到 47 行 31 列 |

三者之间的关系只有一句话，但它是 B&B 的全部：

```text
best bound <= 真最优 <= incumbent
```

- `incumbent` 是**可以交出去的答案**（它是真可行解的目标值）；
- `best bound` 是**不能交出去的答案**（它只是「还没被排除的最好可能」）；
- 两者相等时 `gap = 0`，搜索结束，最优性得到证明；
- `gap > 0` 时说明还有节点没探完，「目前最好的解」与「可能存在的更好解」之间的空间没有关闭。

**这就是 Day 3 的界为 0 意味着什么**：搜索从一个「可能的最好可能是 0」的状态出发，必须自己爬出 0 到 85 这一段距离，才能证明 85 是最优的。

### 3.2 伪代码

```text
DFS branch-and-bound（最小化）：

  incumbent <- +∞                     # 或用启发式给一个初始可行解
  stack     <- [根节点（所有 x 都自由）]
  while stack 非空:
      node <- stack.pop()
      (bound, values) <- 解 node 的 LP relaxation（已固定的 x 钉住）
      if LP 不可行:                    # 剪枝一：不可行
          continue
      if bound >= incumbent:           # 剪枝二：按界
          continue
      if 所有 x 已定（或 LP 解为整数）:
          schedule <- 由完整顺序构造排程   # 剪枝三：得到整数解
          if 目标值 < incumbent:
              incumbent <- 目标值
          continue
      key <- 选一个取分数值的 x
      stack.push({ fixed ∪ key=0 })
      stack.push({ fixed ∪ key=1 })
```

三处细节值得单独点出：

1. **节点 LP 用的是「已固定决策 + 其余放松」**：每往下一层，就多钉住一个 `x`，LP 的可行域随之变小、界随之变高。分支的过程就是「界被逐步抬高」的过程。
2. **剪枝二用的是 `>=`**：`bound >= incumbent` 时可以安全剪掉，因为该节点的一切后代的目标值都不会小于 `bound`，而 `bound` 已经不优于现有的可行解。反过来若写成 `>`，搜索会多探一些「恰好等于 incumbent」的节点，不影响正确性但变慢。
3. **`x` 先分支哪一个**：本日脚本选「离 `0.5` 最近」的那个（即 `min(x, 1-x)` 最大的），这是最朴素的分支策略；工业求解器会做伪代价、强分支等选择（Day 4 的日志里会看到 `strong branching` 这个词）。

---

## 4. 手算：两个小实例的完整搜索树

### 4.1 3 job 实例：SPT 给出的 incumbent 恰好最优

实例是 Day 1 的 `hand3`（`A: p=3, d=4`；`B: p=2, d=2`；`C: r=5, p=4, d=10`），真最优 `ΣTj = 1`。M1 的 `spt` 规则给出的排程也恰好是 `ΣTj = 1`，于是初始 `incumbent = 1`。

手工 B&B 的追踪（整理自第 7 节的实际输出）：

```text
node  深度  固定决策            LP 界   incumbent   best bound   gap   动作
   1     0  (根节点)             0.000        1           0       1.00  分支：x(A,C)=0.214
   2     1  A<C                 0.000        1           0       1.00  分支：x(B,C)=0.214
   3     2  A<C B<C             0.000        1           0       1.00  分支：x(A,B)=0.048
   4     3  A<B A<C B<C         3.000        1           1       0.00  剪枝：界 >= incumbent
   5     3  B<A A<C B<C         1.000        1           1       0.00  剪枝：界 >= incumbent
   6     2  A<C C<B             9.000        1           1       0.00  剪枝：界 >= incumbent
   7     1  C<A                 8.000        1           1       0.00  剪枝：界 >= incumbent
节点总数 7，其中叶节点 0，按界剪枝 4，按不可行剪枝 0
```

有三处值得停下来看：

- **根节点的界是 0**（与 Day 3 测到的一致），`gap = 1.00`：搜索开始时「什么都不排除」；
- **往下固定一个顺序，界就从 0 跳到 1 以上**：节点 4 的界是 3、节点 5 是 1、节点 6 是 9、节点 7 是 8。顺序一旦定下来，LP 就不能再让所有工序重叠了；
- **`叶节点 0`**：整棵树被「界 >= incumbent」剪完，**一次整数解都没有自己找**。原因是初始 incumbent 恰好等于最优值，而每个分支节点的界都 ≥ 1 = incumbent。

同一实例、同一目标，把初始 incumbent 拿掉（从 `+∞` 开始）再跑一遍：

```text
node  深度  固定决策            LP 界   incumbent   best bound   gap   动作
   1     0  (根节点)             0.000        无          无        -   分支：x(A,C)=0.214
   2     1  A<C                 0.000        无          无        -   分支：x(B,C)=0.214
   3     2  A<C B<C             0.000        无          无        -   分支：x(A,B)=0.048
   4     3  A<B A<C B<C         3.000        3           3       0.00  整数解 3，更新 incumbent
   5     3  B<A A<C B<C         1.000        1           1       0.00  整数解 1，更新 incumbent
   6     2  A<C C<B             9.000        1           1       0.00  剪枝：界 >= incumbent
   7     1  C<A                 8.000        1           1       0.00  剪枝：界 >= incumbent
节点总数 7，其中叶节点 2，按界剪枝 2，按不可行剪枝 0
```

**两次的节点数完全相同（都是 7），叶节点从 0 变成 2。** 这个对比把 incumbent 的角色说透了：

> `incumbent` 不做任何「算得更准」的事，它只是**把剪枝的门槛抬高**。没有 incumbent 时门槛是 `+∞`（等于没有门槛），前两个到达底层的节点必须自己找出整数解来建立 incumbent（`3`，然后 `1`），之后剩下的节点才被剪掉。

### 4.2 4 job 实例：界真的剪掉了东西

实例 `four_jobs`（`r = [0,2,5,1]`、`p = [3,4,2,5]`），目标换成 `ΣCj`，真最优 `33`（由 24 个加工顺序独立枚举得到）。

与 `ΣTj` 不同，`ΣCj` 的 LP 界是有内容的：根节点的界就是 `Σ_j (r_j + p_j) = 22`，也就是「只有释放时间、没有机器容量」的理想值（Day 3 第 5 节的结论在这里再次出现）。搜索从 `22` 出发，实际输出前 10 行如下（完整输出见第 7 节）：

```text
  node  深度  节点上的固定决策                       LP 界    incumbent   best bound   gap   动作
     1     0  (根节点)                              22.000         33         22   0.33   分支：x(J0,J2)=0.092
     2     1  J0<J2                              22.000         33         22   0.33   分支：x(J0,J1)=0.079
     3     2  J0<J1 J0<J2                        23.000         33         23   0.30   分支：x(J0,J3)=0.079
     4     3  J0<J1 J0<J2 J0<J3                  25.000         33         25   0.24   分支：x(J1,J3)=0.066
     5     4  J0<J1 J0<J2 J0<J3 J1<J3            29.000         33         29   0.12   分支：x(J2,J3)=0.092
     6     5  J0<J1 J0<J2 J0<J3 J1<J3 J2<J3      29.000         33         29   0.12   分支：x(J1,J2)=0.053
     7     6  J0<J1 J0<J2 J0<J3 J1<J2 J1<J3 J2<J3   33.000         33         33   0.00   剪枝：界 >= incumbent
     8     6  J0<J1 J0<J2 J0<J3 J2<J1 J1<J3 J2<J3   37.000         33         33   0.00   剪枝：界 >= incumbent
     9     5  J0<J1 J0<J2 J0<J3 J1<J3 J3<J2      36.000         33         33   0.00   剪枝：界 >= incumbent
    10     4  J0<J1 J0<J2 J0<J3 J3<J1            30.000         33         30   0.09   分支：x(J2,J3)=0.039
  …… 其余 13 行省略（完整节点数见下方统计）
  节点总数 23，其中叶节点 0，按界剪枝 11，按不可行剪枝 1
```

界在这里做了一件看得见的事：随着决策被逐个固定，界从 `22` 一路抬到 `25`、`29`、`33`；一旦界到 `33 = incumbent`，节点立刻被剪。**`gap` 这一列从 `0.33` 一路降到 `0.00`，就是「搜索把不确定性关闭」的过程**。

手工 B&B 得到的最优值 `33`，与独立枚举 24 个顺序得到的 `33` 一致 —— 手工实现与独立穷举互为对拍。

---

## 5. 实现：节点 LP 与搜索循环

脚本 [m2w2d4_branch_and_bound_walk.py](../../projects/02_optimization_models/examples/m2w2d4_branch_and_bound_walk.py) 里三块关键实现：

| 函数 | 职责 |
|---|---|
| `node_lp(instance, objective_name, fixed)` | 解一个节点的 LP：`fixed` 里的 `x` 钉成常数，其余 `x ∈ [0,1]` |
| `schedule_from_orders(instance, orders)` | 把「完整顺序」翻译成一个真实排程（用于更新 incumbent） |
| `walk(instance, objective_name, initial)` | DFS 主循环，返回逐节点的 trace、最终 incumbent 与统计 |

节点 LP 里用的是一个**足够大的常数** `M = n·H`：

```python
big_m = len(instance.jobs) * horizon
solver.Add(start[second.id] >= start[first.id] + p_first - big_m * (1 - x))
solver.Add(start[first.id] >= start[second.id] + p_second - big_m * x)
```

这里可以放心用 loose 的界，理由正是 Day 2 的结论：**只要 `M` 合法，模型就是精确的**；`M` 的紧度只影响界爬得多快、不影响界的合法性。节点 LP 的职责是提供一个**有效下界**，而合法性由时间界保证。

`walk` 的统计口径也要说清，因为它直接决定了怎么读输出：

```text
nodes              = 被处理过的节点数（包含根节点）
leaves             = 得到整数解的节点数（可能更新 incumbent，也可能没有）
pruned_by_bound    = 因 bound >= incumbent 被剪的节点数
pruned_infeasible  = 因节点 LP 不可行被剪的节点数
```

在一个「每个分支节点恰好长出两个子节点」的搜索树里，这些数满足 `叶类节点数 = 分支节点数 + 1`：本日 3 job 实例是 `4 = 3 + 1`（有 incumbent）与 `4 = 3 + 1`（无 incumbent），4 job 实例是 `12 = 11 + 1`。**这条恒等式是检查统计口径没写错的一个快速办法。**

---

## 6. 从手工版本到真实求解器：中间还差什么

手工版本只有「节点 LP + 剪枝」，真实求解器在同样的主干上还加了三类动作：

```text
presolve      建模后先化简：删冗余行、收紧变量界、固定变量
              → 日志里的「Presolve 64 (0) rows, 44 (-1) columns ...」
割平面        根节点（以及某些节点）上切掉一批「整数解绝不会经过」的分数区域
              → 日志里的「At root node, 19 cuts changed objective from 47 to 65」
强分支/伪代价  选择分支变量与分支方向的高级策略
              → 日志里的「Integer solution of 115 found by strong branching」
```

这三类动作都会让「根节点的界」变得比「纯 LP 松弛界」高。**这是第 7 节里最容易读错的一处**：日志里的根节点界 `65` 与 Day 3 量到的纯松弛界 `0` 不是同一个量，后者是「一条割都没有」时的界。

---

## 7. 实验：`m2w2d4_branch_and_bound_walk`

脚本：[m2w2d4_branch_and_bound_walk.py](../../projects/02_optimization_models/examples/m2w2d4_branch_and_bound_walk.py)。

在项目目录 `projects/02_optimization_models` 下运行：

```bash
python -m examples.m2w2d4_branch_and_bound_walk
```

实际输出（原样粘贴，日志段为关键词过滤后的前 20 行）：

```text
=== 手推 branch-and-bound，再读求解器的数字 ===

== 1. hand 实例（3 job，ΣTj 真最优 1）：DFS branch-and-bound 全过程 ==
  初始 incumbent 来自 M1 的 SPT 规则：ΣTj = 1

  node  深度  节点上的固定决策                       LP 界    incumbent   best bound   gap   动作
     1     0  (根节点)                               0.000          1          0   1.00   分支：x(A,C)=0.214
     2     1  A<C                                 0.000          1          0   1.00   分支：x(B,C)=0.214
     3     2  A<C B<C                             0.000          1          0   1.00   分支：x(A,B)=0.048
     4     3  A<B A<C B<C                         3.000          1          1   0.00   剪枝：界 >= incumbent
     5     3  B<A A<C B<C                         1.000          1          1   0.00   剪枝：界 >= incumbent
     6     2  A<C C<B                             9.000          1          1   0.00   剪枝：界 >= incumbent
     7     1  C<A                                 8.000          1          1   0.00   剪枝：界 >= incumbent
  节点总数 7，其中叶节点 0，按界剪枝 4，按不可行剪枝 0

  手工 B&B 得到的最优值 1，与 M1 独立穷举的 1 一致。
  注意：整棵树被「界 >= incumbent」剪完，一次整数解都没找 —— 因为初始 incumbent
  恰好等于最优值，而每往下固定一个顺序，界就被抬高到 1 以上。

  同一实例、同一目标，把初始 incumbent 拿掉（incumbent = +∞）再跑一遍：

  node  深度  节点上的固定决策                       LP 界    incumbent   best bound   gap   动作
     1     0  (根节点)                               0.000          无          无      -   分支：x(A,C)=0.214
     2     1  A<C                                 0.000          无          无      -   分支：x(B,C)=0.214
     3     2  A<C B<C                             0.000          无          无      -   分支：x(A,B)=0.048
     4     3  A<B A<C B<C                         3.000          3          3   0.00   整数解 3，更新 incumbent
     5     3  B<A A<C B<C                         1.000          1          1   0.00   整数解 1，更新 incumbent
     6     2  A<C C<B                             9.000          1          1   0.00   剪枝：界 >= incumbent
     7     1  C<A                                 8.000          1          1   0.00   剪枝：界 >= incumbent
  节点总数 7，其中叶节点 2，按界剪枝 2，按不可行剪枝 0

  两次的节点数都是 7，但叶节点从 0 变成 2：没有 incumbent 时界剪枝的门槛是 +∞，
  前两个叶节点必须自己找出整数解来建立 incumbent，之后剩下的节点才被剪掉。
  这就是 incumbent 的作用：它不做任何「算得更准」的事，只是把界剪枝的门槛抬高。

== 2. 4 job 实例（ΣCj 真最优 33，由 24 个加工顺序独立枚举得到）==
  ΣCj 的 LP 界比 ΣTj 有信息：根节点的界就是 Σ_j (r_j + p_j) = 22

  node  深度  节点上的固定决策                       LP 界    incumbent   best bound   gap   动作
     1     0  (根节点)                              22.000         33         22   0.33   分支：x(J0,J2)=0.092
     2     1  J0<J2                              22.000         33         22   0.33   分支：x(J0,J1)=0.079
     3     2  J0<J1 J0<J2                        23.000         33         23   0.30   分支：x(J0,J3)=0.079
     4     3  J0<J1 J0<J2 J0<J3                  25.000         33         25   0.24   分支：x(J1,J3)=0.066
     5     4  J0<J1 J0<J2 J0<J3 J1<J3            29.000         33         29   0.12   分支：x(J2,J3)=0.092
     6     5  J0<J1 J0<J2 J0<J3 J1<J3 J2<J3      29.000         33         29   0.12   分支：x(J1,J2)=0.053
     7     6  J0<J1 J0<J2 J0<J3 J1<J2 J1<J3 J2<J3   33.000         33         33   0.00   剪枝：界 >= incumbent
     8     6  J0<J1 J0<J2 J0<J3 J2<J1 J1<J3 J2<J3   37.000         33         33   0.00   剪枝：界 >= incumbent
     9     5  J0<J1 J0<J2 J0<J3 J1<J3 J3<J2      36.000         33         33   0.00   剪枝：界 >= incumbent
    10     4  J0<J1 J0<J2 J0<J3 J3<J1            30.000         33         30   0.09   分支：x(J2,J3)=0.039
  …… 其余 13 行省略（完整节点数见下方统计）
  节点总数 23，其中叶节点 0，按界剪枝 11，按不可行剪枝 1

  手工 B&B 得到的最优值 33，与独立枚举的 33 一致。

== 3. 同一实例交给 CBC：数字对照 ==
  method       状态       objective   best bound   gap       nodes   建模(s)  求解(s)
  milp_tight   OPTIMAL        85.0        85.0   0.0000    130   0.0062    1.572
  milp_loose   OPTIMAL        85.0        85.0   0.0000    124   0.0025    1.513
  milp_alt     OPTIMAL        85.0        85.0   0.0000      0   0.0226    0.118
  nodes = 0 表示 CBC 在根节点就用割平面把问题解完了，一次分支都没做。

== 4. 真实 CBC 日志（子进程捕获，按关键词过滤，原文粘贴）==
  Presolve 64 (0) rows, 44 (-1) columns and 184 (0) elements
  Optimal objective 0 - 23 iterations time 0.002, Presolve 0.00
  Continuous objective value is 0 - 0.00 seconds
  Presolve 64 (0) rows, 44 (-1) columns and 184 (0) elements
  Presolve 64 (0) rows, 44 (0) columns and 184 (0) elements
  processed model has 64 rows, 44 columns (44 integer (28 of which binary)) and 184 elements
  Presolve 57 (-7) rows, 36 (-8) columns and 144 (-40) elements
  Presolve 57 (-7) rows, 36 (-8) columns and 144 (-40) elements
  Presolve is modifying 5 integer bounds and re-presolving
  Presolve 47 (-10) rows, 31 (-5) columns and 124 (-20) elements
  processed model has 47 rows, 31 columns (31 integer (17 of which binary)) and 124 elements
  At root node, 19 cuts changed objective from 47 to 65 in 2 passes
  After 0 nodes, 1 on tree, 1e+50 best solution, best possible 65 (0.01 seconds)
  Integer solution of 120 found by rounding after 68 iterations and 9 nodes (0.01 seconds)
  Integer solution of 115 found by strong branching after 68 iterations and 11 nodes (0.01 seconds)
  Integer solution of 112 found after 131 iterations and 24 nodes (0.01 seconds)
  Integer solution of 107 found after 131 iterations and 25 nodes (0.01 seconds)
  Search completed - best objective 107, took 343 iterations and 48 nodes (0.02 seconds)
  Maximum depth 8, 2 variables fixed on reduced cost
  Presolve 0 (-64) rows, 0 (-44) columns and 0 (-184) elements
  日志共 6902 行，这里摘了 20 行。
  读法一：Presolve 行说的是 presolve 把模型缩到多大（括号里是相对上一版的增减），
          At root node 行说的是根节点切了几轮割、界从多少抬到多少，
          Integer solution 行是搜索过程中找到的 incumbent。
  读法二：日志里的 47 / 65 / 107 都不是最终答案。上表同一实例的最终值是 85，
          107 只是某个内部阶段的 interim 值 —— 日志行必须跟 SolveResult 对账。
  读法三：这里的根节点界 65 与 Day 3 量到的纯 LP relaxation 界 0 不是同一个量：
          它经过了 presolve 的整数界收紧（日志第 10 行）与 19 条根节点割。
          说「root bound」时必须说明是哪一层：纯松弛、presolve 后、还是加割后。
```

### 7.1 第 3 段：`nodes = 0` 是什么情况

```text
milp_alt     OPTIMAL    85.0    85.0    0.0000     0 节点    0.118s
```

`nodes = 0` 表示 CBC 在根节点就用割平面把问题解完了，一次分支都没做。这与第 1、2 段手工树里的 `7` / `23` 个节点形成对照：**手工版本没有割平面，所以必须一路分支到叶节点才能定下顺序；CBC 有割平面，可以在根节点就把分数区域切掉。** 这也是「为什么 Day 6 不能只看节点数就下结论」的伏笔：节点数是「算法 + 求解器策略 + 模型」的共同产物，不是模型的单独属性。

同时注意第 3 段里 `tight` 与 `loose` 的数字：`130` 与 `124` 个节点、`1.572s` 与 `1.513s`。这两个数字**当天不足以支撑任何结论**（差得太小、且限时搜索的节点数会波动），Day 6 会在更大实例上用更大的预算重新测。

### 7.2 第 4 段：读日志的三条纪律

**纪律一：日志是「阶段顺序」的说明书，不是「结论」的来源。** 从上往下读，日志给出的是求解器动作的顺序：

```text
Presolve ...                     建模后先化简，原地迭代若干轮
Continuous objective value is 0  根节点的纯 LP 松弛值 = 0（与 Day 3 一致）
Presolve is modifying 5 integer bounds   收紧整数变量的界（这一步会抬高后续的界）
At root node, 19 cuts ... 47 to 65       根节点切了 19 条割，界从 47 抬到 65
After 0 nodes ... best possible 65       此时树上 1 个节点（根），best possible = 65
Integer solution of 120 / 115 / 112 / 107  搜索过程中找到的四个 incumbent
Search completed - best objective 107    「搜索结束」这一行
Maximum depth 8, 2 variables fixed on reduced cost   搜索深度与变量固定统计
Presolve 0 (-64) rows ...        求解结束后释放模型（行数/列数归零）
```

**纪律二：日志里的数字必须与 `SolveResult` 对账。** 上表同一实例（8 job、`ΣTj`）的 `milp_tight` 报出的是 `objective = 85.0`、`best_bound = 85.0`、`gap = 0.0000`、`nodes = 130`，而这段日志里出现的 `47 / 65 / 107` 一个都不等于 85。这**不是**矛盾，而是同一个求解过程里不同阶段的中间量；但仅凭这段过滤后的摘录，无法判定 `107` 具体属于哪个阶段 —— 这正是「必须对账」的原因：**日志行不能直接当结论，`SolveResult` 才是对外的记账单**。要追查 `107` 的出处，需要把完整日志（脚本说明共 `6902` 行）落盘后再检索。

**纪律三：说「root bound」时必须说明是哪一层的界。** 日志里的根节点界 `65`、Day 3 量到的纯 LP 松弛界 `0`、presolve 之后的 `47`，三个数都是「根节点上的界」，但含义完全不同：

| 名称 | 含义 | 本日实例取值 |
|---|---|---|
| 纯 LP 松弛界 | 一条割都不加、整数性完全放松 | `0` |
| presolve 后根节点界 | 收紧整数界、删冗余行之后的 LP 值 | `47` |
| 加割后根节点界 | 根节点切了 19 条割之后的界 | `65` |

**跨层比较是这类讨论里最常见的错误**：拿「加割后的根节点界」去说明「这个模型的松弛很强」，等于把求解器的割平面算成了模型的功劳。要说模型强度，就用 Day 3 那种「纯松弛」口径。

### 7.3 手工版本与真实求解器的差距在哪些具体行上

把第 1、2 段的手工树与第 4 段的日志对照，差距可以逐行指出：

| 手工版本 | 真实 CBC | 日志里的证据行 |
|---|---|---|
| 没有 presolve，模型 64 行 44 列直接开解 | 先化简到 47 行 31 列、17 个二元 | `processed model has 47 rows, 31 columns ...` |
| 没有割平面，根节点的界就是纯 LP 值 | 根节点 19 条割把界从 47 抬到 65 | `At root node, 19 cuts ...` |
| 分支变量选「最靠近 0.5」 | 有强分支、按 reduced cost 固定变量 | `found by strong branching`、`2 variables fixed on reduced cost` |
| 剪枝只按 `bound >= incumbent` | 同上，但界更高，剪得更早 | `Search completed ... 48 nodes` |

**这就是「手工走一遍」的收获**：知道主干之后，日志里多出来的每一行都能被归到三类附加动作里，而不是一堆看不懂的输出。

**复跑说明**：上面摘录里的行数与耗时不是可复现读数 —— 重跑同一脚本时日志是 `6185` 行（本节记录的是 `6902` 行）、每个节点的秒数也会变。本节的读法只依赖**量级与结构**（化简到 `47` 行 `31` 列、根节点 `19` 条割、搜索 `48` 个节点），不依赖具体行数；而第 4 段表格里的 `objective = 85.0`、`best_bound = 85.0`、`gap = 0.0000` 与 `nodes = 130 / 124 / 0` 在重跑中保持一致（节点数在规模更大的实例上才会大幅波动，见 Day 6 第 5.2 节）。

---

## 8. 今日练习

1. **练习 1（手算）**：在 4 job 实例上，把节点 4 的界 `25.000` 手算一遍（已知 `J0<J1`、`J0<J2`、`J0<J3` 三条决策已固定），并说明它为什么比根节点的 `22` 大。
2. **练习 2（推导）**：证明「每个分支节点恰好两个子节点时，叶类节点数 = 分支节点数 + 1」，并用本日两组统计（`4 = 3 + 1`、`12 = 11 + 1`）验证。
3. **练习 3（实验）**：把 CBC 的完整日志落盘（`6902` 行），检索 `107` 第一次出现的上下文，判断它属于 presolve、割平面还是主搜索阶段，并说明判断依据。
4. **练习 4（判读）**：某次限时求解结束后 `gap = 0.0000` 但 `status = FEASIBLE`（不是 `OPTIMAL`）。请给出至少一种可能的解释，并说明此时 `objective` 是否可信。
5. **练习 5（设计）**：如果初始 incumbent 用一个很差的启发式（例如把工序按 id 顺序排），节点数会增加还是减少？请结合本日两组实验给出回答，并说明「有没有可能反而更少」。

---

## 9. 验收清单

- [ ] 能默写 B&B 的五个基本动作，并说清每一步在搜索树上的效果。
- [ ] 能写出 `best bound <= 真最优 <= incumbent` 这串不等式，并说明三者各自能否当作答案交出。
- [ ] 能解释 `gap = 0` 与 `status = OPTIMAL` 的关系，以及为什么 `gap > 0` 时结论只能算「目前最好」。
- [ ] 能说清三种剪枝的触发条件，并知道「按界剪枝」用的是 `bound >= incumbent`。
- [ ] 能解释 3 job 实例上「两次都是 7 个节点、叶节点从 0 变 2」的原因。
- [ ] 能说出 `presolve` 在日志里的位置，以及它为什么让「根节点界」与「纯 LP 松弛界」不相等。
- [ ] 能区分「纯 LP 松弛界 `0`」「presolve 后 `47`」「加割后 `65`」三层含义，并且不做跨层比较。
- [ ] 能说出「日志数字必须与 `SolveResult` 对账」这条纪律，并能举出日志里 `107` 与最终值 `85` 不一致的例子。
- [ ] 在项目目录下运行 `python -m examples.m2w2d4_branch_and_bound_walk`，能看到 3 job 的两棵树（7 节点 / 叶节点 0 与 2）与 4 job 的 23 节点统计。
- [ ] 在项目目录下运行 `python -m pytest tests/test_milp_scheduling.py -q`，其中与 `nodes` / `gap` / `best_bound` 一致性相关的用例通过。

---

## 10. 自测题

- Q1：`incumbent` 与 `best bound` 在最小化问题里谁在上、谁在下？为什么？
- Q2：为什么 `best bound` 不能作为答案交出去，而 `incumbent` 可以？
- Q3：`bound >= incumbent` 为什么可以安全剪枝？写成 `bound > incumbent` 会有什么后果？
- Q4：本日 3 job 实例的两棵树节点数相同、叶节点数不同，请解释这个现象。
- Q5：为什么 4 job 实例的根节点界是 `22` 而不是 `0`？换了目标之后发生了什么？
- Q6：手工版本没有割平面，真实 CBC 有；这会对「根节点的界」产生什么影响？
- Q7：`nodes = 0` 说明什么？它是不是说明「这个问题很简单」？
- Q8：CBC 日志里 `Search completed - best objective 107` 与 `SolveResult` 的 `85` 不一致，应该采信哪个？为什么？
- Q9：说「root bound 是 65」时，必须补充说明什么？
- Q10：限时搜索结束后 `gap = 0.0000` 意味着什么？它是否一定意味着搜索证明了最优性？

### 参考答案

- A1：`best bound <= incumbent`。`best bound` 是「还没被排除的最好可能」（下界），`incumbent` 是「已经找到的最好可行解」（上界），真最优夹在中间。
- A2：`best bound` 只是下界，它对应的解可能不可行（LP 的分数解）；`incumbent` 对应一个真实可行解，目标值可以由独立验证器重算。
- A3：因为该节点所有后代的目标值都不会小于 `bound`，而 `bound` 已经不优于现有可行解；写成 `>` 会多探「恰好等于 incumbent」的节点，正确但更慢。
- A4：两棵树的搜索顺序相同（都是 7 个节点）；差别在于有没有 incumbent 决定「界剪枝的门槛」：门槛为 `+∞` 时前两个到底层的节点不会被剪、只能自己找出整数解，因此叶节点数为 2；有 incumbent 时这四个节点全部被剪，叶节点数为 0。
- A5：因为目标换成了 `ΣCj`，LP 不必满足交期，只需最小化完成时间之和；没有机器容量时每道工序都能在释放时间开工，下界即 `Σ_j (r_j + p_j) = 22`。`ΣTj` 的下界是 `0`（不需要任何求解器就能写出），所以那个目标是「零信息」的。
- A6：割平面会切掉一批分数区域，使根节点的界高于纯 LP 值（本实例从 `0` 抬到 `65`，中间还经过 presolve 的 `47`）。
- A7：说明 CBC 在根节点就用割平面把问题解完了，一次分支都没做；它只说明「这个问题在这个求解器 + 这个模型上没触发分支」，不说明问题本身简单（同一实例的另一个 formulation 也可能需要分支）。
- A8：采信 `SolveResult`（`85`）。日志里的行分属不同阶段，未标注阶段归属的数字不能作为结论；`SolveResult` 的目标值还经过了独立验证器与重算两道关卡。
- A9：必须说明是哪一层：纯 LP 松弛、presolve 之后、还是加割之后；三者的数值可以相差很大。
- A10：`gap = 0` 意味着 incumbent 与 best bound 相等，也就是「已找到的解」与「可能的最好解」之间没有空间；若 `iterations` 也正常且状态为 `OPTIMAL`，可以认为最优性已证明；若状态是 `FEASIBLE`（例如被时间限制截断在恰好收敛的那一刻），则应结合 `detail` 判断，不把 `gap = 0` 单独当作证明。

---

## 11. 今日一句话总结

> **branch-and-bound 的全部逻辑就是 `best bound <= 真最优 <= incumbent` 这一串不等式：节点 LP 提供下界、incumbent 抬高剪枝门槛、gap 衡量两者之间还剩多少空间；而真实求解器在这条主干上额外加了 presolve、割平面与强分支三类动作，所以读日志时必须先分清数字属于哪一层，并与 `SolveResult` 逐项对账。**
