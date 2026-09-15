# Day 5：并行机 LPT 基线、最小选机表示与 Schedule/Gantt 数据

> 当日主题：实现 LPT 并行机基线与最小选机表示，输出 Schedule/Gantt 数据
> 当日产出：**并行机 LPT 基线**（`parallel_lpt` + 下界）+ **Gantt 导出**（`to_gantt_rows` / `write_gantt_csv`）+ 单元测试
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说清楚 `P||Cmax` 是什么，以及 `P / Q / R` 三类并行机的区别。
2. 理解从单机到并行机，决策多了一个维度：除了「谁先做」，还要「在哪台做」。
3. 掌握 LPT 列表调度的两步：按 `p` 降序排序 + 分给当前 ready 最小的机器。
4. 掌握「最小选机表示」：输入的 `eligible_machine_ids` 是允许范围，输出的 `machine_id` 是实际决策。
5. 用 `machine_ready_time` 这一个唯一状态，写出 `state → decision → transition` 的循环。
6. 用下界 `LB = max(max p_j, ceil(Σp_j / m))` 判断 LPT 是否已经最优。
7. 知道 LPT 只是启发式（近似界 `4/3 − 1/(3m)`），并会举出 LPT 非最优的例子。
8. 用 `to_gantt_rows` / `write_gantt_csv` 把 Schedule 导出为甘特图数据。

---

## 2. 为什么今天是「从单机到并行机」的转折点

前四天的流水线是：

```text
JSON → Parser → Instance → Validator → 可信输入
                                     ↓
                        Rules → Schedule → Objective → 数字
```

但前四天的 `Rules` 全部是**单机**规则：决策只有一件事——「这些 job 按什么顺序做」。今天的 `P||Cmax` 第一次引入**多台机器**，于是「该怎么做」多了一个全新的维度：

```text
单机：   只决定「顺序」        sequencing：J1 先还是 J2 先？
并行机： 还要决定「机器」      assignment：J1 放 M1 还是 M2？
```

并行机是最小的「非平凡多机环境」：它同时考验「排序」和「选机」两个决策，是后续 flexible job shop、混合流水线等一切多机调度的起点。今天的任务，就是把这「多出来的一个维度」用最小、最干净的方式落地。

---

## 3. 三字段记号与 P / Q / R 三类并行机

三字段记号 `α | β | γ` 里，第一项 `α` 描述**机器环境**。并行机有三类：

| 记号 | 名字 | 加工时间 | 直觉 |
|---|---|---|---|
| `1` | 单机 | —— | 前四天，只有一台机器 |
| `P` | Identical（同质并行机） | `p_j` 与机器无关 | 每台机器一样快 |
| `Q` | Uniform（均匀并行机） | `p_ij = p_j / s_i` | 机器有速度 `s_i`，同样任务在快机上更快 |
| `R` | Unrelated（无关并行机） | `p_ij` 逐机器不同 | 最一般，任务在每台机器上时间都不同 |

今天**只做 `P`（同质并行机）**：同一个 job 在任何机器上加工时间都相同，所以现有 `Operation.processing_time` 这一个字段就够用，无需扩展模型。`Q` 和 `R` 需要「机器相关加工时间」，是后续（M2 的 flexible 模型）才引入的内容。

完整记号 `P||Cmax`：

- `P`：同质并行机；
- 中间空：无释放时间、无优先级约束、不可抢占；
- `Cmax`：目标是最小化 makespan（最后完工的 job 的完工时间）。

---

## 4. 决策：排序 + 选机，缺一不可

`P||Cmax` 的决策是**二元组**：既要给 job 排顺序，又要给每个 job 指定机器。只排序不选机，或只选机不排序，都得不到可行解。

一个关键对比（呼应 Day 4 自测题 Q10）：

```text
单机 1||Cmax：Σpj 固定，任何顺序 Cmax 都一样 —— 顺序「不改变」Cmax。
并行 P||Cmax：Cmax = max_i(机器 i 上的总负载)，负载怎么分「会改变」Cmax。
```

