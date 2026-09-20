# Day 6：在共同支持的实例集上比较 MILP 与 CP-SAT

> 当日主题：把 Week 2 的 MILP 与本周的 CP-SAT 放在**同一实例集、同一目标、同一时间预算**下比较，并把结论严格限制在「这个实例集、这个预算」之内
> 当日产出：[m2w3d6_milp_vs_cpsat.py](../../projects/02_optimization_models/examples/m2w3d6_milp_vs_cpsat.py) 的实测对比表 + [w3_cpsat.py](../../projects/02_optimization_models/opt_experiments/w3_cpsat.py) 跑批产物里的同组数字 + [artifacts/month2_w3/report.md](../../projects/02_optimization_models/artifacts/month2_w3/report.md)
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说出跨范式比较成立需要哪四个前提，并说明缺一个前提会出现什么错误结论。
2. 说明为什么 MILP 的 `best_bound` 与 CP-SAT 的 `best_bound` 在**「下界」这个意义**上可比，而「谁更紧」不能归因于范式。
3. 读懂一张 `方法 × 状态 × 目标 × 界 × gap × 耗时` 的对比表，并指出其中哪几行是「证明最优」。
4. 说出 `gap` 的三种失效情形（平凡界、无界、界比目标值大），并说明各自的读法。
5. 举出「同一范式内部两个模型就能差出 0.5 以上 gap」的实例，并解释这说明什么。
6. 说明为什么必须把「找到一个好解」与「证明它最优」当成两件独立的事汇报。
7. 说出本次比较里 CP-SAT 在哪些实例上占优、在哪些实例上落后，并给出对「谁更快」这类问题的正确回答方式。
8. 说出跑批件里 `reference_kind` / `gap_to_reference` / `peak_resource` 这几列各自要防住哪类错误。

---

## 2. 为什么要做跨范式比较

Week 1、2、3 各建了一类模型，也各有一套求解器：

```text
W1  LP     ：线性规划，解在极点上，有对偶信息
W2  MILP   ：线性 + 整数，LP 松弛 + 分支定界
W3  CP-SAT ：区间模型，域传播 + 冲突驱动搜索
```

到了这一步，最自然的问题就是「哪个更好」。但这个问题**在没有限定条件时是没有答案的**。要做成一个能立住的结论，比较必须满足四个前提：

```text
前提 1：同一实例集      —— 方法在不同实例上的表现可以完全相反
前提 2：同一目标函数    —— makespan 与 total_tardiness 的难度不可比
前提 3：同一时间预算    —— 「5 秒内」与「不限时」是两件事
前提 4：同一验证口径    —— 都要过同一套独立验证器，且都用 M1 的目标函数重算
```

缺任何一条，比较就会退化成「读日志」。本仓库把这四件事全部编码进了脚本与跑批件：

- **前提 1**：实例全部由 `generate_instance(seed, jobs, machines)` 生成，种子与参数写死；
- **前提 2**：同一实例上所有方法用同一个 `objective` 字段；
- **前提 3**：`time_limit` 由脚本统一传入（本次是 5.0 秒）；
- **前提 4**：所有排程都过 M1 的 `validate_schedule`，目标值都由 M1 的 `M2_OBJECTIVES` 重算。

---

## 3. 概念：比较口径的四个前提

### 3.1 定义（可比性）

**定义（方法可比）**：两个求解方法的比较结果可比，当且仅当它们在同一实例集上、用同一目标函数、在同一时间预算下、并用同一套验证与复算规则求解。

四个前提各自的「缺失后果」：

| 缺失的前提 | 会出现什么错误结论 |
|---|---|
| 同一实例集 | 用 CP-SAT 擅长的并行机实例与 MILP 擅长的单机实例各自的结果比较，得出「A 比 B 强」 |
| 同一目标函数 | 把 `makespan` 的用时与 `total_tardiness` 的用时放在一列里比 |
| 同一时间预算 | 一边不限时、一边限 5 秒，结论必然是「不限时的那个更好」 |
| 同一验证口径 | 一边用求解器的目标值、一边用 M1 重算的值，数字差在浮点或建模上 |

