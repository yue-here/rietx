# WP-2017 group H, the cell window, counted over group A's fits

shipped starts: head fabfe9b3f, rietx 1.12.0.dev0+gfabfe9b3f505, linux, 1 kernel thread per worker.
hard starts: head fabfe9b3f, rietx 1.12.0.dev0+gfabfe9b3f505, linux, 1 kernel thread per worker.

298 fits (every arm but the window's own), 2432 solves: a phase took the window in 339, a free cell column was windowed in 0, and a windowed cell ended on an edge in 0.

'Window off' is the arm with ``_freeze_cell_windows`` declaring no phase, read against the same start's shipped arm: 'no, bit-identical' means the same evaluations and the same answer to the bit.

Not counted (fits): 1, cpd1a_x1.03 _M_HI 5.0: FitTimeout: past 1200 s.

| rows | start | fits | solves | a phase windowed | a free cell windowed | on an edge | nearest edge, fraction of window | window off: reached | window off: model esd |
|---|---|---|---|---|---|---|---|---|---|
| shipped starts | lab6 | 23 | 184 | 0 | 0 | 0 | n/a | no, bit-identical | 0 |
| shipped starts | nac | 23 | 161 | 0 | 0 | 0 | n/a | no, bit-identical | 0 |
| shipped starts | fap | 23 | 161 | 0 | 0 | 0 | n/a | no, bit-identical | 0 |
| shipped starts | cpd1a | 23 | 207 | 0 | 0 | 0 | n/a | no, bit-identical | 0 |
| hard starts | lab6_x1.01 | 23 | 184 | 161 | 0 | 0 | n/a | no, bit-identical | 0 |
| hard starts | nac_x1.03 | 23 | 206 | 100 | 0 | 0 | n/a | no, bit-identical | 0 |
| hard starts | lab6_x1.03 | 23 | 186 | 2 | 0 | 0 | n/a | no, bit-identical | 0 |
| hard starts | cpd1a_x1.01 | 23 | 207 | 23 | 0 | 0 | n/a | no, bit-identical | 0 |
| hard starts | fap_x1.01 | 23 | 161 | 0 | 0 | 0 | n/a | no, bit-identical | 0 |
| hard starts | nac_x1.01 | 23 | 161 | 0 | 0 | 0 | n/a | no, bit-identical | 0 |
| hard starts | fap_x1.03 | 23 | 161 | 0 | 0 | 0 | n/a | no, bit-identical | 0 |
| hard starts | cpd1a_x1.03 | 22 | 223 | 30 | 0 | 0 | n/a | no, bit-identical | 0 |
| hard starts | cpd1a_zircon | 23 | 230 | 23 | 0 | 0 | n/a | no, bit-identical | 0 |

## Positive arm

LaB₆ +1 % with the absent-phase hold off at every stage's start (``window_control``).

| arm | solves | a phase windowed | a free cell windowed | on an edge | nearest edge | Rwp | evaluations |
|---|---|---|---|---|---|---|---|
| no_start_hold | 14 | 13 | 6 | 0 | 0.5 | 0.861637 | 15 |
| no_start_hold_off | 14 | 0 | 0 | 0 | n/a | 0.861637 | 15 |
