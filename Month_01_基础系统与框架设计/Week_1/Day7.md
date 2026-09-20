# Day 7：规则最优性条件、失效反例与 Week 1 复盘

> 当日主题：汇总规则最优性条件、失效反例与本周问题
> 当日产出：**`week1.md` 周总结 + 规则知识卡片 + 反例集 + 遗留问题清单**
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说清楚 Day 1–6 到底建立了什么，而不是背出六天的目录。
2. 把四条规则**和它们的最优目标一起**说出来（`SPT → 1||ΣCj`，而不是「SPT 最优」）。
3. 区分三类语句：**定义**、**理论结论**、**实验观察**——它们不能混写。
4. 完整写出四个失效反例（CE-01 ~ CE-04），并说明每个反例推翻了什么。
5. 说清楚 `Lower Bound` 能证明什么、不能证明什么。
6. 明确写出 Week 1 **还没有做**什么，以及为什么这不是缺陷而是分阶段推进。
7. 留下至少 5 个明确问题，作为本周复盘的遗留问题清单。

**Day 7 不新增任何算法。** 今天的任务是：把 Day 1–6 的零散知识，整理成可复用的调度基础框架。

---

## 2. 为什么要有「复盘日」

前六天每天在加东西：模型、解析、规则、并行机、手算对拍。零散的知识有一个共同的毛病：

> **学过 ≠ 会判断什么时候能用。**

具体表现：

- 知道 SPT 最优，但不知道「加了 `rj` 就不最优了」；
- 知道 EDD 管交期，但不知道它**只管 Lmax、不管 ΣTj**；
- 写上 `heuristic` 的解，却在报告里写成 `optimum`；
- 被问「你的算法好不好」，答不出「和什么比、在什么条件下比」。

复盘的产出不是「更长的笔记」，而是把知识压缩成**条件表 + 反例集 + 接口约定**——这三样东西以后每个月都会被重新翻出来用。参考文档说得很直接：Day 7 应该按「概念 → 结论 → 证据 → 局限 → 下一步」组织，而不是按「Day 1 学了什么、Day 2 写了什么」写流水账。

---

## 3. Week 1 的七天链路

```text
Day 1  调度问题语言 α|β|γ + 领域词汇
        ↓
Day 2  Job / Operation / Machine / Instance 不可变输入模型
        ↓
Day 3  JSON / CSV 解析 + 输入校验 + Objective
        ↓
Day 4  SPT / EDD / WSPT / LPT + 释放时间处理
        ↓
Day 5  并行机 LPT + 最小选机表示 + Schedule/Gantt 数据
        ↓
Day 6  ≥10 个手算实例 + pytest 对拍
        ↓
Day 7  最优性条件 + 失效反例 + 接口约定 + 遗留问题
```

工程上已经形成一条完整流水线：

```text
Raw Data → Parser → Instance → Input Validator
        → Scheduling Rule → Schedule → Objective
        → Gantt / Metrics → Manual Test Cases
```

这条骨架是 Month 1 后续所有算法的基础，也是后面 MILP / CP-SAT / 局部搜索 / RL 都必须挂上来的地方。

---

## 4. 四条规则的核心知识卡

| 规则 | 排序 / 决策 | 经典最优问题 | 结论 |
|---|---|---|---|
| SPT | `p` 升序 | `1\|\|ΣCj` | **最优** |
| EDD | `d` 升序 | `1\|\|Lmax` | **最优** |
| WSPT | `p/w` 升序 | `1\|\|ΣwjCj` | **最优** |
| LPT（并行） | `p` 降序 + 选最小 ready 机器 | `P\|\|Cmax` | **启发式 / 近似** |

四点补充：

- **WSPT 的键是比值 `p/w`**，不是「w 大的先做」。直觉是「单位权重耗时越短越优先」。
- **EDD 遇 `due_date=None` 视为 +∞**，排到最后；实现上用 `(has_due, due_date)` 元组。
- **LPT 在单机上几乎没有对应目标**，它真正的用武之地是 `P||Cmax`。
- 上表的「最优」全部附带条件：**无释放时间、无额外约束**。