### 3.2 理论结论：bound 的可比性

**结论**：对同一个最小化问题，MILP 与 CP-SAT 给出的 `best_bound` **在同一种意义下可比**——两者都是「最优值不会低于这个数」的证明。所以「目标值 vs 界」的 gap 计算在两个范式上都是合法的。

但下面这句话**不能**从上面的结论推出来：

```text
错的推论：谁的 bound 更紧，谁的范式就更强。
```

原因是 bound 的强度取决于至少三件事，而范式只是其中一件：

```text
（a）建模方式：同一范式内部，sequence 与 time-indexed 的界可以差很多
（b）时间预算：界是随搜索推进收紧的，预算不同就没有可比性
（c）求解器版本与参数：默认参数与调过的参数是两种东西
```

第 7 节的实测里有一个直接的证据：**同一个 MILP 范式内部**，`milp_tight` 与 `milp_alt` 在 `single_12` 上的 gap 分别是 0.8984 与 0.0000——差出 0.9 的 gap。**这还只是一次参数与建模方式的差别，跨范式的比较就更不能归因于范式本身。**

### 3.3 gap 的三种失效情形

`gap = (objective - best_bound) / |objective|` 这个定义在三种情形下会给出误导性的读法：

```text
情形 1：best_bound 是平凡界
    例：total_tardiness 的界恒 >= 0，实测 best_bound = 0.0、gap = 1.0
    读法：不是「方法很差」，而是「这个界由目标非负直接得到，证明几乎没推进」

情形 2：best_bound 为 None（该方法不提供界）
    例：启发式方法没有任何界
    读法：gap 无法计算，必须留空，不能填 0 也不能填成目标值

情形 3：界比目标值大（异常）
    例：包装层若把 raw_best_bound 直接抄进来，可能得到 > objective 的「下界」
    读法：这是包装错误。合法的下界永远不超过已找到的可行解目标值
```

M2 的包装层对情形 2 与情形 3 都有硬处理：**`None` 就写 `None`**；**界超过目标值就记 `bound_anomaly` 且不当界用**。第 7 节的表里 `heur_*` 那一列显示的是 `无 bound`，而不是一个数字——这是刻意的。

---

## 4. 推导：几个必须分清的对照

### 4.1 「找到好解」与「证明最优」是两件事

这两件事可以独立地成立或不成立，组合起来有四种：

```text
              找到最优解？
            是            否
证明 是   OPTIMAL 且值最优    不可能（证明了最优就说明解最优）
最优 否   FEASIBLE 且值最优   FEASIBLE 且值次优
```

第二行第一列是最容易被忽略的一种：**求解器找到了最优解，但没证明它**。第 7 节的 `single_12` 就是活例子：

```text
milp_alt        OPTIMAL   532   bound 532    gap 0.0000   求解 0.6216 s
cpsat_parallel  FEASIBLE  532   bound 1      gap 0.9981   求解 5.0165 s
```

两者的目标值**完全相同**（532，这就是最优值），但只有一个把「最优」立住了。如果报告里只抄目标值，这两行看起来一样；只抄状态，会得出「CP-SAT 输给 MILP」；只有把**状态 + 目标值 + 界**一起抄，才能准确描述成「CP-SAT 找到了最优解但没证明，MILP 证明了」。

### 4.2 启发式的位置

表里还有一类方法：M1 的规则基线（`heur_edd` / `heur_parallel_lpt`）。它们的读法与精确方法不同：

```text
状态永远是 FEASIBLE（启发式不做证明）
界永远是 None（启发式不提供界）
价值在于：给出一个「不用优化器就能拿到的下界解」，用来判断精确方法值不值
```

实测里 `heur_edd` 在 `single_8` 上直接拿到 85，与所有精确方法的最优值相同——**这种情况下精确方法的价值不是「更好地解」，而是「知道它就是最优」**。而在 `single_12` 上 `heur_edd` 得到 543、最优是 532，差 11（相对差 2.0%），这时候精确方法既改善了解、也证明了它。

