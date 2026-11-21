# WP-2017 group L: the magnetic solve's three counts

Written by `group_l.py summary` from the raw rows of the workstation run; solves and arms in its docstring.
Commit `1f2b58ab2`, Linux x86_64, numpy 2.5.3, rietx-kernels 1.5.0, compiled tier on, one kernel thread.

`same answer`: verdict, pick, k, route, every trial's status, ΔBIC and Rwp, and the k-trial table all equal to `shipped`'s; `class trials same`: the class trials alone, every field.  `ranked k`: the list `top_k` cuts, with satellites matched.  `minima`: each trial's n_minima/n_starts.

| Solve | Arm | verdict | pick | k (route) | ranked k (matched) | k trials | minima | same answer | class trials same | can act | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `cr2wo6_4k` | shipped | solved | P 42/m n m | (0,0,0) (forbidden lattice points) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (2), (0, 0, 1/2) (0) | (0,0,0) ΔBIC 167.3 | 1/1, 1/1, 1/1, 1/1, 1/1, 1/1 | — | — |  | 2 |
| `cr2wo6_4k` | rtol_lo | solved | P 42/m n m | (0,0,0) (forbidden lattice points) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (2), (0, 0, 1/2) (0) | (0,0,0) ΔBIC 167.3 | 1/1, 1/1, 1/1, 1/1, 1/1, 1/1 | yes | yes | 0 trial(s) with ≥ 2 starts | 3 |
| `cr2wo6_4k` | rtol_hi | solved | P 42/m n m | (0,0,0) (forbidden lattice points) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (2), (0, 0, 1/2) (0) | (0,0,0) ΔBIC 167.3 | 1/1, 1/1, 1/1, 1/1, 1/1, 1/1 | yes | yes | 0 trial(s) with ≥ 2 starts | 3 |
| `cr2wo6_4k` | topk_2 | solved | P 42/m n m | (0,0,0) (forbidden lattice points) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (2) | (0,0,0) ΔBIC 167.3 | 1/1, 1/1, 1/1, 1/1, 1/1, 1/1 | yes | yes | forbidden lattice points | 2 |
| `cr2wo6_4k` | topk_4 | solved | P 42/m n m | (0,0,0) (forbidden lattice points) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (2), (0, 0, 1/2) (0), (1/2, 1/2, 0) (0) | (0,0,0) ΔBIC 167.3 | 1/1, 1/1, 1/1, 1/1, 1/1, 1/1 | yes | yes | forbidden lattice points | 3 |
| `cr2wo6_4k` | ktrials_1 | solved | P 42/m n m | (0,0,0) (forbidden lattice points) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (2), (0, 0, 1/2) (0) | (0,0,0) ΔBIC 167.3 | 1/1, 1/1, 1/1, 1/1, 1/1, 1/1 | yes | yes | 1 k trial(s), 3 ranked | 3 |
| `cr2wo6_4k` | ktrials_3 | solved | P 42/m n m | (0,0,0) (forbidden lattice points) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (2), (0, 0, 1/2) (0) | (0,0,0) ΔBIC 167.3 | 1/1, 1/1, 1/1, 1/1, 1/1, 1/1 | yes | yes | 1 k trial(s), 3 ranked | 3 |
| `cr2wo6_4k` | repeat | solved | P 42/m n m | (0,0,0) (forbidden lattice points) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (2), (0, 0, 1/2) (0) | (0,0,0) ΔBIC 167.3 | 1/1, 1/1, 1/1, 1/1, 1/1, 1/1 | yes | yes |  | 3 |
| `cr2wo6_150k` | shipped | nothing to solve | P 42/m n m | (0,1/2,1/2) (satellite ranking) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (1), (0, 0, 1/2) (0) | (0,1/2,1/2) ΔBIC — | 1/1, 1/1, 1/1, 1/1 | — | — |  | 40 |
| `cr2wo6_150k` | rtol_lo | nothing to solve | P 42/m n m | (0,1/2,1/2) (satellite ranking) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (1), (0, 0, 1/2) (0) | (0,1/2,1/2) ΔBIC — | 1/1, 1/1, 1/1, 1/1 | yes | yes | 0 trial(s) with ≥ 2 starts | 40 |
| `cr2wo6_150k` | rtol_hi | nothing to solve | P 42/m n m | (0,1/2,1/2) (satellite ranking) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (1), (0, 0, 1/2) (0) | (0,1/2,1/2) ΔBIC — | 1/1, 1/1, 1/1, 1/1 | yes | yes | 0 trial(s) with ≥ 2 starts | 39 |
| `cr2wo6_150k` | topk_2 | nothing to solve | P 42/m n m | (0,1/2,1/2) (satellite ranking) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (1) | (0,1/2,1/2) ΔBIC — | 1/1, 1/1, 1/1, 1/1 | yes | yes | 3 ranked k | 38 |
| `cr2wo6_150k` | topk_4 | nothing to solve | P 42/m n m | (0,1/2,1/2) (satellite ranking) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (1), (0, 0, 1/2) (0), (1/2, 1/2, 0) (0) | (0,1/2,1/2) ΔBIC — | 1/1, 1/1, 1/1, 1/1 | yes | yes | 3 ranked k | 39 |
| `cr2wo6_150k` | ktrials_1 | nothing to solve | P 42/m n m | (0,1/2,1/2) (satellite ranking) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (1), (0, 0, 1/2) (0) | (0,1/2,1/2) ΔBIC — | 1/1, 1/1, 1/1, 1/1 | yes | yes | 1 k trial(s), 3 ranked | 39 |
| `cr2wo6_150k` | ktrials_3 | nothing to solve | P 42/m n m | (0,1/2,1/2) (satellite ranking) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (1), (0, 0, 1/2) (0) | (0,1/2,1/2) ΔBIC — | 1/1, 1/1, 1/1, 1/1 | yes | yes | 1 k trial(s), 3 ranked | 39 |
| `cr2wo6_150k` | repeat | nothing to solve | P 42/m n m | (0,1/2,1/2) (satellite ranking) | (0, 1/2, 1/2) (2), (0, 1/2, 0) (1), (0, 0, 1/2) (0) | (0,1/2,1/2) ΔBIC — | 1/1, 1/1, 1/1, 1/1 | yes | yes |  | 39 |
| `lamno3_50k` | shipped | solved | P n m a | (0,0,0) (forbidden lattice points) | (1/2, 0, 1/2) (1), (0, 1/2, 1/2) (1), (0, 0, 1/2) (0) | (0,0,0) ΔBIC 423.7 | 1/1, 1/1, 1/1, 1/1 | — | — |  | 6 |
| `lamno3_50k` | rtol_lo | solved | P n m a | (0,0,0) (forbidden lattice points) | (1/2, 0, 1/2) (1), (0, 1/2, 1/2) (1), (0, 0, 1/2) (0) | (0,0,0) ΔBIC 423.7 | 1/1, 1/1, 1/1, 1/1 | yes | yes | 0 trial(s) with ≥ 2 starts | 5 |
| `lamno3_50k` | rtol_hi | solved | P n m a | (0,0,0) (forbidden lattice points) | (1/2, 0, 1/2) (1), (0, 1/2, 1/2) (1), (0, 0, 1/2) (0) | (0,0,0) ΔBIC 423.7 | 1/1, 1/1, 1/1, 1/1 | yes | yes | 0 trial(s) with ≥ 2 starts | 6 |
| `lamno3_50k` | topk_2 | solved | P n m a | (0,0,0) (forbidden lattice points) | (1/2, 0, 1/2) (1), (0, 1/2, 1/2) (1) | (0,0,0) ΔBIC 423.7 | 1/1, 1/1, 1/1, 1/1 | yes | yes | forbidden lattice points | 6 |
| `lamno3_50k` | topk_4 | solved | P n m a | (0,0,0) (forbidden lattice points) | (1/2, 0, 1/2) (1), (0, 1/2, 1/2) (1), (0, 0, 1/2) (0), (0, 1/2, 0) (0) | (0,0,0) ΔBIC 423.7 | 1/1, 1/1, 1/1, 1/1 | yes | yes | forbidden lattice points | 6 |
| `lamno3_50k` | ktrials_1 | solved | P n m a | (0,0,0) (forbidden lattice points) | (1/2, 0, 1/2) (1), (0, 1/2, 1/2) (1), (0, 0, 1/2) (0) | (0,0,0) ΔBIC 423.7 | 1/1, 1/1, 1/1, 1/1 | yes | yes | 1 k trial(s), 3 ranked | 6 |
| `lamno3_50k` | ktrials_3 | solved | P n m a | (0,0,0) (forbidden lattice points) | (1/2, 0, 1/2) (1), (0, 1/2, 1/2) (1), (0, 0, 1/2) (0) | (0,0,0) ΔBIC 423.7 | 1/1, 1/1, 1/1, 1/1 | yes | yes | 1 k trial(s), 3 ranked | 6 |
| `lamno3_50k` | repeat | solved | P n m a | (0,0,0) (forbidden lattice points) | (1/2, 0, 1/2) (1), (0, 1/2, 1/2) (1), (0, 0, 1/2) (0) | (0,0,0) ΔBIC 423.7 | 1/1, 1/1, 1/1, 1/1 | yes | yes |  | 6 |
| `ba2fesbse5_1p5k` | shipped | solved | P n m a | (1/2,0,1/2) (satellite ranking) | (1/2, 0, 1/2) (11), (1/2, 1/2, 0) (11), (0, 1/2, 1/2) (6) | (1/2,0,1/2) ΔBIC 143.9; (1/2,1/2,0) ΔBIC 47.9 | 1/1, 1/1, 1/1, 1/1 | — | — |  | 556 |
| `ba2fesbse5_1p5k` | rtol_lo | solved | P n m a | (1/2,0,1/2) (satellite ranking) | (1/2, 0, 1/2) (11), (1/2, 1/2, 0) (11), (0, 1/2, 1/2) (6) | (1/2,0,1/2) ΔBIC 143.9; (1/2,1/2,0) ΔBIC 47.9 | 1/1, 1/1, 1/1, 1/1 | yes | yes | 0 trial(s) with ≥ 2 starts | 561 |
| `ba2fesbse5_1p5k` | rtol_hi | solved | P n m a | (1/2,0,1/2) (satellite ranking) | (1/2, 0, 1/2) (11), (1/2, 1/2, 0) (11), (0, 1/2, 1/2) (6) | (1/2,0,1/2) ΔBIC 143.9; (1/2,1/2,0) ΔBIC 47.9 | 1/1, 1/1, 1/1, 1/1 | yes | yes | 0 trial(s) with ≥ 2 starts | 561 |
| `ba2fesbse5_1p5k` | topk_2 | solved | P n m a | (1/2,0,1/2) (satellite ranking) | (1/2, 0, 1/2) (11), (1/2, 1/2, 0) (11) | (1/2,0,1/2) ΔBIC 143.9; (1/2,1/2,0) ΔBIC 47.9 | 1/1, 1/1, 1/1, 1/1 | yes | yes | 3 ranked k | 551 |
| `ba2fesbse5_1p5k` | topk_4 | solved | P n m a | (1/2,0,1/2) (satellite ranking) | (1/2, 0, 1/2) (11), (1/2, 1/2, 0) (11), (0, 1/2, 1/2) (6), (1/2, 0, 0) (5) | (1/2,0,1/2) ΔBIC 143.9; (1/2,1/2,0) ΔBIC 47.9 | 1/1, 1/1, 1/1, 1/1 | yes | yes | 3 ranked k | 565 |
| `ba2fesbse5_1p5k` | ktrials_1 | solved | P n m a | (1/2,0,1/2) (satellite ranking) | (1/2, 0, 1/2) (11), (1/2, 1/2, 0) (11), (0, 1/2, 1/2) (6) | (1/2,0,1/2) ΔBIC 143.9 | 1/1, 1/1, 1/1, 1/1 | **no** | yes | 2 k trial(s), 3 ranked | 114 |
| `ba2fesbse5_1p5k` | ktrials_3 | solved | P n m a | (1/2,0,1/2) (satellite ranking) | (1/2, 0, 1/2) (11), (1/2, 1/2, 0) (11), (0, 1/2, 1/2) (6) | (1/2,0,1/2) ΔBIC 143.9; (1/2,1/2,0) ΔBIC 47.9 | 1/1, 1/1, 1/1, 1/1 | yes | yes | 2 k trial(s), 3 ranked | 555 |
| `ba2fesbse5_1p5k` | repeat | solved | P n m a | (1/2,0,1/2) (satellite ranking) | (1/2, 0, 1/2) (11), (1/2, 1/2, 0) (11), (0, 1/2, 1/2) (6) | (1/2,0,1/2) ΔBIC 143.9; (1/2,1/2,0) ΔBIC 47.9 | 1/1, 1/1, 1/1, 1/1 | yes | yes |  | 557 |

Shipped trials (class, group, status, ΔBIC, Rwp):

- `cr2wo6_4k`: 4 58.395 refined 167.3 0.1144; 0 136.502 refined 24.5 0.1848; 5 58.398 refined -3.4 0.1991; 3 136.503 refined -4.7 0.2033; 2 136.501 refined -4.8 0.2034; 1 136.499 refined -5.0 0.2035
- `cr2wo6_150k`: 2 12.64 refined -12.6 0.0986; 0 12.64 refined -18.5 0.0992; 3 2.7 refined -36.2 0.0979; 1 2.7 refined -37.4 0.0980
- `lamno3_50k`: 0 62.448 refined 423.7 0.0638; 3 62.441 refined 259.8 0.0852; 1 62.447 refined 47.4 0.1234; 2 62.446 refined -17.0 0.1381
- `ba2fesbse5_1p5k`: 1 11.55 refined 143.9 0.0480; 0 14.82 refined 75.8 0.0615; 3 14.82 refined 73.7 0.0620; 2 11.55 refined 67.7 0.0663