所以单机上 LPT 对 `Cmax` 毫无意义（只是另一个顺序），而到了并行机，**负载分配**才第一次成为真正要优化的对象。这也是为什么 Day 4 说「LPT 的正途是并行机 `P||Cmax`」。

---

## 5. LPT List Scheduling：两步

LPT（Longest Processing Time First）是 `P||Cmax` 最经典的列表调度（list scheduling）基线，分两步：

1. **排序（sequencing）**：把所有 job 按加工时间 `p` 从大到小排好。
2. **分配（assignment）**：按这个顺序，把每个 job 放到「当前 ready 时间最小」的那台机器上。

直觉：**长任务先放**，短任务最后用来「填空」，负载自然趋近平衡。用一个四 job 的例子感受一下（先不给出完整表格，见第 9 节）：

```text
p = [8, 7, 6, 5]，m = 2 台机器
LPT 顺序：8, 7, 6, 5
8 → M1（负载 0），7 → M2（负载 0），6 → M2（负载 7 < 8），5 → M1（负载 8 < 13）
M1：8 + 5 = 13；M2：7 + 6 = 13  →  Cmax = 13，完美平衡
```

列表调度的「两步」是理解今天所有内容的主线：**排序回答「顺序」，选机回答「机器」，两者合起来才是并行机的完整决策。**

---

## 6. 最小选机表示：`eligible_machine_ids` vs `machine_id`

这是今天要修正的一个重要概念。旧的笔记把「机器指派」描述成「一个元组，位置与 `instance.operations` 一一对应」——那是 Week 2 的 `Candidate.assignments` **中间表示**，不是今天要教的最小选机表示。

最小选机表示只有两个字段，一个在输入、一个在输出：

| 字段 | 位置 | 含义 | 性质 |
|---|---|---|---|
| `Operation.eligible_machine_ids` | 输入模型 | 这个工序**允许**在哪几台机器上做 | 约束（允许范围） |
| `ScheduledOperation.machine_id` | 排程结果 | 这个工序**实际**被安排到了哪台机器 | 决策（实际选择） |

关键认识：

- **输入只写「允许范围」，不写「选哪台」。** `eligible_machine_ids` 是一组机器 ID，是一个集合/元组，例如 `("M0", "M1")`。
- **输出才写「最终决策」。** 算法从允许范围里挑出一台，记成单个 `machine_id` 字符串，例如 `"M1"`。
- 「允许范围」是问题给的约束，「实际选择」是算法做的决策，两者不能混为一谈。

```python
Operation(id="O0", job_id="J0", processing_time=8,
          eligible_machine_ids=("M0", "M1"))     # 输入：可以在 M0 或 M1 上做

ScheduledOperation(operation_id="O0", machine_id="M1",
                   start_time=0, end_time=8)      # 输出：最终选在了 M1
```

今天的 `P||Cmax` 每个 job 一道工序、全机器资格，所以 `eligible_machine_ids` 里是全部机器，选机结果体现在输出的 `machine_id` 上。这也是「最小」的含义：**不需要为选机发明任何新数据结构，Schedule 里的一个 `machine_id` 字段就是选机决策。**

---

## 7. `machine_ready_time`：唯一状态

算法只需要维护一个状态：**每台机器当前的 ready 时间**（= 这台机器上已排任务的总加工量，`r=0` 时）。

```text
state       machine_ready: dict[str, int]   每台机器当前的 ready 时间
decision    这台工序放到哪台机器上
transition  把该机器的 ready 时间推进到这道工序的完工时间
```

伪代码：

```text
machine_ready = {每台机器: 0}                    # state
order = 按 p 降序、job.id 升序排序的工序列表      # 排序决策

for op in order:                                 # 分配决策
    m = argmin( machine_ready[m] )               # 选 ready 最小的机器（平局按 machine.id）
    start = machine_ready[m]                     # r=0 时 start 就是该机器 ready
    end = start + op.processing_time             # transition
    machine_ready[m] = end
    scheduled.append(ScheduledOperation(op, m, start, end))
```

