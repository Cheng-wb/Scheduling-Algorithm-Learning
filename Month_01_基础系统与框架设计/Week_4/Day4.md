# Day 4：批量运行、失败留痕与复现

> 当日主题：把「我跑过一次」升级为可审计的批次记录——失败要留痕、时间要排除、版本要可定位。
> 当日产出：**一次完整批次的验收清单与三层复现的真实对照**，以及对 `examples/m1w4d4_reproduce.py` 四道闸门的逐条解读。
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 列出一个合格批次目录里应有的全部文件，并说出 `results.csv`（162 行）、`runs/`（162 份 JSON 与 162 份 `trace.csv`）、`summary.csv`（54 行）各自的口径。
2. 区分「批次准备失败」与「单次求解失败」，说明两者分别留下什么痕迹、CLI 退出码如何反映。
3. 按顺序说出可复现性的三个层次，并指出哪些字段属于允许不同的时间类字段。
4. 读懂 [m1w4d4_reproduce.py](../../projects/01_scheduling_core/examples/m1w4d4_reproduce.py) 的四道闸门，以及每一道对应的失败信息。
5. 解释为什么「重复运行后 `summary.csv` 均值一致」不足以证明复现，并能举出一条真实反例。
6. 说明失败注入测试 `test_benchmark_failure_is_recorded` 覆盖了什么，以及为什么不能破坏正式实验文件来模拟失败。
7. 说出删除 seed 或删除实例之前必须先定规则、后看结果的理由。

---

## 2. 为什么第 4 天要讲批量运行与复现

前半周的两份产出各自回答一个问题：Day 2 第 4 节回答「跑了哪些题」，Day 3 第 3 节回答「结果长什么样」。但它们都是**单次运行**层面的证据——一次运行可以手工重跑核对，一个 162 次运行的批次不行。批次需要的是流程：留下什么、失败怎么办、以后怎么核对。

「我跑过一次」这句话有三个漏洞：

- **只留成功**：失败如果只被打印到屏幕、或者让整批中断，产物里就看不出发生过什么。批次必须把失败写进 `results.csv` 与 `failures.json`，同时让其余运行继续。
- **只留数字**：`objective=42.0` 这个数字本身不含来源信息——哪份输入、哪版源码、什么配置。换了源码再跑出同一个 42.0，那是另一个实验。于是要有 `input_sha256`、`source_sha256`、`config_sha256` 三份哈希。
- **只比均值**：`summary.csv` 是跨 seed 的汇总，粒度太粗。第 5 节会给出一条真实的「目标值相同、解不同」反例。

三份哈希各管一段，分工不能互相代替：

| 哈希 | 记录位置 | 固定的是什么 | 变化意味着什么 |
|---|---|---|---|
| `input_sha256` | `results.csv` 每一行 | 这一行的题目（实例 JSON 的字节内容） | 实例 JSON 被改过，旧结果指不回原题（Day 2 第 4 节） |
| `config_sha256` | `metadata.json` | 整批的配置：实例列表、`seeds`、`algorithms`、`search` | 搜索参数或实验设计变了，两批结果不能直接合并比较 |
| `source_sha256` | `metadata.json` | 四个包的全部 `*.py` | 算法实现变了，第 7 节的闸门 1 会拒绝复现 |

**定义**：本文说的**批次**（batch）指一次 `run(config, output)` 调用写出的整个输出目录；**可复现**指在记录的条件齐备时，重跑得到的算法结果与保存的记录一致。

**理论结论**：在输入、配置与源码完全相同的前提下，`solve` 是确定性的——随机性只来自 `Random(seed)`（见 Day 2 第 4 节），因此 `objective`、`evaluations`、`status`、`Candidate`、`Schedule` 与逐评价 `trace` 都必须逐字段相同。

**实验观察**：`elapsed_seconds` 是例外，它度量的是本次机器上的耗时，不参与「相同」的定义。本批次保存的值是 `0.02270120003959164` 秒，重解两次分别是 `0.03429879999021068` 与 `0.033107099996414036` 秒（第 5 节）。

