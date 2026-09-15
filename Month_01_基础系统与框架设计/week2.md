# Week 2 周报：解表示、邻域与独立验证

## 已交付

Candidate、追加式 decoder、swap/insert/reassign、独立 schedule validator、随机实例生成器和单工序极小枚举 oracle。

笔记：[Day1](Week_2/Day1.md) · [Day2](Week_2/Day2.md) · [Day3](Week_2/Day3.md) · [Day4](Week_2/Day4.md) · [Day5](Week_2/Day5.md) · [Day6](Week_2/Day6.md) · [Day7](Week_2/Day7.md)。

## 验证与结论

三条精确解码轨迹通过；九类损坏排程被拒绝；五个固定种子四任务两机实例，各枚举 384 个排列/指派组合，独立 oracle 与 decoder 的最小值一致。

assignments 永远对齐 instance.operations；order 是优先级，不强制前驱在前。验证器不调用 decoder，避免共用构造逻辑掩盖可行性错误。

## 局限

追加解码不填已有空隙；随机生成器默认全资格；枚举只对单工序、完成时间单调目标提供全局参考。多工序测试只证明已覆盖样例正确，不能替代完整工业约束建模。

## 复跑与练习

仓库根目录：`python projects/01_scheduling_core/examples/m1w2d6_verification.py`。个人练习：不用 decoder 构造一个包含机器重叠的 Schedule，并解释验证器为什么拒绝它。