**为什么不能给输入 `Machine` 加一个 `current_load` 字段？** 因为 `Machine` 是**输入模型**（frozen dataclass），机器此刻「已经干了多少活」是**求解过程中的临时状态**，不是问题本身的数据：

1. 混入后输入不再纯净——同一个 Instance 两次求解之间会互相污染；
2. 破坏不可变性——`Machine` 是 frozen 的，本就不该被改动；
3. 破坏可复现——结果依赖调用历史，违背「确定性实验」的原则。

所以 `machine_ready` 必须是**算法内部的局部字典**，进函数创建、出函数丢弃。这是「输入 / 状态 / 结果」三分离的体现（Day 2 的约定）。

---

## 8. 确定性 tie-breaking

并行机有两个地方可能出现平局，都要做确定性决胜：

| 平局场景 | 决胜键 | 例子 |
|---|---|---|
| 两个 job 的 `p` 相同 | `job.id` 升序 | `p=[5,5]` → J1 先于 J2 |
| 两台机器 ready 相同 | `machine.id` 升序 | 初始 0/0 → 选 M1 |

这保证**同一个 Instance 每次跑出完全相同的结果**，与输入顺序、运行次数无关——是「可复现实验」的基本保障（与 Day 4 第 7.5 节同一个原则，只是决胜键从 `job.id` 扩展到了 `machine.id`）。

---

## 9. 手算：2 台机器 `[8, 7, 6, 5]`

| Job | `pj` |
|---|---:|
| J1 | 8 |
| J2 | 7 |
| J3 | 6 |
| J4 | 5 |

LPT 排序：J1(8), J2(7), J3(6), J4(5)。逐台分配：

| 步骤 | Job | `p` | 选机 | 开始 | 完成 | 选机理由 |
|---|---|---|---:|---:|---:|---|
| 1 | J1 | 8 | M1 | 0 | 8 | M1/M2 都 0，平局 → M1 |
| 2 | J2 | 7 | M2 | 0 | 7 | M2(0) < M1(8) |
| 3 | J3 | 6 | M2 | 7 | 13 | M2(7) < M1(8) |
| 4 | J4 | 5 | M1 | 8 | 13 | M1(8) < M2(13) |

```text
M1：J1(0-8), J4(8-13)  → 负载 13
M2：J2(0-7), J3(7-13)  → 负载 13
Cmax = 13，ΣCj = 8 + 7 + 13 + 13 = 41
```

下界 `LB = max(max p, ceil(Σp/m)) = max(8, ceil(26/2)) = max(8, 13) = 13`。`Cmax == LB`，所以这个实例上 LPT **已经最优**。

---

## 10. 手算：3 台机器 `[9, 8, 7, 6, 5, 4]`

| Job | `pj` |
|---|---:|
| J1 | 9 |
| J2 | 8 |
| J3 | 7 |
| J4 | 6 |
| J5 | 5 |
| J6 | 4 |

LPT 排序：9, 8, 7, 6, 5, 4。

| 步骤 | Job | `p` | 选机 | 完成后各机 ready |
|---|---|---|---:|---|
| 1 | J1 | 9 | M1 | M1=9 |
| 2 | J2 | 8 | M2 | M2=8 |
| 3 | J3 | 7 | M3 | M3=7 |
| 4 | J4 | 6 | M3（7 最小） | M3=13 |
| 5 | J5 | 5 | M2（8 最小） | M2=13 |
| 6 | J6 | 4 | M1（9 最小） | M1=13 |

```text
M1：9 + 4 = 13；M2：8 + 5 = 13；M3：7 + 6 = 13
Cmax = 13，LB = max(9, ceil(39/3)) = max(9, 13) = 13  →  最优
```

这个例子说明 LPT 在 3 台机器上也能把负载摊平到恰好等于下界。

---

## 11. Lower Bound：何时能说「LPT 已最优」

`P||Cmax` 有两个天然下界，任一可行排程都迈不过去：