---

## 3. 运行验收：一个合格批次的全部产出

[benchmark.py](../../projects/01_scheduling_core/scheduling_experiments/benchmark.py) 的 `run()` 第一件事是拒绝写进非空目录：

```python
    if output.exists() and any(output.iterdir()):
        raise ValueError(
            f"output must be empty (preserve previous experiments): {output}"
        )
```

这是「不覆盖上一次实验」的硬约束：宁可报错重跑，也不要把两批结果混在同一个目录里——混在一起之后，`results.csv` 的每一行属于哪一版源码就再也说不清了。

在项目目录下运行：

```bash
python -m scheduling_experiments.benchmark --config configs/month1.json --output artifacts/month1_refactored
```

CLI 结束时打印一行汇总，并在有失败时用非零状态退出：

```python
    rows = run(args.config, args.output)
    failed = sum(row["status"] == "FAILED" for row in rows)
    print(f"runs={len(rows)}, failed={failed}, output={args.output.resolve()}")
    if failed:
        raise SystemExit(1)
```

本批次 `artifacts/month1_refactored/` 的实际成员与口径：

| 成员 | 本次实测 | 口径 |
|---|---|---|
| `results.csv` | 162 行 | 每次**运行**一行，批次层唯一入口 |
| `runs/<run_id>.json` | 162 份 | 每次运行的 `config` / `candidate` / `schedule` |
| `runs/<run_id>.trace.csv` | 162 份 | 每次**评价**一行（`runs/` 目录共 324 个文件） |
| `summary.csv` | 54 行 | 实例 × 组 × 算法，跨 seed 汇总（6 × 3 × 3） |
| `failures.json` | `[]` | `results.csv` 中 `status == "FAILED"` 的子集 |
| `metadata.json` | 9 个键 | 批次级环境与版本证据 |
| `instances/` | 6 份 JSON | 输入快照，逐行哈希记录在 `results.csv` |
| `config.json` | 1 份 | 本次批次用的配置副本 |
| `report.md` | 1 份 | 脚本生成的汇总表 |
| `quality.png` / `convergence.png` / `gantt.png` | 3 张 | 质量对比、收敛曲线、甘特图 |
| `verification.json` | 1 份 | 批次收尾时写入的独立复现结论 |

`status` 计数（Day 3 第 3 节已核对）：`BASELINE` 18、`BUDGET` 132、`LOCAL_OPTIMUM` 12、`FAILED` 0。

`verification.json` 记录的关键项（实测读取）：

```text
tests_passed                                  107
mypy_source_files                              18
reproduced_runs                               162
pre_refactor_rows_equal_excluding_timing      162
identical_candidates_schedules_and_traces     162
```

`reproduced_runs = 162` 与 `results.csv` 的 162 行一致，说明**每一次成功运行**都被重解核对过，而不是抽查。要注意 `tests_passed = 107` 是批次当时的测试数，与今天 `pytest -q` 的 127 不同——测试在批次之后继续增加，这也是第 7 节版本闸门会变化的原因之一。

`report.md` 与三张 PNG 是**派生视图**：它们从 `results.csv` 与 `runs/` 渲染而来，方便人看，但不承担审计职责——`report.md` 只保留汇总表，图上更不可能写出每行的 `input_sha256`。审计的入口始终是 `results.csv` 以及它指向的 `runs/<run_id>.*`。

---

## 4. 失败留痕：把「整批没开始」与「单次求解失败」分开

两类失败的后果完全不同：

| 情形 | 触发点 | 产物 | 退出码 |
|---|---|---|---|
| 批次准备失败 | `run()` 开头：输出目录非空、配置读不出、实例生成失败 | `results.csv` 可能根本不存在 | 异常直接抛出 |
| 单次求解失败 | 循环里的 `solve()` 抛异常 | 该行保留 `FAILED` 与 `failure_reason`，其余运行照常 | 批次跑完后 `SystemExit(1)` |
| 全部成功 | —— | 162 行齐全，`failures.json` 为 `[]` | 0 |

