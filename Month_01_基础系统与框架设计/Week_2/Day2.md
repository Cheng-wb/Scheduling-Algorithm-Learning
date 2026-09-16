# Day 2：串行解码器与三类轨迹

> 当日主题：用统一解码把「顺序 + 机器」翻译成可行排程
> 当日产出：**串行追加解码器 `decode`**（`decoder.py` + 三条精确轨迹 + 实验脚本）
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说清楚 `decode(instance, candidate) → Schedule` 的输入、输出，以及为什么它是本周唯一产生时间的地方。
2. 写出解码器的六个局部状态，并说明每一个的作用。
3. 默写递推公式 `start = max(machine_ready[m], 前驱完工, release(job))` 与 `end = start + p`。
4. 解释「前驱已排定」是**集合条件**，而「不早于前驱完工」是**时间约束**，两者是两件事。
5. 手推三条精确轨迹，并逐位写出每道工序的机器与开始/结束时刻。
6. 解释 append-only（追加式）的含义，以及为什么 `M0` 的 `[0,2)` 空隙不会被填。
7. 说出解码器确实不需要平局决胜（tie-breaking），以及这和 Week 1 规则基线的区别。
8. 说出解码器的复杂度量级与已知局限，知道它不覆盖哪些工业约束。

---

## 2. 为什么 Day 2 要把「决策」翻译成「时间」

Day 1 结束时，流水线长这样：

```text
可信输入 → Candidate(order, assignments) → ？
```

`Candidate` 描述了「谁先做、在哪台做」，但它里面**一个时刻都没有**。要把决策变成一张排程表，必须补上今天这一环：

```text
                    Candidate(order, assignments)
                              ↓
                          decode            ← 今天新增的一环
                              ↓
              Schedule(operations=(ScheduledOperation(
                  operation_id, machine_id, start_time, end_time), ...))
                              ↓
                objective → 数字      validate_schedule → 诊断
```

选择「用函数推导时间」而不是「把时间直接放进 `Candidate`」，有三个理由：

1. **决策与时间是一一对应的推导关系。** 同一个 `Candidate` 每次 `decode` 必须给出同一个 `Schedule`，这一点必须是显然的。写成函数之后，「时间算错」只可能出现在一个地方。
2. **Week 1 已经有三套时间推进逻辑。** `list_schedule`（单机 non-delay）、`parallel_lpt`（并行机选机）各自内嵌了一套。多工序 + 释放时间 + 机器资格同时出现时，三套逻辑无法拼在一起；`decode` 把它们合并成**一条公共路径**（Day 5 第 13 节已经预告过这个委托结构）。
3. **求解与评价彻底分离。** 搜索只改 `Candidate`，`decode` 只负责把它变成 `Schedule`，`objective` 只负责给 `Schedule` 打分。任何一环都不越界，实验才可能公平比较。

一句话：**`decode` 是「决策空间」与「时间轴」之间唯一的桥。**

---

## 3. 解码器的状态与递推公式

### 3.1 六个局部状态

```text
输入：instance, candidate

operations     op.id → Operation                    查加工时间与作业归属
predecessors   op.id → 同作业内前一道工序（首道为 None）  判断可否被选中
machines       op.id → candidate 指定的机器          查出 start 的门槛之一
machine_ready  machine.id → 该机器当前可用时刻        只增不减的游标
ends           op.id → 已排定工序的完工时刻           留给后继做 max
remaining      candidate.order 的剩余列表            优先级顺序在这里生效
output         已排定的 ScheduledOperation 列表       顺序 = 构造顺序
```

`predecessors` 的构造只需要一行推导式：对每个作业的 `operation_ids`，第 `i` 道工序的前驱是第 `i-1` 道，第 0 道为 `None`。**前置关系来自 `Job.operation_ids` 的顺序，不需要额外的边表**（这是 Week 1 输入模型的设计红利）。

### 3.2 三步递推

每一步循环做三件事：