完整速查见 [rules_cheatsheet.md](../../projects/01_scheduling_core/notes/rules_cheatsheet.md)。

---

## 5. 「最优性条件」比规则名字更重要

这一节是今天最核心的观念。错误记忆和正确表述的对比：

| 错误 | 正确 |
|---|---|
| SPT 是最优算法 | SPT 对 `1\|\|ΣCj` 最优 |
| EDD 能解决交期问题 | EDD 对 `1\|\|Lmax` 最优 |
| WSPT 对带权问题最优 | WSPT 对 `1\|\|ΣwjCj` 最优 |
| LPT 是并行机最优算法 | LPT 是 `P\|\|Cmax` 的经典启发式，有近似保证，一般不保证最优 |

> **调度学习里必须养成：规则和 `α|β|γ` 一起记。**

原因很实际：`β` 字段改一点点，结论可能就完全变了。加了 `rj`，SPT 不最优了；目标从 `Lmax` 换成 `ΣTj`，EDD 不最优了。脱离问题描述的「最优」没有意义。

---

## 6. 三个层次的知识：定义 / 理论 / 实验

写周报和以后写论文时，这三类语句**不能混**：

| 内容 | 类型 |
|---|---|
| SPT 按 `p` 升序排列 | 定义 |
| SPT 对 `1\|\|ΣCj` 最优 | **理论结论** |
| 本仓库 10 个手算 case 中 SPT 的 `ΣCj` 最低 | **实验观察** |
| EDD 对 `1\|\|Lmax` 最优 | **理论结论** |
| Case A 中 EDD 的 `Lmax` 最小 | **实验观察** |
| Parallel LPT 在 `[8,7,6,5]` 上 `Cmax=13` | **实验观察** |
| LPT 一般不保证 `P\|\|Cmax` 最优 | **理论边界** |

为什么重要：以后写「我的 ALNS 在 20 个实例上最好」，这是**实验观察**，不等于「ALNS 总是最好」。把实验结果写成理论结论，是算法研究里最常见、也最致命的表述错误。

---

## 7. 失效反例 1（CE-01）：释放时间破坏 SPT 最优性

| Job | `rj` | `pj` |
|---|---:|---:|
| A | 0 | 100 |
| B | 1 | 1 |

目标 `1|rj|ΣCj`。

**non-delay SPT**（机器不空闲）：

```text
t=0  只有 A 已释放 → A: 0→100
B: 100→101
ΣCj = 100 + 101 = 201
```

**故意空转**：

```text
idle 0→1
B: 1→2
A: 2→102
ΣCj = 2 + 102 = 104
```

**结论**：SPT 对 `1||ΣCj` 的最优性**不能推广**到 `1|rj|ΣCj`。有 `rj` 时，最优排程可能需要在机器空闲时**故意等待**一个即将到达的短任务（`1|rj|ΣCj` 是 NP-hard）。non-delay 策略主动放弃了这类选择——它是基线，不是最优。

---

## 8. 失效反例 2（CE-02）：EDD 不保证最小 ΣTj

| Job | `pj` | `dj` |
|---|---:|---:|
| J1 | 1 | 1 |
| J2 | 1 | 3 |
| J3 | 3 | 2 |

**EDD**（`d` 升序 → J1, J3, J2）：

```text
C = [1, 4, 5]
T = [0, 4-2=2, 5-3=2]
ΣTj = 4
```

**J1, J2, J3**：

```text
C = [1, 2, 5]
T = [0, 0, 5-2=3]
ΣTj = 3   ← 更小
```

**结论**：EDD 对 `1||Lmax` 最优，但推不出它对 `1||ΣTj` 最优。两者都是「交期指标」，但：

```text
Lmax = max_j (Cj - dj)      看「最严重的一次偏离」
ΣTj  = Σ max(0, Cj - dj)    看「累计迟交量」
```