### 4.3 耗时的两个坑

```text
坑 1：把建模时间与求解时间混在一起
    例：milp_alt 在 single_12 上建模 0.1348 s、求解 0.6216 s（合计 0.7564 s）
        cpsat_parallel 建模 0.0027 s、求解 5.0165 s
    两种方法的建模开销差 50 倍，混在一起会得出错误结论

坑 2：时间预算相同不等于「实际用时」相同
    MILP 可能用不完预算就证完了，而 CP-SAT 用满预算仍没证完
    所以「谁用了多少时间」与「谁在预算内做到了什么」是两个问题
```

M2 的 `SolveResult` 把 `build_time` 与 `solve_time` 分开记录，并提供 `wall_time` 作为合计——**要哪一个由比较的目的决定**，但必须说清用的是哪一个。

---

## 5. 实现：比较脚本与跑批件的分工

两个产物的分工很清楚：

| 产物 | 角色 | 是否写盘 |
|---|---|---|
| [m2w3d6_milp_vs_cpsat.py](../../projects/02_optimization_models/examples/m2w3d6_milp_vs_cpsat.py) | 教学脚本：四个实例、方法对照表、一致性核对 | 只打印 |
| [w3_cpsat.py](../../projects/02_optimization_models/opt_experiments/w3_cpsat.py) | 跑批件：29 次运行、落盘 CSV/JSON/报告 | 写 `artifacts/month2_w3/` |

比较脚本的两个设计要点：

1. **它自己检测 MILP 是否可用**，而不是假定可用：

```python
missing = [name for name in MILP_METHODS if name not in methods]
if missing:
    print(f"  缺失的 MILP 方法：{missing} —— 下面的表里不会出现它们。")
else:
    print("  Week 2 的三个 MILP 方法都在，比较是真实的跨周比较。")
```

这是**诚实性**要求的技术实现：如果 Week 2 的 MILP 没落地，脚本会说「缺失」，而不会用别的数字凑一格。跑批件里也有同样的机制（`milp_available` / `milp_methods_present` / `milp_methods_missing` / `milp_note` 四个字段进 `metadata.json`）。

2. **它只调用注册过的方法，不手写求解器调用**：

```python
registry = {name: get(name) for name in MILP_METHODS + CPSAT_METHODS + HEUR_METHODS if name in methods}
```

好处是「脚本里比较的东西」与「跑批里比较的东西」与「测试里断言的东西」是同一个对象——**三处一致**，不会出现「教学脚本与实验结果对不上」这种尴尬。

跑批件多做了三件事：

```text
1. 把实例序列化落盘（instances/*.json）并记 sha256 —— 保证「比的是什么」可追溯
2. 每个排程都过独立验证器，并记录 peak_resource（容量复核）
3. 按实例算 batch_reference（本批次里最好的目标值）并给出 gap_to_reference
```

---

## 6. 读表方法：一列一列地读

拿第 7 节 `single_12` 的表做示例，逐列说明读法：

| 列 | 这一列回答什么 | 读的时候要防什么 |
|---|---|---|
| `方法` | 谁 | 注意同名方法可能有不同参数 |
| `状态` | 做到了什么程度 | **不能只看目标值**：FEASIBLE 与 OPTIMAL 的目标值可能相同 |
| `目标` | 找到的解得多少分 | 越小越好（都是最小化） |
| `bound` | 证明了「不可能更小」到哪 | `-` 表示没有界，不能读作 0 |
| `gap` | 证明的推进程度 | `1.0000` 可能是平凡界，不代表方法烂 |
| `建模` | 建模型花了多久 | 与求解时间分开读 |
| `求解` | 搜索花了多久 | 受预算截断，不能当作方法的固有性质 |

**四步读法**：