```text
选   oid = remaining 中第一道「前驱已排定」的工序
算   start = max(machine_ready[m], ends[前驱] 或 0, release(作业))
     end   = start + p(op)
更新 machine_ready[m] = end
     ends[oid]        = end
     remaining 移除 oid
     output 追加 ScheduledOperation(oid, m, start, end)
```

写成一个循环：

```python
while remaining:
    oid = next(
        oid
        for oid in remaining
        if predecessors[oid] is None or predecessors[oid] in ends
    )
    remaining.remove(oid)
    ...
```

### 3.3 「前驱已排定」与「不早于前驱完工」是两件事

这是今天最值得停下来看清楚的一点：

| 概念 | 表达式 | 作用 |
|---|---|---|
| 前驱**已排定** | `predecessors[oid] in ends` | 决定这道工序**现在能不能被选中** |
| 不早于前驱**完工** | `max(..., ends[predecessor], ...)` | 决定选中后**最早从哪一刻开工** |

前者是**集合成员检查**，与时刻无关；后者是**数值取上界**。初学者常把两者混成一句话「等前驱做完再做」，结果会写出「当前时刻不到前驱完工时间就跳过这道工序」的错误实现——那会让 `order` 里排在后面的工序被无限推迟，也会让 `order` 事实上变成必须满足的拓扑序。

正确实现的效果是：**只要前驱进入了 `ends`，后继立刻可以被选中，哪怕它要等到很久以后才开工。** 结果就是「选中的顺序」与「开工的顺序」可以不一致——见第 5.5 节。

### 3.4 三项 `max` 各管什么

```text
machine_ready[m]   机器容量约束：同一台机器不能重叠加工
ends[前驱] 或 0     precedence 约束：后继不早于前驱完工
release(作业)       释放时间约束：工序不早于作业就绪
```

三项缺一不可，而且**顺序无关**——取的是上界。这也解释了 Day 1 里 `Σp = 6` 而 `Cmax = 7`：总工作量只是「机器侧」的下界，释放时间还会额外造成等待。

---

## 4. append-only、构造顺序与确定性

### 4.1 append-only：空隙为什么不被填

看第 5.1 节的轨迹 1：`M0` 在 `[0,2)` 完全空闲，而 C 明明被指派到了 `M0`，却要等到 `t=5` 才开工。为什么 C 不填进 `[0,2)`？

`machine_ready` 是一台机器上「已经排到哪儿」的**只增不减的游标**（轨迹 1 上 `machine_ready[M0]` 走 0 → 5 → 6）。递推式里的 `start = max(machine_ready[m], ...)` 只会把开工时刻**往后推**，没有任何分支可以把它拉回去。C 被选中时 `machine_ready[M0]` 已经是 5，`max` 的结果不可能小于 5。**实现里根本没有「在已有区间之间找空隙」这一步。**

### 4.2 代价（必须诚实写下来的局限）

> **append-only 用解质量换实现简单。** 它不保证产出 active schedule（没有任何工序能左移而不推迟其他工序的排程）。

以轨迹 1 为例：把 C 从 `M0[5,6)` 左移到 `M0[0,1)`，A 仍在 `[2,5)` 开工、B 仍在 `M1[5,7)` 完工，**没有任何其他工序被推迟**，而 `ΣCj` 从 13 降到 8。也就是说：

```text
轨迹 1 的排程不是 active 的：存在可左移的工序 C
而且它不是该实例上 ΣCj 最好的排程（13 > 8）
```

三点要一起记住：append-only 是**实现选择**而非调度理论的要求，它让程序易懂、行为可预测；它可能让某些「本来能找到」的好解够不到——左移这类改良动作不在当前实现的邻域里；因此「解码结果可行」只说明**满足约束**，不说明**质量好**，可行性与质量是两件事，Day 4 的验证器只管前者。

### 4.3 `order` 不是时间顺序

`Schedule.operations` 是**构造顺序**，不是按 `start_time` 排序的展示顺序（第 5.5 节给出反例）。Week 1 第 5 天的 Gantt 导出之所以要显式排序 `(machine_id, start_time, operation_id)`，就是为了把「构造顺序」整理成「展示顺序」——两件事不要混为一谈。Day 4 的独立验证器也明确「不假设工序列表按时间排序」。