**都是交期指标，不代表有相同的最优规则。** `1||ΣTj` 也是 NP-hard。

---

## 9. 失效反例 3（CE-03）：Parallel LPT 不保证 P||Cmax 最优

```text
2 台机器，p = [3, 3, 2, 2, 2]
```

**LPT**（`p` 降序 + 最小负载机器，平局选 M0）：

```text
M0: 3 → 3+2=5 → 5+2=7
M1: 3 → 3+2=5
Cmax_LPT = 7
```

**最优**：

```text
M0: 3+3 = 6
M1: 2+2+2 = 6
Cmax_OPT = 6
```

**结论**：LPT 是 `P||Cmax` 的启发式，有近似界 `4/3 − 1/(3m)`，但**一般不保证最优**。

这里还能顺带验证第 12 节的下界用法：`LB = max(3, ceil(12/2)) = 6`，而 LPT 得 7 > LB——**下界低于实际值，说明确实还有改进空间**（此处确实找得到 6）。

---

## 10. 失效反例 4（CE-04）：单机 LPT 对 ΣCj 很差

```text
p = [6, 4, 2]

SPT: 2 → 4 → 6    C = [2, 6, 12]     ΣCj = 20
LPT: 6 → 4 → 2    C = [6, 10, 12]    ΣCj = 28
```

**结论**：单机上 LPT 只应作为**对照 baseline**，不能当作 `ΣCj` 规则。先做长任务会拖长所有后续任务的完工时间，而 `ΣCj` 是对**每一个**完成时刻求和。LPT 的正途是 `P||Cmax` 的列表调度。

四个反例都已编码成可执行断言，见 [test_week1_review.py](../../projects/01_scheduling_core/tests/test_week1_review.py)，反例库见 [counterexamples.md](../../projects/01_scheduling_core/notes/counterexamples.md)。

---

## 11. 释放时间下的 dispatching 逻辑

Day 4 实现的基线：

```text
while 还有未排程的 job:
    available = { j | rj <= current_time }      # 可选集合
    if available:
        按规则挑一个，加工完推进 current_time
    else:
        current_time = 剩余 job 的最小 rj        # 空转等待
```

关键认识：**释放时间不是「修改优先级」，而是「限制可选集合」。** 规则只决定「在已释放的 job 里挑谁」，`rj` 决定「哪些 job 现在有资格被挑」。

这套逻辑简单、可解释、确定，但它属于 **heuristic baseline**，不是一般最优算法——CE-01 就是它失效的证据。

---

## 12. Lower Bound 的正确用法

`P||Cmax` 的下界：

```text
LB = max( max_j p_j ,  ceil(Σ p_j / m) )
      ↑ 最长 job 自己至少这么久   ↑ 总工作量平摊
```

正确推理（参考文档 §28）：

```text
若 解 = 13，LB = 13
  则 OPT >= 13（下界定义）
  且已找到可行解 = 13
  所以 OPT = 13   ← 可以证明最优

若 解 = 19，LB = 17
  只能说 17 <= OPT <= 19
  不能说 OPT = 17
  也不能直接说「距离最优 11.76%」    ← best-known ≠ optimum
```

两个 gap 必须区分：

| 概念 | 定义 | 性质 |
|---|---|---|
| lower-bound gap | `Cmax − LB` | 相对**下界**，能证明还有没有改进空间 |
| optimality gap | `Cmax − Cmax_OPT`（best-known） | 相对**已知最好解**，只是估计 |

> **只有 `UB == LB`，或用精确算法证实，才能写 `optimum`。否则写 `solution` / `best found`。**

---

## 13. 数据模型与输入输出分离

当前最小输入模型：

```text
Instance
├── Jobs:       id, operation_ids, release_time, due_date, weight
├── Operations: id, job_id, processing_time, eligible_machine_ids
└── Machines:   id, name
```

输出模型：

```python
ScheduledOperation(operation_id, machine_id, start_time, end_time)
Schedule(operations=(...))
```