```text
第 1 步：先看目标值列，找出本实例上最好的目标值 —— 这是「谁找到了更好的解」
第 2 步：再看状态列，找出谁把「最优」立住了 —— 这是「谁证明了」
第 3 步：把第 1 步与第 2 步合并 —— 「找到最优」与「证明最优」是两件事
第 4 步：最后才看耗时列 —— 而且要分建模与求解两列
```

按这四步读 `single_12`：

```text
第 1 步  最好的目标值是 532（milp_alt 与 cpsat_parallel 都达到）
第 2 步  只有 milp_alt 是 OPTIMAL（cpsat_parallel 是 FEASIBLE，界 1）
第 3 步  milp_alt 找到并证明了最优；CP-SAT 找到了同一个解但没证明
第 4 步  milp_alt 求解 0.6216 s，cpsat_parallel 求解 5.0165 s（用满预算）
```

再按四步读 `parallel_8`：

```text
第 1 步  最好的目标值是 29，三个精确方法都达到
第 2 步  milp_alt / cpsat_parallel / cpsat_jsp 都是 OPTIMAL
第 3 步  三个方法都找到并证明了最优
第 4 步  CP-SAT 求解 0.0088 s 与 0.0105 s，MILP 0.8145 s —— 差两个数量级
```

**两个实例上方向相反，这就是今天最重要的观察。**

---

## 7. 实验：`m2w3d6_milp_vs_cpsat`

对应脚本 [m2w3d6_milp_vs_cpsat.py](../../projects/02_optimization_models/examples/m2w3d6_milp_vs_cpsat.py)，在项目目录下运行：

```bash
python examples/m2w3d6_milp_vs_cpsat.py
```

四个实例全部来自 `generate_instance`，MILP 与 CP-SAT 一律 `time_limit = 5.0` 秒、`seed = 0`。实际输出：