### 4.4 解码器不需要平局决胜

Week 1 的所有规则都必须显式做 tie-breaking（`job.id` 升序、`machine.id` 升序），否则结果不确定。今天的 `decode` **不需要任何决胜键**：`order` 已经是一个全序、没有「并列」的概念；`assignments` 已经指定了机器、没有「选哪台」的余地；`next(...)` 取 `remaining` 中第一道满足条件的工序，与任何外部顺序无关。所以「同一个 `Candidate` 两次 `decode` 结果相同」是**结构性保证**，而不是靠额外的决胜规则兜住。

> **注意这里的确定性是「同一个 Candidate」，不是「同一个 Instance」。** 不同的 `Candidate` 当然可能给出不同的 `Schedule`，那正是搜索要利用的自由度。

### 4.5 模型边界

解码器实现的是 `α = 1 或 P` 且 `β` 含 `prec`（链式）、`rj`、`Mj`（机器资格）的不可抢占模型：

```text
prec    同作业内 A → B（线性链，不是任意 DAG）
rj      每道工序不早于所属作业的 release_time 开工
Mj      每道工序只能上 eligible_machine_ids 里的机器
```

一旦加工开始就运行到结束（non-preemptive）。**换型、维护日历、工人容量、任意 DAG 前置关系、机器相关加工时间（`Q` / `R`）都不在这个 `β` 字段里**，解码器自然也不处理它们。写下边界比假装覆盖更诚实。

---

## 5. 手算：三条精确轨迹

输入与 Day 1 第 5 节完全相同：

| 工序 | 所属 Job | `pj` | Job 的 `rj` | `eligible_machine_ids` |
|---|---|---:|---:|---|
| A | J0 | 3 | 2 | `("M0",)` |
| B | J0 | 2 | 2 | `("M0", "M1")` |
| C | J1 | 1 | 0 | `("M0", "M1")` |

`instance.operations = (A, B, C)`，因此 `assignments` 的第 1/2/3 位分别对应 A/B/C。

### 5.1 轨迹 1：`ABC` / `M0,M1,M0`

```text
① 选 A（remaining=[A,B,C]，无前驱）
   start = max(machine_ready[M0]=0, 0, r(J0)=2) = 2，end = 2+3 = 5
   更新 machine_ready[M0] = 5，ends[A] = 5

② 选 B（remaining=[B,C]，前驱 A ∈ ends）
   start = max(machine_ready[M1]=0, ends[A]=5, r(J0)=2) = 5，end = 5+2 = 7
   更新 machine_ready[M1] = 7，ends[B] = 7

③ 选 C（remaining=[C]，无前驱）
   start = max(machine_ready[M0]=5, 0, r(J1)=0) = 5，end = 5+1 = 6
   更新 machine_ready[M0] = 6，ends[C] = 6

机器时间线：
M0: A[2,5)  C[5,6)        空闲 [0,2)
M1: B[5,7)                空闲 [0,5)
```

### 5.2 轨迹 2：`BCA` / `M0,M1,M0`

```text
① remaining=[B,C,A]，B 的前驱 A ∉ ends → 跳过 B；选 C（无前驱）
   start = max(machine_ready[M0]=0, 0, r(J1)=0) = 0，end = 0+1 = 1
   更新 machine_ready[M0] = 1，ends[C] = 1

② remaining=[B,A]，B 仍不可选 → 跳过；选 A（无前驱）
   start = max(machine_ready[M0]=1, 0, r(J0)=2) = 2，end = 2+3 = 5
   更新 machine_ready[M0] = 5，ends[A] = 5

③ remaining=[B]，前驱 A ∈ ends → 选 B
   start = max(machine_ready[M1]=0, ends[A]=5, r(J0)=2) = 5，end = 5+2 = 7
   更新 machine_ready[M1] = 7，ends[B] = 7

机器时间线：
M0: C[0,1)  A[2,5)        空闲 [1,2)
M1: B[5,7)                空闲 [0,5)
```