```text
LB1 = max_j p_j            # 最长那道工序自己就是串行瓶颈
LB2 = ceil(Σ_j p_j / m)    # 总工作量被 m 台机器平摊的平均负载
LB  = max(LB1, LB2)
```

于是有了一个**证明最优**的捷径：

> 若 `Cmax_LPT == LB`，则该实例上 LPT 排程就是最优的。

因为最优值 `Cmax_OPT` 满足 `LB ≤ Cmax_OPT ≤ Cmax_LPT`，当左右两端相等时三者全等。

**两个概念务必区分**（都是「gap」，但对象不同）：

| 概念 | 英文 | 定义 | 意义 |
|---|---|---|---|
| 下界差距 | lower-bound gap | `Cmax − LB` | 相对「下界」还差多少，**能证明**还有没有改进空间 |
| 最优性差距 | optimality gap | `Cmax − Cmax_OPT`（best-known） | 相对「已知最好解」差多少，只是**估计** |

关键：`LB` 是**下界**，不是最优值。`Cmax == LB` 能证明最优，但 `Cmax > LB` 不意味着还有改进空间——也可能 `LB` 本身太松，最优值本就高于 `LB`。而 `best-known ≠ optimum`，用已知最好解算出的 gap 只是估计。很多初学者把这三者混在一起，是调度实验里最常见的错误之一。

代码里空实例（没有 job）返回 0，作为边界约定：

```python
def parallel_makespan_lower_bound(instance: Instance) -> int:
    processing_times = [操作 p 的列表]
    if not processing_times:
        return 0
    total, longest = sum(processing_times), max(processing_times)
    return max(longest, math.ceil(total / len(instance.machines)))
```

---

## 12. LPT 不是万能的：近似界与反例（选学）

LPT 是启发式，**不保证最优**，但它有一个可证明的近似界：

```text
Cmax_LPT / Cmax_OPT  ≤  4/3 − 1/(3m)
```

当机器数 `m` 很少时这个界最差（`m=1` 时退化为 1，因为单机 LPT 恰好等于最优 `Σp`）；`m` 越大界越紧。它的意义是：**LPT 最多比最优解慢约 33%**（`m` 较小时），是可接受的基线。

LPT 会失败的最小反例（2 台机器，`p = [3, 3, 2, 2, 2]`）：

```text
LPT：3→M1, 3→M2, 2→M1, 2→M2, 2→M1（平局按 M1）
    M1 = 3+2+2 = 7，M2 = 3+2 = 5  →  Cmax = 7

最优：M1 = 3+3 = 6，M2 = 2+2+2 = 6  →  Cmax = 6

LB = max(3, ceil(12/2)) = 6，而 LPT 得 7 > LB
```

结论：**LPT 是「简单、确定、有界」的基线，不是最优算法**。它的价值在于（1）给后续更复杂的算法提供一个必须打败的下限；（2）在大多数实例上已经接近最优。这条基线先打对，比急着上精确求解更重要。

---

## 13. 实现：`parallel_lpt` 与 decoder

对应文件 [rules.py](../../projects/01_scheduling_core/scheduling_algorithms/rules.py) 与 [decoder.py](../../projects/01_scheduling_core/scheduling_algorithms/decoder.py)。

本仓库的 `parallel_lpt` 是一个**薄入口**，把排序和选机委托给 decoder 的两个函数：

```python
def parallel_lpt(instance: Instance) -> Schedule:
    """并行机 LPT 列表基线。r=0、同质且全资格时为经典 P||Cmax。"""
    from scheduling_algorithms.decoder import decode, initial_candidate

    validate_instance(instance)
    if any(len(job.operation_ids) != 1 for job in instance.jobs):
        raise ValueError("parallel LPT requires one operation per job")
    return decode(instance, initial_candidate(instance))
```

- `initial_candidate(instance)`：做 LPT 排序（`p` 降序、`op.id` 升序）并贪心选机（`(max(load, release), machine.id)` 最小），产出 `Candidate(order, assignments)`。
- `decode(instance, candidate)`：用 `machine_ready` 字典推进时间，产出 `Schedule`。

