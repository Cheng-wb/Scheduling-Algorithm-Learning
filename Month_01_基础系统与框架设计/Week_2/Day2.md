# Day 2：串行解码器与三类轨迹

> 目标：用统一解码把排列和指派转换成可行排程。建议 3 小时。

## 1. 状态与递推

维护每台机器的最后完成时间 machine_ready、已排工序的结束时间 ends，以及未排优先级列表。每一步选择列表里第一道前驱已经排定的工序：

`start(op)=max(machine_ready[m], end(predecessor), release(job))`

`end(op)=start(op)+p(op)`

然后更新机器时间和 ends。这里“前驱已排定”是构造顺序条件；输出中前驱实际完工时间仍通过 max 约束后继。

## 2. 三个可手推轨迹

输入：A(p=3,r=2)→B(p=2)，C(p=1,r=0)；A 只能 M0，B、C 可选 M0/M1。

| 编码 | 扫描过程与最终时间 |
|---|---|
| ABC；指派 M0,M1,M0 | A:M0[2,5)，B:M1[5,7)，C:M0[5,6) |
| BCA；指派 M0,M1,M0 | B 未就绪跳过，C:M0[0,1)，A:M0[2,5)，B:M1[5,7) |
| BCA；指派 M0,M0,M1 | C:M1[0,1)，A:M0[2,5)，B:M0[5,7) |

注意第一例 M0 的 [0,2) 空隙没有插入 C。当前实现是“追加式”，不做空隙插入；这让程序易懂，但可能损失解质量。Schedule.operations 是构造顺序，不保证按开始时间排序。

## 3. 代码与复杂度

读 [decoder.py](../../projects/01_scheduling_core/scheduling_algorithms/decoder.py) 的 `decode`。每步线性扫描候选列表并移除元素，总体约 O(n²)，另外有输入与候选检查开销。M1 优先保持可验证的实现，M5 再研究增量评估。

项目目录运行 `python -m pytest tests/test_month1.py -k three_decoder -v`，应通过三个精确时间轨迹测试。

## 4. 自测与局限

问：交换输入 jobs 的顺序是否应该影响既定 Candidate 的解码？答：合法 ID 引用、明确 order 和 assignments 下不应影响时间；但重排 instance.operations 后必须同步重建 assignments。

问：当前解码器是否覆盖所有工业调度情况？答：只处理不可抢占、作业内线性工序链、释放时间、同质加工时长和机器资格；没有换型、维护日历和工人容量。

验收：能不看代码推出三条轨迹，解释空隙没有自动被填补的原因，并验证重复解码返回相同 Schedule。