**输入与输出必须分开**：

```python
# 错误：把求解结果塞进输入
Operation(processing_time=5, machine_id="M1", start_time=10)
```

`machine_id` 和 `start_time` 是**决策结果**，不是问题数据。对应关系是：

```text
Operation                = 问题数据
Operation.eligible_machine_ids = 允许在哪几台机器加工（约束/允许范围）
ScheduledOperation       = 决策结果
ScheduledOperation.machine_id  = 最终实际选了哪台机器（实际决策）
```

**为什么输入必须不可变**：同一个 `Instance` 要被 SPT、EDD、局部搜索、SA、MILP 公平复用。如果某个算法改了输入，就会污染下一个算法的结果。所以用 `@dataclass(frozen=True)` + `tuple`，把运行状态（如 `machine_ready`）留在**算法内部的局部变量**里。

---

## 14. Objective 总结

| 指标 | 公式 | 业务含义 |
|---|---|---|
| `Cmax` | `max_j C_j` | 所有任务什么时候全部完成 |
| `ΣCj` | `Σ_j C_j` | 整体完成速度、平均完成体验 |
| `Lmax` | `max_j (C_j - d_j)` | 最严重的交期偏离（**可为负**） |
| `ΣTj` | `Σ_j max(0, C_j - d_j)` | 累计迟交程度（恒非负） |
| `ΣwjCj` | `Σ_j w_j C_j` | 高价值任务是否更早完成 |
| `ΣFj` | `Σ_j (C_j - r_j)` | 总流程时间（`r=0` 时等于 `ΣCj`） |

**核心认识：不存在脱离 objective 的「最好排程」。**

```text
同一个 Schedule：可能 ΣCj 很好，但 Lmax 很差
另一个 Schedule：可能交期很好，但 ΣwjCj 不好
```

所以「Rule 产生 Schedule，Objective 评价 Schedule」必须严格分离——规则的代码里**不应该**偷偷算自己的一套指标，否则不同算法之间无法公平比较。

---

## 15. 确定性与平局决胜

Week 1 所有 baseline 都必须是**确定的**：

```text
相同 Instance + 相同 Config  →  相同 Schedule
```

这要求固定 tie-breaking：

```text
Job 平局:     job.id 升序
Machine 平局: machine.id 升序
```

这是**可复现性契约（reproducibility contract）**，以后任何重构都不应随便改。

一个容易忽略的边界：**字符串 ID 的字典序不是自然数字序**。

```text
字符串排序:  J1, J10, J2
自然数字序:  J1, J2, J10
```

Month 1 只要求「确定性」，所以字符串排序可以接受。但如果业务要求自然数字序，需要额外加 `sequence_index` 或规范化 ID 格式。**知道这个边界在哪，比现在就去修它更重要。**

---

## 16. 测试策略：手算 expected + 断言

Day 6 建立的习惯：

```text
小实例 + 手算 expected + pytest assert
```

三条纪律：

1. **expected 必须来自手算，不能由被测函数生成。** 否则测试只能证明「跑两次结果一样」，证明不了「结果正确」。
2. **不能只 assert「不报错」。** 调用成功只说明程序没崩，不代表算法正确。
3. **至少测**：规则顺序、机器指派、开始/结束时间、目标值、平局决胜。

这套习惯要一直带到后面的 decoder、局部搜索、SA、MILP、CP-SAT、RL——**复杂算法的第一道防线永远是「小实例 + 手算答案」。**

---

## 17. 实验：Week 1 复盘

对应脚本 [m1w1d7_review.py](../../projects/01_scheduling_core/examples/m1w1d7_review.py)，在项目目录下运行：

```bash
python -m examples.m1w1d7_review
```

脚本打印四条规则的最优性表，跑四个失效反例并断言成立，最后打印确定性契约：

