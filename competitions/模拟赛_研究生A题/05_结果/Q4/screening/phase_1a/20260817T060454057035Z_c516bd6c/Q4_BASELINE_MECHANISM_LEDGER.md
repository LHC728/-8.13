# Q4 BASELINE MECHANISM LEDGER (Phase 1A screening)

> THIS IS A MECHANISM LEDGER. IT IS NOT AN ADDITIVE DECOMPOSITION OF T
> (parallel activities overlap; T = sum of components is FORBIDDEN).
> Summed over the 20 q4_screening baseline replicates (screening diagnostic only).

| item | A | B | C | E |
|---|---|---|---|---|
| effective_test_time | 5000 | 4000 | 5000 | 5907 |
| retest_time | 95 | 118 | 225/2 | 426 |
| failure_wasted_fragment_time | 13999912566217005/36028797018963968 | 0 | 2441204150641246295/2305843009213693952 | 0 |
| shift_boundary_wasted_fragment_time | 0 | 0 | 0 | 0 |
| terminal_cancelled_fragment_time | 5/2 | 0 | 0 | 1079722365158342637/576460752303423488 |
| calibration_time | 10 | 0 | 20/3 | 40/3 |
| turnover_occupancy_time | 1960 | - | - | - |
| off_shift_time | 7668 | - | - | - |
| queue_blocking_time | SCREENING_APPROX (see note) | - | - | - |
| active_wait_time | 0 | - | - | - |

用途：筛选候选重要因素 + 解释 sensitivity 结果（不构造 T 分解）。
H1 无 WAIT_EVENT → active_wait_time = 0。