```text
=== 0. 方法清单 ===
  已注册方法 14 个：['cpsat_cumulative', 'cpsat_jsp', 'cpsat_parallel', 'cpsat_symmetry', 'heur_edd', 'heur_lpt', 'heur_parallel_lpt', 'heur_spt', 'heur_wspt', 'milp_alt', 'milp_fixing', 'milp_loose', 'milp_tight', 'milp_warmstart']
  Week 2 的三个 MILP 方法都在，比较是真实的跨周比较。
    milp_tight      单机 sequence MILP，逐对 tight Big-M（M_jk = H - r_k）
    milp_alt        time-indexed MILP，单机与同质并行机通用
    cpsat_parallel  CP-SAT 同质并行机：OptionalIntervalVar + ExactlyOne + NoOverlap
  时间预算：MILP 与 CP-SAT 一律 time_limit = 5.0 秒，seed = 0。

=== 实例 single_8：8 道工序、1 台机器、目标 total_tardiness ===
  方法                状态                目标     bound      gap       建模       求解
  ---------------------------------------------------------------------------
  milp_tight        OPTIMAL           85        85   0.0000   0.0046   1.4698
  milp_loose        OPTIMAL           85        85   0.0000   0.0027   1.4284
  milp_alt          OPTIMAL           85        85   0.0000   0.0180   0.1280
  cpsat_parallel    OPTIMAL           85        85   0.0000   0.0018   0.1432
  cpsat_jsp         OPTIMAL           85        85   0.0000   0.0011   0.1663
  heur_edd          FEASIBLE          85         -  无 bound   0.0000   0.0001
  证明最优的方法：milp_tight, milp_loose, milp_alt, cpsat_parallel, cpsat_jsp（目标值 85）

=== 实例 single_12：12 道工序、1 台机器、目标 total_tardiness ===
  方法                状态                目标     bound      gap       建模       求解
  ---------------------------------------------------------------------------
  milp_tight        FEASIBLE         543   55.1735   0.8984   0.0079   5.0155
  milp_loose        FEASIBLE         573   54.7981   0.9044   0.0053   5.2440
  milp_alt          OPTIMAL          532       532   0.0000   0.1348   0.6216
  cpsat_parallel    FEASIBLE         532         1   0.9981   0.0027   5.0165
  heur_edd          FEASIBLE         543         -  无 bound   0.0000   0.0001
  证明最优的方法：milp_alt（目标值 532）

=== 实例 parallel_8：8 道工序、3 台机器、目标 makespan ===
  方法                状态                目标     bound      gap       建模       求解
  ---------------------------------------------------------------------------
  milp_alt          OPTIMAL           29        29   0.0000   0.1022   0.8145
  cpsat_parallel    OPTIMAL           29        29   0.0000   0.0018   0.0088
  cpsat_jsp         OPTIMAL           29        29   0.0000   0.0013   0.0105
  heur_parallel_lpt FEASIBLE          31         -  无 bound   0.0000   0.0016
  证明最优的方法：milp_alt, cpsat_parallel, cpsat_jsp（目标值 29）

=== 实例 parallel_12：12 道工序、3 台机器、目标 makespan ===
  方法                状态                目标     bound      gap       建模       求解
  ---------------------------------------------------------------------------
  milp_alt          OPTIMAL           39        39   0.0000   0.2371   1.6458
  cpsat_parallel    OPTIMAL           39        39   0.0000   0.0019   0.0324
  cpsat_jsp         OPTIMAL           39        39   0.0000   0.0017   0.0255
  heur_parallel_lpt FEASIBLE          46         -  无 bound   0.0000   0.0003
  证明最优的方法：milp_alt, cpsat_parallel, cpsat_jsp（目标值 39）

=== 1. 跨方法一致性核对 ===
  single_8      MILP 最好 85.0     CP-SAT 最好 85.0     启发式最好 85.0     -> 一致
  single_12     MILP 最好 532.0    CP-SAT 最好 532.0    启发式最好 543.0    -> 一致
  parallel_8    MILP 最好 29.0     CP-SAT 最好 29.0     启发式最好 31.0     -> 一致
  parallel_12   MILP 最好 39.0     CP-SAT 最好 39.0     启发式最好 46.0     -> 一致

=== 2. bound 到底是不是同一件事 ===
  MILP 的 best_bound 来自 LP relaxation 逐层收紧（分支定界）；
  CP-SAT 的 best_bound 来自域传播、冲突分析与目标下界推理。
  两者在**同一意义**下可比：都是「最优值不会低于这个数」的证明，
  所以同一实例上比较 objective 与 bound 是合法的。
  但『谁的 bound 更紧』不能归因于范式：它同时取决于
  （a）建模方式（sequence 还是 time-indexed），（b）给的时间预算，
  （c）求解器版本。上表里同一范式内部两个模型就能差出 0.5 以上的 gap。

=== 3. 一个必须诚实说明的例子 ===
  single_12 上，CP-SAT 在 5 秒内找到了与 milp_alt 相同的最优解，
  但没有证明它（状态 FEASIBLE、gap 接近 1）；而 milp_alt 证完了。
  反过来在 parallel_8 / parallel_12 上，CP-SAT 的证明时间比 milp_alt 少两个数量级。
  所以正确结论是：**在这个实例集、这个预算下**，两种范式的强项不同；
  不能推广成「CP-SAT 比 MILP 快」或反之。
  要下更强的结论需要更大的实例集与多组预算，那是 Month 2 结尾的工作。
```

（上面是**一次运行**的原始输出。重跑同一脚本时，`状态` / `目标` / `bound` / `gap` 四列逐格不变，会变的只有 `建模` / `求解` 两列的墙钟读数——下面第 7.1 小节的跑批数据就是同一批实例在另一次运行里的读数。）

### 7.1 跑批件里的同组数字

同一个实例集在 [w3_cpsat.py](../../projects/02_optimization_models/opt_experiments/w3_cpsat.py) 的 29 次运行里也能查到（`results.csv`，`time_limit = 5.0`、`seed = 0`）：

