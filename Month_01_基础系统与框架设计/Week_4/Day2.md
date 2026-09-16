# Day 2：基准实例集与种子

> 当日主题：把「实验覆盖范围」写成一份可审计的实例清单——六道小规模合成题、两种 seed、以及每份输入的 SHA-256。
> 当日产出：**实例参数表与输入哈希核对脚本**（`examples/m1w4d2_instances.py`）
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说清 `generate_instance` 的六个生成参数，以及 `p∈[1,20]`、`r∈[0,10]`、`due_factor=1.5`、`w∈[1,5]`、全机器资格各自意味着什么。
2. 手算验证 `due_date = release_time + int(Σp × due_factor)`，并说清 `int()` 的截断方向。
3. 记住六个实例的名称、输入 seed、规模、目标与参考类型，并说清 routes_12 的 12 是**总工序数**。
4. 区分**输入 seed** 与**算法 seed 0/1/2**：前者决定「哪道题」，后者决定「同一道题怎么搜」。
5. 会数清 162 = 108 + 54 的来源，并说出三组敏感性设置分别改了什么。
6. 解释为什么确定性方法在三个 seed 下重复**不提供三个独立随机样本**。
7. 说清 `input_sha256` 的作用，以及为什么「保存 seed」不能代替「保存输入」。
8. 列出这批实例的范围限制，并知道由此**不能**推出什么结论。

---

## 2. 为什么第 2 天要先把实例集定下来

Day 1 把实验中所有可调的部分收进了配置与命令行：数据规模、目标、seed、预算、敏感性参数都不写死在算法里（见 Day 1 第 1 节）。今天要补齐其中最容易被忽略的一半：**这些题是怎么来的、覆盖了什么、凭什么相信两个月后还是同一道题。**

调度算法的比较有三个前提，缺一不可：

1. **同一批输入**：所有方法跑的是同一份实例数据，而不是「同一个 seed 各自生成一遍」。
2. **同一套评价口径**：目标函数、评价预算、时间推进方式一致（Day 1 讲入口，Day 3 讲记录格式）。
3. **可核查的输入身份**：将来有人质疑结果时，能证明他手里的输入就是当时用的输入。

所以今天的工作顺序是「先定题、再保存、后求解」：

```text
configs/month1.json
        │  输入 seed + 规模参数
        ▼
generate_instance(**generator)          ← 生成器：决定 p / r / d / w
        │
        ▼
instances/<name>.json  ──字节──▶  SHA-256  ──▶  结果行的 input_sha256
        │
        └── 同一实例的 18 条主实验共用这一份落盘输入 ──▶ results.csv / summary.csv / report.md
```

三个问题按顺序回答：**题从哪来**（第 3 节的生成器）、**覆盖什么**（第 4 节的六个实例）、**怎么防止悄悄换题**（第 6、7 节的哈希核对）。

> **一句话**：实例集不是实验的「背景」，而是实验设计本身；先挑对算法有利的题再写算法，等于把结论写进前提。

---

## 3. 实例生成器：参数与设计取舍

对应文件 [generator.py](../../projects/01_scheduling_core/scheduling_io/generator.py)。

```python
def generate_instance(
    seed: int,
    jobs: int = 12,
    machines: int = 3,
    operations_per_job: int = 1,
    release_max: int = 10,
    due_factor: float = 1.5,
) -> Instance:
    ...
    rng = Random(seed)
    for j in range(jobs):
        jid = f"J{j:03}"
        route = tuple(f"{jid}_O{k}" for k in range(operations_per_job))
        processing = [rng.randint(1, 20) for _ in route]
        release = rng.randint(0, release_max)
        orders.append(
            Job(
                jid, route, release,
                release + int(sum(processing) * due_factor),
                float(rng.randint(1, 5)),
            )
        )
```

四个设计点：