第一类是**没跑起来**，第二类是**跑了但这次没成**。两者都不允许被算作一次成功求解：`summarize()` 的判据是「有没有目标值」，而不是 `status`：

```python
        good = [row for row in selected if row["objective"] is not None]
        ...
                "successful": len(good),
                "failed": len(selected) - len(good),
```

因此只要失败行被老老实实写下来，它就一定进 `failed`，`mean`、`best`、`mean_evaluations` 也只会用有目标值的行计算。真正难防的是另一种做法——**把没跑成的运行直接跳过，既不留行也不记录**：那一行会从 162 行里凭空消失，均值看不出变化、成功次数也不会变少，而样本量已经悄悄缩水了。这也是第 3 节要求「输出目录必须为空」的同一个理由：宁可让流程报错，也不让记录对不上。

单次失败的留痕代码：

```python
                    "status": "FAILED",
                    "objective": None,
                    "evaluations": 0,
                    "elapsed_seconds": None,
                    ...
                    "gap": None,
                    "failure_reason": "",
                }
                try:
                    result = solve(instance, settings)
                    row.update(status=result.status, objective=result.objective, ...)
                    write_json(output / "runs" / f"{run_id}.json", {...})
                    write_csv(output / "runs" / f"{run_id}.trace.csv", [...])
                except Exception as exc:  # 单次失败留痕，批次继续；CLI 最终非零退出。
                    row["failure_reason"] = f"{type(exc).__name__}: {exc}"
```

四个设计点值得记住：

- 行是**先预置成失败态**、再被成功结果覆盖的，因此 `except` 分支只需补一个 `failure_reason`，不会漏字段。
- 失败行**没有** `runs/<run_id>.json` 与 `trace.csv`（写入在 `try` 内），所以「目录里少了文件」本身就是失败痕迹。
- `failure_reason` 拼接了异常类型与消息，例如 `ValueError: ...`；只留一句「失败了」无法定位原因。
- `gap` 保持 `None`：`reference` 回填只收集非空的目标值，失败行永远不会把某一实例的 `reference` 拉低（Day 3 第 4 节）。

**结论**：失败要**留痕**（写进结果表与 `failures.json`）、**不阻断**（其余运行继续）、**影响退出码**（`SystemExit(1)`），三者缺一不可。

---

## 5. 示例：三层复现与一组「同分不同解」的真实记录

取 Day 3 第 5 节已经重算过的那条记录 `routes_12__main__sa__0`，把复现拆成三层来看。

**第一层**，算法结果：

| 字段 | 保存的记录 | 现场重解 |
|---|---|---|
| `objective`（`makespan`） | 42.0 | 42.0 |
| `evaluations` | 150 | 150 |
| `status` | `BUDGET` | `BUDGET` |

**第二层**，解与过程。重解一次，再与保存下来的 `runs/<run_id>.json`、`.trace.csv` 逐字段比较：

```text
归一化后与保存记录比较  candidate 相同 : True ；schedule 相同 : True
trace 相同     : True （150 行）
```

这里有一个真实的坑：`dataclasses.asdict()` 会把 `Candidate.order` 还原成 `tuple`，而保存的 JSON 里是 `list`，直接比较永远得到 `False`。所以 [m1w4d4_reproduce.py](../../projects/01_scheduling_core/examples/m1w4d4_reproduce.py) 先做一次 JSON 往返把类型抹平：

```python
        actual = json.loads(
            json.dumps(
                {
                    "candidate": asdict(result.candidate),
                    "schedule": asdict(result.schedule),
                }
            )
        )
```

`trace` 的比较容易写错，它把每个 `TracePoint` 的值统一成字符串（`None` 变空串）后再与 CSV 对比，否则 `54.0` 与 `"54.0"` 又是两个不相等的值。

**第三层**，时间类字段。三次运行的 `elapsed_seconds`：

```text
保存的记录          0.02270120003959164
第一次重解          0.03429879999021068
第二次重解          0.033107099996414036
```

