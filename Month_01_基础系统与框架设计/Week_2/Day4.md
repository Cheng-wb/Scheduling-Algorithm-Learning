# Day 4：独立排程验证器

> 目标：把“求解器声称可行”变为独立检查。建议 3 小时。

## 1. 验证器信任什么

输入先由 validate_instance 校验；排程来自任何算法，可能损坏。验证器不调用 decoder、不假设工序列表按时间排序、不根据某个算法的内部状态判断可行性。

代码：[schedule_validation.py](../../../projects/01_scheduling_core/scheduling_core/schedule_validation.py)。`schedule_errors` 返回诊断列表；`validate_schedule` 在存在错误时抛异常。Objective 只计算指标，调用者应先验证完整可行性。

## 2. 独立检查清单

1. 每道输入工序恰好一次；未知 ID、重复、缺失分别报告。
2. 机器存在且属于工序的 eligible 集合。
3. 起止时刻是整数，start≥0，end−start=p。
4. 开工不早于作业释放时刻。
5. 同一作业内，相邻工序满足 end(before)≤start(after)。
6. 每台机器按 start 排序，当前 start 不早于此前区间的最大 end。

时间区间使用 `[start,end)`，所以 [0,3) 与 [3,5) 可以相接。检查重叠时维护历史最大结束时间，能识别一个长区间包住多个短区间的情况。

## 3. 构造负例

从 Day 2 第一条可行轨迹出发：把 B 改成 [2,4) 是 precedence 错误；把 C 改成 M0[3,4) 是 overlap；把 A 放到 M1 是 illegal assignment；删除 C 是 missing；再附加一次 A 是 duplicate。

项目目录运行：

```powershell
python -m pytest tests/test_month1.py -k corruption -v
```

测试还覆盖 release、duration、unknown operation 和 NaN 时间，共九种破坏。一个坏排程可以产生多个诊断，不要求只出现一条。

## 4. 自测

为什么不能只检查 Cmax 是否合理？因为删掉长任务会得到“更好”的目标值。为什么不能用 decoder 再解码一次代替检查？因为那验证的是新生成的排程，原始输出中的错误时间已经被覆盖。

验收：五类月末要求全部拒绝，合法相接时间接受，多工序作业的 precedence 不能只靠机器不重叠来代替。