1. **局部随机源 `Random(seed)`**。生成器不碰全局 `random` 状态，所以「生成哪些实例」与「算法怎么随机搜索」互不干扰，重复生成结果完全一致。
2. **加工时间 `p ∈ [1,20]` 的整数**。整数工时让手算、下界和「Cmax == LB 即可证明最优」这类推理都能精确做，不用担心浮点比较。
3. **释放时间 `r ∈ [0, release_max=10]`**。释放时间把「静态排序」变成「动态选择」（Week 1 Day 4 第 5 节），是这批实例里唯一让规则基线不再最优的结构性因素。
4. **交期与作业自身加工量挂钩**：`d = r + int(Σp × due_factor)`。`due_factor=1.5` 表示「给 1.5 倍自身工时的交期额度」，**不是**固定松弛量。改成固定松弛（例如 `d = r + 30`）会让长作业必然迟交、短作业必然不迟交，单机总迟交目标（`ΣTj`）就退化成一两个作业在贡献数值，失去区分度。

```text
若 due_factor 很小（例如 0.5）：所有作业都严重迟交，ΣTj ≈ ΣCj − Σd，规则之间几乎无差别。
若 due_factor 很大（例如 10）：所有作业都不迟交，ΣTj 恒为 0，目标失去区分度。
取 1.5：让一部分作业迟交、一部分不迟交，规则顺序才有可比较的差异。
```

本批次配置里**没有**写 `release_max` 与 `due_factor`，用的是默认值 10 与 1.5：

| 参数 | 本批次取值 | 是否写在配置里 | 含义 |
|---|---|---|---|
| `seed` | 10 / 11 / 20 / 21 / 22 / 23 | 是 | **输入 seed**，决定实例内容 |
| `jobs` | 4 / 4 / 12 / 12 / 24 / 6 | 是 | 作业数 |
| `machines` | 1 / 2 / 1 / 3 / 3 / 3 | 是 | 机器数 |
| `operations_per_job` | 1 / 1 / 1 / 1 / 1 / 2 | 是 | 每作业工序数 |
| `release_max` | 10（默认） | 否 | `r` 的采样上界 |
| `due_factor` | 1.5（默认） | 否 | 交期宽松度 |

**这最后两行正是「必须保存输入、不能只保存 seed」的直接理由**：改一个默认值，六个实例会全部改变，而配置文本一个字都不用动。

另一个必须记牢的采样事实：`Operation` 的 `eligible_machine_ids` 直接取**全部机器**（`machine_ids`），所以这批实例全部是「同质、全资格」的 `P` 类环境（Week 1 Day 5 第 3 节）。选机这一步在本批次里没有资格限制，**换型、资格受限、`Q`/`R` 类机器都没有被覆盖**。

---

## 4. 六个实例的参数表

| 名称 | 输入 seed | 作业数 | 机器数 | 每作业工序数 | 总工序数 | 目标 | 参考类型 | 参考值 |
|---|---:|---:|---:|---:|---:|---|---|---:|
| tiny_single | 10 | 4 | 1 | 1 | 4 | 总迟交 | `optimum` | 36 |
| tiny_parallel | 11 | 4 | 2 | 1 | 4 | Cmax | `optimum` | 38 |
| single_12 | 20 | 12 | 1 | 1 | 12 | 总迟交 | `best-known` | 250 |
| parallel_12 | 21 | 12 | 3 | 1 | 12 | Cmax | `best-known` | 43 |
| parallel_24 | 22 | 24 | 3 | 1 | 24 | Cmax | `best-known` | 90 |
| routes_12 | 23 | 6 | 3 | 2 | 12 | Cmax | `best-known` | 40 |

**routes_12 的 12 指总工序数（6 作业 × 2 工序），不是 12 个作业。** 它检验作业内工序链（precedence）能否贯穿「候选解 → 解码 → 独立验证 → 目标计算」整条流水线，**不代表**已经完成工业 JSP / FJSP 建模：作业数只有 6，工序只有 2 道，没有任何柔性路径。

选择这六个实例的理由：

| 实例 | 想检验什么 |
|---|---|
| tiny_single | 4 作业可完整枚举，为单机总迟交提供一个**真正的 `optimum`**（36） |
| tiny_parallel | 4 作业 2 机器可完整枚举，为并行 Cmax 提供 `optimum`（38） |
| single_12 | 单机 12 作业，排序决策第一次到 12 个 |
| parallel_12 | 3 机器 12 作业，检验负载分配带来的差异 |
| parallel_24 | 本月最大规模，检验 150 次预算在小实例之外还够不够 |
| routes_12 | 唯一的**多工序**实例，检验 precedence 与选机同时存在时的表现 |