三个值互不相同，而其余一切相同。**定义**：`elapsed_seconds` 与 `metadata.created_utc` 是**观测字段**，不是**结果字段**；复现时排除它们，等于排除「这台机器这次运行得多快」，不等于放宽算法结果。[m1w4d4_reproduce.py](../../projects/01_scheduling_core/examples/m1w4d4_reproduce.py) 结尾那句 `timing intentionally excluded` 说的就是这件事。

反过来，**只比第一层是不够的**。`parallel_12` 主实验里有一对真实记录：

| `run_id` | `status` | `objective` | `evaluations` | `gap` |
|---|---|---|---|---|
| `parallel_12__main__random__0` | `BUDGET` | 44.0 | 150 | 0.023255813953488372 |
| `parallel_12__main__random__2` | `BUDGET` | 44.0 | 150 | 0.023255813953488372 |

第一层完全一致，但排程不同：12 道工序全不相同，机器负载也不同（`random__0` 为 M0=38、M1=36、M2=38；`random__2` 为 M0=37、M1=41、M2=34），第一条差异就是 `J004_O0` 在 `random__0` 落 M0、在 `random__2` 落 M2。两条记录只被保存的 `order` 与 `assignments` 区分开——只看目标值，它们看起来是「同一个结果」。

**结论**：可复现性的比较必须落到**解与过程**这一层；`objective` 与 `evaluations` 相同只说明「同样好」，不说明「同一个解」。同理，只看 `summary.csv` 的均值更粗：两个 seed 得到 44.0 与 45.0 的均值是 44.5，而两个 seed 都得到 44.5 的均值也是 44.5，但它们是不同的实验记录；均值还可能掩盖成功与失败的不同组合。顺带一提，`summary.csv` 的 `mean_seconds` 同样是观测字段，不该用来比较两批实验的快慢——机器、负载与缓存都不一样。

---

## 6. 实现：`examples/m1w4d4_reproduce.py` 的四道闸门

[m1w4d4_reproduce.py](../../projects/01_scheduling_core/examples/m1w4d4_reproduce.py) 的入口是一个 `reproduce(directory)`：读 `metadata.json` 与 `results.csv`，对每一行重解并核对。它一共设了四道闸门，任何一道不过就抛 `ValueError` 并中止——**宁可拒绝，也不输出一份无法解释的对比**。

| 闸门 | 检查 | 不过时抛出的信息 |
|---|---|---|
| 1. 源码哈希 | `source_hash() == metadata["source_sha256"]` | `source hash differs from recorded run; use its original source version` |
| 2. 输入哈希 | 每行 `instances/<name>.json` 的 SHA-256 `== row["input_sha256"]` | `input hash mismatch: <run_id>` |
| 3. 解与过程 | 归一化后的 `candidate` / `schedule` 与保存 JSON 相同；`trace.csv` 逐行相同 | `schedule/candidate mismatch` 或 `trace mismatch` |
| 4. 算法结果 | `objective`、`evaluations`、`status` 与结果行相同 | `result mismatch: <run_id>` |

几个细节：

```python
    for row in rows:
        if row["status"] == "FAILED":
            continue
```

失败行被跳过——它本来就没有可重解的 `Candidate`；它们由 `failures.json` 负责留痕，最后在汇总行里以 `recorded_failures` 出现：

```python
    print(
        f"reproduced={checked}, recorded_failures={len(rows) - checked}; timing intentionally excluded"
    )
```

`reproduce()` 用的是**保存下来的 `config`** 与**保存下来的输入 JSON**，不读今天的配置：

```python
        result = solve(load_json_instance(path), SearchConfig(**saved["config"]))
```

这样即使配置被改过，重解也仍然按批次当时的口径走。闸门 1 之所以只拦源码、不拦配置，是因为配置由 `config_sha256` 单独记录在 `metadata.json` 里，而 `reproduce()` 并不比对它——所以「换了配置但没换源码」这一路，得靠你自己看 `config_sha256`。

第一道闸门用的 `source_hash()` 覆盖四个包的**全部 `*.py`**，按相对路径（posix 形式）与文件内容（读取时统一换行）依次累加：