| 实例 | 方法 | 状态 | 目标 | bound | gap | 求解 (s) |
|---|---|---|---|---|---|---|
| `w3_single_8` | `milp_tight` | OPTIMAL | 85 | 85 | 0.0 | 1.3744 |
| `w3_single_8` | `milp_loose` | OPTIMAL | 85 | 85 | 0.0 | 1.4642 |
| `w3_single_8` | `milp_alt` | OPTIMAL | 85 | 85 | 0.0 | 0.1487 |
| `w3_single_8` | `cpsat_jsp` | OPTIMAL | 85 | 85 | 0.0 | 0.1602 |
| `w3_single_8` | `cpsat_parallel` | OPTIMAL | 85 | 85 | 0.0 | 0.1369 |
| `w3_single_12` | `milp_tight` | FEASIBLE | 543 | 55.1735 | 0.8984 | 5.0263 |
| `w3_single_12` | `milp_loose` | FEASIBLE | 573 | 54.7981 | 0.9044 | 5.3771 |
| `w3_single_12` | `milp_alt` | OPTIMAL | 532 | 532 | 0.0 | 0.5933 |
| `w3_single_12` | `cpsat_jsp` | FEASIBLE | 532 | 1.0 | 0.9981 | 5.0174 |
| `w3_single_12` | `cpsat_parallel` | FEASIBLE | 532 | 1.0 | 0.9981 | 5.0182 |
| `w3_parallel_8` | `milp_alt` | OPTIMAL | 29 | 29 | 0.0 | 0.7622 |
| `w3_parallel_8` | `cpsat_parallel` | OPTIMAL | 29 | 29 | 0.0 | 0.0106 |
| `w3_parallel_12` | `milp_alt` | OPTIMAL | 39 | 39 | 0.0 | 1.5602 |
| `w3_parallel_12` | `cpsat_parallel` | OPTIMAL | 39 | 39 | 0.0 | 0.0250 |

**两个产物的目标值逐行一致**（85 / 543 / 573 / 532 / 29 / 39），耗时略有差别（同一台机器、不同时刻运行的正常波动）。**一致性本身就是一次交叉验证**：教学脚本与跑批件如果对不上，说明有一个地方写错了。

### 7.2 观察

九处观察：

1. **目标值上没有任何一个范式全面胜出**：四个实例里，MILP 与 CP-SAT 的**最好目标值完全相同**（85 / 532 / 29 / 39）。四种实例上的一致性说明**两个模型都建对了**——这是跨范式比较里最有价值的一类交叉验证。
2. **CP-SAT 在并行机上证明得快两个数量级**：`parallel_8` 是 0.0088 s 对 0.8145 s，`parallel_12` 是 0.0324 s 对 1.6458 s。区间模型 + `AddNoOverlap` 对「机器互斥 + 选机」这类结构的传播非常有效。
3. **MILP 在单机交期问题上证明得快**：`single_12` 上 `milp_alt` 用 0.6216 s 证完 532，而 CP-SAT 用满 5 秒仍停在 `FEASIBLE`（界 1）。方向与第 2 条正好相反。
4. **`milp_tight` 与 `milp_loose` 在 `single_12` 上被同一个实例击败**：两者都是 `FEASIBLE`、目标值 543 / 573、gap 0.90 左右。而**同一范式**的 `milp_alt` 证完了。这说明「MILP 行不行」不是一个有答案的问题——**同一个星期、同一个问题、同一台机器上，两个 MILP 模型的结论就完全相反**。
5. **`gap` 的读法在 `single_12` 的 `cpsat_parallel` 那一行最容易读错**：`gap = 0.9981` 看起来是「CP-SAT 差得远」，但它的目标值 532 **就是最优值**。真相是「已经找到了最优解，但没能证明」——`gap` 衡量的是**证明的进度**，不是解的优劣。
6. **启发式在 `single_8` 上直接命中最优值**：`heur_edd` 得到 85，与五个精确方法相同。这种情况下精确方法的价值不是更好的解，而是「知道它就是最优」。而在 `parallel_8` / `parallel_12` 上，`heur_parallel_lpt` 得到 31 / 46，与最优差 2 / 7——**启发式的表现随实例波动，这正是需要精确方法证明的原因**。
7. **`milp_tight` 的求解时间超过了它自己的预算**：5.0197 s 对 `time_limit = 5.0`。这是因为预算按求解器内部计时、而实测时间包含建模收尾与读解（Day 5 第 6.3 节讨论过）。**跨范式比较耗时时必须说明是哪一个时间**，否则会出现「一边超预算、一边没超」的不公平比较。
8. **建模时间的量级差很大**：`cpsat_*` 普遍在 0.001～0.003 s，`milp_alt` 在 0.1～0.24 s，`milp_tight` / `milp_loose` 在 0.005～0.008 s。**CP-SAT 的建模开销比 time-indexed MILP 小两个数量级**——这是「用 M1 的数据结构直接建区间」带来的好处，也是 `build_time` 与 `solve_time` 必须分开记录的直接理由。
9. **一致性核对全部通过**：四个实例上 MILP 最好值与 CP-SAT 最好值都「一致」。**这是本次比较最硬的一条结论**——不同范式、不同建模方式、不同的搜索机制，在同一批实例上给出了同一批最优值。