目标的选择也有讲究：单机实例用总迟交（`ΣTj`），并行与多工序实例用 Cmax。原因是单机 `r=0` 时 `Σpj` 固定、任何顺序的 Cmax 都相同（Week 1 Day 4 第 4 节），用 Cmax 做单机目标几乎没有排序区分度，演示搜索会变成「看谁运气好」。

**结论**：这六个实例不是「随便挑的六道题」，而是「两个可枚举 + 三个纯排序/分配 + 一个带 precedence」的最小覆盖。

---

## 5. 示例：两份真实实例记录

### 5.1 tiny_single（单机、4 作业）

数据来自已保存的 `instances/tiny_single.json`（只读）：

| Job | `pj` | `rj` | `dj` | `wj` |
|---|---:|---:|---:|---:|
| J000 | 19 | 0 | 28 | 4 |
| J001 | 16 | 9 | 33 | 1 |
| J002 | 7 | 7 | 17 | 4 |
| J003 | 9 | 10 | 23 | 2 |

用生成器公式逐一手算交期：

```text
J000：d = 0  + int(19 × 1.5) = 0  + int(28.5) = 0  + 28 = 28  ✓
J001：d = 9  + int(16 × 1.5) = 9  + 24       = 33           ✓
J002：d = 7  + int(7  × 1.5) = 7  + int(10.5) = 7  + 10 = 17  ✓
J003：d = 10 + int(9  × 1.5) = 10 + int(13.5) = 10 + 13 = 23  ✓
```

`int()` 向零截断，因此 `28.5 → 28`、`10.5 → 10`、`13.5 → 13`：交期永远是不大于 `r + 1.5Σp` 的整数。手算与文件完全一致，说明**每一条实例数据都能由它的参数和 seed 反推**。

### 5.2 routes_12（多工序）

| Job | `rj` | `dj` | `wj` | 工序工时 |
|---|---:|---:|---:|---|
| J000 | 0 | 19 | 5 | `(10, 3)` |
| J001 | 6 | 42 | 5 | `(10, 14)` |
| J002 | 3 | 28 | 3 | `(12, 5)` |
| J003 | 3 | 27 | 5 | `(15, 1)` |
| J004 | 1 | 25 | 1 | `(15, 1)` |
| J005 | 0 | 45 | 5 | `(16, 14)` |

```text
J000：Σp = 10 + 3  = 13 → d = 0 + int(13 × 1.5) = 0 + int(19.5) = 19  ✓
J001：Σp = 10 + 14 = 24 → d = 6 + int(24 × 1.5) = 6 + 36        = 42  ✓
J005：Σp = 16 + 14 = 30 → d = 0 + int(30 × 1.5) = 45                ✓
```

注意交期用的是**整个作业的 Σp**，不是单道工序的工时。多工序时这一点很容易写错：交期约束的是作业全部完工的时刻（`Cj` 是最后一道工序的 `end_time`），而不是某一道工序。

### 5.3 同一份事实的三个出处

| 事实 | 配置里的写法 | `instances/tiny_single.json` | `results.csv` 的一行 |
|---|---|---|---|
| 题的身份 | `"seed": 10` | 文件本身 | `input_sha256 = e55495a6…` |
| 作业数 | `"jobs": 4` | `jobs` 数组 4 项 | —（可从输入反查） |
| 总工序数 | 4 × 1 = 4 | `operations` 数组 4 项 | — |
| 目标 | `"objective"` | — 不在实例文件里 | `objective_name = total_tardiness` |
| 参考 | `"exact": true` | — | `reference_type = optimum`，`reference = 36.0` |

三处必须能互相印证：**配置给出「怎么造题」，实例文件给出「题是什么」，结果行给出「用哪一份题、什么目标、什么参考」**。缺任何一处，审计链就断了。

---

## 6. 实现：配置、输入保存与结果行的绑定

对应文件 [month1.json](../../projects/01_scheduling_core/configs/month1.json)、[benchmark.py](../../projects/01_scheduling_core/scheduling_experiments/benchmark.py)、[parser.py](../../projects/01_scheduling_core/scheduling_io/parser.py)。