```python
def source_hash() -> str:
    digest = hashlib.sha256()
    for package in ("scheduling_core", "scheduling_algorithms", "scheduling_io", "scheduling_experiments"):
        for path in sorted((ROOT / package).rglob("*.py")):
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_text(encoding="utf-8").encode("utf-8"))
    return digest.hexdigest()
```

它**不覆盖**测试、文档与配置：改动测试不会让闸门失败，这一点在解读闸门时要说清楚。

脚本的 CLI 只接一个可选的位置参数（要核对的批次目录），省略时默认核对本批次：

```python
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory",
        type=Path,
        nargs="?",
        default=ROOT / "artifacts" / "month1_refactored",
    )
    reproduce(parser.parse_args().directory)
```

换成别的目录时，它同样先校验那个批次的 `metadata.json` 与每一行的 `input_sha256`，再逐行重解——也就是说，同一个脚本可以核对任意一批产物，前提是那一批把源码哈希、输入哈希与每次运行的 `config` 都记全了。在项目目录下运行：

```bash
python -m examples.m1w4d4_reproduce
```

最后用 `reproduced=N, recorded_failures=M` 收尾：`N` 应等于成功运行数，`M` 应等于 `failures.json` 的长度，两者之和应等于 `results.csv` 的行数。核对这三个数字，就能判断这次复现是否覆盖了整批。

---

## 7. 实验：`m1w4d4_reproduce` 的第一道闸门与失败注入

本文档不重跑 [m1w4d4_reproduce.py](../../projects/01_scheduling_core/examples/m1w4d4_reproduce.py)（它要做 162 次求解），但可以**只读地**验证它的第一道闸门，并完整跑一次失败注入测试。

在项目目录下运行：

```bash
python -c "import json,pathlib; from scheduling_experiments.benchmark import source_hash; m=json.loads(pathlib.Path('artifacts/month1_refactored/metadata.json').read_text(encoding='utf-8')); print('current source_hash', source_hash()); print('recorded source_hash', m['source_sha256']); print('match', source_hash()==m['source_sha256'])"
```

实际输出：

```text
current source_hash 4d6d74ea57637b7c253ca504712449dbc58705ecf0ca0148b1331e92cf868d88
recorded source_hash 025ed469c2621c036403f7876a865ac858c1951563f7dc7058113c305e142477
match False
```

**结论**：按今天的源码，`m1w4d4_reproduce.py` 会在第一道闸门停下并抛出 `source hash differs from recorded run`——这是设计行为，不是缺陷。原因记在 `metadata.json` 里：

```text
git_commit           538886b3ded5c11afcfd137fa1aebc14fe59020c
working_tree_dirty   True
source_sha256        025ed469c2621c036403f7876a865ac858c1951563f7dc7058113c305e142477
config_sha256        8b126be787355ee715d0113338609863e130b7f047f6c25da8fb255a4742eeaa
```

批次是在**工作区有未提交改动**的状态下产生的，所以记录的 `git_commit` 只说明「从哪个提交出发」，不足以定位当时的确切源码。只读地对两个提交各取一份 `projects/01_scheduling_core` 下的四个包、用同一个 `source_hash()` 算法计算，得到：

```text
commit 538886b 的四个包      4f2c6d1e0c80994146a239652cb794e3eb700f98ce0753406e6a3795f8305c9f（13 个 .py）
commit 4b7c4e1 的四个包      4d6d74ea57637b7c253ca504712449dbc58705ecf0ca0148b1331e92cf868d88（19 个 .py）
批次记录的 source_sha256     025ed469c2621c036403f7876a865ac858c1951563f7dc7058113c305e142477
```

（测法：把两个提交下的 `projects/01_scheduling_core` 各自解到临时目录，用与 `source_hash()` 相同的累加规则计算；全程只读，不写仓库。）

