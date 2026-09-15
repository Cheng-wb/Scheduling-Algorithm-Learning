# Day 3：结果 schema、排程与轨迹

> 目标：让每个数字都能追溯到输入、参数和排程。建议 2.5 小时。

## 1. 三层结果

`results.csv`：每次运行一行；`runs/<run_id>.json`：该次配置、最好候选和完整排程；`runs/<run_id>.trace.csv`：每次评价一行。不要把三种粒度混在一张表里。

| 结果字段 | 含义 |
|---|---|
| run_id / instance / input_sha256 | 运行与输入标识 |
| group / algorithm / seed | 主实验或敏感性设置、方法、随机种子 |
| objective_name / budget / temperature / cooling | 指标和关键参数 |
| status / failure_reason | 终止原因或失败诊断 |
| objective / evaluations / elapsed_seconds | 解质量和实际成本 |
| reference_type / reference / gap | 参考性质、数值和相对差异 |

metadata.json 保存 schema_version、Python、平台、Git commit、工作区 dirty 标记、源码 SHA-256 与配置 SHA-256。完整运行配置还保存 restart_interval。

## 2. 状态不是最优性声明

BASELINE 表示规则基线完成；BUDGET 表示达到评价上限；LOCAL_OPTIMUM 表示局部邻域无法严格改善；FAILED 表示该次求解异常。成功状态都不自动等于 OPTIMAL。

只有适用范围内完整枚举得到的参考才叫 optimum。其他参考是本批次所有成功主实验与敏感性运行中的最小值，明确标 best-known。

## 3. gap 约定

本项目 `gap=(value-reference)/max(1,abs(reference))`。参考为 0 时退化为绝对差，不能当作百分比。对 best-known 的 gap 不是真正的最优性差距；将来发现更好解，参考值和 gap 都可能更新。

## 4. 实验与验收

打开一条 results.csv 记录，按 run_id 找到 JSON，重新调用 validate_schedule 与 objective，检查目标一致。复现脚本在项目 README 中说明。

问：为何失败目标使用空值而不是 0？答：对最小化目标，0 会被误判为最好解，污染均值和参考值。failure_reason 是诊断证据，失败行不能从总次数中消失。