`benchmark.py` 里「先保存、后求解」的顺序是刻意的：

```python
instance = generate_instance(**spec["generator"])
path = output / "instances" / f"{name}.json"
save_json_instance(instance, path)
input_hash = hashlib.sha256(path.read_bytes()).hexdigest()
optimum = (
    exhaustive_optimum(instance, spec["objective"])[0]
    if spec.get("exact", False)
    else None
)
```

四个要点：

1. **先落盘再求解**：同一实例的所有算法（6 组主实验 + 3 组敏感性 × 3 seed）共用这一份文件，而不是各自重生成一遍。
2. **`input_sha256` 算的是文件字节**（`path.read_bytes()`），不是内存对象。任何字节级改动——数值、字段顺序、换行符——都会改变哈希。所以它同时也是「文件在传输/复制过程中有没有被改动」的证据。
3. **`save_json_instance` 用 `asdict` + `json.dumps(indent=2)`**：字段顺序由 dataclass 定义决定，输出确定；解析侧 [parser.py](../../projects/01_scheduling_core/scheduling_io/parser.py) 的 `_parse_instance` 负责还原成 `Instance`，两侧互为往返测试。
4. **`exact: true` 才计算枚举参考**：只有 tiny 两个实例调用 `exhaustive_optimum`，其余实例的 `reference` 留空，等所有运行结束后再回填（Day 3 第 4 节）。

结果行的 `run_id` 把四元组写进标识，让每一行都能被唯一定位：

```text
run_id = f"{name}__{group}__{algorithm}__{seed}"
       = tiny_single__main__lpt__0
```

---

## 7. 实验：`m1w4d2_instances`

对应脚本 [m1w4d2_instances.py](../../projects/01_scheduling_core/examples/m1w4d2_instances.py)。脚本**只读** `artifacts/`，不写任何文件。在项目目录下运行：

```bash
python examples/m1w4d2_instances.py
```

脚本做四件事：打印六实例参数表并断言作业/机器/工序数、核对每份输入 JSON 的 SHA-256、逐作业打印 `r/d/w/p`、演示两种 seed 的分工。实际输出：