这等价于第 7 节的自包含 `machine_ready_time` 循环——只是把「排序 + 选机」拆到了 `initial_candidate`、把「状态推进」拆到了 `decode`。**为什么保留这个委托结构而不是重写成自包含循环？** 因为 `decode` 已经能正确处理 `r > 0`、前置工序等更一般的情况，重写一遍只会复制逻辑并退回「只支持 r=0」的窄版本。今天教概念时用第 7 节的简单循环，读代码时看真实实现。

下界函数放在 `parallel_lpt` 旁边：

```python
def parallel_makespan_lower_bound(instance: Instance) -> int:
    """P||Cmax 的下界：max(最长加工时间, ceil(总加工时间 / 机器数))。"""
    ...
    return max(longest, math.ceil(total / machine_count))
```

注意：`parallel_lpt` 要求「每个 job 恰好一道工序」，不满足时抛 `ValueError`；多工序是 Week 2 decoder 的内容，今天不涉及。

---

## 14. Gantt 数据：`to_gantt_rows` / `write_gantt_csv`

对应文件 [export.py](../../projects/01_scheduling_core/scheduling_io/export.py)。

甘特图只需要六列数据，`to_gantt_rows` 把 `Schedule` 转成六字段的 dict 列表：

```text
machine_id, job_id, operation_id, start_time, end_time, duration
```

两点设计：

1. **`job_id` 由 `operation_id` 反查**。`Schedule` 里的 `ScheduledOperation` 只存 `operation_id`（结果的最小表示），`job_id` 通过 `instance.operations` 反查得到。这再次体现「结果最小化、其余可反查」的原则。
2. **按 `(machine_id, start_time, operation_id)` 排序**。算法内部的决策顺序不是甘特图的展示顺序；排序让输出确定、便于人工查看和 diff。

`write_gantt_csv` 用 `csv.DictWriter` 写出固定六列的 CSV（`newline=""` 避免 Windows 下空行，`utf-8` 编码）。

**Gantt 数据 ≠ Schedule**：`Schedule` 是**领域模型**（不可变、最小、只含结果字段），`gantt rows` 是**展示模型**（给绘图/报表用的宽表，含 `job_id`、`duration` 等派生字段）。领域模型负责「正确」，展示模型负责「好看」，两者分开，不要互相污染。

---

## 15. 实验：`m1w1d5_parallel`

对应脚本 [m1w1d5_parallel.py](../../projects/01_scheduling_core/examples/m1w1d5_parallel.py)，在项目目录下运行：

```bash
python -m examples.m1w1d5_parallel
```

脚本流程：`parallel_lpt → validate_schedule → makespan → parallel_makespan_lower_bound → to_gantt_rows → write_gantt_csv`。对 `[8,7,6,5]` 2 台机器，输出：

```text
makespan = 13, lower_bound = 13   （相等 → 该实例最优）
四行六字段 gantt rows，并写出 lpt_gantt.csv
```

脚本里的 `assert value == 13 and lower == 13` 把第 9 节的手算固化成断言——实验脚本的第一职责就是「把手算变成可重复的检查」。

---

## 16. 今日练习

1. **练习 1（手算）**：对 `p=[5,5,4,4,3,3,3]` 3 台机器手算 LPT，求 Cmax 和下界，判断是否最优。
2. **练习 2（选机观察）**：把第 9 节实例的 J4 改成 `p=9`，手算新结果，确认长任务先放会影响后续选机。
3. **练习 3（资格限制）**：把 J3 的 `eligible_machine_ids` 限定为 `("M1",)`，观察资格限制如何改变负载分配。
4. **练习 4（反例）**：自己再构造一个 LPT 非最优的 `P||Cmax` 例子，验证 `Cmax_LPT > LB`。
5. **练习 5（代码阅读）**：不看 `export.py`，自己写出 `to_gantt_rows` 的六字段和排序键，再与实现对照。