A 在 `t=1` 就被选中，却因为 `r(J0)=2` 只能从 2 开工——**「可被选中」不等于「可以开工」**，这是第 3.3 节那张表的直接体现。

### 5.3 轨迹 3：`BCA` / `M0,M0,M1`

只把 `assignments` 换掉（B 由 M1 改为 M0，C 由 M0 改为 M1），顺序不变：

```text
① B 跳过；选 C（指派 M1）
   start = max(machine_ready[M1]=0, 0, r(J1)=0) = 0，end = 0+1 = 1
   更新 machine_ready[M1] = 1，ends[C] = 1

② B 跳过；选 A（指派 M0）
   start = max(machine_ready[M0]=0, 0, r(J0)=2) = 2，end = 2+3 = 5
   更新 machine_ready[M0] = 5，ends[A] = 5

③ 选 B（指派 M0）
   start = max(machine_ready[M0]=5, ends[A]=5, r(J0)=2) = 5，end = 5+2 = 7
   更新 machine_ready[M0] = 7，ends[B] = 7

机器时间线：
M0: A[2,5)  B[5,7)        空闲 [0,2)
M1: C[0,1)                无空闲
```

### 5.4 对比表

| 编码 | 构造顺序 | A | B | C | `Cmax` | `ΣCj` |
|---|---|---|---|---|---|---|
| `ABC` / `M0,M1,M0` | A,B,C | M0[2,5) | M1[5,7) | M0[5,6) | 7 | 13 |
| `BCA` / `M0,M1,M0` | C,A,B | M0[2,5) | M1[5,7) | M0[0,1) | 7 | **8** |
| `BCA` / `M0,M0,M1` | C,A,B | M0[2,5) | M0[5,7) | M1[0,1) | 7 | **8** |

```text
轨迹 1：C_J0 = max(end(A), end(B)) = max(5, 7) = 7；C_J1 = end(C) = 6
        Cmax = 7，ΣCj = 7 + 6 = 13
轨迹 2、3：C_J0 = max(5, 7) = 7；C_J1 = 1
        Cmax = 7，ΣCj = 7 + 1 = 8
```

三条轨迹的 `Cmax` 都是 7：总工作量 `Σp = 3+2+1 = 6`，而关键路径 A→B 占 `3+2 = 5`，再加上 A 必须等 `r=2` 才开工，机器在 `[0,2)` 无法做 A。**`ΣCj` 的差距全部来自 C 放在哪一段**——这就是 `1|rj|ΣCj` 类问题上「决策决定目标」的最小实例。

另外注意轨迹 2 与轨迹 3：**构造顺序相同、`ΣCj` 相同，但机器不同**。这再次说明「目标值」不是排程的唯一描述，评估时必须同时看 `Schedule` 本身。

### 5.5 输出顺序 ≠ 时间顺序

再取一个 `order = ("A", "C", "B")`、`assignments = ("M0", "M0", "M1")` 的组合（A→M0，B→M0，C→M1）：

```text
选 A（无前驱）→ A 在 M0：start = max(0, 0, 2) = 2，end = 5
选 C（无前驱）→ C 在 M1：start = max(0, 0, 0) = 0，end = 1
选 B（前驱已排定）→ B 在 M0：start = max(5, 5, 2) = 5，end = 7

构造顺序 = [A, C, B]      各自 start = [2, 0, 5]
```

**C 的 `start` 最小，却排在 A 之后。** `Schedule.operations` 只记录构造顺序，验证器和 objective 都不依赖它有序。任何需要按时间展示的地方（Gantt、报告）都必须自己排序。

---

## 6. 实现：`decoder.py`

对应文件 [decoder.py](../../projects/01_scheduling_core/scheduling_algorithms/decoder.py)。

### 6.1 循环骨架

核心就是第 3.2 节的三步，逐行对应：