```text
=== 1. 实例参数表（输入见 instances/*.json，目标与参考取自 results.csv） ===
实例           输入seed  作业  机器  每作业工序  总工序  目标             参考类型    参考值
tiny_single    10        4     1     1           4       total_tardiness  optimum     36.0
tiny_parallel  11        4     2     1           4       makespan         optimum     38.0
single_12      20        12    1     1           12      total_tardiness  best-known  250.0
parallel_12    21        12    3     1           12      makespan         best-known  43.0
parallel_24    22        24    3     1           24      makespan         best-known  90.0
routes_12      23        6     3     2           12      makespan         best-known  40.0

注意：routes_12 的 12 是总工序数（6 作业 × 2 工序），不是 12 个作业。

=== 2. 输入 JSON 的 SHA-256 与 results.csv 记录的 input_sha256 核对 ===
实例           sha256(instances/*.json)                                          results.csv 记录                                                  核对
tiny_single    e55495a649146422c71d4bbceadd6dcfc4c027a6c3605a643ef53ca6a677986a  e55495a649146422c71d4bbceadd6dcfc4c027a6c3605a643ef53ca6a677986a  一致
tiny_parallel  01af25b0b32a85afe63efe71d03e93267f3ab588f21aa3fea42a2731a1404453  01af25b0b32a85afe63efe71d03e93267f3ab588f21aa3fea42a2731a1404453  一致
single_12      de904454fddb4a082f8efe66a26c940f94997a57de4f5098ddd6034ff67564df  de904454fddb4a082f8efe66a26c940f94997a57de4f5098ddd6034ff67564df  一致
parallel_12    8af7c957e42e17ad0f5c23a6406046dad98822892c51e335254dfcea536d7852  8af7c957e42e17ad0f5c23a6406046dad98822892c51e335254dfcea536d7852  一致
parallel_24    54f0c68424dbeeff0dc38517d6855d9d1da02545b8f913ed8b969bc35c6b9be3  54f0c68424dbeeff0dc38517d6855d9d1da02545b8f913ed8b969bc35c6b9be3  一致
routes_12      ed8b606f720337b89df97898c7ab6168abf514416d8e3b1d0d97e2a7a07ad58c  ed8b606f720337b89df97898c7ab6168abf514416d8e3b1d0d97e2a7a07ad58c  一致

=== 3. 逐作业数据（r=release_time，d=due_date，w=weight，p=processing_time） ===
[tiny_single]  4 作业 / 1 机器 / 4 工序
  J000  r=0  d=28  w=4  p=19
  J001  r=9  d=33  w=1  p=16
  J002  r=7  d=17  w=4  p=7
  J003  r=10 d=23  w=2  p=9
[tiny_parallel]  4 作业 / 2 机器 / 4 工序
  J000  r=8  d=30  w=4  p=15
  J001  r=8  d=30  w=5  p=15
  J002  r=2  d=12  w=5  p=7
  J003  r=10 d=34  w=5  p=16
[single_12]  12 作业 / 1 机器 / 12 工序
  J000  r=4  d=11  w=1  p=5
  J001  r=9  d=25  w=2  p=11
  J002  r=6  d=7   w=4  p=1
  J003  r=1  d=5   w=2  p=3
  J004  r=7  d=23  w=5  p=11
  J005  r=6  d=28  w=2  p=15
  J006  r=5  d=15  w=3  p=7
  J007  r=6  d=22  w=1  p=11
  J008  r=7  d=32  w=4  p=17
  J009  r=3  d=7   w=5  p=3
  J010  r=0  d=12  w=2  p=8
  J011  r=1  d=7   w=2  p=4
[parallel_12]  12 作业 / 3 机器 / 12 工序
  J000  r=6  d=15  w=4  p=6
  J001  r=7  d=22  w=2  p=10
  J002  r=8  d=32  w=2  p=16
  J003  r=8  d=33  w=2  p=17
  J004  r=0  d=1   w=3  p=1
  J005  r=6  d=34  w=1  p=19
  J006  r=3  d=10  w=2  p=5
  J007  r=6  d=9   w=4  p=2
  J008  r=7  d=37  w=1  p=20
  J009  r=8  d=24  w=4  p=11
  J010  r=10 d=16  w=3  p=4
  J011  r=2  d=3   w=1  p=1
[parallel_24]  24 作业 / 3 机器 / 24 工序
  J000  r=3  d=10  w=1  p=5
  J001  r=7  d=37  w=2  p=20
  J002  r=10 d=16  w=3  p=4
  J003  r=3  d=7   w=3  p=3
  J004  r=5  d=8   w=5  p=2
  J005  r=8  d=17  w=4  p=6
  J006  r=9  d=12  w=1  p=2
  J007  r=4  d=32  w=3  p=19
  J008  r=3  d=24  w=2  p=14
  J009  r=9  d=15  w=5  p=4
  J010  r=0  d=28  w=3  p=19
  J011  r=5  d=35  w=3  p=20
  J012  r=6  d=15  w=3  p=6
  J013  r=2  d=27  w=3  p=17
  J014  r=10 d=23  w=2  p=9
  J015  r=0  d=21  w=3  p=14
  J016  r=0  d=27  w=4  p=18
  J017  r=8  d=21  w=3  p=9
  J018  r=6  d=31  w=4  p=17
  J019  r=4  d=13  w=5  p=6
  J020  r=6  d=24  w=5  p=12
  J021  r=4  d=5   w=5  p=1
  J022  r=8  d=38  w=5  p=20
  J023  r=6  d=31  w=5  p=17
[routes_12]  6 作业 / 3 机器 / 12 工序
  J000  r=0  d=19  w=5  p=(10, 3)
  J001  r=6  d=42  w=5  p=(10, 14)
  J002  r=3  d=28  w=3  p=(12, 5)
  J003  r=3  d=27  w=5  p=(15, 1)
  J004  r=1  d=25  w=1  p=(15, 1)
  J005  r=0  d=45  w=5  p=(16, 14)

=== 4. 两种 seed 的分工（同一实例、同一 input_sha256，只改算法 seed） ===
算法  算法seed  run_id                     status    objective  evaluations
lpt   0         parallel_12__main__lpt__0  BASELINE  45.0       1
lpt   1         parallel_12__main__lpt__1  BASELINE  45.0       1
lpt   2         parallel_12__main__lpt__2  BASELINE  45.0       1
sa    0         parallel_12__main__sa__0   BUDGET    45.0       150
sa    1         parallel_12__main__sa__1   BUDGET    44.0       150
sa    2         parallel_12__main__sa__2   BUDGET    45.0       150

输入 seed 交给生成器，决定 p / r / d / w 与机器数：同一实例的 18 条主实验只有一个 input_sha256。
算法 seed 只交给 Random(seed)，决定搜索动作序列：lpt 三行完全相同，sa 三行的目标值不同。
所以改输入 seed = 换一道题，改算法 seed = 同一道题换一次随机搜索，二者不能互相代替。
只保存 seed 不够强：生成器一旦改动（采样区间、due_factor 等），同一个 seed 会生成另一道题，旧结果行就再也指不回原输入。
保存输入 JSON 并逐行记录 SHA-256 之后，即使生成器变化，仍可用这份 JSON 重算并核对 input_sha256。
```