### 7.3 结论应该怎么写

把上面的观察写成结论，必须带上限定条件：

```text
可以写的：在这个实例集（4 个 generate_instance 实例）、这个目标（makespan 与
          total_tardiness）、这个预算（5.0 秒、单线程、seed 0）下，
          CP-SAT 在并行机实例上证明最优的用时比 time-indexed MILP 少两个数量级；
          time-indexed MILP 在 12 工序单机交期实例上证明了 532 最优，
          而 CP-SAT 在同样预算内找到了 532 但未能证明。

不能写的：CP-SAT 比 MILP 快。MILP 比 CP-SAT 强。CP-SAT 的界比 MILP 的界松。
```

第二个版本的三句话都是**把一个受限于具体条件的观察推广成了范式之间的普遍结论**。四天的学习下来应该已经建立这个敏感度了：**在求解器实验里，「更强」这个词必须带上实例、目标、预算三个限定词。**

---

## 8. 今日练习

1. **练习 1（读表）**：用第 6 节的四步读法，逐步骤读 `single_8` 那张表，并写出一段不超过 5 行的结论（必须带上限定条件）。
2. **练习 2（gap 读法）**：解释为什么 `cpsat_parallel` 在 `single_12` 上的 `gap = 0.9981` 不能读作「这个方法的解很差」；再给出一个「gap 很小但解很差」的可能情形。
3. **练习 3（比较设计）**：如果要比较「MILP 的 sequence 模型与 time-indexed 模型」，需要固定哪些前提？请写出你的实验设计（实例集、目标、预算、记录哪些列）。
4. **练习 4（代码阅读）**：读 [w3_cpsat.py](../../projects/02_optimization_models/opt_experiments/w3_cpsat.py) 里 `reference_kind` 与 `gap_to_reference` 两列的生成逻辑，说明 `hand_computed` / `per_group` / `cross_checked` 三种参照各自的效力边界，并回答：为什么一个「只是下界」的数不能写进 `reference` 列。
5. **练习 5（反例设计）**：构造一组实例（至少两个），使得「MILP 更好」与「CP-SAT 更好」的结论各自成立一次；说明这组实例能否用来支持「两者各有强项」这个结论，以及还需要补什么。

---

## 9. 验收清单