```python
    while remaining:
        oid = next(
            oid
            for oid in remaining
            if predecessors[oid] is None or predecessors[oid] in ends
        )
        remaining.remove(oid)
        op = operations[oid]
        machine = machines[oid]
        predecessor = predecessors[oid]
        start = max(
            machine_ready[machine],
            ends[predecessor] if predecessor is not None else 0,
            jobs[op.job_id].release_time,
        )
        end = start + op.processing_time
        output.append(ScheduledOperation(oid, machine, start, end))
        machine_ready[machine] = ends[oid] = end
    return Schedule(tuple(output))
```

四个细节：

- **`machines` 用 `zip(operations, candidate.assignments, strict=True)` 建立。** `strict=True` 让长度不匹配当场报错，而不是静默截断——这是 Day 1 第 4.1 节不变量的第二道保险。
- **`predecessors` 从 `job.operation_ids` 推导。** 不需要额外的边表；作业内线性链已经是输入模型自带的语义。
- **`machine_ready[machine] = ends[oid] = end` 一行写两个赋值。** 它们语义相同（该机器当前可用时刻 = 这道工序完工时刻），写在一起强调「两者永远一致」。
- **`output` 用 `list` 累加、最后转 `tuple`。** 循环中追加用 `list` 最快，出口统一冻结成不可变的 `Schedule`。

### 6.2 为什么第一次调用就能确定结果

`decode` 的开头是 `validate_instance(instance)` 与 `validate_candidate(instance, candidate)` 两行校验，进入循环时已经保证 `order` 是全部工序的全排列、`assignments` 长度正确、指派机器合格。剩下的「选择」只有 `next(...)` 一处，它完全由 `remaining` 的顺序与 `ends` 集合决定——**没有任何随机性、没有任何依赖外部状态的决胜规则**。

### 6.3 复杂度

```text
每步：next(...) 线性扫描 remaining（最坏 n 次判断）
      remaining.remove(oid) 线性搬移（最坏 n 次）
共 n 步 → 约 O(n²)，再加上两个 validate 的检查开销
```

n 是工序总数。Month 1 的实例规模下这个量级完全够用；**先把可验证的实现做对，增量评估与优先队列加速留给 M5**（那时搜索的评价次数会上几个数量级）。

### 6.4 同一文件里的 `initial_candidate`

[decoder.py](../../projects/01_scheduling_core/scheduling_algorithms/decoder.py) 里还有一个 `initial_candidate(instance)`，做的是「LPT 优先级 + 最早完工指派」，产出第一个 `Candidate`。Week 1 第 5 天的 `parallel_lpt` 就是 `decode(instance, initial_candidate(instance))` 的两行组合。

把它放在这里而不是 `rules.py`，是因为它的产物是 `Candidate` 而不是 `Schedule`：**谁定义 `Candidate` 的构造，谁就负责给出一个合法的起点**。多工序时它只是一个通用初始解，不再具备 `P||Cmax` 意义上的排序含义。

---

## 7. 实验：`m1w2d2_decoder`

对应脚本 [m1w2d2_decoder.py](../../projects/01_scheduling_core/examples/m1w2d2_decoder.py)，在项目目录下运行：

```bash
python examples/m1w2d2_decoder.py
```

脚本做四件事：重建三条轨迹并逐位断言（工序、机器、开始、结束四个字段一起比）、打印每台机器的区间与空闲段、演示 append-only、演示「输出顺序 ≠ 时间顺序」。实际输出：