**实验观察**：

1. 第 4 节表格里的每个数字都在第 1 段输出里出现，并且脚本对作业数、机器数、每作业工序数和总工序数逐项做了 `assert`——表里的数不是抄来的，是算出来的。
2. 第 2 段输出显示六份输入的 SHA-256 与 162 条结果行记录的 `input_sha256` 逐字节一致；脚本同时断言「同一实例的所有结果行只对应一个 `input_sha256`」。
3. 第 3 段把 62 个作业的 `r/d/w/p` 全部摊开，读者可以拿第 5 节的手算逐行对拍。
4. 第 4 段是最有信息量的一段：`lpt` 三个 seed 的 `objective` 完全相同（45.0）且 `evaluations` 都是 1，因为它不消费随机数；`sa` 三个 seed 的 `objective` 分别是 45.0 / 44.0 / 45.0，同样的输入、同样的预算，只因为算法 seed 不同而走出不同的搜索轨迹。

**结论**：确定性方法在三个 seed 下重复，只是在**验证同一个接口与同一种记录格式**，并不提供三个独立的随机样本。把 `lpt` 的三次 45.0 当成「三个观测」去算标准差（会得到 0.0），再据此说「LPT 比 SA 稳定」，是把「确定性」和「低方差」混为一谈。

---

## 8. 今日练习

1. **练习 1（手算）**：用生成器公式手算 tiny_parallel 的 J002 与 J003 的 `due_date`，再与第 7 节输出的 `d=12`、`d=34` 对照，说明 `int()` 在这里各截掉了多少。
2. **练习 2（配置实验）**：另存一份配置，只把 `release_max` 改成 0，比较释放时间对解码与目标的影响。**这组实验不在本次 162 条里**，结论必须自己跑完再写，不能凭直觉填。
3. **练习 3（两种 seed）**：固定实例与算法，只改输入 seed，观察实例 JSON 的差异；再固定输入 seed，只改算法 seed，观察 `objective` 的差异。各写一句结论。
4. **练习 4（哈希）**：把某份实例 JSON 复制到临时目录，只改一个 `processing_time`，重新算 SHA-256，确认与原值不同；并说明为什么这个练习**必须**在副本上做，不能改正式目录。
5. **练习 5（覆盖分析）**：列出这批实例没有覆盖的三类情形（例如机器资格受限、工序数大于 2、机器数大于 3），各写一句「要检验什么」。

---

## 9. 验收清单

- [ ] 能背出六个实例的名称、输入 seed、规模，以及 routes_12 的 12 指总工序数。
- [ ] 能写出交期公式 `d = r + int(Σp × due_factor)` 并说明 `int()` 的截断方向（`28.5 → 28`）。
- [ ] 能说清哪些生成参数写在配置里、哪些用的是默认值，以及这件事对「只保存 seed」意味着什么。
- [ ] 能区分输入 seed 与算法 seed 0/1/2，并各举一个真实运行行说明。
- [ ] 能数清 162 = 6×6×3（108 主实验）+ 6×3×3（54 敏感性），并说出三组敏感性改了什么。
- [ ] 能解释确定性方法跨 seed 重复为什么不算独立样本。
- [ ] 能解释 `input_sha256` 保护的是什么改动，以及它为什么不能由「重新生成一次」代替。
- [ ] 能说出这批实例的至少三个覆盖限制，并说明报告不能由此推什么。
- [ ] `python -m examples.m1w4d2_instances` 打印六实例参数表与 SHA-256 核对结果，全部一致、无断言失败。
- [ ] `python -m pytest -q` 全部通过（本日不新增测试，仍为 127 条）。