```text
CE-01 release-time SPT: non-delay ΣCj=201 > 最优 104
CE-02 EDD vs ΣTj:      EDD ΣTj=4 > 最优 3
CE-03 parallel LPT:    LPT Cmax=7 > 最优 6.0
CE-04 单机 LPT vs ΣCj:  SPT ΣCj=20 < LPT ΣCj=28
```

**实验观察 ≠ 理论结论**：这里每个反例都只是**一个实例上的观察**，它们的作用是**证伪**（「SPT 加了 rj 还最优」被推翻），而不是**证明**（不能证明「SPT 在所有 rj 实例上都很差」）。

---

## 18. 本周还没有做什么

必须明确写下，不要假装基础问题都解决了：

```text
没有实现 MILP / CP-SAT
没有做局部搜索 / SA / 元启发式
没有工业级约束：setup / calendar / worker
```

这些不是缺陷，是**分阶段推进**：先把 `baseline + validator + objective + benchmark` 做可信，后面的精确算法才有公平参照。现在急着上 MILP 或强化学习，最大的问题是「没有可信基线，好坏无法判断」。

---

## 19. 遗留问题（Open Questions）

| # | 问题 | 状态 |
|---|---|---|
| 1 | 候选解（Candidate）与 Schedule 应如何分离？ | 已由 `scheduling_core/solution.py` 落地 |
| 2 | decoder 应保证可行，还是 validator 负责发现错误？ | 两者独立：`decoder.py` 构造，`schedule_validation.py` 独立校验 |
| 3 | 有释放时间时，静态 permutation 如何解码？ | `decode` 用 `max(machine_ready, predecessor_end, release)` |
| 4 | 并行机 permutation 是否足以表示机器指派？ | 不足，`Candidate` 需同时含 `order` 与 `assignments` |
| 5 | 邻域如何保证不制造非法解？ | `neighborhoods.py` 只产生新 Candidate，由 `validate_candidate` 把关 |
| 6 | 如何做小规模枚举对拍？ | `oracle.py` 独立穷举，`test_month1.py` 已验证 5 个种子 |
| 7 | 随机实例从哪来？ | `scheduling_io/generator.py`（局部 RNG，不改全局随机状态） |

**关键原则**：枚举对拍和独立校验器解决的是同一个问题——**不能让 decoder 自己证明自己**。这和 Day 6「expected 不由被测函数生成」是同一个思想。

---

## 20. 验收清单（Week 1 Exit Checklist）

**问题语言**

- [ ] 能解释 `α|β|γ`
- [ ] 能解释 `1||ΣCj` / `1||Lmax` / `1||ΣwjCj` / `P||Cmax`

**模型**

- [ ] Job / Operation / Machine / Instance / Schedule
- [ ] 输入不可变（`frozen=True` + `tuple`）
- [ ] 输入与结果分离（`eligible_machine_ids` vs `machine_id`）

**Objective**

- [ ] Cmax / ΣCj / Lmax / ΣTj / ΣwjCj 的公式与业务含义
- [ ] Lmax 可为负、ΣTj 恒非负

**规则**

- [ ] SPT / EDD / WSPT / LPT / Parallel LPT 的排序键与最优目标
- [ ] 能说出每条规则的失效边界

**释放时间**

- [ ] available set / 空转 / next release / non-delay 的局限

**测试**

- [ ] ≥10 个手算 case 通过
- [ ] 4 个失效反例可执行
- [ ] 确定性 tie-breaking 已固定
- [ ] `python -m pytest -q` 全绿

**工程**

- [ ] 当前 API 已记录
- [ ] Gantt schema 已记录（六字段 + 排序键）
- [ ] `week1.md` 已完成

---

## 21. 自测题

不看上文回答：