```text
instance：J0 = A(p=3, r=2) -> B(p=2)，J1 = C(p=1, r=0)
A 的资格 = ('M0',)  B 的资格 = ('M0', 'M1')  C 的资格 = ('M0', 'M1')

[轨迹 1] order=A,B,C  assignments=M0,M1,M0
  扫描顺序（= Schedule.operations 的构造顺序）: A -> B -> C
    A: M0[2,5)
    B: M1[5,7)
    C: M0[5,6)
    M0: A[2,5) C[5,6)   （空闲 [0,2)）
    M1: B[5,7)   （空闲 [0,5)）
  与手算轨迹一致，且重复解码得到相同 Schedule。

[轨迹 2] order=B,C,A  assignments=M0,M1,M0
  扫描顺序（= Schedule.operations 的构造顺序）: C -> A -> B
    C: M0[0,1)
    A: M0[2,5)
    B: M1[5,7)
    M0: C[0,1) A[2,5)   （空闲 [1,2)）
    M1: B[5,7)   （空闲 [0,5)）
  与手算轨迹一致，且重复解码得到相同 Schedule。

[轨迹 3] order=B,C,A  assignments=M0,M0,M1
  扫描顺序（= Schedule.operations 的构造顺序）: C -> A -> B
    C: M1[0,1)
    A: M0[2,5)
    B: M0[5,7)
    M0: A[2,5) B[5,7)   （空闲 [0,2)）
    M1: C[0,1)   （无空闲）
  与手算轨迹一致，且重复解码得到相同 Schedule。

[append-only] 不向机器已有空隙插入工序
  轨迹 1 中 A 的释放时间 r=2，M0 的 [0,2) 一直空闲。
  但 C 虽然指派在 M0，start = 5，落在 A 之后，没有回填 [0,2)。
  原因：decoder 只做 start = max(machine_ready, 前驱完工, 释放时间)，
        machine_ready 只增不减，机器一旦推进就不会退回填空隙。

[输出顺序] Schedule.operations 是构造顺序，不按 start_time 排序
  order=A,C,B  assignments=M0,M0,M1  ->
    构造顺序 = ['A', 'C', 'B']
    各自 start = [2, 0, 5]
  C 的 start 最小却排在 A 之后，说明输出元组只反映构造顺序。
```

**实验结论**：

1. 轨迹 1 的 `M0` 空闲是 `[0,2)`（释放时间造成的等待），轨迹 2 是 `[1,2)`（A 在 `t=1` 被选中但 `r=2` 未到）——**同样是「空闲」，成因不同**。
2. 轨迹 1 的 `M1` 空闲 `[0,5)`，说明**空闲本身不是错误**：B 必须等 A，而 A 最早 2 开工、5 完工，M1 在 `[0,5)` 本就无事可做。
3. 脚本用 `assert quadruple(schedule) == expected` 把第 5 节的手算固化成了断言——**实验脚本的第一职责是把「手算」变成「可重复的检查」**（与 Week 1 Day 5 同一原则）。
4. append-only 的输出与第 4.1 节推导完全对应：`start = 5` 不是巧合，而是 `machine_ready[M0]` 已被 A 推到 5。

配套测试在项目目录下运行：

```bash
python -m pytest tests/test_month1.py -k three_decoder -v
```

三个参数化用例 `test_three_decoder_traces` 就是第 5 节的这三条轨迹；它们除了比较 `(operation_id, start_time, end_time)`，还会调用 `validate_schedule` 断言可行性，并断言重复解码得到相同 `Schedule`。

---

## 8. 今日练习

1. **练习 1（手推）**：把轨迹 1 的 `assignments` 改成 `("M0", "M1", "M1")`，完整写出三步递推，求出 `Cmax` 与 `ΣCj`。
2. **练习 2（空隙）**：在轨迹 1 的基础上，手工把 C 左移到 `M0[0,1)`，验证 A、B 的时刻都不变，并算出新的 `ΣCj`。
3. **练习 3（顺序条件）**：把 `order` 改成 `("B", "A", "C")`，说明为什么解码结果与 `("A", "B", "C")` 完全相同。
4. **练习 4（释放时间）**：把 J0 的 `release_time` 从 2 改成 0，重新手算三条轨迹，观察哪一条的 `ΣCj` 变化最大。
5. **练习 5（代码阅读）**：不看 [decoder.py](../../projects/01_scheduling_core/scheduling_algorithms/decoder.py)，自己写出 `predecessors` 的推导式与 `start` 的三项 `max`，再与实现对照。

---

## 9. 验收清单