---

## 17. 验收清单

- [ ] 能说出 `P/Q/R` 三类并行机的区别，以及今天为什么只做 `P`。
- [ ] 能解释并行机决策 = 排序 + 选机，缺一不可。
- [ ] 能说清 `eligible_machine_ids`（允许范围）与 `machine_id`（实际决策）的区别。
- [ ] 能独立写出 `machine_ready_time` 的 `state → decision → transition` 循环。
- [ ] 能解释为什么不能给输入 `Machine` 加 `current_load` 字段。
- [ ] 会用下界 `LB = max(max p, ceil(Σp/m))` 证明 LPT 最优，并区分 lower-bound gap 与 optimality gap。
- [ ] 能举出 LPT 非最优的例子，并说出 `4/3 − 1/(3m)` 近似界。
- [ ] 代码补齐：`parallel_makespan_lower_bound`、`to_gantt_rows`、`write_gantt_csv`。
- [ ] `python -m pytest -q` 全部通过（本日新增 12 条并行 LPT/下界测试 + 4 条 Gantt 导出测试）。
- [ ] `python -m examples.m1w1d5_parallel` 输出 makespan=13、lower_bound=13 并写出 CSV。

---

## 18. 自测题

不看上文回答：

- Q1：`P`、`Q`、`R` 三类并行机各是什么？加工时间分别如何定义？
- Q2：`P||Cmax` 的决策为什么比 `1||Cmax` 多一个维度？
- Q3：LPT 列表调度的两步分别是什么？
- Q4：`eligible_machine_ids` 和 `machine_id` 分别是什么？谁在输入、谁在输出？
- Q5：为什么不能把「机器当前负载」存进输入 `Machine`？
- Q6：两个 job 的 p 相同、两台机器 ready 相同时，分别用什么做平局决胜？
- Q7：`P||Cmax` 的下界公式是什么？什么条件下能证明 LPT 最优？
- Q8：lower-bound gap 和 optimality gap 的区别？
- Q9：LPT 的近似界是多少？举一个 LPT 非最优的例子。
- Q10：Gantt 数据与 Schedule 是什么关系？为什么 `to_gantt_rows` 要排序？

### 参考答案

- A1：`P` 同质（`p_j` 与机器无关）、`Q` 均匀（`p_j / s_i`，机器有速度）、`R` 无关（`p_ij` 逐机器不同）。今天只做 `P`。
- A2：单机只决定「顺序」，并行机还要决定「每道工序放哪台机器」，即 assignment。
- A3：① 按 `p` 降序排序；② 把每个 job 放到当前 ready 最小的机器。
- A4：`eligible_machine_ids` 是输入的「允许范围」约束；`machine_id` 是输出的「实际选择」决策。前者在输入 `Operation`，后者在结果 `ScheduledOperation`。
- A5：`Machine` 是 frozen 输入模型，`current_load` 是求解过程的临时状态；混入会污染输入、破坏不可变与可复现。应作为算法内部局部字典。
- A6：job 平局按 `job.id` 升序，机器平局按 `machine.id` 升序。
- A7：`LB = max(max_j p_j, ceil(Σ p_j / m))`。当 `Cmax_LPT == LB` 时证明最优。
- A8：lower-bound gap 是 `Cmax − LB`（相对下界，能证明改进空间）；optimality gap 是相对 best-known 的估计，best-known 未必是最优。
- A9：`4/3 − 1/(3m)`。反例 `p=[3,3,2,2,2]` 2 机：LPT=7，最优=6。
- A10：Gantt 是展示模型、Schedule 是领域模型；排序 `(machine_id, start_time, operation_id)` 让输出确定、便于查看和 diff。

---

## 19. 今日一句话总结

> **并行机让「排谁」之外多出「排哪台机器」；LPT 用「长任务先放、短任务填空」把负载摊平，下界 `max(max p, ceil(Σp/m))` 告诉你能不能证明它已经最优，而 `machine_id` 这一个字段就是选机决策的最小表示。**