- Q1：什么是 `α|β|γ`？`1||ΣCj` 每个字段表示什么？
- Q2：SPT 为什么对 `1||ΣCj` 最优？（说得出相邻交换论证）
- Q3：EDD 对什么问题最优？`Lateness` 与 `Tardiness` 有什么区别？
- Q4：WSPT 的排序键是什么？方向如何？
- Q5：为什么 `release_time` 会改变 SPT 的结论？给出反例。
- Q6：什么叫 available set？什么叫 non-delay schedule？
- Q7：Parallel LPT 的两个核心步骤是什么？
- Q8：为什么机器负载不应写进输入对象？
- Q9：`eligible_machine_ids` 与 `machine_id` 有什么区别？
- Q10：什么是 lower bound？`solution == LB` 时能推出什么？
- Q11：为什么 heuristic 值和 optimum 不能混写？
- Q12：Input Validator 和 Schedule Validator 有什么区别？
- Q13：为什么 Objective 要独立于 Rule？
- Q14：为什么 expected 不能由被测函数生成？
- Q15：为什么要固定 tie-breaking？
- Q16：为什么单机 LPT 对 ΣCj 很差？它的正确用途是什么？

### 参考答案

- A1：机器环境 | 约束 | 目标。`1` = 单机，`β` 空 = 无额外约束，`ΣCj` = 最小化总完成时间。
- A2：相邻两任务 a,b，前面已有时间 t。顺序 ab 的两项完成时间和为 `2t+2pa+pb`，ba 为 `2t+2pb+pa`，差为 `pa−pb`。所以 `pa< pb` 时 ab 更优，即短任务在前；更后面的任务完成时间不变。
- A3：EDD 对 `1||Lmax` 最优。`Lj = Cj − dj` 可为负，`Tj = max(0, Cj − dj)` 恒非负；前者衡量最糟的一次延迟，后者衡量总迟交量。
- A4：`p/w` 升序（等价于 `w/p` 降序）。
- A5：加了 `rj` 后，最优可能需要故意空等即将到达的短任务。反例：A(r=0,p=100)、B(r=1,p=1)，non-delay 得 201，空转得 104。
- A6：available set 是当前已释放（`rj <= t`）的可选任务集合；non-delay 指只要机器空闲且存在可用任务就立即加工，绝不空等。它是启发式，不是最优。
- A7：① 按 `p` 降序排序；② 每道工序分给当前 `ready_time` 最小的机器。
- A8：`Machine` 是 frozen 输入模型，机器当前负载是**求解过程的临时状态**；混入会污染输入、破坏不可变性与可复现性。应作为算法内部局部变量（如 `machine_ready`）。
- A9：`eligible_machine_ids` 是输入的「允许范围」约束；`machine_id` 是输出的「实际选择」决策。
- A10：下界是任何可行解都迈不过去的值。`solution == LB` 时由 `LB <= OPT <= solution` 推出 `OPT = solution`，即证明最优。
- A11：heuristic 只是「找到了一个好解」，optimum 是「证明了这就是最好」。把前者写成后者，会导致后续算法比较失去意义（不知道自己是不是真的打败了它）。
- A12：Input Validator 检查**问题数据**是否合法（重复 ID、非法引用、`p>0` 等）；Schedule Validator 检查**求解结果**是否可行（机器重叠、precedence 违规、非法指派、工序缺失/重复）。
- A13：这样 SPT、局部搜索、MILP、RL 才能用同一把尺子公平比较；规则自己算指标会导致「各自定义好坏」。
- A14：否则测试只能证明「重复执行结果一致」，无法证明结果正确。expected 必须独立于被测代码。
- A15：保证「相同输入 → 相同输出」，与输入顺序和运行次数无关。这是可复现实验的基础，也是后续 Benchmark 公平比较的前提。
- A16：单机上先做长任务会拖长所有后续任务的完工时间，而 ΣCj 对每一个完成时刻求和。LPT 的正确用途是 `P||Cmax` 的并行机列表调度。

---

## 22. 今日一句话总结

> **Week 1 的核心成果不是「学会了几个排序规则」，而是建立了第一套可信的调度算法工作方式：先精确定义问题，再构造不可变输入，用经典 baseline 产生 Schedule，用独立 Objective 评价，用手算反例和自动化测试验证，并始终明确每条结论的适用条件与失效边界。**