---

## 10. 自测题

不看上文回答：

- Q1：本批次实例的 `p`、`r`、`w` 采样区间与 `due_factor` 各是多少？哪些写在配置里？
- Q2：`due_date` 的计算公式是什么？`int(28.5)` 的结果是多少？
- Q3：六个实例的输入 seed 与规模各是多少？
- Q4：routes_12 里的 12 指什么？它的题目结构与其他五个实例有什么本质不同？
- Q5：108 与 54 分别是怎么来的？加起来是多少？
- Q6：输入 seed 与算法 seed 的分工是什么？
- Q7：为什么确定性方法在三个 seed 下重复不算三个独立随机样本？
- Q8：为什么结果行要记 `input_sha256`，而不是只记输入 seed？
- Q9：tiny_single 的参考类型为什么是 `optimum`，而 parallel_12 是 `best-known`？
- Q10：举出这批实例的三个覆盖限制，并说明报告不能由此推出什么。

### 参考答案

- A1：`p ∈ [1,20]`（`rng.randint(1, 20)`）、`r ∈ [0,10]`（`release_max` 默认 10）、`w ∈ {1,…,5}`（`rng.randint(1, 5)` 转 float）、`due_factor = 1.5`；配置里只写了 `seed / jobs / machines / operations_per_job`，`release_max` 与 `due_factor` 用的是默认值。
- A2：`d = r + int(Σp × due_factor)`，其中 `Σp` 是该作业所有工序的工时之和；`int()` 向零截断，`int(28.5) = 28`。
- A3：tiny_single 10（4 作业 1 机器 1 工序）、tiny_parallel 11（4/2/1）、single_12 20（12/1/1）、parallel_12 21（12/3/1）、parallel_24 22（24/3/1）、routes_12 23（6/3/2）。
- A4：指总工序数（6 作业 × 2 工序 = 12）；它是唯一的**多工序**实例，作业内有 precedence 链，其余五个实例每作业只有一道工序。
- A5：108 = 6 实例 × 6 方法（`lpt/random/first/best/multistart/sa`）× 3 个算法 seed；54 = 6 实例 × 3 组 SA 敏感性设置（T=0.1、T=100、cooling=0.9）× 3 个算法 seed；合计 162。
- A6：输入 seed 交给生成器，决定实例的 `p/r/d/w` 与规模；算法 seed 交给 `Random(seed)`，只决定搜索动作序列。前者换题，后者换搜索轨迹。
- A7：确定性方法不消费随机数，三次运行的解与评价数完全相同（`parallel_12__main__lpt__*` 都是 45.0、1 次评价），因此它们是同一个观测被记了三遍，不是三个独立样本。
- A8：种子只是「生成输入的方式」，不是输入本身。生成器或默认参数一旦改变，同一个 seed 会生成另一道题，旧结果行便失去可复核的输入；保存 JSON 并逐行记录字节级 SHA-256 才能锁定当时真正用的输入。
- A9：tiny_single 在配置里标了 `exact: true`，参考值由 `exhaustive_optimum` 在可枚举范围内完整枚举得到，故记为 `optimum`；parallel_12 的参考是本批次全部成功主实验与敏感性运行的最小值，只是这一批数据里的最好记录，故记为 `best-known`。
- A10：例如「全部作业全机器资格」「机器数不超过 3」「工序数不超过 2 且无柔性路径」。因此报告不能声称结论适用于资格受限、大规模或一般 FJSP 场景，也不能把本批次的均值排名当作普遍规律。

---

## 11. 今日一句话总结

> **实例集是实验设计的一部分：输入 seed 决定题、算法 seed 决定搜法，而只有把输入 JSON 连同它的 SHA-256 一起留下，才谈得上「同一批题再跑一次」。**