两个提交都不是记录值；当前工作区（`git status` 对四个包为空，HEAD 为 `4b7c4e1`）的哈希等于 `4b7c4e1` 那一版，说明批次之后源码又改过——`git diff --stat 538886b HEAD` 对这四包统计为 17 files changed, 285 insertions(+), 194 deletions(-)。`verification.json` 里 `tests_passed = 107`、`mypy_source_files = 18` 与今天的 127 个测试、19 个源文件对不上，是同一件事的另一面。

这正是第三层复现的价值：**它不能让我们用今天的源码复现昨天的批次，但它把「不能复现」这件事说清楚了**。记录在案的是 `source_sha256`，而不是一句「我跑过」；如果当时只记了 `git_commit` 538886b，今天就会误以为「源码没变、可以复现」。

也**不要为了让闸门通过去改 `metadata.json` 里的 `source_sha256`**：那份记录是批次的证据，改动它，闸门就从「证明源码没变」退化成「证明你改过记录」，此后任何复现结论都不可信。正确做法是保留原记录，让复现按批次当时的源码进行。

第二项实验是失败注入。在项目目录下运行：

```bash
python -m pytest tests/test_month1.py -k benchmark_failure -v
```

实际输出（节选尾部）：

```text
collecting ... collected 56 items / 55 deselected / 1 selected

tests/test_month1.py::test_benchmark_failure_is_recorded PASSED          [100%]

====================== 1 passed, 55 deselected in 0.30s =======================
```

这个测试的做法是：在临时目录里写一份**两行**的小配置（`random` 与 `sa` 各一个 seed），把 `benchmark.solve` 换成「遇到 `sa` 就抛异常、其余照常」的包装函数：

```python
    def fail_once(instance, settings):
        if settings.algorithm == "sa":
            raise RuntimeError("injected failure")
        return original(instance, settings)

    monkeypatch.setattr(benchmark, "solve", fail_once)
    monkeypatch.setattr(benchmark, "plot", lambda *args: None)
```

然后断言四件事：批次跑完仍是 2 行、第二行 `status == "FAILED"`、`failure_reason` 含 `injected failure`、`failures.json` 里那一行的 `gap` 为 `None`，最后 `summary.csv` 各行的 `failed` 计数合计为 1。它验证的正是第 4 节那三条设计：留痕、不阻断、计入统计。

**注意**：`monkeypatch` 只在测试进程内生效，输出目录是 `tmp_path`，不会碰到 `artifacts/` 下的任何正式产物。真实批次 0 失败只能说明「这次没出事」，只有注入过失败，才说明失败路径也被测过——**不要为了看失败长什么样去破坏正式实验文件**。

---

## 8. 今日练习

1. **练习 1（核对）**：只用 `results.csv`，按 `status` 统计行数，并核对四类计数之和是否等于 162。
2. **练习 2（区分）**：各举一个场景说明「批次准备失败」与「单次求解失败」，分别写出产物与退出码的差异。
3. **练习 3（分层）**：写出你自己的复现比较清单，并标注每一项属于第一层、第二层还是第三层。
4. **练习 4（找反例）**：在 `parallel_12` 主实验里再找一对「目标值相同、排程不同」的记录，写出 `run_id` 与机器负载差异。
5. **练习 5（规则先行）**：为「排除某些 seed」写一条可执行的规则，并说明它为什么必须在看结果之前确定。

---

## 9. 验收清单

- [ ] 能列出批次目录的全部成员，并说出 `results.csv`、`runs/`、`summary.csv`、`failures.json` 各自的口径。
- [ ] 能说出 `run()` 为什么要求输出目录为空，以及非空时会抛什么。
- [ ] 能区分批次准备失败与单次求解失败，并说出两者的产物与退出码差异。
- [ ] 能说出失败行缺了哪些文件、`gap` 为什么是空的、它如何影响 `reference` 回填。
- [ ] 能按顺序说出可复现性的三层，以及各层要比较的字段。
- [ ] 能解释为什么 `elapsed_seconds` 与 `created_utc` 允许不同，以及「排除时间字段」不等于「放宽算法结果」。
- [ ] 能举出一条真实的「目标值相同、排程不同」记录，说明只比目标值或均值为什么不够。
- [ ] 能说出 `m1w4d4_reproduce.py` 的四道闸门，并解释第一道闸门今天为什么会拒绝。
- [ ] 在项目目录下运行 `python -m examples.m1w4d2_instances` 与 `python -m examples.m1w4d3_schema`，两条命令都能在十秒内跑完，且打印的计数与本文档一致。
- [ ] 在项目目录下运行 `python -m pytest -q`，全部测试通过。

