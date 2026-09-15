# Day 1：统一 Benchmark 入口

> 目标：一条命令完成输入生成、算法运行、记录、统计和图表。建议 2.5 小时。

## 1. 配置驱动

[benchmark.py](../../projects/01_scheduling_core/scheduling_experiments/benchmark.py) 读取 JSON 配置；数据规模、目标、种子、预算和敏感性参数都不写死在算法中。默认配置：[month1.json](../../projects/01_scheduling_core/configs/month1.json)。

仓库根目录复跑：

```powershell
python projects/01_scheduling_core/examples/m1w4d1_benchmark.py --output projects/01_scheduling_core/artifacts/my_run
```

输出目录须为空或不存在，避免覆盖已有证据。实验记录放在 artifacts/month1_refactored；再次运行换新目录名即可。项目目录也支持 `python -m scheduling_experiments.benchmark --output artifacts/my_run`。

## 2. 运行顺序

读取配置→生成并保存输入→对 tiny 实例计算精确参考→按算法/种子运行→保存候选和排程→保存轨迹→补充参考值和 gap→生成统计表与 PNG。

先保存输入再求解，让同一个实例的所有算法共享完全相同的输入。运行 ID 包含实例、实验组、算法和 seed，能定位每一条结果。

## 3. 安装与环境

项目目录执行 `python -m pip install -r requirements-dev.txt`。运行库主要使用标准库；绘图依赖 matplotlib。验收环境的精确包版本另外保存在 requirements-lock.txt；不同 Python/平台的墙钟时间不能直接比较。

## 4. 自测

为什么不把结果直接 print 后复制进报告？手工复制容易遗漏失败、参数和版本。为什么禁止覆盖非空目录？同名输出被覆盖后，旧报告会失去证据。

验收：使用一个全新输出目录成功执行，得到 config.json、metadata.json、instances、runs、results.csv、summary.csv、failures.json、report.md 和三张图。