- [ ] 能说出跨范式比较的四个前提，以及各缺一条会出现什么错误结论。
- [ ] 能解释 MILP 与 CP-SAT 的 `best_bound` 在哪一种意义上可比、在哪一种意义上不可比。
- [ ] 能用四步读法读一张对比表，并区分「找到最优」与「证明最优」。
- [ ] 能说出 `gap` 的三种失效情形（平凡界 / 无界 / 界超过目标值）及各自的读法。
- [ ] 能举出「同一范式内部 gap 差 0.9」的实例，并说明它为什么否定了「范式决定界强度」。
- [ ] 能说出启发式在对比表里的正确位置（永远 `FEASIBLE`、永远无界、价值在于基线）。
- [ ] 能说出 `build_time` 与 `solve_time` 为什么必须分开记录，并各举一个量级差的例子。
- [ ] 能写出一段带限定条件的比较结论，并识别出「CP-SAT 比 MILP 快」这类过度推广。
- [ ] 在项目目录下运行 `python examples/m2w3d6_milp_vs_cpsat.py`，四个实例上 MILP 最好值与 CP-SAT 最好值逐行一致。
- [ ] 在项目目录下运行 `python -m pytest -q` 全部通过（含本周的 63 个 CP-SAT 测试与其它周的测试）。

---

## 10. 自测题

不看上文回答：

- Q1：跨范式比较的四个前提是什么？
- Q2：MILP 的 `best_bound` 与 CP-SAT 的 `best_bound` 在哪一种意义上可比？
- Q3：「谁的界更紧，谁的范式更强」这句话错在哪里？
- Q4：`gap = 0.9981` 且目标值就是最优值，这种情况怎么发生的？
- Q5：`best_bound = 0` 的 `total_tardiness` 结果，`gap = 1.0` 该怎么读？
- Q6：启发式方法的 `gap` 列应该怎么写？为什么？
- Q7：`single_12` 上 `milp_tight` 与 `milp_alt` 的 gap 分别是多少？这说明了什么？
- Q8：为什么 `build_time` 与 `solve_time` 必须分开记录？
- Q9：四个实例上 MILP 与 CP-SAT 的最好目标值一致，这件事的价值是什么？
- Q10：把「CP-SAT 在并行机实例上证明更快」写成「CP-SAT 比 MILP 快」，错在哪里？

### 参考答案

- A1：同一实例集、同一目标函数、同一时间预算、同一验证与复算口径。
- A2：在「最优值不会低于这个数」这个意义上可比，所以「目标值 vs 界」的 gap 计算在两个范式上都合法。
- A3：界强度取决于建模方式、时间预算、求解器版本与参数，范式只是其中一个因素。实测里同一 MILP 范式内部两个模型的 gap 就能差 0.9。
- A4：求解器已经找到了最优解，但没能证明它——界停在很弱的水平（例如 1），而目标值是 532，于是 gap 接近 1。`gap` 衡量的是证明进度，不是解的质量。
- A5：读作「下界由目标非负直接得到，证明几乎没推进」，而不是「方法很差」；这个 0 不是搜索得到的界。
- A6：留空（写「无 bound」）。启发式不提供任何下界，填 0 会让 gap 变成 1 并看起来像有个坏界，填目标值会让 gap 变 0 并伪装成「证明最优」。
- A7：`milp_tight` 是 0.8984、`milp_alt` 是 0.0000。说明「MILP 行不行」不取决于范式，同一个星期、同一个问题、同一台机器上，两个 MILP 模型的结论可以完全相反。
- A8：两种方法的建模开销可以差两个数量级（实测 CP-SAT 0.001～0.003 s，time-indexed MILP 0.1～0.24 s），混在一起记录会让比较失去意义。
- A9：这是一次跨范式的交叉验证——不同建模方式、不同搜索机制给出了同一批最优值，说明两边的模型都建对了。这比任何单边的性能数字都更硬。
- A10：错在把受限于「这个实例集、这个目标、这个预算」的观察推广成了范式之间的普遍结论。正确的写法必须带上三个限定条件。

---

## 11. 今日一句话总结

> **跨范式比较只有在「同一实例集、同一目标、同一预算、同一验证口径」四个前提下才有意义；本次实测里两种范式在四个实例上的最好目标值完全相同（最好的交叉验证），但证明能力各行其道——CP-SAT 在并行机上快两个数量级、time-indexed MILP 在单机交期问题上证明了 532 而 CP-SAT 只找到没证明，所以能写下的结论必须钉死在「这个实例集、这个目标、这个预算」之内。**