---

## 10. 自测题

- Q1：`results.csv` 有 162 行，为什么 `summary.csv` 只有 54 行？
- Q2：`failures.json` 为 `[]` 说明什么？又不能说明什么？
- Q3：批次准备失败与单次求解失败，哪一种会让 `results.csv` 根本不存在？
- Q4：单次求解失败后，为什么 `runs/<run_id>.json` 不会出现？
- Q5：可复现性的三层分别比较什么？哪一层最容易被「只比数字」蒙混过去？
- Q6：`m1w4d4_reproduce.py` 的第一道闸门拦的是什么？它为什么拦不住「配置被改过」？
- Q7：为什么 `reproduce()` 要用保存的 `config` 与输入 JSON，而不是今天的 `configs/month1.json`？
- Q8：两次重解 `routes_12__main__sa__0` 得到完全相同的 `Candidate`，但 `elapsed_seconds` 不同，这算复现成功吗？
- Q9：`parallel_12__main__random__0` 与 `__2` 的目标值都是 44.0，为什么不能说它们「复现了同一个结果」？
- Q10：为什么不能因为某个 seed 的结果「不好看」就把它的记录删掉？

### 参考答案

- A1：`results.csv` 逐运行一行（162 次运行）；`summary.csv` 是实例 × 组 × 算法三个维度的跨 seed 汇总：6 × 3 × 3 = 54 组，每组一行。
- A2：说明本批次 162 次求解没有一次抛异常，每一行都是成功运行；不能说明求解路径不会失败，失败路径由注入测试覆盖（第 7 节）。
- A3：批次准备失败。它在写结果之前就抛异常，可能连 `results.csv` 都没有；单次求解失败仍会写出一行 `FAILED`。
- A4：因为 `runs/<run_id>.json` 与 `trace.csv` 的写入在 `try` 内、紧跟成功的 `solve`，异常发生时这两份文件还没被创建。目录里少一份 JSON 本身就是失败痕迹。
- A5：第一层比 `objective`、`evaluations`、`status`；第二层比归一化后的 `candidate`、`schedule` 与逐行 `trace`；第三层比环境、源码与输入的记录。第一层最容易被蒙混，第 5 节的 44.0 反例就停在第一层。
- A6：拦的是「当前源码的 `source_hash()` 与记录的 `source_sha256` 不一致」，即批次之后源码被改过。它只覆盖四个包的 `*.py`，配置变化由 `config_sha256` 记录，而 `reproduce()` 并不比对后者。
- A7：`reproduce()` 要回答的是「按批次当时的口径能否重算出同样结果」，不是「用今天的口径能否得到更好的结果」。用保存的 `config` 与输入 JSON，才能把口径固定在批次当时。
- A8：算成功。`elapsed_seconds` 是观测字段而非结果字段；第一层与第二层全部一致，即算法结果、解与过程都复现了。
- A9：因为两者的排程不同——12 道工序全不相同，机器负载也不同（38/36/38 对 37/41/34）。目标值相同只说明「同样好」，不说明是同一个解；真正的复现要落到第二层。
- A10：因为删除记录等于修改实验结果，而「哪个 seed 不好看」只有看过结果才知道；只有事先定好排除规则、并把规则与原记录一起保留，才能避免「按结果挑数据」。

---

## 11. 今日一句话总结

> **一个可审计的批次要同时留下成功、失败与版本三样东西：失败写进 `results.csv` 与 `failures.json` 并让 CLI 非零退出，版本靠 `source_sha256`、`config_sha256`、`input_sha256` 三份哈希固定，而复现只有在解与过程这一层逐字段对齐时才成立。**
