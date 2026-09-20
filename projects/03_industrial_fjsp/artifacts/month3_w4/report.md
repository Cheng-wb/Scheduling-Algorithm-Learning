# M3 Week 4 实验：逐条工业约束的消融（脚本生成）

时间预算 15 秒／次，seed 0，单线程。目标函数 `makespan`。
**同一份工序数据**，约束逐层累加：`base` → `+setup` → `+calendar` →
`+qualification` → `+worker` → `+locked`。

每加一条约束可行域只会变小，所以目标值**只会变大或不变**。这条单调性
同时是正确性检查：违反它的那一行一定是建模方向写错了。

## 消融链：`fjsp_cpsat_full`

| 阶段 | 新增约束 | 状态 | 目标值 | 相对上一层 | 目标值变化 | wall(s) | 分支数 |
|---|---|---|---:|---:|---|---:|---:|
| `base` | 机器相关工时 + 柔性 + 释放/交期 | OPTIMAL | 9 | — | — | 0.03 | 687 |
| `+setup` | sequence-dependent setup（工序族换型） | OPTIMAL | 9 | +0 | 没有改变 | 0.02 | 465 |
| `+calendar` | 机器日历（可用窗） | OPTIMAL | 9 | +0 | 没有改变 | 0.02 | 484 |
| `+qualification` | 机器资质（谁能做） | OPTIMAL | 27 | +18 | **变了** | 0.01 | 253 |
| `+worker` | 次生资源能力 + 容量（谁能开、同时开几个） | OPTIMAL | 27 | +0 | 没有改变 | 0.02 | 284 |
| `+locked` | WIP / 锁定工序（已在机不可再选） | OPTIMAL | 31 | +4 | **变了** | 0.01 | 215 |

单调性核对（目标值随约束增加不下降）：**通过**。

## 消融链：`fjsp_cpsat_qualified`

| 阶段 | 新增约束 | 状态 | 目标值 | 相对上一层 | 目标值变化 | wall(s) | 分支数 |
|---|---|---|---:|---:|---|---:|---:|
| `base` | 机器相关工时 + 柔性 + 释放/交期 | OPTIMAL | 9 | — | — | 0.01 | 31 |
| `+setup` | sequence-dependent setup（工序族换型） | OPTIMAL | 13 | +4 | **变了** | 0.01 | 27 |
| `+calendar` | 机器日历（可用窗） | OPTIMAL | 28 | +15 | **变了** | 0.02 | 77 |
| `+qualification` | 机器资质（谁能做） | OPTIMAL | 29 | +1 | **变了** | 0.01 | 43 |
| `+worker` | 次生资源能力 + 容量（谁能开、同时开几个） | OPTIMAL | 29 | +0 | 没有改变 | 0.01 | 89 |
| `+locked` | WIP / 锁定工序（已在机不可再选） | OPTIMAL | 35 | +6 | **变了** | 0.01 | 16 |

单调性核对（目标值随约束增加不下降）：**通过**。

## 怎么读这张表

* 「没有改变」是**结论**，不是「测不出来」。约束加上去之后可行域一样会缩小，
  只是这个实例的最优解恰好落在缩小后的区域里，所以目标值没动。
  约束是否真的生效，看的是验证器的诊断标签与 `MODEL_COVERAGE` 表，不是这里的数字。
* `fjsp_cpsat_full` 与 `fjsp_cpsat_qualified` 只差**换型的编码方式**（精确槽位链 vs
  区间膨胀）。两者在同一行的差值是「保守编码切掉了多少」。
* 目标值由独立评估器重算；`OPTIMAL` 只说明求解器证明了自己的模型最优，
  排程可行性另由独立验证器判定。
* `best_bound` 为空表示该行没有可用下界（见 `fjsp_core.result` 的约定：
  **没有界就写空，不写 0**）。

## 明细

| run_id | 方法 | 阶段 | 状态 | 目标值 | 独立重算 | 一致 | 验证 |
|---|---|---|---|---:|---:|---|---|
| `ablation__base__fjsp_cpsat_full` | `fjsp_cpsat_full` | `base` | OPTIMAL | 9 | 9 | 是 | OK |
| `ablation__base__fjsp_cpsat_qualified` | `fjsp_cpsat_qualified` | `base` | OPTIMAL | 9 | 9 | 是 | OK |
| `ablation__+setup__fjsp_cpsat_full` | `fjsp_cpsat_full` | `+setup` | OPTIMAL | 9 | 9 | 是 | OK |
| `ablation__+setup__fjsp_cpsat_qualified` | `fjsp_cpsat_qualified` | `+setup` | OPTIMAL | 13 | 13 | 是 | OK |
| `ablation__+calendar__fjsp_cpsat_full` | `fjsp_cpsat_full` | `+calendar` | OPTIMAL | 9 | 9 | 是 | OK |
| `ablation__+calendar__fjsp_cpsat_qualified` | `fjsp_cpsat_qualified` | `+calendar` | OPTIMAL | 28 | 28 | 是 | OK |
| `ablation__+qualification__fjsp_cpsat_full` | `fjsp_cpsat_full` | `+qualification` | OPTIMAL | 27 | 27 | 是 | OK |
| `ablation__+qualification__fjsp_cpsat_qualified` | `fjsp_cpsat_qualified` | `+qualification` | OPTIMAL | 29 | 29 | 是 | OK |
| `ablation__+worker__fjsp_cpsat_full` | `fjsp_cpsat_full` | `+worker` | OPTIMAL | 27 | 27 | 是 | OK |
| `ablation__+worker__fjsp_cpsat_qualified` | `fjsp_cpsat_qualified` | `+worker` | OPTIMAL | 29 | 29 | 是 | OK |
| `ablation__+locked__fjsp_cpsat_full` | `fjsp_cpsat_full` | `+locked` | OPTIMAL | 31 | 31 | 是 | OK |
| `ablation__+locked__fjsp_cpsat_qualified` | `fjsp_cpsat_qualified` | `+locked` | OPTIMAL | 35 | 35 | 是 | OK |
| `ind_worker__main__fjsp_cpsat_full` | `fjsp_cpsat_full` | `batch` | FEASIBLE | 101 | 101 | 是 | OK |
| `ind_worker__main__fjsp_cpsat_qualified` | `fjsp_cpsat_qualified` | `batch` | FEASIBLE | 97 | 97 | 是 | OK |
| `ind_qualified__main__fjsp_cpsat_full` | `fjsp_cpsat_full` | `batch` | FEASIBLE | 78 | 78 | 是 | OK |
| `ind_qualified__main__fjsp_cpsat_qualified` | `fjsp_cpsat_qualified` | `batch` | FEASIBLE | 75 | 75 | 是 | OK |