- [ ] 能说出解码器的六个局部状态，以及每个状态在递推中的角色。
- [ ] 能默写 `start = max(machine_ready[m], 前驱完工, release(job))` 与 `end = start + p`。
- [ ] 能解释「前驱已排定」是集合条件、「不早于前驱完工」是时间约束，并说明混为一谈会写出什么错误实现。
- [ ] 能不看代码推出三条精确轨迹（工序、机器、开始、结束）。
- [ ] 能解释「输出顺序是构造顺序、不是时间顺序」，并给出 C 的 `start` 最小却排在 A 之后的例子。
- [ ] 能解释 append-only 的成因（`machine_ready` 只增不减），并说明它会损失解质量。
- [ ] 能说出解码器不需要平局决胜的两个原因（`order` 是全序、`assignments` 已指定机器）。
- [ ] 能说明复杂度约 `O(n²)`，以及哪些工业约束不在当前模型的 `β` 字段内。
- [ ] `python -m examples.m1w2d2_decoder` 输出与第 5 节三条手算轨迹逐位一致。
- [ ] `python -m pytest tests/test_month1.py -k three_decoder -q` 全部通过（3 条）。

---

## 10. 自测题

不看上文回答：

- Q1：`decode` 的输入与输出分别是什么？
- Q2：解码器维护哪几个局部状态？`machine_ready` 的物理含义是什么？
- Q3：默写递推公式。
- Q4：「前驱已排定」与「不早于前驱完工」分别对应哪段代码？为什么不能合并？
- Q5：轨迹 2 里 B 排在 `order` 第一位，为什么第二个才被选中？
- Q6：A 在 `t=1` 被选中，为什么 `start` 是 2 而不是 1？
- Q7：什么是 append-only？轨迹 1 里 M0 的 `[0,2)` 为什么没被 C 填上？
- Q8：解码器为什么不需要 tie-breaking？这与 Week 1 的规则基线有何不同？
- Q9：`Schedule.operations` 的顺序是什么顺序？举一个它与时间顺序不一致的例子。
- Q10：解码器的复杂度量级是多少？它不处理哪些约束？

### 参考答案

- A1：输入 `(instance, candidate)`，输出 `Schedule`（由若干 `ScheduledOperation` 组成）。
- A2：`operations` / `predecessors` / `machines` / `machine_ready` / `ends` / `remaining` / `output`；`machine_ready[m]` 是机器 m 当前可用的最早时刻，只增不减。
- A3：`start = max(machine_ready[m], ends[前驱] 或 0, release(作业))`，`end = start + p`。
- A4：前者是 `predecessors[oid] in ends`（能否被选中），后者是 `max(..., ends[predecessor], ...)`（最早何时开工）。合并会导致「不到前驱完工就跳过」，使 `order` 事实上被迫变成拓扑序。
- A5：B 的前驱 A 尚未排定，`next(...)` 会跳过 B；此时 C 无前驱，于是先被选中。
- A6：A 所属作业 J0 的 `release_time = 2`，`start` 的 `max` 里第三项把开工时刻顶到了 2。
- A7：append-only 指机器只在自己的时间线末端追加，不回填已有空隙。因为 `machine_ready[M0]` 在 A 之后已经是 5，`max` 不可能把它拉回 0。
- A8：`order` 是全序、`assignments` 已指定机器，唯一的「选择」是取 `remaining` 中第一道可选中工序，没有并列。Week 1 的规则必须自己排全序，所以需要 `job.id` / `machine.id` 决胜。
- A9：构造顺序。例：`order=("A","C","B")`、`assignments=("M0","M0","M1")` 时输出顺序是 A→C→B，而 `start` 分别是 2、0、5。
- A10：约 `O(n²)`（扫描 + 移除各一次线性）。不处理换型、维护日历、工人容量、任意 DAG 前置关系、机器相关加工时间（`Q` / `R`）。

---

## 11. 今日一句话总结

> **解码器用 `machine_ready`、`ends`、`remaining` 把「优先级 + 指派」逐道推进成时间线：`start = max(机器空闲, 前驱完工, 释放时间)`；它是全周唯一产生时间的地方，是 append-only 的构造式实现（不填空隙、可能损失解质量），而「前驱已排定」与「不早于前驱完工」必须分开理解。**
