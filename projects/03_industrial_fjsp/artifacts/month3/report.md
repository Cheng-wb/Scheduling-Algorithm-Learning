# M3 实验汇总（脚本生成）

`gap` 相对**求解器自己的界**；`gap_to_reference` 相对**该实例的参考值**。
启发式没有 bound，两者都为空，**不能当作 0**。

## 实例参考值

| 实例 | 参考类型 | 参考值 |
|---|---|---:|
| fjsp_10x5_f3 | `proven_by_solver` | 56 |
| fjsp_6x4_f2 | `proven_by_solver` | 42 |
| flow_5x3 | `proven_by_solver` | 69 |
| flow_8x4 | `proven_by_solver` | 126 |
| ind_calendar | `proven_by_solver` | 79 |
| ind_qualified | `best-known` | 75 |
| ind_setup | `best-known` | 61 |
| ind_worker | `best-known` | 97 |
| jsp_6x4 | `proven_by_solver` | 67 |
| jsp_8x5 | `proven_by_solver` | 84 |

`optimum` 来自独立枚举，`proven_by_solver` 来自某个求解器在预算内的证明，
`best-known` 只是本批见过的最好可行解——**不是最优性证书**。

## 逐方法汇总

| 实例 | 组 | 方法 | 成功/失败 | 已证明最优 | 均值 | 平均 gap | 平均 ref gap | 平均耗时(s) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| fjsp_10x5_f3 | main | fjsp_cpsat | 1/0 | 1 | 56.000 | 0.0000 | 0.0000 | 4.132 |
| fjsp_10x5_f3 | main | fjsp_loadbalance | 1/0 | 0 | 90.000 | — | 0.6071 | 0.001 |
| fjsp_10x5_f3 | main | fjsp_random | 1/0 | 0 | 115.000 | — | 1.0536 | 0.001 |
| fjsp_10x5_f3 | main | fjsp_shortest | 1/0 | 0 | 111.000 | — | 0.9821 | 0.001 |
| fjsp_10x5_f3 | tl_30 | fjsp_cpsat | 1/0 | 1 | 56.000 | 0.0000 | 0.0000 | 4.341 |
| fjsp_10x5_f3 | tl_5 | fjsp_cpsat | 1/0 | 1 | 56.000 | 0.0000 | 0.0000 | 4.794 |
| fjsp_6x4_f2 | main | fjsp_cpsat | 1/0 | 1 | 42.000 | 0.0000 | 0.0000 | 0.038 |
| fjsp_6x4_f2 | main | fjsp_loadbalance | 1/0 | 0 | 61.000 | — | 0.4524 | 0.001 |
| fjsp_6x4_f2 | main | fjsp_random | 1/0 | 0 | 87.000 | — | 1.0714 | 0.001 |
| fjsp_6x4_f2 | main | fjsp_shortest | 1/0 | 0 | 67.000 | — | 0.5952 | 0.001 |
| fjsp_6x4_f2 | tl_30 | fjsp_cpsat | 1/0 | 1 | 42.000 | 0.0000 | 0.0000 | 0.034 |
| fjsp_6x4_f2 | tl_5 | fjsp_cpsat | 1/0 | 1 | 42.000 | 0.0000 | 0.0000 | 0.037 |
| flow_5x3 | main | flow_johnson | 1/0 | 0 | 78.000 | — | 0.1304 | 0.000 |
| flow_5x3 | main | flow_neh | 1/0 | 0 | 70.000 | — | 0.0145 | 0.001 |
| flow_5x3 | main | jsp_cpsat | 1/0 | 1 | 69.000 | 0.0000 | 0.0000 | 0.022 |
| flow_5x3 | main | jsp_priority | 1/0 | 0 | 78.000 | — | 0.1304 | 0.001 |
| flow_5x3 | tl_30 | jsp_cpsat | 1/0 | 1 | 69.000 | 0.0000 | 0.0000 | 0.014 |
| flow_5x3 | tl_5 | jsp_cpsat | 1/0 | 1 | 69.000 | 0.0000 | 0.0000 | 0.026 |
| flow_8x4 | main | flow_johnson | 1/0 | 0 | 151.000 | — | 0.1984 | 0.001 |
| flow_8x4 | main | flow_neh | 1/0 | 0 | 127.000 | — | 0.0079 | 0.006 |
| flow_8x4 | main | jsp_cpsat | 1/0 | 1 | 126.000 | 0.0000 | 0.0000 | 0.042 |
| flow_8x4 | main | jsp_priority | 1/0 | 0 | 162.000 | — | 0.2857 | 0.001 |
| flow_8x4 | tl_30 | jsp_cpsat | 1/0 | 1 | 126.000 | 0.0000 | 0.0000 | 0.043 |
| flow_8x4 | tl_5 | jsp_cpsat | 1/0 | 1 | 126.000 | 0.0000 | 0.0000 | 0.042 |
| ind_calendar | main | fjsp_cpsat_calendar | 1/0 | 1 | 79.000 | 0.0000 | 0.0000 | 0.142 |
| ind_qualified | main | fjsp_cpsat_full | 1/0 | 0 | 78.000 | 0.5641 | 0.0400 | 15.060 |
| ind_qualified | main | fjsp_cpsat_qualified | 1/0 | 0 | 75.000 | 0.5200 | 0.0000 | 15.024 |
| ind_setup | main | fjsp_cpsat_multiobj | 1/0 | 0 | 61.000 | — | 0.0000 | 14.345 |
| ind_setup | main | fjsp_cpsat_setup | 1/0 | 0 | 61.000 | — | 0.0000 | 15.029 |
| ind_worker | main | fjsp_cpsat_full | 1/0 | 0 | 97.000 | 0.5773 | 0.0000 | 15.021 |
| jsp_6x4 | main | jsp_cpsat | 1/0 | 1 | 67.000 | 0.0000 | 0.0000 | 0.010 |
| jsp_6x4 | main | jsp_priority | 1/0 | 0 | 71.000 | — | 0.0597 | 0.000 |
| jsp_6x4 | tl_30 | jsp_cpsat | 1/0 | 1 | 67.000 | 0.0000 | 0.0000 | 0.010 |
| jsp_6x4 | tl_5 | jsp_cpsat | 1/0 | 1 | 67.000 | 0.0000 | 0.0000 | 0.010 |
| jsp_8x5 | main | jsp_cpsat | 1/0 | 1 | 84.000 | 0.0000 | 0.0000 | 0.019 |
| jsp_8x5 | main | jsp_priority | 1/0 | 0 | 86.000 | — | 0.0238 | 0.001 |
| jsp_8x5 | tl_30 | jsp_cpsat | 1/0 | 1 | 84.000 | 0.0000 | 0.0000 | 0.020 |
| jsp_8x5 | tl_5 | jsp_cpsat | 1/0 | 1 | 84.000 | 0.0000 | 0.0000 | 0.019 |

同一实例跨方法汇总。时间预算相同不代表实际耗时相同；
`OPTIMAL` 只说明求解器证明了自己的**模型**最优，排程可行性另由独立验证器判定。
