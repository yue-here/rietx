## IUCr CPD sample-1 chain 1a-1h (real, lab Cu Kα)

Protocol: tests/test_acceptance_sequential.py chained_all: SequentialRefinement(structure, qarr_instrument()) with seed_scales on 1a, carry=('*',), plan=qpa_plan(), refit='single', dispersion declined, compiled tier default.  Arms: on, status, off, status_maxiter, status_runaway, on_nobound, off_nobound; reference `ref_seeded`.

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev | status_maxiter: rungs [kept] | status_maxiter: Rwp warm→kept | status_maxiter: fence | status_maxiter: nfev | status_runaway: rungs [kept] | status_runaway: Rwp warm→kept | status_runaway: fence | status_runaway: nfev | on_nobound: rungs [kept] | on_nobound: Rwp warm→kept | on_nobound: fence | on_nobound: nfev | off_nobound: rungs [kept] | off_nobound: Rwp warm→kept | off_nobound: fence | off_nobound: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | cpd-1a | c [c] | 0.1631 | — | 175 | c [c] | 0.1631 | — | 175 | c [c] | 0.1631 | — | 175 | c [c] | 0.1631 | — | 175 | c [c] | 0.1631 | — | 175 | c [c] | 0.1631 | — | 175 | c [c] | 0.1631 | — | 175 |
| 1 | cpd-1b | w [w] | 0.1398 | 0.2038 | 301 | w [w] | 0.1398 | inf | 301 | w [w] | 0.1398 | 0.2038 | 301 | w [w] | 0.1398 | inf | 301 | w→ws [ws] | 0.1398→0.1378 | inf | 395 | w [w] | 0.1398 | 0.2038 | 301 | w [w] | 0.1398 | 0.2038 | 301 |
| 2 | cpd-1c | w [w] | 0.1095 | 0.1893 | 48 | w [w] | 0.1095 | inf | 48 | w [w] | 0.1095 | 0.1893 | 48 | w [w] | 0.1095 | inf | 48 | w [w] | 0.1057 | inf | 68 | w [w] | 0.1095 | 0.1893 | 48 | w [w] | 0.1095 | 0.1893 | 48 |
| 3 | cpd-1d | w [w] | 0.1278 | 0.1748 | 28 | w [w] | 0.1278 | inf | 28 | w [w] | 0.1278 | 0.1748 | 28 | w [w] | 0.1278 | inf | 28 | w [w] | 0.1247 | inf | 34 | w [w] | 0.1278 | 0.1748 | 28 | w [w] | 0.1278 | 0.1748 | 28 |
| 4 | cpd-1e | w [w] | 0.1267 | 0.1673 | 23 | w [w] | 0.1267 | inf | 23 | w [w] | 0.1267 | 0.1673 | 23 | w [w] | 0.1267 | inf | 23 | w [w] | 0.1244 | inf | 29 | w [w] | 0.1267 | 0.1673 | 23 | w [w] | 0.1267 | 0.1673 | 23 |
| 5 | cpd-1f | w [w] | 0.1132 | 0.1598 | 25 | w [w] | 0.1132 | inf | 25 | w [w] | 0.1132 | 0.1598 | 25 | w [w] | 0.1132 | inf | 25 | w [w] | 0.1102 | inf | 29 | w [w] | 0.1132 | 0.1598 | 25 | w [w] | 0.1132 | 0.1598 | 25 |
| 6 | cpd-1g | w [w] | 0.1213 | 0.1591 | 20 | w [w] | 0.1213 | inf | 20 | w [w] | 0.1213 | 0.1591 | 20 | w [w] | 0.1213 | inf | 20 | w [w] | 0.1182 | inf | 25 | w [w] | 0.1213 | 0.1591 | 20 | w [w] | 0.1213 | 0.1591 | 20 |
| 7 | cpd-1h | w [w] | 0.1238 | 0.1584 | 24 | w [w] | 0.1238 | inf | 24 | w [w] | 0.1238 | 0.1584 | 24 | w [w] | 0.1238 | inf | 24 | w [w] | 0.1211 | inf | 30 | w [w] | 0.1238 | 0.1584 | 24 | w [w] | 0.1238 | 0.1584 | 24 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound |
|---|---|---|---|---|---|---|---|
| 0 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 1 | CELL_RUNAWAY, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CELL_RUNAWAY, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CELL_RUNAWAY, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CELL_RUNAWAY, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE, SPACE_GROUP_SETTING_ASSUMED | CELL_RUNAWAY, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CELL_RUNAWAY, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 2 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 3 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 4 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 5 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 6 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 7 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, the arm's pair, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | status_maxiter vs on: worst |Δ|/esd (path) | status_runaway vs on: worst |Δ|/esd (path) | on_nobound vs on: worst |Δ|/esd (path) | off_nobound vs on: worst |Δ|/esd (path) | status_maxiter vs status | status_runaway vs status | off_nobound vs off | on vs ref_seeded | status vs ref_seeded | off vs ref_seeded | status_maxiter vs ref_seeded | status_runaway vs ref_seeded | on_nobound vs ref_seeded | off_nobound vs ref_seeded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1 | 0 | 0 | 0 | 8.97 (phases.0.lor_strain) | 0 | 0 | 0 | 8.97 (phases.0.lor_strain) | 0 | 4.07 (instrument.profile.v) | 4.07 (instrument.profile.v) | 4.07 (instrument.profile.v) | 4.07 (instrument.profile.v) | 9.45 (phases.0.lor_strain) | 4.07 (instrument.profile.v) | 4.07 (instrument.profile.v) |
| 2 | 0 | 0 | 0 | 13.3 (phases.1.lor_strain) | 0 | 0 | 0 | 13.3 (phases.1.lor_strain) | 0 | 5.62 (instrument.profile.v) | 5.62 (instrument.profile.v) | 5.62 (instrument.profile.v) | 5.62 (instrument.profile.v) | 14.3 (phases.1.lor_strain) | 5.62 (instrument.profile.v) | 5.62 (instrument.profile.v) |
| 3 | 0 | 0 | 0 | 9.42 (phases.2.lor_strain) | 0 | 0 | 0 | 9.42 (phases.2.lor_strain) | 0 | 2.87 (instrument.profile.v) | 2.87 (instrument.profile.v) | 2.87 (instrument.profile.v) | 2.87 (instrument.profile.v) | 9.29 (phases.2.lor_strain) | 2.87 (instrument.profile.v) | 2.87 (instrument.profile.v) |
| 4 | 0 | 0 | 0 | 6.81 (phases.2.lor_strain) | 0 | 0 | 0 | 6.81 (phases.2.lor_strain) | 0 | 3.88 (instrument.profile.v) | 3.88 (instrument.profile.v) | 3.88 (instrument.profile.v) | 3.88 (instrument.profile.v) | 7.45 (phases.0.lor_strain) | 3.88 (instrument.profile.v) | 3.88 (instrument.profile.v) |
| 5 | 0 | 0 | 0 | 10.9 (phases.1.lor_strain) | 0 | 0 | 0 | 10.9 (phases.1.lor_strain) | 0 | 4.78 (instrument.profile.v) | 4.78 (instrument.profile.v) | 4.78 (instrument.profile.v) | 4.78 (instrument.profile.v) | 11.9 (phases.1.lor_strain) | 4.78 (instrument.profile.v) | 4.78 (instrument.profile.v) |
| 6 | 0 | 0 | 0 | 8.36 (phases.2.lor_strain) | 0 | 0 | 0 | 8.36 (phases.2.lor_strain) | 0 | 5.59 (instrument.profile.v) | 5.59 (instrument.profile.v) | 5.59 (instrument.profile.v) | 5.59 (instrument.profile.v) | 9.06 (phases.1.lor_strain) | 5.59 (instrument.profile.v) | 5.59 (instrument.profile.v) |
| 7 | 0 | 0 | 0 | 7 (phases.2.lor_strain) | 0 | 0 | 0 | 7 (phases.2.lor_strain) | 0 | 3.6 (instrument.profile.v) | 3.6 (instrument.profile.v) | 3.6 (instrument.profile.v) | 3.6 (instrument.profile.v) | 7.09 (phases.2.lor_strain) | 3.6 (instrument.profile.v) | 3.6 (instrument.profile.v) |

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref_seeded` the reference.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound | ref_seeded |
|---|---|---|---|---|---|---|---|---|---|
| 0 | `phases.0.cell.a` | 4.7585(32) | 4.7585(32) | 4.7585(32) | 4.7585(32) | 4.7585(32) | 4.7585(32) | 4.7585(32) | 4.7585(32) |
| 0 | `phases.0.cell.c` | 12.990(13) | 12.990(13) | 12.990(13) | 12.990(13) | 12.990(13) | 12.990(13) | 12.990(13) | 12.990(13) |
| 0 | `phases.1.cell.a` | 3.24861(64) | 3.24861(64) | 3.24861(64) | 3.24861(64) | 3.24861(64) | 3.24861(64) | 3.24861(64) | 3.24861(64) |
| 0 | `phases.2.cell.a` | 5.46281(98) | 5.46281(98) | 5.46281(98) | 5.46281(98) | 5.46281(98) | 5.46281(98) | 5.46281(98) | 5.46281(98) |
| 0 | `instrument.zero_shift` | -0.049(67) | -0.049(67) | -0.049(67) | -0.049(67) | -0.049(67) | -0.049(67) | -0.049(67) | -0.049(67) |
| 0 | `instrument.geometry.sample_displacement` | -0.086(97) | -0.086(97) | -0.086(97) | -0.086(97) | -0.086(97) | -0.086(97) | -0.086(97) | -0.086(97) |
| 1 | `phases.0.cell.a` | 4.75801(41) | 4.75801(41) | 4.75801(41) | 4.75801(41) | 4.75804(39) | 4.75801(41) | 4.75801(41) | 4.75809(38) |
| 1 | `phases.0.cell.c` | 12.9893(11) | 12.9893(11) | 12.9893(11) | 12.9893(11) | 12.9894(11) | 12.9893(11) | 12.9893(11) | 12.9895(10) |
| 1 | `phases.1.cell.a` | 3.24897(56) | 3.24897(56) | 3.24897(56) | 3.24897(56) | 3.24896(50) | 3.24897(56) | 3.24897(56) | 3.24906(54) |
| 1 | `phases.2.cell.a` | 5.46277(55) | 5.46277(55) | 5.46277(55) | 5.46277(55) | 5.46280(52) | 5.46277(55) | 5.46277(55) | 5.46287(52) |
| 1 | `instrument.zero_shift` | -0.048(37) | -0.048(37) | -0.048(37) | -0.048(37) | -0.045(35) | -0.048(37) | -0.048(37) | -0.040(35) |
| 1 | `instrument.geometry.sample_displacement` | 0.013(58) | 0.013(58) | 0.013(58) | 0.013(58) | 0.019(55) | 0.013(58) | 0.013(58) | 0.026(54) |
| 2 | `phases.0.cell.a` | 4.75773(93) | 4.75773(93) | 4.75773(93) | 4.75773(93) | 4.75760(88) | 4.75773(93) | 4.75773(93) | 4.75753(88) |
| 2 | `phases.0.cell.c` | 12.9888(39) | 12.9888(39) | 12.9888(39) | 12.9888(39) | 12.9884(37) | 12.9888(39) | 12.9888(39) | 12.9880(38) |
| 2 | `phases.1.cell.a` | 3.24902(28) | 3.24902(28) | 3.24902(28) | 3.24902(28) | 3.24892(23) | 3.24902(28) | 3.24902(28) | 3.24886(23) |
| 2 | `phases.2.cell.a` | 5.46241(96) | 5.46241(96) | 5.46241(96) | 5.46241(96) | 5.46224(87) | 5.46241(96) | 5.46241(96) | 5.46211(89) |
| 2 | `instrument.zero_shift` | -0.052(35) | -0.052(35) | -0.052(35) | -0.052(35) | -0.073(29) | -0.052(35) | -0.052(35) | -0.088(29) |
| 2 | `instrument.geometry.sample_displacement` | -0.076(52) | -0.076(52) | -0.076(52) | -0.076(52) | -0.114(45) | -0.076(52) | -0.076(52) | -0.140(44) |
| 3 | `phases.0.cell.a` | 4.75831(56) | 4.75831(56) | 4.75831(56) | 4.75831(56) | 4.75824(47) | 4.75831(56) | 4.75831(56) | 4.75828(51) |
| 3 | `phases.0.cell.c` | 12.9901(18) | 12.9901(18) | 12.9901(18) | 12.9901(18) | 12.9902(15) | 12.9901(18) | 12.9901(18) | 12.9901(17) |
| 3 | `phases.1.cell.a` | 3.24921(35) | 3.24921(35) | 3.24921(35) | 3.24921(35) | 3.24917(29) | 3.24921(35) | 3.24921(35) | 3.24919(32) |
| 3 | `phases.2.cell.a` | 5.46314(59) | 5.46314(59) | 5.46314(59) | 5.46314(59) | 5.46308(49) | 5.46314(59) | 5.46314(59) | 5.46312(54) |
| 3 | `instrument.zero_shift` | -0.029(41) | -0.029(41) | -0.029(41) | -0.029(41) | -0.044(34) | -0.029(41) | -0.029(41) | -0.039(37) |
| 3 | `instrument.geometry.sample_displacement` | -0.068(59) | -0.068(59) | -0.068(59) | -0.068(59) | -0.097(50) | -0.068(59) | -0.068(59) | -0.088(55) |
| 4 | `phases.0.cell.a` | 4.75827(42) | 4.75827(42) | 4.75827(42) | 4.75827(42) | 4.75821(37) | 4.75827(42) | 4.75827(42) | 4.75823(37) |
| 4 | `phases.0.cell.c` | 12.9897(12) | 12.9897(12) | 12.9897(12) | 12.9897(12) | 12.9896(10) | 12.9897(12) | 12.9897(12) | 12.9896(11) |
| 4 | `phases.1.cell.a` | 3.24920(30) | 3.24920(30) | 3.24920(30) | 3.24920(30) | 3.24916(26) | 3.24920(30) | 3.24920(30) | 3.24917(27) |
| 4 | `phases.2.cell.a` | 5.46313(50) | 5.46313(50) | 5.46313(50) | 5.46313(50) | 5.46306(44) | 5.46313(50) | 5.46313(50) | 5.46309(44) |
| 4 | `instrument.zero_shift` | -0.031(35) | -0.031(35) | -0.031(35) | -0.031(35) | -0.041(32) | -0.031(35) | -0.031(35) | -0.042(32) |
| 4 | `instrument.geometry.sample_displacement` | -0.036(53) | -0.036(53) | -0.036(53) | -0.036(53) | -0.056(47) | -0.036(53) | -0.036(53) | -0.058(48) |
| 5 | `phases.0.cell.a` | 4.75821(42) | 4.75821(42) | 4.75821(42) | 4.75821(42) | 4.75811(35) | 4.75821(42) | 4.75821(42) | 4.75808(36) |
| 5 | `phases.0.cell.c` | 12.9896(13) | 12.9896(13) | 12.9896(13) | 12.9896(13) | 12.9894(11) | 12.9896(13) | 12.9896(13) | 12.9893(11) |
| 5 | `phases.1.cell.a` | 3.24913(28) | 3.24913(28) | 3.24913(28) | 3.24913(28) | 3.24906(23) | 3.24913(28) | 3.24913(28) | 3.24905(24) |
| 5 | `phases.2.cell.a` | 5.46293(49) | 5.46293(49) | 5.46293(49) | 5.46293(49) | 5.46282(40) | 5.46293(49) | 5.46293(49) | 5.46279(41) |
| 5 | `instrument.zero_shift` | -0.033(34) | -0.033(34) | -0.033(34) | -0.033(34) | -0.050(28) | -0.033(34) | -0.033(34) | -0.054(29) |
| 5 | `instrument.geometry.sample_displacement` | -0.068(50) | -0.068(50) | -0.068(50) | -0.068(50) | -0.098(42) | -0.068(50) | -0.068(50) | -0.107(43) |
| 6 | `phases.0.cell.a` | 4.75816(40) | 4.75816(40) | 4.75816(40) | 4.75816(40) | 4.75810(33) | 4.75816(40) | 4.75816(40) | 4.75809(34) |
| 6 | `phases.0.cell.c` | 12.9894(12) | 12.9894(12) | 12.9894(12) | 12.9894(12) | 12.9893(10) | 12.9894(12) | 12.9894(12) | 12.9892(10) |
| 6 | `phases.1.cell.a` | 3.24907(27) | 3.24907(27) | 3.24907(27) | 3.24907(27) | 3.24902(23) | 3.24907(27) | 3.24907(27) | 3.24902(23) |
| 6 | `phases.2.cell.a` | 5.46282(46) | 5.46282(46) | 5.46282(46) | 5.46282(46) | 5.46274(39) | 5.46282(46) | 5.46282(46) | 5.46274(40) |
| 6 | `instrument.zero_shift` | -0.033(32) | -0.033(32) | -0.033(32) | -0.033(32) | -0.046(28) | -0.033(32) | -0.033(32) | -0.050(28) |
| 6 | `instrument.geometry.sample_displacement` | -0.052(48) | -0.052(48) | -0.052(48) | -0.052(48) | -0.075(41) | -0.052(48) | -0.052(48) | -0.082(42) |
| 7 | `phases.0.cell.a` | 4.75831(50) | 4.75831(50) | 4.75831(50) | 4.75831(50) | 4.75820(43) | 4.75831(50) | 4.75831(50) | 4.75822(43) |
| 7 | `phases.0.cell.c` | 12.9898(14) | 12.9898(14) | 12.9898(14) | 12.9898(14) | 12.9895(13) | 12.9898(14) | 12.9898(14) | 12.9896(13) |
| 7 | `phases.1.cell.a` | 3.24918(34) | 3.24918(34) | 3.24918(34) | 3.24918(34) | 3.24910(29) | 3.24918(34) | 3.24918(34) | 3.24911(30) |
| 7 | `phases.2.cell.a` | 5.46319(58) | 5.46319(58) | 5.46319(58) | 5.46319(58) | 5.46305(50) | 5.46319(58) | 5.46319(58) | 5.46308(51) |
| 7 | `instrument.zero_shift` | -0.032(40) | -0.032(40) | -0.032(40) | -0.032(40) | -0.052(35) | -0.032(40) | -0.032(40) | -0.050(36) |
| 7 | `instrument.geometry.sample_displacement` | -0.099(60) | -0.099(60) | -0.099(60) | -0.099(60) | -0.134(52) | -0.099(60) | -0.099(60) | -0.133(53) |

### Weight fractions, per pattern (wt %)

W(σ(W)) per arm; weighed = the composition as weighed, the QPA truth.

| k | phase | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound | ref_seeded | weighed |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | corundum | 1.72(0.64) | 1.72(0.64) | 1.72(0.64) | 1.72(0.64) | 1.72(0.64) | 1.72(0.64) | 1.72(0.64) | 1.72(0.64) | 1.15 |
| 0 | zincite | 3.35(0.21) | 3.35(0.21) | 3.35(0.21) | 3.35(0.21) | 3.35(0.21) | 3.35(0.21) | 3.35(0.21) | 3.35(0.21) | 4.04 |
| 0 | fluorite | 94.93(0.65) | 94.93(0.65) | 94.93(0.65) | 94.93(0.65) | 94.93(0.65) | 94.93(0.65) | 94.93(0.65) | 94.93(0.65) | 94.81 |
| 1 | corundum | 94.32(0.23) | 94.32(0.23) | 94.32(0.23) | 94.32(0.23) | 94.24(0.23) | 94.32(0.23) | 94.32(0.23) | 94.29(0.23) | 94.31 |
| 1 | zincite | 1.28(0.12) | 1.28(0.12) | 1.28(0.12) | 1.28(0.12) | 1.34(0.12) | 1.28(0.12) | 1.28(0.12) | 1.28(0.12) | 1.36 |
| 1 | fluorite | 4.40(0.19) | 4.40(0.19) | 4.40(0.19) | 4.40(0.19) | 4.42(0.19) | 4.40(0.19) | 4.40(0.19) | 4.43(0.19) | 4.33 |
| 2 | corundum | 6.37(0.66) | 6.37(0.66) | 6.37(0.66) | 6.37(0.66) | 6.26(0.61) | 6.37(0.66) | 6.37(0.66) | 6.30(0.62) | 5.04 |
| 2 | zincite | 91.88(0.70) | 91.88(0.70) | 91.88(0.70) | 91.88(0.70) | 91.93(0.65) | 91.88(0.70) | 91.88(0.70) | 91.92(0.66) | 93.59 |
| 2 | fluorite | 1.76(0.23) | 1.76(0.23) | 1.76(0.23) | 1.76(0.23) | 1.80(0.22) | 1.76(0.23) | 1.76(0.23) | 1.78(0.22) | 1.36 |
| 3 | corundum | 15.28(0.53) | 15.28(0.53) | 15.28(0.53) | 15.28(0.53) | 15.42(0.50) | 15.28(0.53) | 15.28(0.53) | 15.34(0.52) | 13.53 |
| 3 | zincite | 28.85(0.35) | 28.85(0.35) | 28.85(0.35) | 28.85(0.35) | 28.97(0.33) | 28.85(0.35) | 28.85(0.35) | 28.85(0.35) | 32.89 |
| 3 | fluorite | 55.87(0.47) | 55.87(0.47) | 55.87(0.47) | 55.87(0.47) | 55.62(0.45) | 55.87(0.47) | 55.87(0.47) | 55.80(0.46) | 53.58 |
| 4 | corundum | 57.32(0.43) | 57.32(0.43) | 57.32(0.43) | 57.32(0.43) | 57.35(0.41) | 57.32(0.43) | 57.32(0.43) | 57.34(0.42) | 55.12 |
| 4 | zincite | 12.79(0.22) | 12.79(0.22) | 12.79(0.22) | 12.79(0.22) | 12.88(0.21) | 12.79(0.22) | 12.79(0.22) | 12.82(0.21) | 15.25 |
| 4 | fluorite | 29.89(0.37) | 29.89(0.37) | 29.89(0.37) | 29.89(0.37) | 29.77(0.36) | 29.89(0.37) | 29.89(0.37) | 29.84(0.36) | 29.62 |
| 5 | corundum | 30.14(0.53) | 30.14(0.53) | 30.14(0.53) | 30.14(0.53) | 30.22(0.50) | 30.14(0.53) | 30.14(0.53) | 30.20(0.50) | 27.06 |
| 5 | zincite | 50.17(0.47) | 50.17(0.47) | 50.17(0.47) | 50.17(0.47) | 50.11(0.43) | 50.17(0.47) | 50.17(0.47) | 50.12(0.44) | 55.22 |
| 5 | fluorite | 19.69(0.34) | 19.69(0.34) | 19.69(0.34) | 19.69(0.34) | 19.66(0.32) | 19.69(0.34) | 19.69(0.34) | 19.68(0.32) | 17.72 |
| 6 | corundum | 33.66(0.45) | 33.66(0.45) | 33.66(0.45) | 33.66(0.45) | 33.74(0.43) | 33.66(0.45) | 33.66(0.45) | 33.73(0.44) | 31.37 |
| 6 | zincite | 30.24(0.31) | 30.24(0.31) | 30.24(0.31) | 30.24(0.31) | 30.30(0.29) | 30.24(0.31) | 30.24(0.31) | 30.22(0.30) | 34.21 |
| 6 | fluorite | 36.10(0.37) | 36.10(0.37) | 36.10(0.37) | 36.10(0.37) | 35.96(0.34) | 36.10(0.37) | 36.10(0.37) | 36.05(0.35) | 34.42 |
| 7 | corundum | 37.24(0.55) | 37.24(0.55) | 37.24(0.55) | 37.24(0.55) | 37.28(0.52) | 37.24(0.55) | 37.24(0.55) | 37.31(0.53) | 35.12 |
| 7 | zincite | 26.35(0.35) | 26.35(0.35) | 26.35(0.35) | 26.35(0.35) | 26.44(0.34) | 26.35(0.35) | 26.35(0.35) | 26.34(0.34) | 30.19 |
| 7 | fluorite | 36.41(0.45) | 36.41(0.45) | 36.41(0.45) | 36.41(0.45) | 36.28(0.43) | 36.41(0.45) | 36.41(0.45) | 36.35(0.43) | 34.69 |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, the arm's pair, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`; "pair" is the arm differing from this one by one switch (`PAIRED`).  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | pair: bit-identical, differ | differ from ref_seeded | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 8 | 0 | 0 | 0 | 0 | 8 | — | — | 7 (1, 2, 3, 4, 5, 6, 7) | 644 | 644 | 644 / 615 | 2.6-16.5 | 41 |
| status | 8 | 0 | 0 | 0 | 0 | 8 | 0 | — | 7 (1, 2, 3, 4, 5, 6, 7) | 644 | 644 | 644 / 615 | 2.9-16.5 | 42 |
| off | 8 | 0 | 0 | 0 | 0 | 8 | 0 | — | 7 (1, 2, 3, 4, 5, 6, 7) | 644 | 644 | 644 / 615 | 2.9-18.4 | 45 |
| status_maxiter | 8 | 0 | 0 | 0 | 0 | 8 | 0 | `status`: 8, 0 | 7 (1, 2, 3, 4, 5, 6, 7) | 644 | 644 | 644 / 615 | 2.7-17.6 | 43 |
| status_runaway | 8 | 1 | 0 | 0 | 0 | 1 | 7 (1, 2, 3, 4, 5, 6, 7) | `status`: 1, 7 (1, 2, 3, 4, 5, 6, 7) | 7 (1, 2, 3, 4, 5, 6, 7) | 785 | 484 | 785 / 751 | 3.4-26.1 | 59 |
| on_nobound | 8 | 0 | 0 | 0 | 0 | 8 | 0 | — | 7 (1, 2, 3, 4, 5, 6, 7) | 644 | 644 | 644 / 615 | 3.1-21.6 | 52 |
| off_nobound | 8 | 0 | 0 | 0 | 0 | 8 | 0 | `off`: 8, 0 | 7 (1, 2, 3, 4, 5, 6, 7) | 644 | 644 | 644 / 615 | 3.0-22.0 | 53 |
| ref_seeded | 8 | 0 | 0 | 0 | 0 | 1 | 7 (1, 2, 3, 4, 5, 6, 7) | — | — | 1255 | 1255 | 1255 / 1221 | 4.9-6.4 | 44 |

### Series-level codes

| code | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound |
|---|---|---|---|---|---|---|---|
| `SEQUENTIAL_PERSISTENT_FINDING` | 26 | 26 | 26 | 26 | 26 | 26 | 26 |

Failures (`SeriesFailure`): on 0, status 0, off 0, status_maxiter 0, status_runaway 0, on_nobound 0, off_nobound 0.

## IUCr CPD sample-1 chain 1a-1h (real, lab Cu Kα), closing stage off (declared variant)

Protocol: tests/test_acceptance_sequential.py chained_all: SequentialRefinement(structure, qarr_instrument()) with seed_scales on 1a, carry=('*',), plan=qpa_plan(), refit='single', dispersion declined, compiled tier default; the one change: plan.closing_window_tol = None.  Arms: on, status, off, status_maxiter, status_runaway, on_nobound, off_nobound; reference `ref_seeded`.

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev | status_maxiter: rungs [kept] | status_maxiter: Rwp warm→kept | status_maxiter: fence | status_maxiter: nfev | status_runaway: rungs [kept] | status_runaway: Rwp warm→kept | status_runaway: fence | status_runaway: nfev | on_nobound: rungs [kept] | on_nobound: Rwp warm→kept | on_nobound: fence | on_nobound: nfev | off_nobound: rungs [kept] | off_nobound: Rwp warm→kept | off_nobound: fence | off_nobound: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | cpd-1a | c [c] | 0.1676 | — | 162 | c [c] | 0.1676 | — | 162 | c [c] | 0.1676 | — | 162 | c [c] | 0.1676 | — | 162 | c [c] | 0.1676 | — | 162 | c [c] | 0.1676 | — | 162 | c [c] | 0.1676 | — | 162 |
| 1 | cpd-1b | w [w] | 0.1633 | 0.2095 | 410 | w [w] | 0.1633 | inf | 410 | w [w] | 0.1633 | 0.2095 | 410 | w [w] | 0.1633 | inf | 410 | w→ws [ws] | 0.1633→0.1393 | inf | 481 | w [w] | 0.1633 | 0.2095 | 410 | w [w] | 0.1633 | 0.2095 | 410 |
| 2 | cpd-1c | w [w] | 0.1135 | 0.2068 | 52 | w [w] | 0.1135 | inf | 52 | w [w] | 0.1135 | 0.2068 | 52 | w [w] | 0.1135 | inf | 52 | w [w] | 10.8332 | inf | 314 | w [w] | 0.1135 | 0.2068 | 52 | w [w] | 0.1135 | 0.2068 | 52 |
| 3 | cpd-1d | w [w] | 0.1303 | 0.2042 | 21 | w [w] | 0.1303 | inf | 21 | w [w] | 0.1303 | 0.2042 | 21 | w [w] | 0.1303 | inf | 21 | w [w] | 0.7715 (max_iter) | inf | 400 | w [w] | 0.1303 | 0.2042 | 21 | w [w] | 0.1303 | 0.2042 | 21 |
| 4 | cpd-1e | w [w] | 0.1287 | 0.1835 | 16 | w [w] | 0.1287 | inf | 16 | w [w] | 0.1287 | 0.1835 | 16 | w [w] | 0.1287 | inf | 16 | w [w] | 0.7585 (max_iter) | inf | 400 | w [w] | 0.1287 | 0.1835 | 16 | w [w] | 0.1287 | 0.1835 | 16 |
| 5 | cpd-1f | w [w] | 0.1161 | 0.1629 | 18 | w [w] | 0.1161 | inf | 18 | w [w] | 0.1161 | 0.1629 | 18 | w [w] | 0.1161 | inf | 18 | w [w] | 0.7673 (max_iter) | inf | 400 | w [w] | 0.1161 | 0.1629 | 18 | w [w] | 0.1161 | 0.1629 | 18 |
| 6 | cpd-1g | w [w] | 0.1236 | 0.1619 | 13 | w [w] | 0.1236 | inf | 13 | w [w] | 0.1236 | 0.1619 | 13 | w [w] | 0.1236 | inf | 13 | w [w] | 0.7597 (max_iter) | inf | 400 | w [w] | 0.1236 | 0.1619 | 13 | w [w] | 0.1236 | 0.1619 | 13 |
| 7 | cpd-1h | w [w] | 0.1262 | 0.1609 | 16 | w [w] | 0.1262 | inf | 16 | w [w] | 0.1262 | 0.1609 | 16 | w [w] | 0.1262 | inf | 16 | w [w] | 0.7608 (max_iter) | inf | 400 | w [w] | 0.1262 | 0.1609 | 16 | w [w] | 0.1262 | 0.1609 | 16 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound |
|---|---|---|---|---|---|---|---|
| 0 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 1 | CELL_RUNAWAY, CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLOOR_HIT, HIGH_CORRELATION, P_UNC, SPACE_GROUP_SETTING_ASSUMED | CELL_RUNAWAY, CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLOOR_HIT, HIGH_CORRELATION, P_UNC, SPACE_GROUP_SETTING_ASSUMED | CELL_RUNAWAY, CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLOOR_HIT, HIGH_CORRELATION, P_UNC, SPACE_GROUP_SETTING_ASSUMED | CELL_RUNAWAY, CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLOOR_HIT, HIGH_CORRELATION, P_UNC, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CELL_RUNAWAY, CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLOOR_HIT, HIGH_CORRELATION, P_UNC, SPACE_GROUP_SETTING_ASSUMED | CELL_RUNAWAY, CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLOOR_HIT, HIGH_CORRELATION, P_UNC, SPACE_GROUP_SETTING_ASSUMED |
| 2 | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, FROZEN_COMPILE_STALE, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, FROZEN_COMPILE_STALE, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, FROZEN_COMPILE_STALE, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, FROZEN_COMPILE_STALE, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | BISO_UNUSUALLY_LARGE, CONSTRAINT_ACTIVE, COVARIANCE_DIRECTION_DISCARDED, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, FROZEN_COMPILE_STALE, HIGH_CORRELATION, MODEL_FAR_FROM_DATA, RESOLUTION_NOT_POSITIVE, RESOLUTION_UNC, SPACE_GROUP_SETTING_ASSUMED | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, FROZEN_COMPILE_STALE, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, FROZEN_COMPILE_STALE, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 3 | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | BACKGROUND_ABSORPTION, CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, PEAK_WIDTH_LAW_MISMATCH, RESOLUTION_NOT_POSITIVE, RESOLUTION_UNC, SPACE_GROUP_SETTING_ASSUMED, STAGE_MAX_ITER, STRAIN_UNUSUALLY_LARGE | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 4 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | BACKGROUND_ABSORPTION, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, PEAK_WIDTH_LAW_MISMATCH, RESOLUTION_NOT_POSITIVE, RESOLUTION_UNC, SPACE_GROUP_SETTING_ASSUMED, STAGE_MAX_ITER, STRAIN_UNUSUALLY_LARGE | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 5 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | BACKGROUND_ABSORPTION, BISO_UNUSUALLY_LARGE, BOUND_HIT, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, PEAK_WIDTH_LAW_MISMATCH, RESOLUTION_NOT_POSITIVE, RESOLUTION_UNC, SPACE_GROUP_SETTING_ASSUMED, STAGE_MAX_ITER, STRAIN_UNUSUALLY_LARGE | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 6 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | BACKGROUND_ABSORPTION, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, PEAK_WIDTH_LAW_MISMATCH, RESOLUTION_NOT_POSITIVE, RESOLUTION_UNC, SPACE_GROUP_SETTING_ASSUMED, STAGE_MAX_ITER, STRAIN_UNUSUALLY_LARGE | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 7 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | BACKGROUND_ABSORPTION, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, PEAK_WIDTH_LAW_MISMATCH, RESOLUTION_NOT_POSITIVE, RESOLUTION_UNC, SPACE_GROUP_SETTING_ASSUMED, STAGE_MAX_ITER, STRAIN_UNUSUALLY_LARGE | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, the arm's pair, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | status_maxiter vs on: worst |Δ|/esd (path) | status_runaway vs on: worst |Δ|/esd (path) | on_nobound vs on: worst |Δ|/esd (path) | off_nobound vs on: worst |Δ|/esd (path) | status_maxiter vs status | status_runaway vs status | off_nobound vs off | on vs ref_seeded | status vs ref_seeded | off vs ref_seeded | status_maxiter vs ref_seeded | status_runaway vs ref_seeded | on_nobound vs ref_seeded | off_nobound vs ref_seeded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1 | 0 | 0 | 0 | 9.26 (instrument.profile.v) +8 | 0 | 0 | 0 | 9.26 (instrument.profile.v) +8 | 0 | 10 (phases.0.scale) +8 | 10 (phases.0.scale) +8 | 10 (phases.0.scale) +8 | 10 (phases.0.scale) +8 | 4.5 (phases.0.lor_strain) | 10 (phases.0.scale) +8 | 10 (phases.0.scale) +8 |
| 2 | 0 | 0 | 0 | 9.53e+03 (instrument.geometry.axial_sl) | 0 | 0 | 0 | 9.53e+03 (instrument.geometry.axial_sl) | 0 | 4.95 (instrument.profile.v) | 4.95 (instrument.profile.v) | 4.95 (instrument.profile.v) | 4.95 (instrument.profile.v) | 1.34e+04 (instrument.geometry.axial_sl) | 4.95 (instrument.profile.v) | 4.95 (instrument.profile.v) |
| 3 | 0 | 0 | 0 | 4.54e+04 (instrument.geometry.axial_sl) | 0 | 0 | 0 | 4.54e+04 (instrument.geometry.axial_sl) | 0 | 2.42 (instrument.profile.v) | 2.42 (instrument.profile.v) | 2.42 (instrument.profile.v) | 2.42 (instrument.profile.v) | 5.32e+04 (instrument.geometry.axial_sl) | 2.42 (instrument.profile.v) | 2.42 (instrument.profile.v) |
| 4 | 0 | 0 | 0 | 4.2e+04 (instrument.geometry.axial_sl) | 0 | 0 | 0 | 4.2e+04 (instrument.geometry.axial_sl) | 0 | 3.68 (instrument.profile.v) | 3.68 (instrument.profile.v) | 3.68 (instrument.profile.v) | 3.68 (instrument.profile.v) | 4.98e+04 (instrument.geometry.axial_sl) | 3.68 (instrument.profile.v) | 3.68 (instrument.profile.v) |
| 5 | 0 | 0 | 0 | 3.6e+04 (instrument.geometry.axial_sl) | 0 | 0 | 0 | 3.6e+04 (instrument.geometry.axial_sl) | 0 | 3.82 (instrument.profile.v) | 3.82 (instrument.profile.v) | 3.82 (instrument.profile.v) | 3.82 (instrument.profile.v) | 4.67e+04 (instrument.geometry.axial_sl) | 3.82 (instrument.profile.v) | 3.82 (instrument.profile.v) |
| 6 | 0 | 0 | 0 | 4.12e+04 (instrument.geometry.axial_sl) | 0 | 0 | 0 | 4.12e+04 (instrument.geometry.axial_sl) | 0 | 5.19 (instrument.profile.v) | 5.19 (instrument.profile.v) | 5.19 (instrument.profile.v) | 5.19 (instrument.profile.v) | 5.14e+04 (instrument.geometry.axial_sl) | 5.19 (instrument.profile.v) | 5.19 (instrument.profile.v) |
| 7 | 0 | 0 | 0 | 4.05e+04 (instrument.geometry.axial_sl) | 0 | 0 | 0 | 4.05e+04 (instrument.geometry.axial_sl) | 0 | 3.36 (instrument.profile.v) | 3.36 (instrument.profile.v) | 3.36 (instrument.profile.v) | 3.36 (instrument.profile.v) | 5.05e+04 (instrument.geometry.axial_sl) | 3.36 (instrument.profile.v) | 3.36 (instrument.profile.v) |

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref_seeded` the reference.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound | ref_seeded |
|---|---|---|---|---|---|---|---|---|---|
| 0 | `phases.0.cell.a` | 4.7584(33) | 4.7584(33) | 4.7584(33) | 4.7584(33) | 4.7584(33) | 4.7584(33) | 4.7584(33) | 4.7584(33) |
| 0 | `phases.0.cell.c` | 12.991(13) | 12.991(13) | 12.991(13) | 12.991(13) | 12.991(13) | 12.991(13) | 12.991(13) | 12.991(13) |
| 0 | `phases.1.cell.a` | 3.24862(70) | 3.24862(70) | 3.24862(70) | 3.24862(70) | 3.24862(70) | 3.24862(70) | 3.24862(70) | 3.24862(70) |
| 0 | `phases.2.cell.a` | 5.4628(11) | 5.4628(11) | 5.4628(11) | 5.4628(11) | 5.4628(11) | 5.4628(11) | 5.4628(11) | 5.4628(11) |
| 0 | `instrument.zero_shift` | -0.050(73) | -0.050(73) | -0.050(73) | -0.050(73) | -0.050(73) | -0.050(73) | -0.050(73) | -0.050(73) |
| 0 | `instrument.geometry.sample_displacement` | -0.09(11) | -0.09(11) | -0.09(11) | -0.09(11) | -0.09(11) | -0.09(11) | -0.09(11) | -0.09(11) |
| 1 | `phases.0.cell.a` | — | — | — | — | 4.75808(39) | — | — | 4.75809(39) |
| 1 | `phases.0.cell.c` | — | — | — | — | 12.9895(11) | — | — | 12.9896(11) |
| 1 | `phases.1.cell.a` | 3.24913(60) | 3.24913(60) | 3.24913(60) | 3.24913(60) | 3.24905(53) | 3.24913(60) | 3.24913(60) | 3.24909(55) |
| 1 | `phases.2.cell.a` | 5.46325(38) | 5.46325(38) | 5.46325(38) | 5.46325(38) | 5.46288(53) | 5.46325(38) | 5.46325(38) | 5.46290(53) |
| 1 | `instrument.zero_shift` | -0.012(14) | -0.012(14) | -0.012(14) | -0.012(14) | -0.041(36) | -0.012(14) | -0.012(14) | -0.040(36) |
| 1 | `instrument.geometry.sample_displacement` | 0.062(29) | 0.062(29) | 0.062(29) | 0.062(29) | 0.025(56) | 0.062(29) | 0.062(29) | 0.026(56) |
| 2 | `phases.0.cell.a` | 4.7575(11) | 4.7575(11) | 4.7575(11) | 4.7575(11) | 4.668(38) | 4.7575(11) | 4.7575(11) | 4.7572(10) |
| 2 | `phases.0.cell.c` | 12.9893(44) | 12.9893(44) | 12.9893(44) | 12.9893(44) | 12.72(11) | 12.9893(44) | 12.9893(44) | 12.9889(43) |
| 2 | `phases.1.cell.a` | 3.24901(32) | 3.24901(32) | 3.24901(32) | 3.24901(32) | 3.186(24) | 3.24901(32) | 3.24901(32) | 3.24884(26) |
| 2 | `phases.2.cell.a` | 5.4624(11) | 5.4624(11) | 5.4624(11) | 5.4624(11) | 5.348(45) | 5.4624(11) | 5.4624(11) | 5.4621(10) |
| 2 | `instrument.zero_shift` | -0.053(39) | -0.053(39) | -0.053(39) | -0.053(39) | -6.3(26) | -0.053(39) | -0.053(39) | -0.090(33) |
| 2 | `instrument.geometry.sample_displacement` | -0.079(59) | -0.079(59) | -0.079(59) | -0.079(59) | -8.9(37) | -0.079(59) | -0.079(59) | -0.145(50) |
| 3 | `phases.0.cell.a` | 4.75829(66) | 4.75829(66) | 4.75829(66) | 4.75829(66) | 4.66(58) | 4.75829(66) | 4.75829(66) | 4.75826(61) |
| 3 | `phases.0.cell.c` | 12.9902(21) | 12.9902(21) | 12.9902(21) | 12.9902(21) | 12.7(16) | 12.9902(21) | 12.9902(21) | 12.9902(20) |
| 3 | `phases.1.cell.a` | 3.24921(41) | 3.24921(41) | 3.24921(41) | 3.24921(41) | 3.18(38) | 3.24921(41) | 3.24921(41) | 3.24919(38) |
| 3 | `phases.2.cell.a` | 5.46314(70) | 5.46314(70) | 5.46314(70) | 5.46314(70) | 5.31(65) | 5.46314(70) | 5.46314(70) | 5.46311(64) |
| 3 | `instrument.zero_shift` | -0.030(48) | -0.030(48) | -0.030(48) | -0.030(48) | -6(40) | -0.030(48) | -0.030(48) | -0.041(45) |
| 3 | `instrument.geometry.sample_displacement` | -0.070(70) | -0.070(70) | -0.070(70) | -0.070(70) | -9(57) | -0.070(70) | -0.070(70) | -0.091(65) |
| 4 | `phases.0.cell.a` | 4.75827(44) | 4.75827(44) | 4.75827(44) | 4.75827(44) | 4.67(47) | 4.75827(44) | 4.75827(44) | 4.75823(39) |
| 4 | `phases.0.cell.c` | 12.9897(12) | 12.9897(12) | 12.9897(12) | 12.9897(12) | 12.8(13) | 12.9897(12) | 12.9897(12) | 12.9897(11) |
| 4 | `phases.1.cell.a` | 3.24920(31) | 3.24920(31) | 3.24920(31) | 3.24920(31) | 3.19(31) | 3.24920(31) | 3.24920(31) | 3.24917(28) |
| 4 | `phases.2.cell.a` | 5.46314(52) | 5.46314(52) | 5.46314(52) | 5.46314(52) | 5.35(52) | 5.46314(52) | 5.46314(52) | 5.46309(47) |
| 4 | `instrument.zero_shift` | -0.031(37) | -0.031(37) | -0.031(37) | -0.031(37) | -6(33) | -0.031(37) | -0.031(37) | -0.042(34) |
| 4 | `instrument.geometry.sample_displacement` | -0.037(55) | -0.037(55) | -0.037(55) | -0.037(55) | -9(48) | -0.037(55) | -0.037(55) | -0.059(50) |
| 5 | `phases.0.cell.a` | 4.75820(53) | 4.75820(53) | 4.75820(53) | 4.75820(53) | 4.68(56) | 4.75820(53) | 4.75820(53) | 4.75806(44) |
| 5 | `phases.0.cell.c` | 12.9897(16) | 12.9897(16) | 12.9897(16) | 12.9897(16) | 12.9(15) | 12.9897(16) | 12.9897(16) | 12.9894(14) |
| 5 | `phases.1.cell.a` | 3.24913(35) | 3.24913(35) | 3.24913(35) | 3.24913(35) | 3.19(37) | 3.24913(35) | 3.24913(35) | 3.24904(29) |
| 5 | `phases.2.cell.a` | 5.46294(61) | 5.46294(61) | 5.46294(61) | 5.46294(61) | 5.37(65) | 5.46294(61) | 5.46294(61) | 5.46278(51) |
| 5 | `instrument.zero_shift` | -0.033(42) | -0.033(42) | -0.033(42) | -0.033(42) | -6(39) | -0.033(42) | -0.033(42) | -0.056(36) |
| 5 | `instrument.geometry.sample_displacement` | -0.069(63) | -0.069(63) | -0.069(63) | -0.069(63) | -10(55) | -0.069(63) | -0.069(63) | -0.110(54) |
| 6 | `phases.0.cell.a` | 4.75816(43) | 4.75816(43) | 4.75816(43) | 4.75816(43) | 4.68(50) | 4.75816(43) | 4.75816(43) | 4.75808(36) |
| 6 | `phases.0.cell.c` | 12.9895(13) | 12.9895(13) | 12.9895(13) | 12.9895(13) | 12.9(14) | 12.9895(13) | 12.9895(13) | 12.9893(11) |
| 6 | `phases.1.cell.a` | 3.24907(29) | 3.24907(29) | 3.24907(29) | 3.24907(29) | 3.19(34) | 3.24907(29) | 3.24907(29) | 3.24902(25) |
| 6 | `phases.2.cell.a` | 5.46283(50) | 5.46283(50) | 5.46283(50) | 5.46283(50) | 5.36(58) | 5.46283(50) | 5.46283(50) | 5.46274(42) |
| 6 | `instrument.zero_shift` | -0.034(35) | -0.034(35) | -0.034(35) | -0.034(35) | -6(35) | -0.034(35) | -0.034(35) | -0.050(30) |
| 6 | `instrument.geometry.sample_displacement` | -0.052(51) | -0.052(51) | -0.052(51) | -0.052(51) | -9(50) | -0.052(51) | -0.052(51) | -0.083(45) |
| 7 | `phases.0.cell.a` | 4.75831(53) | 4.75831(53) | 4.75831(53) | 4.75831(53) | 4.68(49) | 4.75831(53) | 4.75831(53) | 4.75821(46) |
| 7 | `phases.0.cell.c` | 12.9898(15) | 12.9898(15) | 12.9898(15) | 12.9898(15) | 12.9(13) | 12.9898(15) | 12.9898(15) | 12.9896(14) |
| 7 | `phases.1.cell.a` | 3.24918(37) | 3.24918(37) | 3.24918(37) | 3.24918(37) | 3.19(33) | 3.24918(37) | 3.24918(37) | 3.24911(32) |
| 7 | `phases.2.cell.a` | 5.46319(62) | 5.46319(62) | 5.46319(62) | 5.46319(62) | 5.36(56) | 5.46319(62) | 5.46319(62) | 5.46308(55) |
| 7 | `instrument.zero_shift` | -0.033(43) | -0.033(43) | -0.033(43) | -0.033(43) | -6(34) | -0.033(43) | -0.033(43) | -0.052(38) |
| 7 | `instrument.geometry.sample_displacement` | -0.100(64) | -0.100(64) | -0.100(64) | -0.100(64) | -10(48) | -0.100(64) | -0.100(64) | -0.136(57) |

### Weight fractions, per pattern (wt %)

W(σ(W)) per arm; weighed = the composition as weighed, the QPA truth.

| k | phase | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound | ref_seeded | weighed |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | corundum | 1.59(0.64) | 1.59(0.64) | 1.59(0.64) | 1.59(0.64) | 1.59(0.64) | 1.59(0.64) | 1.59(0.64) | 1.59(0.64) | 1.15 |
| 0 | zincite | 3.31(0.23) | 3.31(0.23) | 3.31(0.23) | 3.31(0.23) | 3.31(0.23) | 3.31(0.23) | 3.31(0.23) | 3.31(0.23) | 4.04 |
| 0 | fluorite | 95.09(0.65) | 95.09(0.65) | 95.09(0.65) | 95.09(0.65) | 95.09(0.65) | 95.09(0.65) | 95.09(0.65) | 95.09(0.65) | 94.81 |
| 1 | corundum | 94.84(0.27) | 94.84(0.27) | 94.84(0.27) | 94.84(0.27) | 94.26(0.23) | 94.84(0.27) | 94.84(0.27) | 94.29(0.23) | 94.31 |
| 1 | zincite | 1.08(0.13) | 1.08(0.13) | 1.08(0.13) | 1.08(0.13) | 1.30(0.12) | 1.08(0.13) | 1.08(0.13) | 1.28(0.12) | 1.36 |
| 1 | fluorite | 4.08(0.24) | 4.08(0.24) | 4.08(0.24) | 4.08(0.24) | 4.43(0.20) | 4.08(0.24) | 4.08(0.24) | 4.43(0.20) | 4.33 |
| 2 | corundum | 6.25(0.75) | 6.25(0.75) | 6.25(0.75) | 6.25(0.75) | 3.91(3.37) | 6.25(0.75) | 6.25(0.75) | 6.16(0.72) | 5.04 |
| 2 | zincite | 92.01(0.80) | 92.01(0.80) | 92.01(0.80) | 92.01(0.80) | 94.74(3.58) | 92.01(0.80) | 92.01(0.80) | 92.09(0.76) | 93.59 |
| 2 | fluorite | 1.73(0.27) | 1.73(0.27) | 1.73(0.27) | 1.73(0.27) | 1.36(1.25) | 1.73(0.27) | 1.73(0.27) | 1.75(0.25) | 1.36 |
| 3 | corundum | 15.26(0.62) | 15.26(0.62) | 15.26(0.62) | 15.26(0.62) | 55.45(71.37) | 15.26(0.62) | 15.26(0.62) | 15.32(0.62) | 13.53 |
| 3 | zincite | 28.89(0.42) | 28.89(0.42) | 28.89(0.42) | 28.89(0.42) | 16.93(32.09) | 28.89(0.42) | 28.89(0.42) | 28.90(0.42) | 32.89 |
| 3 | fluorite | 55.84(0.56) | 55.84(0.56) | 55.84(0.56) | 55.84(0.56) | 27.62(55.40) | 55.84(0.56) | 55.84(0.56) | 55.78(0.56) | 53.58 |
| 4 | corundum | 57.29(0.45) | 57.29(0.45) | 57.29(0.45) | 57.29(0.45) | 73.21(39.07) | 57.29(0.45) | 57.29(0.45) | 57.31(0.44) | 55.12 |
| 4 | zincite | 12.80(0.23) | 12.80(0.23) | 12.80(0.23) | 12.80(0.23) | 8.68(16.92) | 12.80(0.23) | 12.80(0.23) | 12.84(0.22) | 15.25 |
| 4 | fluorite | 29.90(0.39) | 29.90(0.39) | 29.90(0.39) | 29.90(0.39) | 18.11(32.93) | 29.90(0.39) | 29.90(0.39) | 29.85(0.38) | 29.62 |
| 5 | corundum | 30.07(0.67) | 30.07(0.67) | 30.07(0.67) | 30.07(0.67) | 67.52(58.16) | 30.07(0.67) | 30.07(0.67) | 30.11(0.63) | 27.06 |
| 5 | zincite | 50.30(0.58) | 50.30(0.58) | 50.30(0.58) | 50.30(0.58) | 19.44(37.72) | 50.30(0.58) | 50.30(0.58) | 50.25(0.55) | 55.22 |
| 5 | fluorite | 19.63(0.43) | 19.63(0.43) | 19.63(0.43) | 19.63(0.43) | 13.04(44.77) | 19.63(0.43) | 19.63(0.43) | 19.64(0.40) | 17.72 |
| 6 | corundum | 33.61(0.49) | 33.61(0.49) | 33.61(0.49) | 33.61(0.49) | 66.30(54.87) | 33.61(0.49) | 33.61(0.49) | 33.68(0.47) | 31.37 |
| 6 | zincite | 30.31(0.33) | 30.31(0.33) | 30.31(0.33) | 30.31(0.33) | 14.73(29.12) | 30.31(0.33) | 30.31(0.33) | 30.29(0.32) | 34.21 |
| 6 | fluorite | 36.08(0.39) | 36.08(0.39) | 36.08(0.39) | 36.08(0.39) | 18.97(41.32) | 36.08(0.39) | 36.08(0.39) | 36.03(0.38) | 34.42 |
| 7 | corundum | 37.20(0.59) | 37.20(0.59) | 37.20(0.59) | 37.20(0.59) | 65.54(53.68) | 37.20(0.59) | 37.20(0.59) | 37.24(0.57) | 35.12 |
| 7 | zincite | 26.40(0.38) | 26.40(0.38) | 26.40(0.38) | 26.40(0.38) | 14.24(27.69) | 26.40(0.38) | 26.40(0.38) | 26.41(0.36) | 30.19 |
| 7 | fluorite | 36.40(0.48) | 36.40(0.48) | 36.40(0.48) | 36.40(0.48) | 20.22(40.93) | 36.40(0.48) | 36.40(0.48) | 36.35(0.47) | 34.69 |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, the arm's pair, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`; "pair" is the arm differing from this one by one switch (`PAIRED`).  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | pair: bit-identical, differ | differ from ref_seeded | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 8 | 0 | 0 | 0 | 0 | 8 | — | — | 7 (1, 2, 3, 4, 5, 6, 7) | 708 | 708 | 708 / 669 | 1.2-22.8 | 36 |
| status | 8 | 0 | 0 | 0 | 0 | 8 | 0 | — | 7 (1, 2, 3, 4, 5, 6, 7) | 708 | 708 | 708 / 669 | 1.1-23.1 | 36 |
| off | 8 | 0 | 0 | 0 | 0 | 8 | 0 | — | 7 (1, 2, 3, 4, 5, 6, 7) | 708 | 708 | 708 / 669 | 1.1-20.9 | 34 |
| status_maxiter | 8 | 0 | 0 | 0 | 0 | 8 | 0 | `status`: 8, 0 | 7 (1, 2, 3, 4, 5, 6, 7) | 708 | 708 | 708 / 669 | 1.1-20.9 | 33 |
| status_runaway | 8 | 1 | 0 | 0 | 0 | 1 | 7 (1, 2, 3, 4, 5, 6, 7) | `status`: 1, 7 (1, 2, 3, 4, 5, 6, 7) | 7 (1, 2, 3, 4, 5, 6, 7) | 2957 | 2547 | 2957 / 2522 | 3.9-175.0 | 889 |
| on_nobound | 8 | 0 | 0 | 0 | 0 | 8 | 0 | — | 7 (1, 2, 3, 4, 5, 6, 7) | 708 | 708 | 708 / 669 | 0.9-19.1 | 30 |
| off_nobound | 8 | 0 | 0 | 0 | 0 | 8 | 0 | `off`: 8, 0 | 7 (1, 2, 3, 4, 5, 6, 7) | 708 | 708 | 708 / 669 | 0.9-19.0 | 30 |
| ref_seeded | 8 | 0 | 0 | 0 | 0 | 1 | 7 (1, 2, 3, 4, 5, 6, 7) | — | — | 1164 | 1164 | 1164 / 1138 | 2.9-3.8 | 27 |

### Series-level codes

| code | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound |
|---|---|---|---|---|---|---|---|
| `SEQUENTIAL_DISCONTINUITY` | 1: phases.0.scale 0→1 | 1: phases.0.scale 0→1 | 1: phases.0.scale 0→1 | 1: phases.0.scale 0→1 | 2: phases.0.scale 0→1; phases.2.scale 0→1 | 1: phases.0.scale 0→1 | 1: phases.0.scale 0→1 |
| `SEQUENTIAL_PERSISTENT_FINDING` | 25 | 25 | 25 | 25 | 58 | 25 | 25 |

Failures (`SeriesFailure`): on 0, status 0, off 0, status_maxiter 0, status_runaway 0, on_nobound 0, off_nobound 0.

### Against `cpd`, arm by arm

Each arm against the same arm of `cpd`, the family this one changes one setting of: rungs and nfev with `cpd`'s in brackets, and the worst |Δ|/esd with `cpd`'s esd.

| k | label | on: rungs [kept] (cpd) | on: nfev (cpd) | on vs cpd on | status: rungs [kept] (cpd) | status: nfev (cpd) | status vs cpd status | off: rungs [kept] (cpd) | off: nfev (cpd) | off vs cpd off | status_maxiter: rungs [kept] (cpd) | status_maxiter: nfev (cpd) | status_maxiter vs cpd status_maxiter | status_runaway: rungs [kept] (cpd) | status_runaway: nfev (cpd) | status_runaway vs cpd status_runaway | on_nobound: rungs [kept] (cpd) | on_nobound: nfev (cpd) | on_nobound vs cpd on_nobound | off_nobound: rungs [kept] (cpd) | off_nobound: nfev (cpd) | off_nobound vs cpd off_nobound |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | cpd-1a | c [c] (c [c]) | 162 (175) | 1.3 (instrument.background.c2) | c [c] (c [c]) | 162 (175) | 1.3 (instrument.background.c2) | c [c] (c [c]) | 162 (175) | 1.3 (instrument.background.c2) | c [c] (c [c]) | 162 (175) | 1.3 (instrument.background.c2) | c [c] (c [c]) | 162 (175) | 1.3 (instrument.background.c2) | c [c] (c [c]) | 162 (175) | 1.3 (instrument.background.c2) | c [c] (c [c]) | 162 (175) | 1.3 (instrument.background.c2) |
| 1 | cpd-1b | w [w] (w [w]) | 410 (301) | 10.3 (phases.0.scale) +8 | w [w] (w [w]) | 410 (301) | 10.3 (phases.0.scale) +8 | w [w] (w [w]) | 410 (301) | 10.3 (phases.0.scale) +8 | w [w] (w [w]) | 410 (301) | 10.3 (phases.0.scale) +8 | w→ws [ws] (w→ws [ws]) | 481 (395) | 4.29 (phases.0.lor_strain) | w [w] (w [w]) | 410 (301) | 10.3 (phases.0.scale) +8 | w [w] (w [w]) | 410 (301) | 10.3 (phases.0.scale) +8 |
| 2 | cpd-1c | w [w] (w [w]) | 52 (48) | 1.94 (instrument.background.c2) | w [w] (w [w]) | 52 (48) | 1.94 (instrument.background.c2) | w [w] (w [w]) | 52 (48) | 1.94 (instrument.background.c2) | w [w] (w [w]) | 52 (48) | 1.94 (instrument.background.c2) | w [w] (w [w]) | 314 (68) | 1.34e+04 (instrument.geometry.axial_sl) | w [w] (w [w]) | 52 (48) | 1.94 (instrument.background.c2) | w [w] (w [w]) | 52 (48) | 1.94 (instrument.background.c2) |
| 3 | cpd-1d | w [w] (w [w]) | 21 (28) | 1.76 (instrument.background.c2) | w [w] (w [w]) | 21 (28) | 1.76 (instrument.background.c2) | w [w] (w [w]) | 21 (28) | 1.76 (instrument.background.c2) | w [w] (w [w]) | 21 (28) | 1.76 (instrument.background.c2) | w [w] (w [w]) | 400 (34) | 6.88e+04 (instrument.geometry.axial_sl) | w [w] (w [w]) | 21 (28) | 1.76 (instrument.background.c2) | w [w] (w [w]) | 21 (28) | 1.76 (instrument.background.c2) |
| 4 | cpd-1e | w [w] (w [w]) | 16 (23) | 2.08 (instrument.background.c0) | w [w] (w [w]) | 16 (23) | 2.08 (instrument.background.c0) | w [w] (w [w]) | 16 (23) | 2.08 (instrument.background.c0) | w [w] (w [w]) | 16 (23) | 2.08 (instrument.background.c0) | w [w] (w [w]) | 400 (29) | 5.08e+04 (instrument.geometry.axial_sl) | w [w] (w [w]) | 16 (23) | 2.08 (instrument.background.c0) | w [w] (w [w]) | 16 (23) | 2.08 (instrument.background.c0) |
| 5 | cpd-1f | w [w] (w [w]) | 18 (25) | 2.26 (instrument.background.c2) | w [w] (w [w]) | 18 (25) | 2.26 (instrument.background.c2) | w [w] (w [w]) | 18 (25) | 2.26 (instrument.background.c2) | w [w] (w [w]) | 18 (25) | 2.26 (instrument.background.c2) | w [w] (w [w]) | 400 (29) | 5.59e+04 (instrument.geometry.axial_sl) | w [w] (w [w]) | 18 (25) | 2.26 (instrument.background.c2) | w [w] (w [w]) | 18 (25) | 2.26 (instrument.background.c2) |
| 6 | cpd-1g | w [w] (w [w]) | 13 (20) | 2.3 (instrument.background.c2) | w [w] (w [w]) | 13 (20) | 2.3 (instrument.background.c2) | w [w] (w [w]) | 13 (20) | 2.3 (instrument.background.c2) | w [w] (w [w]) | 13 (20) | 2.3 (instrument.background.c2) | w [w] (w [w]) | 400 (25) | 5.3e+04 (instrument.geometry.axial_sl) | w [w] (w [w]) | 13 (20) | 2.3 (instrument.background.c2) | w [w] (w [w]) | 13 (20) | 2.3 (instrument.background.c2) |
| 7 | cpd-1h | w [w] (w [w]) | 16 (24) | 1.91 (instrument.background.c2) | w [w] (w [w]) | 16 (24) | 1.91 (instrument.background.c2) | w [w] (w [w]) | 16 (24) | 1.91 (instrument.background.c2) | w [w] (w [w]) | 16 (24) | 1.91 (instrument.background.c2) | w [w] (w [w]) | 400 (30) | 5.34e+04 (instrument.geometry.axial_sl) | w [w] (w [w]) | 16 (24) | 1.91 (instrument.background.c2) | w [w] (w [w]) | 16 (24) | 1.91 (instrument.background.c2) |

`on`: nfev 708 against 644, bit-identical 0 of 8, differ 8 (0, 1, 2, 3, 4, 5, 6, 7).
`status`: nfev 708 against 644, bit-identical 0 of 8, differ 8 (0, 1, 2, 3, 4, 5, 6, 7).
`off`: nfev 708 against 644, bit-identical 0 of 8, differ 8 (0, 1, 2, 3, 4, 5, 6, 7).
`status_maxiter`: nfev 708 against 644, bit-identical 0 of 8, differ 8 (0, 1, 2, 3, 4, 5, 6, 7).
`status_runaway`: nfev 2957 against 785, bit-identical 0 of 8, differ 8 (0, 1, 2, 3, 4, 5, 6, 7).
`on_nobound`: nfev 708 against 644, bit-identical 0 of 8, differ 8 (0, 1, 2, 3, 4, 5, 6, 7).
`off_nobound`: nfev 708 against 644, bit-identical 0 of 8, differ 8 (0, 1, 2, 3, 4, 5, 6, 7).

## IUCr CPD sample-1 chain 1a-1h (real, lab Cu Kα), intermediate_ftol = None, closing stage on (declared variant)

Protocol: tests/test_acceptance_sequential.py chained_all: SequentialRefinement(structure, qarr_instrument()) with seed_scales on 1a, carry=('*',), plan=qpa_plan(), refit='single', dispersion declined, compiled tier default; the one change: plan.intermediate_ftol = None (qpa_plan names 1e-6).  Arms: on, status.

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev |
|---|---|---|---|---|---|---|---|---|---|
| 0 | cpd-1a | c [c] | 0.1631 | — | 277 | c [c] | 0.1631 | — | 277 |
| 1 | cpd-1b | w [w] | 0.1398 | 0.2038 | 305 | w [w] | 0.1398 | inf | 305 |
| 2 | cpd-1c | w [w] | 0.1095 | 0.1893 | 48 | w [w] | 0.1095 | inf | 48 |
| 3 | cpd-1d | w [w] | 0.1278 | 0.1748 | 28 | w [w] | 0.1278 | inf | 28 |
| 4 | cpd-1e | w [w] | 0.1267 | 0.1673 | 23 | w [w] | 0.1267 | inf | 23 |
| 5 | cpd-1f | w [w] | 0.1132 | 0.1598 | 25 | w [w] | 0.1132 | inf | 25 |
| 6 | cpd-1g | w [w] | 0.1213 | 0.1591 | 20 | w [w] | 0.1213 | inf | 20 |
| 7 | cpd-1h | w [w] | 0.1238 | 0.1584 | 24 | w [w] | 0.1238 | inf | 24 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status |
|---|---|---|
| 0 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 1 | CELL_RUNAWAY, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CELL_RUNAWAY, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 2 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 3 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 4 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 5 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 6 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 7 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, the arm's pair, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) |
|---|---|
| 0 | 0 |
| 1 | 0 |
| 2 | 0 |
| 3 | 0 |
| 4 | 0 |
| 5 | 0 |
| 6 | 0 |
| 7 | 0 |

### Key values, per pattern

value(esd in the last digits shown) per arm.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status |
|---|---|---|---|
| 0 | `phases.0.cell.a` | 4.7585(32) | 4.7585(32) |
| 0 | `phases.0.cell.c` | 12.990(13) | 12.990(13) |
| 0 | `phases.1.cell.a` | 3.24861(64) | 3.24861(64) |
| 0 | `phases.2.cell.a` | 5.46281(98) | 5.46281(98) |
| 0 | `instrument.zero_shift` | -0.049(67) | -0.049(67) |
| 0 | `instrument.geometry.sample_displacement` | -0.086(97) | -0.086(97) |
| 1 | `phases.0.cell.a` | 4.75801(41) | 4.75801(41) |
| 1 | `phases.0.cell.c` | 12.9893(11) | 12.9893(11) |
| 1 | `phases.1.cell.a` | 3.24897(56) | 3.24897(56) |
| 1 | `phases.2.cell.a` | 5.46277(55) | 5.46277(55) |
| 1 | `instrument.zero_shift` | -0.048(37) | -0.048(37) |
| 1 | `instrument.geometry.sample_displacement` | 0.013(58) | 0.013(58) |
| 2 | `phases.0.cell.a` | 4.75773(93) | 4.75773(93) |
| 2 | `phases.0.cell.c` | 12.9888(39) | 12.9888(39) |
| 2 | `phases.1.cell.a` | 3.24902(28) | 3.24902(28) |
| 2 | `phases.2.cell.a` | 5.46241(96) | 5.46241(96) |
| 2 | `instrument.zero_shift` | -0.052(35) | -0.052(35) |
| 2 | `instrument.geometry.sample_displacement` | -0.076(52) | -0.076(52) |
| 3 | `phases.0.cell.a` | 4.75831(56) | 4.75831(56) |
| 3 | `phases.0.cell.c` | 12.9901(18) | 12.9901(18) |
| 3 | `phases.1.cell.a` | 3.24921(35) | 3.24921(35) |
| 3 | `phases.2.cell.a` | 5.46314(59) | 5.46314(59) |
| 3 | `instrument.zero_shift` | -0.029(41) | -0.029(41) |
| 3 | `instrument.geometry.sample_displacement` | -0.068(59) | -0.068(59) |
| 4 | `phases.0.cell.a` | 4.75827(42) | 4.75827(42) |
| 4 | `phases.0.cell.c` | 12.9897(12) | 12.9897(12) |
| 4 | `phases.1.cell.a` | 3.24920(30) | 3.24920(30) |
| 4 | `phases.2.cell.a` | 5.46313(50) | 5.46313(50) |
| 4 | `instrument.zero_shift` | -0.031(35) | -0.031(35) |
| 4 | `instrument.geometry.sample_displacement` | -0.036(53) | -0.036(53) |
| 5 | `phases.0.cell.a` | 4.75821(42) | 4.75821(42) |
| 5 | `phases.0.cell.c` | 12.9896(13) | 12.9896(13) |
| 5 | `phases.1.cell.a` | 3.24913(28) | 3.24913(28) |
| 5 | `phases.2.cell.a` | 5.46293(48) | 5.46293(48) |
| 5 | `instrument.zero_shift` | -0.033(34) | -0.033(34) |
| 5 | `instrument.geometry.sample_displacement` | -0.068(50) | -0.068(50) |
| 6 | `phases.0.cell.a` | 4.75816(40) | 4.75816(40) |
| 6 | `phases.0.cell.c` | 12.9894(12) | 12.9894(12) |
| 6 | `phases.1.cell.a` | 3.24907(27) | 3.24907(27) |
| 6 | `phases.2.cell.a` | 5.46282(46) | 5.46282(46) |
| 6 | `instrument.zero_shift` | -0.033(32) | -0.033(32) |
| 6 | `instrument.geometry.sample_displacement` | -0.052(48) | -0.052(48) |
| 7 | `phases.0.cell.a` | 4.75831(50) | 4.75831(50) |
| 7 | `phases.0.cell.c` | 12.9898(14) | 12.9898(14) |
| 7 | `phases.1.cell.a` | 3.24918(34) | 3.24918(34) |
| 7 | `phases.2.cell.a` | 5.46319(58) | 5.46319(58) |
| 7 | `instrument.zero_shift` | -0.032(40) | -0.032(40) |
| 7 | `instrument.geometry.sample_displacement` | -0.099(59) | -0.099(59) |

### Weight fractions, per pattern (wt %)

W(σ(W)) per arm; weighed = the composition as weighed, the QPA truth.

| k | phase | on | status | weighed |
|---|---|---|---|---|
| 0 | corundum | 1.72(0.64) | 1.72(0.64) | 1.15 |
| 0 | zincite | 3.35(0.21) | 3.35(0.21) | 4.04 |
| 0 | fluorite | 94.93(0.65) | 94.93(0.65) | 94.81 |
| 1 | corundum | 94.32(0.23) | 94.32(0.23) | 94.31 |
| 1 | zincite | 1.28(0.12) | 1.28(0.12) | 1.36 |
| 1 | fluorite | 4.40(0.19) | 4.40(0.19) | 4.33 |
| 2 | corundum | 6.37(0.66) | 6.37(0.66) | 5.04 |
| 2 | zincite | 91.88(0.70) | 91.88(0.70) | 93.59 |
| 2 | fluorite | 1.76(0.23) | 1.76(0.23) | 1.36 |
| 3 | corundum | 15.28(0.53) | 15.28(0.53) | 13.53 |
| 3 | zincite | 28.85(0.35) | 28.85(0.35) | 32.89 |
| 3 | fluorite | 55.87(0.47) | 55.87(0.47) | 53.58 |
| 4 | corundum | 57.32(0.43) | 57.32(0.43) | 55.12 |
| 4 | zincite | 12.79(0.22) | 12.79(0.22) | 15.25 |
| 4 | fluorite | 29.89(0.37) | 29.89(0.37) | 29.62 |
| 5 | corundum | 30.14(0.53) | 30.14(0.53) | 27.06 |
| 5 | zincite | 50.17(0.47) | 50.17(0.47) | 55.22 |
| 5 | fluorite | 19.69(0.34) | 19.69(0.34) | 17.72 |
| 6 | corundum | 33.66(0.45) | 33.66(0.45) | 31.37 |
| 6 | zincite | 30.24(0.31) | 30.24(0.31) | 34.21 |
| 6 | fluorite | 36.10(0.37) | 36.10(0.37) | 34.42 |
| 7 | corundum | 37.24(0.55) | 37.24(0.55) | 35.12 |
| 7 | zincite | 26.35(0.35) | 26.35(0.35) | 30.19 |
| 7 | fluorite | 36.41(0.45) | 36.41(0.45) | 34.69 |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, the arm's pair, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`; "pair" is the arm differing from this one by one switch (`PAIRED`).  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 8 | 0 | 0 | 0 | 0 | 8 | — | 750 | 750 | 750 / 719 | 3.1-22.1 | 54 |
| status | 8 | 0 | 0 | 0 | 0 | 8 | 0 | 750 | 750 | 750 / 719 | 3.2-22.7 | 55 |

### Series-level codes

| code | on | status |
|---|---|---|
| `SEQUENTIAL_PERSISTENT_FINDING` | 26 | 26 |

Failures (`SeriesFailure`): on 0, status 0.

### Against `cpd`, arm by arm

Each arm against the same arm of `cpd`, the family this one changes one setting of: rungs and nfev with `cpd`'s in brackets, and the worst |Δ|/esd with `cpd`'s esd.

| k | label | on: rungs [kept] (cpd) | on: nfev (cpd) | on vs cpd on | status: rungs [kept] (cpd) | status: nfev (cpd) | status vs cpd status |
|---|---|---|---|---|---|---|---|
| 0 | cpd-1a | c [c] (c [c]) | 277 (175) | 0.000112 (instrument.profile.v) | c [c] (c [c]) | 277 (175) | 0.000112 (instrument.profile.v) |
| 1 | cpd-1b | w [w] (w [w]) | 305 (301) | 0.000147 (instrument.profile.v) | w [w] (w [w]) | 305 (301) | 0.000147 (instrument.profile.v) |
| 2 | cpd-1c | w [w] (w [w]) | 48 (48) | 0.000205 (instrument.profile.v) | w [w] (w [w]) | 48 (48) | 0.000205 (instrument.profile.v) |
| 3 | cpd-1d | w [w] (w [w]) | 28 (28) | 0.000173 (instrument.profile.v) | w [w] (w [w]) | 28 (28) | 0.000173 (instrument.profile.v) |
| 4 | cpd-1e | w [w] (w [w]) | 23 (23) | 0.00017 (instrument.profile.v) | w [w] (w [w]) | 23 (23) | 0.00017 (instrument.profile.v) |
| 5 | cpd-1f | w [w] (w [w]) | 25 (25) | 0.000209 (instrument.profile.v) | w [w] (w [w]) | 25 (25) | 0.000209 (instrument.profile.v) |
| 6 | cpd-1g | w [w] (w [w]) | 20 (20) | 0.000207 (instrument.profile.v) | w [w] (w [w]) | 20 (20) | 0.000207 (instrument.profile.v) |
| 7 | cpd-1h | w [w] (w [w]) | 24 (24) | 0.000161 (instrument.profile.v) | w [w] (w [w]) | 24 (24) | 0.000161 (instrument.profile.v) |

`on`: nfev 750 against 644, bit-identical 0 of 8, differ 0.
`status`: nfev 750 against 644, bit-identical 0 of 8, differ 0.

## planted perovskite cooling ramp, 248 patterns (synthetic), events: background step 50, blank frame 87, unmodelled phase from 124, cubic → tetragonal 186

Protocol: tests/planted_series.py refine(): cubic_model(T0), plan='mccusker_default', refit='single', forward, x=T (K), carry=('*',), compiled tier OFF (numpy_path).  Arms: on, status, off, status_maxiter, status_runaway, on_nobound, off_nobound; reference `ref`; truth: the simulation.

248 patterns.  The ladder, codes and accepted-value tables carry the 162 where any two arms differ (rungs tried or kept, status, fence verdict, entry codes, or a value by > 0.1 esd) or an arm differs from `ref` by > 0.1 esd, plus every event pattern ±2; the key-value tables carry only the 53 of those where a value differs, plus the events ±2.  Every other pattern has the same rungs, status, verdict and codes in every arm and values within 0.1 esd of each other and of `ref`; all of them are in the JSON.  Distance from truth selects no row (every pattern is some esd from it).

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev | status_maxiter: rungs [kept] | status_maxiter: Rwp warm→kept | status_maxiter: fence | status_maxiter: nfev | status_runaway: rungs [kept] | status_runaway: Rwp warm→kept | status_runaway: fence | status_runaway: nfev | on_nobound: rungs [kept] | on_nobound: Rwp warm→kept | on_nobound: fence | on_nobound: nfev | off_nobound: rungs [kept] | off_nobound: Rwp warm→kept | off_nobound: fence | off_nobound: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 48 | T048 | w [w] | 0.0501 | 0.0613 | 10 | w [w] | 0.0501 | inf | 10 | w [w] | 0.0501 | 0.0613 | 10 | w [w] | 0.0501 | inf | 10 | w [w] | 0.0501 | inf | 10 | w [w] | 0.0501 | 0.0613 | 10 | w [w] | 0.0501 | 0.0613 | 10 |
| 49 | T049 | w [w] | 0.0488 | 0.0614 | 8 | w [w] | 0.0488 | inf | 8 | w [w] | 0.0488 | 0.0614 | 8 | w [w] | 0.0488 | inf | 8 | w [w] | 0.0488 | inf | 8 | w [w] | 0.0488 | 0.0614 | 8 | w [w] | 0.0488 | 0.0614 | 8 |
| 50 | T050 | w [w] | 0.0413 | 0.0613 | 7 | w [w] | 0.0413 | inf | 7 | w [w] | 0.0413 | 0.0613 | 7 | w [w] | 0.0413 | inf | 7 | w [w] | 0.0413 | inf | 7 | w [w] | 0.0413 | 0.0613 | 7 | w [w] | 0.0413 | 0.0613 | 7 |
| 51 | T051 | w [w] | 0.0420 | 0.0613 | 9 | w [w] | 0.0420 | inf | 9 | w [w] | 0.0420 | 0.0613 | 9 | w [w] | 0.0420 | inf | 9 | w [w] | 0.0420 | inf | 9 | w [w] | 0.0420 | 0.0613 | 9 | w [w] | 0.0420 | 0.0613 | 9 |
| 52 | T052 | w [w] | 0.0429 | 0.0613 | 9 | w [w] | 0.0429 | inf | 9 | w [w] | 0.0429 | 0.0613 | 9 | w [w] | 0.0429 | inf | 9 | w [w] | 0.0429 | inf | 9 | w [w] | 0.0429 | 0.0613 | 9 | w [w] | 0.0429 | 0.0613 | 9 |
| 85 | T085 | w [w] | 0.0415 | 0.0605 | 10 | w [w] | 0.0415 | inf | 10 | w [w] | 0.0415 | 0.0605 | 10 | w [w] | 0.0415 | inf | 10 | w [w] | 0.0415 | inf | 10 | w [w] | 0.0415 | 0.0605 | 10 | w [w] | 0.0415 | 0.0605 | 10 |
| 86 | T086 | w [w] | 0.0420 | 0.0605 | 10 | w [w] | 0.0420 | inf | 10 | w [w] | 0.0420 | 0.0605 | 10 | w [w] | 0.0420 | inf | 10 | w [w] | 0.0420 | inf | 10 | w [w] | 0.0420 | 0.0605 | 10 | w [w] | 0.0420 | 0.0605 | 10 |
| 87 | T087 | w→ws [ws] | 0.0480→0.0481 | 0.0605 | 110 | w→ws [ws] | 0.0480→0.0481 | inf | 110 | w→ws [ws] | 0.0480→0.0481 | 0.0605 | 110 | w→ws [ws] | 0.0480→0.0481 | inf | 110 | w→ws [ws] | 0.0480→0.0481 | inf | 110 | w [w] | 0.0480 | 0.0605 | 108 | w [w] | 0.0480 | 0.0605 | 108 |
| 88 | T088 | w [w] | 0.0415 | 0.0605 | 17 | w [w] | 0.0415 | inf | 17 | w [w] | 0.0415 | 0.0605 | 17 | w [w] | 0.0415 | inf | 17 | w [w] | 0.0415 | inf | 17 | w→ws→c [c]! | 0.4334→0.0415 | 0.0605 | 68 | w [w] | 0.4334 | 0.0605* | 28 |
| 89 | T089 | w [w] | 0.0419 | 0.0604 | 7 | w [w] | 0.0419 | inf | 7 | w [w] | 0.0419 | 0.0604 | 7 | w [w] | 0.0419 | inf | 7 | w [w] | 0.0419 | inf | 7 | w [w] | 0.0419 | 0.0604 | 7 | w [w] | 0.4342 | 0.0605* | 26 |
| 90 | T090 | w [w] | 0.0420 | 0.0603 | 7 | w [w] | 0.0420 | inf | 7 | w [w] | 0.0420 | 0.0603 | 7 | w [w] | 0.0420 | inf | 7 | w [w] | 0.0420 | inf | 7 | w [w] | 0.0420 | 0.0603 | 7 | w [w] | 0.4344 | 0.0605* | 26 |
| 91 | T091 | w [w] | 0.0416 | 0.0602 | 9 | w [w] | 0.0416 | inf | 9 | w [w] | 0.0416 | 0.0602 | 9 | w [w] | 0.0416 | inf | 9 | w [w] | 0.0416 | inf | 9 | w [w] | 0.0416 | 0.0602 | 9 | w [w] | 0.4340 | 0.0605* | 26 |
| 92 | T092 | w [w] | 0.0416 | 0.0601 | 7 | w [w] | 0.0416 | inf | 7 | w [w] | 0.0416 | 0.0601 | 7 | w [w] | 0.0416 | inf | 7 | w [w] | 0.0416 | inf | 7 | w [w] | 0.0416 | 0.0601 | 7 | w [w] | 0.4343 | 0.0606* | 26 |
| 93 | T093 | w [w] | 0.0422 | 0.0601 | 7 | w [w] | 0.0422 | inf | 7 | w [w] | 0.0422 | 0.0601 | 7 | w [w] | 0.0422 | inf | 7 | w [w] | 0.0422 | inf | 7 | w [w] | 0.0422 | 0.0601 | 7 | w [w] | 0.4335 | 0.0606* | 26 |
| 94 | T094 | w [w] | 0.0429 | 0.0601 | 10 | w [w] | 0.0429 | inf | 10 | w [w] | 0.0429 | 0.0601 | 10 | w [w] | 0.0429 | inf | 10 | w [w] | 0.0429 | inf | 10 | w [w] | 0.0429 | 0.0601 | 10 | w [w] | 0.4338 | 0.0606* | 26 |
| 95 | T095 | w [w] | 0.0423 | 0.0601 | 8 | w [w] | 0.0423 | inf | 8 | w [w] | 0.0423 | 0.0601 | 8 | w [w] | 0.0423 | inf | 8 | w [w] | 0.0423 | inf | 8 | w [w] | 0.0423 | 0.0600 | 8 | w [w] | 0.4336 | 0.0606* | 26 |
| 96 | T096 | w [w] | 0.0419 | 0.0600 | 9 | w [w] | 0.0419 | inf | 9 | w [w] | 0.0419 | 0.0600 | 9 | w [w] | 0.0419 | inf | 9 | w [w] | 0.0419 | inf | 9 | w [w] | 0.0419 | 0.0600 | 9 | w [w] | 0.4339 | 0.0607* | 26 |
| 97 | T097 | w [w] | 0.0415 | 0.0599 | 7 | w [w] | 0.0415 | inf | 7 | w [w] | 0.0415 | 0.0599 | 7 | w [w] | 0.0415 | inf | 7 | w [w] | 0.0415 | inf | 7 | w [w] | 0.0415 | 0.0599 | 7 | w [w] | 0.4339 | 0.0608* | 26 |
| 98 | T098 | w [w] | 0.0418 | 0.0598 | 7 | w [w] | 0.0418 | inf | 7 | w [w] | 0.0418 | 0.0598 | 7 | w [w] | 0.0418 | inf | 7 | w [w] | 0.0418 | inf | 7 | w [w] | 0.0418 | 0.0598 | 7 | w [w] | 0.4340 | 0.0608* | 26 |
| 99 | T099 | w [w] | 0.0413 | 0.0598 | 7 | w [w] | 0.0413 | inf | 7 | w [w] | 0.0413 | 0.0598 | 7 | w [w] | 0.0413 | inf | 7 | w [w] | 0.0413 | inf | 7 | w [w] | 0.0413 | 0.0598 | 7 | w [w] | 0.4345 | 0.0608* | 26 |
| 100 | T100 | w [w] | 0.0425 | 0.0596 | 9 | w [w] | 0.0425 | inf | 9 | w [w] | 0.0425 | 0.0596 | 9 | w [w] | 0.0425 | inf | 9 | w [w] | 0.0425 | inf | 9 | w [w] | 0.0425 | 0.0596 | 9 | w [w] | 0.4333 | 0.0609* | 26 |
| 101 | T101 | w [w] | 0.0424 | 0.0595 | 7 | w [w] | 0.0424 | inf | 7 | w [w] | 0.0424 | 0.0595 | 7 | w [w] | 0.0424 | inf | 7 | w [w] | 0.0424 | inf | 7 | w [w] | 0.0424 | 0.0595 | 7 | w [w] | 0.4339 | 0.0609* | 26 |
| 102 | T102 | w [w] | 0.0425 | 0.0566 | 10 | w [w] | 0.0425 | inf | 10 | w [w] | 0.0425 | 0.0566 | 10 | w [w] | 0.0425 | inf | 10 | w [w] | 0.0425 | inf | 10 | w [w] | 0.0425 | 0.0566 | 10 | w [w] | 0.4334 | 0.0609* | 26 |
| 103 | T103 | w [w] | 0.0429 | 0.0537 | 10 | w [w] | 0.0429 | inf | 10 | w [w] | 0.0429 | 0.0537 | 10 | w [w] | 0.0429 | inf | 10 | w [w] | 0.0429 | inf | 10 | w [w] | 0.0429 | 0.0537 | 10 | w [w] | 0.4337 | 0.0610* | 26 |
| 104 | T104 | w [w] | 0.0426 | 0.0537 | 7 | w [w] | 0.0426 | inf | 7 | w [w] | 0.0426 | 0.0537 | 7 | w [w] | 0.0426 | inf | 7 | w [w] | 0.0426 | inf | 7 | w [w] | 0.0426 | 0.0537 | 7 | w [w] | 0.4340 | 0.0610* | 26 |
| 105 | T105 | w [w] | 0.0423 | 0.0537 | 7 | w [w] | 0.0423 | inf | 7 | w [w] | 0.0423 | 0.0537 | 7 | w [w] | 0.0423 | inf | 7 | w [w] | 0.0423 | inf | 7 | w [w] | 0.0423 | 0.0537 | 7 | w [w] | 0.4331 | 0.0610* | 26 |
| 106 | T106 | w [w] | 0.0421 | 0.0537 | 7 | w [w] | 0.0421 | inf | 7 | w [w] | 0.0421 | 0.0537 | 7 | w [w] | 0.0421 | inf | 7 | w [w] | 0.0421 | inf | 7 | w [w] | 0.0421 | 0.0537 | 7 | w [w] | 0.4336 | 0.0610* | 26 |
| 107 | T107 | w [w] | 0.0423 | 0.0536 | 9 | w [w] | 0.0423 | inf | 9 | w [w] | 0.0423 | 0.0536 | 9 | w [w] | 0.0423 | inf | 9 | w [w] | 0.0423 | inf | 9 | w [w] | 0.0423 | 0.0536 | 9 | w [w] | 0.4341 | 0.0610* | 26 |
| 108 | T108 | w [w] | 0.0424 | 0.0536 | 8 | w [w] | 0.0424 | inf | 8 | w [w] | 0.0424 | 0.0536 | 8 | w [w] | 0.0424 | inf | 8 | w [w] | 0.0424 | inf | 8 | w [w] | 0.0424 | 0.0536 | 8 | w [w] | 0.4342 | 0.0610* | 26 |
| 109 | T109 | w [w] | 0.0428 | 0.0536 | 8 | w [w] | 0.0428 | inf | 8 | w [w] | 0.0428 | 0.0536 | 8 | w [w] | 0.0428 | inf | 8 | w [w] | 0.0428 | inf | 8 | w [w] | 0.0428 | 0.0536 | 8 | w [w] | 0.4343 | 0.0610* | 26 |
| 110 | T110 | w [w] | 0.0429 | 0.0536 | 7 | w [w] | 0.0429 | inf | 7 | w [w] | 0.0429 | 0.0536 | 7 | w [w] | 0.0429 | inf | 7 | w [w] | 0.0429 | inf | 7 | w [w] | 0.0429 | 0.0536 | 7 | w [w] | 0.4339 | 0.0610* | 26 |
| 111 | T111 | w [w] | 0.0430 | 0.0536 | 9 | w [w] | 0.0430 | inf | 9 | w [w] | 0.0430 | 0.0536 | 9 | w [w] | 0.0430 | inf | 9 | w [w] | 0.0430 | inf | 9 | w [w] | 0.0430 | 0.0536 | 9 | w [w] | 0.4337 | 0.0610* | 26 |
| 112 | T112 | w [w] | 0.0426 | 0.0536 | 9 | w [w] | 0.0426 | inf | 9 | w [w] | 0.0426 | 0.0536 | 9 | w [w] | 0.0426 | inf | 9 | w [w] | 0.0426 | inf | 9 | w [w] | 0.0426 | 0.0536 | 9 | w [w] | 0.4337 | 0.0611* | 26 |
| 113 | T113 | w [w] | 0.0431 | 0.0536 | 9 | w [w] | 0.0431 | inf | 9 | w [w] | 0.0431 | 0.0536 | 9 | w [w] | 0.0431 | inf | 9 | w [w] | 0.0431 | inf | 9 | w [w] | 0.0431 | 0.0536 | 9 | w [w] | 0.4330 | 0.0612* | 26 |
| 114 | T114 | w [w] | 0.0420 | 0.0536 | 7 | w [w] | 0.0420 | inf | 7 | w [w] | 0.0420 | 0.0536 | 7 | w [w] | 0.0420 | inf | 7 | w [w] | 0.0420 | inf | 7 | w [w] | 0.0420 | 0.0536 | 7 | w [w] | 0.4337 | 0.0612* | 26 |
| 115 | T115 | w [w] | 0.0420 | 0.0536 | 9 | w [w] | 0.0420 | inf | 9 | w [w] | 0.0420 | 0.0536 | 9 | w [w] | 0.0420 | inf | 9 | w [w] | 0.0420 | inf | 9 | w [w] | 0.0420 | 0.0536 | 9 | w [w] | 0.4332 | 0.0612* | 26 |
| 116 | T116 | w [w] | 0.0418 | 0.0536 | 8 | w [w] | 0.0418 | inf | 8 | w [w] | 0.0418 | 0.0536 | 8 | w [w] | 0.0418 | inf | 8 | w [w] | 0.0418 | inf | 8 | w [w] | 0.0418 | 0.0536 | 8 | w [w] | 0.4338 | 0.0612* | 25 |
| 117 | T117 | w [w] | 0.0424 | 0.0536 | 8 | w [w] | 0.0424 | inf | 8 | w [w] | 0.0424 | 0.0536 | 8 | w [w] | 0.0424 | inf | 8 | w [w] | 0.0424 | inf | 8 | w [w] | 0.0424 | 0.0536 | 8 | w [w] | 0.4333 | 0.0613* | 26 |
| 118 | T118 | w [w] | 0.0422 | 0.0536 | 9 | w [w] | 0.0422 | inf | 9 | w [w] | 0.0422 | 0.0536 | 9 | w [w] | 0.0422 | inf | 9 | w [w] | 0.0422 | inf | 9 | w [w] | 0.0422 | 0.0536 | 9 | w [w] | 0.4344 | 0.0613* | 26 |
| 119 | T119 | w [w] | 0.0421 | 0.0536 | 10 | w [w] | 0.0421 | inf | 10 | w [w] | 0.0421 | 0.0536 | 10 | w [w] | 0.0421 | inf | 10 | w [w] | 0.0421 | inf | 10 | w [w] | 0.0421 | 0.0536 | 10 | w [w] | 0.4327 | 0.0613* | 26 |
| 120 | T120 | w [w] | 0.0413 | 0.0535 | 9 | w [w] | 0.0413 | inf | 9 | w [w] | 0.0413 | 0.0535 | 9 | w [w] | 0.0413 | inf | 9 | w [w] | 0.0413 | inf | 9 | w [w] | 0.0413 | 0.0535 | 9 | w [w] | 0.4333 | 0.0613* | 26 |
| 121 | T121 | w [w] | 0.0423 | 0.0534 | 10 | w [w] | 0.0423 | inf | 10 | w [w] | 0.0423 | 0.0534 | 10 | w [w] | 0.0423 | inf | 10 | w [w] | 0.0423 | inf | 10 | w [w] | 0.0423 | 0.0534 | 10 | w [w] | 0.4331 | 0.0613* | 26 |
| 122 | T122 | w [w] | 0.0415 | 0.0534 | 8 | w [w] | 0.0415 | inf | 8 | w [w] | 0.0415 | 0.0534 | 8 | w [w] | 0.0415 | inf | 8 | w [w] | 0.0415 | inf | 8 | w [w] | 0.0415 | 0.0534 | 8 | w [w] | 0.4335 | 0.0613* | 26 |
| 123 | T123 | w [w] | 0.0420 | 0.0534 | 7 | w [w] | 0.0420 | inf | 7 | w [w] | 0.0420 | 0.0534 | 7 | w [w] | 0.0420 | inf | 7 | w [w] | 0.0420 | inf | 7 | w [w] | 0.0420 | 0.0534 | 7 | w [w] | 0.4336 | 0.0613* | 26 |
| 124 | T124 | w [w] | 0.0427 | 0.0534 | 10 | w [w] | 0.0427 | inf | 10 | w [w] | 0.0427 | 0.0534 | 10 | w [w] | 0.0427 | inf | 10 | w [w] | 0.0427 | inf | 10 | w [w] | 0.0427 | 0.0534 | 10 | w [w] | 0.4340 | 0.0613* | 26 |
| 125 | T125 | w [w] | 0.0430 | 0.0533 | 9 | w [w] | 0.0430 | inf | 9 | w [w] | 0.0430 | 0.0533 | 9 | w [w] | 0.0430 | inf | 9 | w [w] | 0.0430 | inf | 9 | w [w] | 0.0430 | 0.0533 | 9 | w [w] | 0.4335 | 0.0613* | 26 |
| 126 | T126 | w [w] | 0.0426 | 0.0534 | 7 | w [w] | 0.0426 | inf | 7 | w [w] | 0.0426 | 0.0534 | 7 | w [w] | 0.0426 | inf | 7 | w [w] | 0.0426 | inf | 7 | w [w] | 0.0426 | 0.0534 | 7 | w [w] | 0.4336 | 0.0613* | 26 |
| 127 | T127 | w [w] | 0.0443 | 0.0533 | 10 | w [w] | 0.0443 | inf | 10 | w [w] | 0.0443 | 0.0533 | 10 | w [w] | 0.0443 | inf | 10 | w [w] | 0.0443 | inf | 10 | w [w] | 0.0443 | 0.0533 | 10 | w [w] | 0.4328 | 0.0614* | 26 |
| 134 | T134 | w→ws→c [ws] | 0.0553→0.0553 | 0.0536* | 66 | w [w] | 0.0553 | inf | 7 | w [w] | 0.0553 | 0.0536* | 7 | w [w] | 0.0553 | inf | 7 | w [w] | 0.0553 | inf | 7 | w→ws→c [w] | 0.0553→0.0553 | 0.0536* | 66 | w [w] | 0.0553 | 0.0614 | 7 |
| 135 | T135 | w→ws→c [c] | 0.0561→0.0561 | 0.0536* | 71 | w [w] | 0.0561 | inf | 11 | w [w] | 0.0561 | 0.0536* | 11 | w [w] | 0.0561 | inf | 11 | w [w] | 0.0561 | inf | 11 | w→ws→c [c] | 0.0561→0.0561 | 0.0536* | 71 | w [w] | 0.0561 | 0.0614 | 11 |
| 136 | T136 | w→ws→c [ws] | 0.0573→0.0573 | 0.0536* | 72 | w [w] | 0.0573 | inf | 10 | w [w] | 0.0573 | 0.0536* | 10 | w [w] | 0.0573 | inf | 10 | w [w] | 0.0573 | inf | 10 | w→ws→c [ws] | 0.0573→0.0573 | 0.0536* | 72 | w [w] | 0.0573 | 0.0614 | 10 |
| 137 | T137 | w→ws→c [c] | 0.0590→0.0590 | 0.0536* | 69 | w [w] | 0.0590 | inf | 9 | w [w] | 0.0590 | 0.0536* | 9 | w [w] | 0.0590 | inf | 9 | w [w] | 0.0590 | inf | 9 | w→ws→c [c] | 0.0590→0.0590 | 0.0536* | 69 | w [w] | 0.0590 | 0.0614 | 9 |
| 138 | T138 | w→ws→c [ws] | 0.0605→0.0605 | 0.0536* | 64 | w [w] | 0.0605 | inf | 7 | w [w] | 0.0605 | 0.0536* | 7 | w [w] | 0.0605 | inf | 7 | w [w] | 0.0605 | inf | 7 | w→ws→c [ws] | 0.0605→0.0605 | 0.0536* | 64 | w [w] | 0.0605 | 0.0615 | 7 |
| 139 | T139 | w→ws→c [ws] | 0.0621→0.0621 | 0.0536* | 71 | w [w] | 0.0621 | inf | 8 | w [w] | 0.0621 | 0.0536* | 8 | w [w] | 0.0621 | inf | 8 | w [w] | 0.0621 | inf | 8 | w→ws→c [ws] | 0.0621→0.0621 | 0.0536* | 71 | w [w] | 0.0621 | 0.0615* | 8 |
| 140 | T140 | w→ws→c [c] | 0.0638→0.0638 | 0.0536* | 71 | w [w] | 0.0638 | inf | 9 | w [w] | 0.0638 | 0.0536* | 9 | w [w] | 0.0638 | inf | 9 | w [w] | 0.0638 | inf | 9 | w→ws→c [c] | 0.0638→0.0638 | 0.0536* | 71 | w [w] | 0.0638 | 0.0615* | 9 |
| 141 | T141 | w→ws→c [ws] | 0.0647→0.0647 | 0.0536* | 66 | w [w] | 0.0647 | inf | 8 | w [w] | 0.0647 | 0.0536* | 8 | w [w] | 0.0647 | inf | 8 | w [w] | 0.0647 | inf | 8 | w→ws→c [ws] | 0.0647→0.0647 | 0.0536* | 66 | w [w] | 0.0647 | 0.0616* | 8 |
| 142 | T142 | w→ws→c [c] | 0.0671→0.0671 | 0.0537* | 67 | w [w] | 0.0671 | inf | 7 | w [w] | 0.0671 | 0.0537* | 7 | w [w] | 0.0671 | inf | 7 | w [w] | 0.0671 | inf | 7 | w→ws→c [c] | 0.0671→0.0671 | 0.0537* | 67 | w [w] | 0.0671 | 0.0616* | 7 |
| 143 | T143 | w→ws→c [c] | 0.0676→0.0676 | 0.0537* | 64 | w [w] | 0.0676 | inf | 7 | w [w] | 0.0676 | 0.0537* | 7 | w [w] | 0.0676 | inf | 7 | w [w] | 0.0676 | inf | 7 | w→ws→c [c] | 0.0676→0.0676 | 0.0537* | 64 | w [w] | 0.0676 | 0.0616* | 7 |
| 144 | T144 | w→ws→c [w] | 0.0699→0.0699 | 0.0537* | 64 | w [w] | 0.0699 | inf | 7 | w [w] | 0.0699 | 0.0537* | 7 | w [w] | 0.0699 | inf | 7 | w [w] | 0.0699 | inf | 7 | w→ws→c [w] | 0.0699→0.0699 | 0.0537* | 64 | w [w] | 0.0699 | 0.0616* | 7 |
| 145 | T145 | w→ws→c [ws] | 0.0712→0.0712 | 0.0537* | 69 | w [w] | 0.0712 | inf | 7 | w [w] | 0.0712 | 0.0537* | 7 | w [w] | 0.0712 | inf | 7 | w [w] | 0.0712 | inf | 7 | w→ws→c [ws] | 0.0712→0.0712 | 0.0537* | 69 | w [w] | 0.0712 | 0.0616* | 7 |
| 146 | T146 | w→ws→c [c] | 0.0729→0.0729 | 0.0537* | 67 | w [w] | 0.0729 | inf | 7 | w [w] | 0.0729 | 0.0537* | 7 | w [w] | 0.0729 | inf | 7 | w [w] | 0.0729 | inf | 7 | w→ws→c [c] | 0.0729→0.0729 | 0.0537* | 67 | w [w] | 0.0729 | 0.0616* | 7 |
| 147 | T147 | w→ws→c [c] | 0.0743→0.0743 | 0.0537* | 68 | w [w] | 0.0743 | inf | 7 | w [w] | 0.0743 | 0.0537* | 7 | w [w] | 0.0743 | inf | 7 | w [w] | 0.0743 | inf | 7 | w→ws→c [c] | 0.0743→0.0743 | 0.0537* | 68 | w [w] | 0.0743 | 0.0616* | 7 |
| 148 | T148 | w→ws→c [c] | 0.0761→0.0761 | 0.0537* | 64 | w [w] | 0.0761 | inf | 7 | w [w] | 0.0761 | 0.0537* | 7 | w [w] | 0.0761 | inf | 7 | w [w] | 0.0761 | inf | 7 | w→ws→c [c] | 0.0761→0.0761 | 0.0537* | 64 | w [w] | 0.0761 | 0.0616* | 7 |
| 149 | T149 | w→ws→c [c] | 0.0787→0.0787 | 0.0537* | 67 | w [w] | 0.0787 | inf | 8 | w [w] | 0.0787 | 0.0537* | 8 | w [w] | 0.0787 | inf | 8 | w [w] | 0.0787 | inf | 8 | w→ws→c [c] | 0.0787→0.0787 | 0.0537* | 67 | w [w] | 0.0787 | 0.0617* | 8 |
| 150 | T150 | w→ws→c [c] | 0.0789→0.0789 | 0.0538* | 65 | w [w] | 0.0789 | inf | 8 | w [w] | 0.0789 | 0.0538* | 8 | w [w] | 0.0789 | inf | 8 | w [w] | 0.0789 | inf | 8 | w→ws→c [c] | 0.0789→0.0789 | 0.0538* | 65 | w [w] | 0.0789 | 0.0617* | 8 |
| 151 | T151 | w→ws→c [c] | 0.0802→0.0802 | 0.0539* | 71 | w [w] | 0.0802 | inf | 9 | w [w] | 0.0802 | 0.0539* | 9 | w [w] | 0.0802 | inf | 9 | w [w] | 0.0802 | inf | 9 | w→ws→c [c] | 0.0802→0.0802 | 0.0539* | 71 | w [w] | 0.0802 | 0.0617* | 9 |
| 152 | T152 | w→ws→c [c] | 0.0819→0.0819 | 0.0546* | 66 | w [w] | 0.0819 | inf | 7 | w [w] | 0.0819 | 0.0546* | 7 | w [w] | 0.0819 | inf | 7 | w [w] | 0.0819 | inf | 7 | w→ws→c [c] | 0.0819→0.0819 | 0.0546* | 66 | w [w] | 0.0819 | 0.0617* | 7 |
| 153 | T153 | w→ws→c [w] | 0.0834→0.0834 | 0.0554* | 64 | w [w] | 0.0834 | inf | 7 | w [w] | 0.0834 | 0.0554* | 7 | w [w] | 0.0834 | inf | 7 | w [w] | 0.0834 | inf | 7 | w→ws→c [w] | 0.0834→0.0834 | 0.0554* | 64 | w [w] | 0.0834 | 0.0617* | 7 |
| 154 | T154 | w→ws→c [c] | 0.0848→0.0848 | 0.0566* | 66 | w [w] | 0.0848 | inf | 9 | w [w] | 0.0848 | 0.0566* | 9 | w [w] | 0.0848 | inf | 9 | w [w] | 0.0848 | inf | 9 | w→ws→c [c] | 0.0848→0.0848 | 0.0566* | 66 | w [w] | 0.0848 | 0.0617* | 9 |
| 155 | T155 | w→ws→c [c] | 0.0868→0.0868 | 0.0579* | 66 | w [w] | 0.0868 | inf | 7 | w [w] | 0.0868 | 0.0579* | 7 | w [w] | 0.0868 | inf | 7 | w [w] | 0.0868 | inf | 7 | w→ws→c [c] | 0.0868→0.0868 | 0.0579* | 66 | w [w] | 0.0868 | 0.0617* | 7 |
| 156 | T156 | w→ws→c [ws] | 0.0882→0.0882 | 0.0587* | 67 | w [w] | 0.0882 | inf | 9 | w [w] | 0.0882 | 0.0587* | 9 | w [w] | 0.0882 | inf | 9 | w [w] | 0.0882 | inf | 9 | w→ws→c [ws] | 0.0882→0.0882 | 0.0587* | 67 | w [w] | 0.0882 | 0.0618* | 9 |
| 157 | T157 | w→ws→c [c] | 0.0882→0.0882 | 0.0595* | 65 | w [w] | 0.0882 | inf | 7 | w [w] | 0.0882 | 0.0595* | 7 | w [w] | 0.0882 | inf | 7 | w [w] | 0.0882 | inf | 7 | w→ws→c [c] | 0.0882→0.0882 | 0.0595* | 65 | w [w] | 0.0882 | 0.0618* | 7 |
| 158 | T158 | w→ws→c [w] | 0.0905→0.0905 | 0.0595* | 63 | w [w] | 0.0905 | inf | 7 | w [w] | 0.0905 | 0.0595* | 7 | w [w] | 0.0905 | inf | 7 | w [w] | 0.0905 | inf | 7 | w→ws→c [w] | 0.0905→0.0905 | 0.0595* | 63 | w [w] | 0.0905 | 0.0618* | 7 |
| 159 | T159 | w→ws→c [w] | 0.0921→0.0921 | 0.0596* | 70 | w [w] | 0.0921 | inf | 8 | w [w] | 0.0921 | 0.0596* | 8 | w [w] | 0.0921 | inf | 8 | w [w] | 0.0921 | inf | 8 | w→ws→c [w] | 0.0921→0.0921 | 0.0596* | 70 | w [w] | 0.0921 | 0.0618* | 8 |
| 160 | T160 | w→ws→c [w] | 0.0922→0.0922 | 0.0597* | 66 | w [w] | 0.0922 | inf | 7 | w [w] | 0.0922 | 0.0597* | 7 | w [w] | 0.0922 | inf | 7 | w [w] | 0.0922 | inf | 7 | w→ws→c [w] | 0.0922→0.0922 | 0.0597* | 66 | w [w] | 0.0922 | 0.0619* | 7 |
| 161 | T161 | w→ws→c [ws] | 0.0934→0.0934 | 0.0598* | 63 | w [w] | 0.0934 | inf | 7 | w [w] | 0.0934 | 0.0598* | 7 | w [w] | 0.0934 | inf | 7 | w [w] | 0.0934 | inf | 7 | w→ws→c [ws] | 0.0934→0.0934 | 0.0598* | 63 | w [w] | 0.0934 | 0.0619* | 7 |
| 162 | T162 | w→ws→c [ws] | 0.0951→0.0951 | 0.0598* | 66 | w [w] | 0.0951 | inf | 7 | w [w] | 0.0951 | 0.0598* | 7 | w [w] | 0.0951 | inf | 7 | w [w] | 0.0951 | inf | 7 | w→ws→c [ws] | 0.0951→0.0951 | 0.0598* | 66 | w [w] | 0.0951 | 0.0620* | 7 |
| 163 | T163 | w→ws→c [w] | 0.0968→0.0968 | 0.0599* | 71 | w [w] | 0.0968 | inf | 9 | w [w] | 0.0968 | 0.0599* | 9 | w [w] | 0.0968 | inf | 9 | w [w] | 0.0968 | inf | 9 | w→ws→c [w] | 0.0968→0.0968 | 0.0599* | 71 | w [w] | 0.0968 | 0.0620* | 9 |
| 164 | T164 | w→ws→c [c] | 0.0976→0.0976 | 0.0600* | 66 | w [w] | 0.0976 | inf | 8 | w [w] | 0.0976 | 0.0600* | 8 | w [w] | 0.0976 | inf | 8 | w [w] | 0.0976 | inf | 8 | w→ws→c [c] | 0.0976→0.0976 | 0.0600* | 66 | w [w] | 0.0976 | 0.0620* | 8 |
| 165 | T165 | w→ws→c [ws] | 0.0991→0.0991 | 0.0601* | 70 | w [w] | 0.0991 | inf | 10 | w [w] | 0.0991 | 0.0601* | 10 | w [w] | 0.0991 | inf | 10 | w [w] | 0.0991 | inf | 10 | w→ws→c [ws] | 0.0991→0.0991 | 0.0600* | 70 | w [w] | 0.0991 | 0.0621* | 10 |
| 166 | T166 | w→ws→c [ws] | 0.1002→0.1002 | 0.0601* | 68 | w [w] | 0.1002 | inf | 8 | w [w] | 0.1002 | 0.0601* | 8 | w [w] | 0.1002 | inf | 8 | w [w] | 0.1002 | inf | 8 | w→ws→c [ws] | 0.1002→0.1002 | 0.0601* | 68 | w [w] | 0.1002 | 0.0621* | 8 |
| 167 | T167 | w→ws→c [ws] | 0.1014→0.1014 | 0.0601* | 71 | w [w] | 0.1014 | inf | 10 | w [w] | 0.1014 | 0.0601* | 10 | w [w] | 0.1014 | inf | 10 | w [w] | 0.1014 | inf | 10 | w→ws→c [ws] | 0.1014→0.1014 | 0.0601* | 71 | w [w] | 0.1014 | 0.0621* | 10 |
| 168 | T168 | w→ws→c [ws] | 0.1020→0.1020 | 0.0601* | 72 | w [w] | 0.1020 | inf | 9 | w [w] | 0.1020 | 0.0601* | 9 | w [w] | 0.1020 | inf | 9 | w [w] | 0.1020 | inf | 9 | w→ws→c [ws] | 0.1020→0.1020 | 0.0601* | 72 | w [w] | 0.1020 | 0.0621* | 9 |
| 169 | T169 | w→ws→c [c] | 0.1051→0.1051 | 0.0602* | 65 | w [w] | 0.1051 | inf | 8 | w [w] | 0.1051 | 0.0602* | 8 | w [w] | 0.1051 | inf | 8 | w [w] | 0.1051 | inf | 8 | w→ws→c [c] | 0.1051→0.1051 | 0.0602* | 65 | w [w] | 0.1051 | 0.0621* | 8 |
| 170 | T170 | w→ws→c [ws] | 0.1046→0.1046 | 0.0603* | 73 | w [w] | 0.1046 | inf | 10 | w [w] | 0.1046 | 0.0603* | 10 | w [w] | 0.1046 | inf | 10 | w [w] | 0.1046 | inf | 10 | w→ws→c [ws] | 0.1046→0.1046 | 0.0603* | 73 | w [w] | 0.1046 | 0.0622* | 10 |
| 171 | T171 | w→ws→c [w] | 0.1068→0.1068 | 0.0604* | 68 | w [w] | 0.1068 | inf | 10 | w [w] | 0.1068 | 0.0604* | 10 | w [w] | 0.1068 | inf | 10 | w [w] | 0.1068 | inf | 10 | w→ws→c [w] | 0.1068→0.1068 | 0.0604* | 68 | w [w] | 0.1068 | 0.0623* | 10 |
| 172 | T172 | w→ws→c [w] | 0.1069→0.1069 | 0.0605* | 66 | w [w] | 0.1069 | inf | 7 | w [w] | 0.1069 | 0.0605* | 7 | w [w] | 0.1069 | inf | 7 | w [w] | 0.1069 | inf | 7 | w→ws→c [w] | 0.1069→0.1069 | 0.0605* | 66 | w [w] | 0.1069 | 0.0623* | 7 |
| 173 | T173 | w→ws→c [w] | 0.1092→0.1092 | 0.0605* | 72 | w [w] | 0.1092 | inf | 10 | w [w] | 0.1092 | 0.0605* | 10 | w [w] | 0.1092 | inf | 10 | w [w] | 0.1092 | inf | 10 | w→ws→c [w] | 0.1092→0.1092 | 0.0605* | 72 | w [w] | 0.1092 | 0.0623* | 10 |
| 174 | T174 | w→ws→c [ws] | 0.1105→0.1105 | 0.0605* | 66 | w [w] | 0.1105 | inf | 7 | w [w] | 0.1105 | 0.0605* | 7 | w [w] | 0.1105 | inf | 7 | w [w] | 0.1105 | inf | 7 | w→ws→c [ws] | 0.1105→0.1105 | 0.0605* | 66 | w [w] | 0.1105 | 0.0624* | 7 |
| 175 | T175 | w→ws→c [c] | 0.1108→0.1108 | 0.0605* | 66 | w [w] | 0.1108 | inf | 7 | w [w] | 0.1108 | 0.0605* | 7 | w [w] | 0.1108 | inf | 7 | w [w] | 0.1108 | inf | 7 | w→ws→c [c] | 0.1108→0.1108 | 0.0605* | 66 | w [w] | 0.1108 | 0.0624* | 7 |
| 176 | T176 | w→ws→c [w] | 0.1125→0.1125 | 0.0605* | 74 | w [w] | 0.1125 | inf | 9 | w [w] | 0.1125 | 0.0605* | 9 | w [w] | 0.1125 | inf | 9 | w [w] | 0.1125 | inf | 9 | w→ws→c [w] | 0.1125→0.1125 | 0.0605* | 74 | w [w] | 0.1125 | 0.0625* | 9 |
| 177 | T177 | w→ws→c [c] | 0.1137→0.1137 | 0.0605* | 65 | w [w] | 0.1137 | inf | 7 | w [w] | 0.1137 | 0.0605* | 7 | w [w] | 0.1137 | inf | 7 | w [w] | 0.1137 | inf | 7 | w→ws→c [c] | 0.1137→0.1137 | 0.0605* | 65 | w [w] | 0.1137 | 0.0625* | 7 |
| 178 | T178 | w→ws→c [ws] | 0.1145→0.1145 | 0.0606* | 65 | w [w] | 0.1145 | inf | 7 | w [w] | 0.1145 | 0.0606* | 7 | w [w] | 0.1145 | inf | 7 | w [w] | 0.1145 | inf | 7 | w→ws→c [ws] | 0.1145→0.1145 | 0.0606* | 65 | w [w] | 0.1145 | 0.0625* | 7 |
| 179 | T179 | w→ws→c [w] | 0.1155→0.1155 | 0.0606* | 67 | w [w] | 0.1155 | inf | 7 | w [w] | 0.1155 | 0.0606* | 7 | w [w] | 0.1155 | inf | 7 | w [w] | 0.1155 | inf | 7 | w→ws→c [w] | 0.1155→0.1155 | 0.0606* | 67 | w [w] | 0.1155 | 0.0626* | 7 |
| 180 | T180 | w→ws→c [c] | 0.1173→0.1173 | 0.0606* | 66 | w [w] | 0.1173 | inf | 8 | w [w] | 0.1173 | 0.0606* | 8 | w [w] | 0.1173 | inf | 8 | w [w] | 0.1173 | inf | 8 | w→ws→c [c] | 0.1173→0.1173 | 0.0606* | 66 | w [w] | 0.1173 | 0.0626* | 8 |
| 181 | T181 | w→ws→c [w] | 0.1178→0.1178 | 0.0606* | 63 | w [w] | 0.1178 | inf | 7 | w [w] | 0.1178 | 0.0606* | 7 | w [w] | 0.1178 | inf | 7 | w [w] | 0.1178 | inf | 7 | w→ws→c [w] | 0.1178→0.1178 | 0.0606* | 63 | w [w] | 0.1178 | 0.0626* | 7 |
| 182 | T182 | w→ws→c [c] | 0.1190→0.1190 | 0.0607* | 64 | w [w] | 0.1190 | inf | 8 | w [w] | 0.1190 | 0.0607* | 8 | w [w] | 0.1190 | inf | 8 | w [w] | 0.1190 | inf | 8 | w→ws→c [c] | 0.1190→0.1190 | 0.0607* | 64 | w [w] | 0.1190 | 0.0626* | 8 |
| 183 | T183 | w→ws→c [c] | 0.1207→0.1207 | 0.0608* | 64 | w [w] | 0.1207 | inf | 8 | w [w] | 0.1207 | 0.0608* | 8 | w [w] | 0.1207 | inf | 8 | w [w] | 0.1207 | inf | 8 | w→ws→c [c] | 0.1207→0.1207 | 0.0608* | 64 | w [w] | 0.1207 | 0.0626* | 8 |
| 184 | T184 | w→ws→c [c] | 0.1212→0.1212 | 0.0608* | 64 | w [w] | 0.1212 | inf | 7 | w [w] | 0.1212 | 0.0608* | 7 | w [w] | 0.1212 | inf | 7 | w [w] | 0.1212 | inf | 7 | w→ws→c [c] | 0.1212→0.1212 | 0.0608* | 64 | w [w] | 0.1212 | 0.0631* | 7 |
| 185 | T185 | w→ws→c [w] | 0.1228→0.1228 | 0.0608* | 65 | w [w] | 0.1228 | inf | 7 | w [w] | 0.1228 | 0.0608* | 7 | w [w] | 0.1228 | inf | 7 | w [w] | 0.1228 | inf | 7 | w→ws→c [w] | 0.1228→0.1228 | 0.0608* | 65 | w [w] | 0.1228 | 0.0636* | 7 |
| 186 | T186 | w→ws→c [c] | 0.2288→0.2288 | 0.0609* | 184 | w [w] | 0.2288 | inf | 36 | w [w] | 0.2288 | 0.0609* | 36 | w [w] | 0.2288 | inf | 36 | w [w] | 0.2288 | inf | 36 | w→ws→c [c] | 0.2288→0.2288 | 0.0609* | 184 | w [w] | 0.2288 | 0.0649* | 36 |
| 187 | T187 | w→ws→c [w] | 0.2298→0.2298 | 0.0609* | 126 | w [w] | 0.2298 | inf | 24 | w [w] | 0.2298 | 0.0609* | 24 | w [w] | 0.2298 | inf | 24 | w [w] | 0.2298 | inf | 24 | w→ws→c [w] | 0.2298→0.2298 | 0.0609* | 126 | w [w] | 0.2298 | 0.0663* | 24 |
| 188 | T188 | w→ws→c [ws] | 0.2306→0.2306 | 0.0609* | 142 | w [w] | 0.2306 | inf | 27 | w [w] | 0.2306 | 0.0609* | 27 | w [w] | 0.2306 | inf | 27 | w [w] | 0.2306 | inf | 27 | w→ws→c [ws] | 0.2306→0.2306 | 0.0609* | 142 | w [w] | 0.2306 | 0.0677* | 27 |
| 189 | T189 | w→ws→c [ws] | 0.2303→0.2303 | 0.0610* | 136 | w [w] | 0.2303 | inf | 22 | w [w] | 0.2303 | 0.0610* | 22 | w [w] | 0.2303 | inf | 22 | w [w] | 0.2303 | inf | 22 | w→ws→c [ws] | 0.2303→0.2303 | 0.0610* | 136 | w [w] | 0.2303 | 0.0692* | 22 |
| 190 | T190 | w→ws→c [ws] | 0.2302→0.2302 | 0.0610* | 125 | w [w] | 0.2302 | inf | 21 | w [w] | 0.2302 | 0.0610* | 21 | w [w] | 0.2302 | inf | 21 | w [w] | 0.2302 | inf | 21 | w→ws→c [ws] | 0.2302→0.2302 | 0.0610* | 125 | w [w] | 0.2302 | 0.0696* | 21 |
| 191 | T191 | w→ws→c [ws] | 0.2314→0.2314 | 0.0610* | 134 | w [w] | 0.2314 | inf | 24 | w [w] | 0.2314 | 0.0610* | 24 | w [w] | 0.2314 | inf | 24 | w [w] | 0.2314 | inf | 24 | w→ws→c [ws] | 0.2314→0.2314 | 0.0610* | 134 | w [w] | 0.2314 | 0.0701* | 24 |
| 192 | T192 | w→ws→c [c] | 0.2305→0.2305 | 0.0610* | 131 | w [w] | 0.2305 | inf | 25 | w [w] | 0.2305 | 0.0610* | 25 | w [w] | 0.2305 | inf | 25 | w [w] | 0.2305 | inf | 25 | w→ws→c [c] | 0.2305→0.2305 | 0.0610* | 131 | w [w] | 0.2305 | 0.0709* | 25 |
| 193 | T193 | w→ws→c [w] | 0.2332→0.2332 | 0.0610* | 139 | w [w] | 0.2332 | inf | 24 | w [w] | 0.2332 | 0.0610* | 24 | w [w] | 0.2332 | inf | 24 | w [w] | 0.2332 | inf | 24 | w→ws→c [w] | 0.2332→0.2332 | 0.0610* | 139 | w [w] | 0.2332 | 0.0717* | 24 |
| 194 | T194 | w→ws→c [ws] | 0.2327→0.2327 | 0.0610* | 126 | w [w] | 0.2327 | inf | 22 | w [w] | 0.2327 | 0.0610* | 22 | w [w] | 0.2327 | inf | 22 | w [w] | 0.2327 | inf | 22 | w→ws→c [ws] | 0.2327→0.2327 | 0.0610* | 126 | w [w] | 0.2327 | 0.0727* | 22 |
| 195 | T195 | w→ws→c [w] | 0.2351→0.2351 | 0.0610* | 137 | w [w] | 0.2351 | inf | 26 | w [w] | 0.2351 | 0.0610* | 26 | w [w] | 0.2351 | inf | 26 | w [w] | 0.2351 | inf | 26 | w→ws→c [w] | 0.2351→0.2351 | 0.0610* | 137 | w [w] | 0.2351 | 0.0738* | 26 |
| 196 | T196 | w→ws→c [c] | 0.2341→0.2341 | 0.0610* | 140 | w [w] | 0.2341 | inf | 25 | w [w] | 0.2341 | 0.0610* | 25 | w [w] | 0.2341 | inf | 25 | w [w] | 0.2341 | inf | 25 | w→ws→c [c] | 0.2341→0.2341 | 0.0610* | 140 | w [w] | 0.2341 | 0.0747* | 25 |
| 197 | T197 | w→ws→c [w] | 0.2348→0.2348 | 0.0610* | 135 | w [w] | 0.2348 | inf | 22 | w [w] | 0.2348 | 0.0610* | 22 | w [w] | 0.2348 | inf | 22 | w [w] | 0.2348 | inf | 22 | w→ws→c [w] | 0.2348→0.2348 | 0.0610* | 135 | w [w] | 0.2348 | 0.0756* | 22 |
| 198 | T198 | w→ws→c [c] | 0.2367→0.2367 | 0.0611* | 134 | w [w] | 0.2367 | inf | 25 | w [w] | 0.2367 | 0.0611* | 25 | w [w] | 0.2367 | inf | 25 | w [w] | 0.2367 | inf | 25 | w→ws→c [c] | 0.2367→0.2367 | 0.0611* | 134 | w [w] | 0.2367 | 0.0766* | 25 |
| 199 | T199 | w→ws→c [w] | 0.2366→0.2366 | 0.0612* | 133 | w [w] | 0.2366 | inf | 24 | w [w] | 0.2366 | 0.0612* | 24 | w [w] | 0.2366 | inf | 24 | w [w] | 0.2366 | inf | 24 | w→ws→c [w] | 0.2366→0.2366 | 0.0612* | 133 | w [w] | 0.2366 | 0.0776* | 24 |
| 200 | T200 | w→ws→c [ws] | 0.2364→0.2364 | 0.0612* | 129 | w [w] | 0.2364 | inf | 22 | w [w] | 0.2364 | 0.0612* | 22 | w [w] | 0.2364 | inf | 22 | w [w] | 0.2364 | inf | 22 | w→ws→c [ws] | 0.2364→0.2364 | 0.0612* | 129 | w [w] | 0.2364 | 0.0787* | 22 |
| 201 | T201 | w→ws→c [w] | 0.2378→0.2378 | 0.0612* | 139 | w [w] | 0.2378 | inf | 26 | w [w] | 0.2378 | 0.0612* | 26 | w [w] | 0.2378 | inf | 26 | w [w] | 0.2378 | inf | 26 | w→ws→c [w] | 0.2378→0.2378 | 0.0612* | 139 | w [w] | 0.2378 | 0.0798* | 26 |
| 202 | T202 | w→ws→c [ws] | 0.2370→0.2370 | 0.0612* | 134 | w [w] | 0.2370 | inf | 20 | w [w] | 0.2370 | 0.0612* | 20 | w [w] | 0.2370 | inf | 20 | w [w] | 0.2370 | inf | 20 | w→ws→c [ws] | 0.2370→0.2370 | 0.0612* | 134 | w [w] | 0.2370 | 0.0803* | 20 |
| 203 | T203 | w→ws→c [ws] | 0.2391→0.2391 | 0.0613* | 139 | w [w] | 0.2391 | inf | 24 | w [w] | 0.2391 | 0.0613* | 24 | w [w] | 0.2391 | inf | 24 | w [w] | 0.2391 | inf | 24 | w→ws→c [ws] | 0.2391→0.2391 | 0.0613* | 139 | w [w] | 0.2391 | 0.0809* | 24 |
| 204 | T204 | w→ws→c [c] | 0.2388→0.2388 | 0.0613* | 138 | w [w] | 0.2388 | inf | 26 | w [w] | 0.2388 | 0.0613* | 26 | w [w] | 0.2388 | inf | 26 | w [w] | 0.2388 | inf | 26 | w→ws→c [c] | 0.2388→0.2388 | 0.0613* | 138 | w [w] | 0.2388 | 0.0823* | 26 |
| 205 | T205 | w→ws→c [w] | 0.2374→0.2374 | 0.0613* | 136 | w [w] | 0.2374 | inf | 25 | w [w] | 0.2374 | 0.0613* | 25 | w [w] | 0.2374 | inf | 25 | w [w] | 0.2374 | inf | 25 | w→ws→c [w] | 0.2374→0.2374 | 0.0613* | 136 | w [w] | 0.2374 | 0.0838* | 25 |
| 206 | T206 | w→ws→c [ws] | 0.2392→0.2392 | 0.0613* | 136 | w [w] | 0.2392 | inf | 25 | w [w] | 0.2392 | 0.0613* | 25 | w [w] | 0.2392 | inf | 25 | w [w] | 0.2392 | inf | 25 | w→ws→c [ws] | 0.2392→0.2392 | 0.0613* | 136 | w [w] | 0.2392 | 0.0842* | 25 |
| 207 | T207 | w→ws→c [c] | 0.2414→0.2414 | 0.0613* | 144 | w [w] | 0.2414 | inf | 28 | w [w] | 0.2414 | 0.0613* | 28 | w [w] | 0.2414 | inf | 28 | w [w] | 0.2414 | inf | 28 | w→ws→c [c] | 0.2414→0.2414 | 0.0613* | 144 | w [w] | 0.2414 | 0.0845* | 28 |
| 208 | T208 | w→ws→c [w] | 0.2406→0.2406 | 0.0613* | 133 | w [w] | 0.2406 | inf | 26 | w [w] | 0.2406 | 0.0613* | 26 | w [w] | 0.2406 | inf | 26 | w [w] | 0.2406 | inf | 26 | w→ws→c [w] | 0.2406→0.2406 | 0.0613* | 133 | w [w] | 0.2406 | 0.0860* | 26 |
| 209 | T209 | w→ws→c [w] | 0.2397→0.2397 | 0.0613* | 127 | w [w] | 0.2397 | inf | 21 | w [w] | 0.2397 | 0.0613* | 21 | w [w] | 0.2397 | inf | 21 | w [w] | 0.2397 | inf | 21 | w→ws→c [w] | 0.2397→0.2397 | 0.0613* | 127 | w [w] | 0.2397 | 0.0874* | 21 |
| 210 | T210 | w→ws→c [w] | 0.2417→0.2417 | 0.0613* | 129 | w [w] | 0.2417 | inf | 22 | w [w] | 0.2417 | 0.0613* | 22 | w [w] | 0.2417 | inf | 22 | w [w] | 0.2417 | inf | 22 | w→ws→c [w] | 0.2417→0.2417 | 0.0613* | 129 | w [w] | 0.2417 | 0.0882* | 22 |
| 211 | T211 | w→ws→c [w] | 0.2419→0.2419 | 0.0613* | 134 | w [w] | 0.2419 | inf | 24 | w [w] | 0.2419 | 0.0613* | 24 | w [w] | 0.2419 | inf | 24 | w [w] | 0.2419 | inf | 24 | w→ws→c [w] | 0.2419→0.2419 | 0.0613* | 134 | w [w] | 0.2419 | 0.0890* | 24 |
| 212 | T212 | w→ws→c [ws] | 0.2413→0.2413 | 0.0613* | 133 | w [w] | 0.2413 | inf | 26 | w [w] | 0.2413 | 0.0613* | 26 | w [w] | 0.2413 | inf | 26 | w [w] | 0.2413 | inf | 26 | w→ws→c [ws] | 0.2413→0.2413 | 0.0613* | 133 | w [w] | 0.2413 | 0.0901* | 26 |
| 213 | T213 | w→ws→c [c] | 0.2430→0.2430 | 0.0614* | 127 | w [w] | 0.2430 | inf | 21 | w [w] | 0.2430 | 0.0614* | 21 | w [w] | 0.2430 | inf | 21 | w [w] | 0.2430 | inf | 21 | w→ws→c [c] | 0.2430→0.2430 | 0.0614* | 127 | w [w] | 0.2430 | 0.0911* | 21 |
| 214 | T214 | w→ws→c [w] | 0.2425→0.2425 | 0.0614* | 133 | w [w] | 0.2425 | inf | 25 | w [w] | 0.2425 | 0.0614* | 25 | w [w] | 0.2425 | inf | 25 | w [w] | 0.2425 | inf | 25 | w→ws→c [w] | 0.2425→0.2425 | 0.0614* | 133 | w [w] | 0.2425 | 0.0920* | 25 |
| 215 | T215 | w→ws→c [w] | 0.2449→0.2449 | 0.0614* | 140 | w [w] | 0.2449 | inf | 26 | w [w] | 0.2449 | 0.0614* | 26 | w [w] | 0.2449 | inf | 26 | w [w] | 0.2449 | inf | 26 | w→ws→c [w] | 0.2449→0.2449 | 0.0614* | 140 | w [w] | 0.2449 | 0.0928* | 26 |
| 216 | T216 | w→ws→c [ws] | 0.2445→0.2445 | 0.0614* | 134 | w [w] | 0.2445 | inf | 23 | w [w] | 0.2445 | 0.0614* | 23 | w [w] | 0.2445 | inf | 23 | w [w] | 0.2445 | inf | 23 | w→ws→c [ws] | 0.2445→0.2445 | 0.0614* | 134 | w [w] | 0.2445 | 0.0940* | 23 |
| 217 | T217 | w→ws→c [ws] | 0.2450→0.2450 | 0.0614* | 130 | w [w] | 0.2450 | inf | 23 | w [w] | 0.2450 | 0.0614* | 23 | w [w] | 0.2450 | inf | 23 | w [w] | 0.2450 | inf | 23 | w→ws→c [ws] | 0.2450→0.2450 | 0.0614* | 130 | w [w] | 0.2450 | 0.0951* | 23 |
| 218 | T218 | w→ws→c [c] | 0.2468→0.2468 | 0.0615* | 135 | w [w] | 0.2468 | inf | 26 | w [w] | 0.2468 | 0.0615* | 26 | w [w] | 0.2468 | inf | 26 | w [w] | 0.2468 | inf | 26 | w→ws→c [c] | 0.2468→0.2468 | 0.0615* | 135 | w [w] | 0.2468 | 0.0967* | 26 |
| 219 | T219 | w→ws→c [ws] | 0.2466→0.2466 | 0.0615* | 137 | w [w] | 0.2466 | inf | 25 | w [w] | 0.2466 | 0.0615* | 25 | w [w] | 0.2466 | inf | 25 | w [w] | 0.2466 | inf | 25 | w→ws→c [ws] | 0.2466→0.2466 | 0.0615* | 137 | w [w] | 0.2466 | 0.0983* | 25 |
| 220 | T220 | w→ws→c [c] | 0.2480→0.2480 | 0.0615* | 138 | w [w] | 0.2480 | inf | 24 | w [w] | 0.2480 | 0.0615* | 24 | w [w] | 0.2480 | inf | 24 | w [w] | 0.2480 | inf | 24 | w→ws→c [c] | 0.2480→0.2480 | 0.0615* | 138 | w [w] | 0.2480 | 0.0985* | 24 |
| 221 | T221 | w→ws→c [w] | 0.2461→0.2461 | 0.0616* | 129 | w [w] | 0.2461 | inf | 23 | w [w] | 0.2461 | 0.0616* | 23 | w [w] | 0.2461 | inf | 23 | w [w] | 0.2461 | inf | 23 | w→ws→c [w] | 0.2461→0.2461 | 0.0616* | 129 | w [w] | 0.2461 | 0.0986* | 23 |
| 222 | T222 | w→ws→c [ws] | 0.2474→0.2474 | 0.0616* | 129 | w [w] | 0.2474 | inf | 24 | w [w] | 0.2474 | 0.0616* | 24 | w [w] | 0.2474 | inf | 24 | w [w] | 0.2474 | inf | 24 | w→ws→c [ws] | 0.2474→0.2474 | 0.0616* | 129 | w [w] | 0.2474 | 0.0994* | 24 |
| 223 | T223 | w→ws→c [w] | 0.2474→0.2474 | 0.0616* | 135 | w [w] | 0.2474 | inf | 25 | w [w] | 0.2474 | 0.0616* | 25 | w [w] | 0.2474 | inf | 25 | w [w] | 0.2474 | inf | 25 | w→ws→c [w] | 0.2474→0.2474 | 0.0616* | 135 | w [w] | 0.2474 | 0.1003* | 25 |
| 224 | T224 | w→ws→c [ws] | 0.2481→0.2481 | 0.0616* | 126 | w [w] | 0.2481 | inf | 21 | w [w] | 0.2481 | 0.0616* | 21 | w [w] | 0.2481 | inf | 21 | w [w] | 0.2481 | inf | 21 | w→ws→c [ws] | 0.2481→0.2481 | 0.0616* | 126 | w [w] | 0.2481 | 0.1013* | 21 |
| 225 | T225 | w→ws→c [w] | 0.2501→0.2501 | 0.0616* | 130 | w [w] | 0.2501 | inf | 22 | w [w] | 0.2501 | 0.0616* | 22 | w [w] | 0.2501 | inf | 22 | w [w] | 0.2501 | inf | 22 | w→ws→c [w] | 0.2501→0.2501 | 0.0616* | 130 | w [w] | 0.2501 | 0.1023* | 22 |
| 226 | T226 | w→ws→c [w] | 0.2505→0.2505 | 0.0616* | 128 | w [w] | 0.2505 | inf | 22 | w [w] | 0.2505 | 0.0616* | 22 | w [w] | 0.2505 | inf | 22 | w [w] | 0.2505 | inf | 22 | w→ws→c [w] | 0.2505→0.2505 | 0.0616* | 128 | w [w] | 0.2505 | 0.1033* | 22 |
| 227 | T227 | w→ws→c [ws] | 0.2495→0.2495 | 0.0616* | 132 | w [w] | 0.2495 | inf | 25 | w [w] | 0.2495 | 0.0616* | 25 | w [w] | 0.2495 | inf | 25 | w [w] | 0.2495 | inf | 25 | w→ws→c [ws] | 0.2495→0.2495 | 0.0616* | 132 | w [w] | 0.2495 | 0.1042* | 25 |
| 228 | T228 | w→ws→c [w] | 0.2513→0.2513 | 0.0616* | 136 | w [w] | 0.2513 | inf | 25 | w [w] | 0.2513 | 0.0616* | 25 | w [w] | 0.2513 | inf | 25 | w [w] | 0.2513 | inf | 25 | w→ws→c [w] | 0.2513→0.2513 | 0.0616* | 136 | w [w] | 0.2513 | 0.1051* | 25 |
| 229 | T229 | w→ws→c [w] | 0.2501→0.2501 | 0.0617* | 131 | w [w] | 0.2501 | inf | 25 | w [w] | 0.2501 | 0.0617* | 25 | w [w] | 0.2501 | inf | 25 | w [w] | 0.2501 | inf | 25 | w→ws→c [w] | 0.2501→0.2501 | 0.0617* | 131 | w [w] | 0.2501 | 0.1060* | 25 |
| 230 | T230 | w→ws→c [w] | 0.2515→0.2515 | 0.0617* | 125 | w [w] | 0.2515 | inf | 22 | w [w] | 0.2515 | 0.0617* | 22 | w [w] | 0.2515 | inf | 22 | w [w] | 0.2515 | inf | 22 | w→ws→c [w] | 0.2515→0.2515 | 0.0617* | 125 | w [w] | 0.2515 | 0.1073* | 22 |
| 231 | T231 | w→ws→c [w] | 0.2533→0.2533 | 0.0617* | 132 | w [w] | 0.2533 | inf | 25 | w [w] | 0.2533 | 0.0617* | 25 | w [w] | 0.2533 | inf | 25 | w [w] | 0.2533 | inf | 25 | w→ws→c [w] | 0.2533→0.2533 | 0.0617* | 132 | w [w] | 0.2533 | 0.1085* | 25 |
| 232 | T232 | w→ws→c [ws] | 0.2530→0.2530 | 0.0617* | 137 | w [w] | 0.2530 | inf | 26 | w [w] | 0.2530 | 0.0617* | 26 | w [w] | 0.2530 | inf | 26 | w [w] | 0.2530 | inf | 26 | w→ws→c [ws] | 0.2530→0.2530 | 0.0617* | 137 | w [w] | 0.2530 | 0.1093* | 26 |
| 233 | T233 | w→ws→c [w] | 0.2531→0.2531 | 0.0617* | 128 | w [w] | 0.2531 | inf | 24 | w [w] | 0.2531 | 0.0617* | 24 | w [w] | 0.2531 | inf | 24 | w [w] | 0.2531 | inf | 24 | w→ws→c [w] | 0.2531→0.2531 | 0.0617* | 128 | w [w] | 0.2531 | 0.1102* | 24 |
| 234 | T234 | w→ws→c [w] | 0.2542→0.2542 | 0.0617* | 139 | w [w] | 0.2542 | inf | 27 | w [w] | 0.2542 | 0.0617* | 27 | w [w] | 0.2542 | inf | 27 | w [w] | 0.2542 | inf | 27 | w→ws→c [w] | 0.2542→0.2542 | 0.0617* | 139 | w [w] | 0.2542 | 0.1103* | 27 |
| 235 | T235 | w→ws→c [ws] | 0.2537→0.2537 | 0.0617* | 135 | w [w] | 0.2537 | inf | 24 | w [w] | 0.2537 | 0.0617* | 24 | w [w] | 0.2537 | inf | 24 | w [w] | 0.2537 | inf | 24 | w→ws→c [ws] | 0.2537→0.2537 | 0.0617* | 135 | w [w] | 0.2537 | 0.1103* | 24 |
| 236 | T236 | w→ws→c [ws] | 0.2551→0.2551 | 0.0618* | 130 | w [w] | 0.2551 | inf | 23 | w [w] | 0.2551 | 0.0618* | 23 | w [w] | 0.2551 | inf | 23 | w [w] | 0.2551 | inf | 23 | w→ws→c [ws] | 0.2551→0.2551 | 0.0618* | 130 | w [w] | 0.2551 | 0.1117* | 23 |
| 237 | T237 | w→ws→c [ws] | 0.2567→0.2567 | 0.0618* | 134 | w [w] | 0.2567 | inf | 26 | w [w] | 0.2567 | 0.0618* | 26 | w [w] | 0.2567 | inf | 26 | w [w] | 0.2567 | inf | 26 | w→ws→c [ws] | 0.2567→0.2567 | 0.0618* | 134 | w [w] | 0.2567 | 0.1131* | 26 |
| 238 | T238 | w→ws→c [w] | 0.2559→0.2559 | 0.0618* | 128 | w [w] | 0.2559 | inf | 23 | w [w] | 0.2559 | 0.0618* | 23 | w [w] | 0.2559 | inf | 23 | w [w] | 0.2559 | inf | 23 | w→ws→c [w] | 0.2559→0.2559 | 0.0618* | 128 | w [w] | 0.2559 | 0.1141* | 23 |
| 239 | T239 | w→ws→c [ws] | 0.2567→0.2567 | 0.0618* | 125 | w [w] | 0.2567 | inf | 22 | w [w] | 0.2567 | 0.0618* | 22 | w [w] | 0.2567 | inf | 22 | w [w] | 0.2567 | inf | 22 | w→ws→c [ws] | 0.2567→0.2567 | 0.0618* | 125 | w [w] | 0.2567 | 0.1151* | 22 |
| 240 | T240 | w→ws→c [c] | 0.2571→0.2571 | 0.0619* | 131 | w [w] | 0.2571 | inf | 24 | w [w] | 0.2571 | 0.0619* | 24 | w [w] | 0.2571 | inf | 24 | w [w] | 0.2571 | inf | 24 | w→ws→c [c] | 0.2571→0.2571 | 0.0619* | 131 | w [w] | 0.2571 | 0.1151* | 24 |
| 241 | T241 | w→ws→c [ws] | 0.2573→0.2573 | 0.0619* | 134 | w [w] | 0.2573 | inf | 23 | w [w] | 0.2573 | 0.0619* | 23 | w [w] | 0.2573 | inf | 23 | w [w] | 0.2573 | inf | 23 | w→ws→c [ws] | 0.2573→0.2573 | 0.0619* | 134 | w [w] | 0.2573 | 0.1152* | 23 |
| 242 | T242 | w→ws→c [w] | 0.2583→0.2583 | 0.0620* | 131 | w [w] | 0.2583 | inf | 24 | w [w] | 0.2583 | 0.0620* | 24 | w [w] | 0.2583 | inf | 24 | w [w] | 0.2583 | inf | 24 | w→ws→c [w] | 0.2583→0.2583 | 0.0620* | 131 | w [w] | 0.2583 | 0.1160* | 24 |
| 243 | T243 | w→ws→c [c] | 0.2591→0.2591 | 0.0620* | 134 | w [w] | 0.2591 | inf | 25 | w [w] | 0.2591 | 0.0620* | 25 | w [w] | 0.2591 | inf | 25 | w [w] | 0.2591 | inf | 25 | w→ws→c [c] | 0.2591→0.2591 | 0.0620* | 134 | w [w] | 0.2591 | 0.1168* | 25 |
| 244 | T244 | w→ws→c [ws] | 0.2599→0.2599 | 0.0620* | 136 | w [w] | 0.2599 | inf | 26 | w [w] | 0.2599 | 0.0620* | 26 | w [w] | 0.2599 | inf | 26 | w [w] | 0.2599 | inf | 26 | w→ws→c [ws] | 0.2599→0.2599 | 0.0620* | 136 | w [w] | 0.2599 | 0.1179* | 26 |
| 245 | T245 | w→ws→c [c] | 0.2593→0.2593 | 0.0621* | 129 | w [w] | 0.2593 | inf | 22 | w [w] | 0.2593 | 0.0621* | 22 | w [w] | 0.2593 | inf | 22 | w [w] | 0.2593 | inf | 22 | w→ws→c [c] | 0.2593→0.2593 | 0.0621* | 129 | w [w] | 0.2593 | 0.1189* | 22 |
| 246 | T246 | w→ws→c [w] | 0.2591→0.2591 | 0.0621* | 133 | w [w] | 0.2591 | inf | 25 | w [w] | 0.2591 | 0.0621* | 25 | w [w] | 0.2591 | inf | 25 | w [w] | 0.2591 | inf | 25 | w→ws→c [w] | 0.2591→0.2591 | 0.0621* | 133 | w [w] | 0.2591 | 0.1199* | 25 |
| 247 | T247 | w→ws→c [ws] | 0.2597→0.2597 | 0.0621* | 130 | w [w] | 0.2597 | inf | 23 | w [w] | 0.2597 | 0.0621* | 23 | w [w] | 0.2597 | inf | 23 | w [w] | 0.2597 | inf | 23 | w→ws→c [ws] | 0.2597→0.2597 | 0.0621* | 130 | w [w] | 0.2597 | 0.1210* | 23 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound |
|---|---|---|---|---|---|---|---|
| 48 | — | — | — | — | — | — | — |
| 49 | — | — | — | — | — | — | — |
| 50 | — | — | — | — | — | — | — |
| 51 | — | — | — | — | — | — | — |
| 52 | — | — | — | — | — | — | — |
| 85 | — | — | — | — | — | — | — |
| 86 | — | — | — | — | — | — | — |
| 87 | FLOOR_HIT, P_UNC | FLOOR_HIT, P_UNC | FLOOR_HIT, P_UNC | FLOOR_HIT, P_UNC | FLOOR_HIT, P_UNC | CONSTRAINT_ACTIVE, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE | CONSTRAINT_ACTIVE, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE |
| 88 | — | — | — | — | — | S_RESEED | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 89 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 90 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 91 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 92 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 93 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 94 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 95 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 96 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 97 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 98 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 99 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 100 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 101 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 102 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 103 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 104 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 105 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 106 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 107 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 108 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 109 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 110 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 111 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 112 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 113 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 114 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 115 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 116 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 117 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 118 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 119 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 120 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 121 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 122 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 123 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 124 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 125 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 126 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 127 | — | — | — | — | — | — | CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, P_UNC, RESOLUTION_NOT_POSITIVE, S_RWP_OUTLIER |
| 134 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | — |
| 135 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | — |
| 136 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | — |
| 137 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | — |
| 138 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | — |
| 139 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 140 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 141 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 142 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 143 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 144 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 145 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 146 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 147 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 148 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 149 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 150 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 151 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 152 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 153 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 154 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 155 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 156 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 157 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 158 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 159 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 160 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 161 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 162 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 163 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 164 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 165 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 166 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 167 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 168 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 169 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 170 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 171 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 172 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 173 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 174 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 175 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 176 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 177 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 178 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 179 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 180 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 181 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 182 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 183 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 184 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RESEED, S_RWP_OUTLIER | S_RWP_OUTLIER |
| 185 | S_RWP_OUTLIER | — | S_RWP_OUTLIER | — | — | S_RWP_OUTLIER | S_RWP_OUTLIER |
| 186 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 187 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 188 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 189 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 190 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 191 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 192 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 193 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 194 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 195 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 196 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 197 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 198 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 199 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 200 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 201 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 202 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 203 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 204 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 205 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 206 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 207 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 208 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 209 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 210 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 211 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 212 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 213 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 214 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 215 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 216 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 217 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 218 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 219 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 220 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 221 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 222 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 223 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 224 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 225 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 226 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 227 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 228 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 229 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 230 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 231 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 232 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 233 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 234 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 235 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 236 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 237 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 238 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 239 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 240 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 241 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 242 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 243 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 244 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 245 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 246 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |
| 247 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT, S_RWP_OUTLIER |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, the arm's pair, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | status_maxiter vs on: worst |Δ|/esd (path) | status_runaway vs on: worst |Δ|/esd (path) | on_nobound vs on: worst |Δ|/esd (path) | off_nobound vs on: worst |Δ|/esd (path) | status_maxiter vs status | status_runaway vs status | off_nobound vs off | on vs ref | status vs ref | off vs ref | status_maxiter vs ref | status_runaway vs ref | on_nobound vs ref | off_nobound vs ref | on vs truth | status vs truth | off vs truth | status_maxiter vs truth | status_runaway vs truth | on_nobound vs truth | off_nobound vs truth |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000475 (instrument.background.c3) | 0.000475 (instrument.background.c3) | 0.000475 (instrument.background.c3) | 0.000475 (instrument.background.c3) | 0.000475 (instrument.background.c3) | 0.000475 (instrument.background.c3) | 0.000475 (instrument.background.c3) | 2.7 (instrument.background.c0) | 2.7 (instrument.background.c0) | 2.7 (instrument.background.c0) | 2.7 (instrument.background.c0) | 2.7 (instrument.background.c0) | 2.7 (instrument.background.c0) | 2.7 (instrument.background.c0) |
| 49 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000124 (instrument.background.c2) | 0.000124 (instrument.background.c2) | 0.000124 (instrument.background.c2) | 0.000124 (instrument.background.c2) | 0.000124 (instrument.background.c2) | 0.000124 (instrument.background.c2) | 0.000124 (instrument.background.c2) | 2.2 (instrument.background.c0) | 2.2 (instrument.background.c0) | 2.2 (instrument.background.c0) | 2.2 (instrument.background.c0) | 2.2 (instrument.background.c0) | 2.2 (instrument.background.c0) | 2.2 (instrument.background.c0) |
| 50 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7.68e-05 (instrument.profile.y) | 7.68e-05 (instrument.profile.y) | 7.68e-05 (instrument.profile.y) | 7.68e-05 (instrument.profile.y) | 7.68e-05 (instrument.profile.y) | 7.68e-05 (instrument.profile.y) | 7.68e-05 (instrument.profile.y) | 0.971 (instrument.background.c0) | 0.971 (instrument.background.c0) | 0.971 (instrument.background.c0) | 0.971 (instrument.background.c0) | 0.971 (instrument.background.c0) | 0.971 (instrument.background.c0) | 0.971 (instrument.background.c0) |
| 51 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000772 (instrument.profile.x) | 0.000772 (instrument.profile.x) | 0.000772 (instrument.profile.x) | 0.000772 (instrument.profile.x) | 0.000772 (instrument.profile.x) | 0.000772 (instrument.profile.x) | 0.000772 (instrument.profile.x) | 1.98 (instrument.background.c0) | 1.98 (instrument.background.c0) | 1.98 (instrument.background.c0) | 1.98 (instrument.background.c0) | 1.98 (instrument.background.c0) | 1.98 (instrument.background.c0) | 1.98 (instrument.background.c0) |
| 52 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000237 (instrument.background.c2) | 0.000237 (instrument.background.c2) | 0.000237 (instrument.background.c2) | 0.000237 (instrument.background.c2) | 0.000237 (instrument.background.c2) | 0.000237 (instrument.background.c2) | 0.000237 (instrument.background.c2) | 2.63 (instrument.background.c0) | 2.63 (instrument.background.c0) | 2.63 (instrument.background.c0) | 2.63 (instrument.background.c0) | 2.63 (instrument.background.c0) | 2.63 (instrument.background.c0) | 2.63 (instrument.background.c0) |
| 85 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000425 (instrument.profile.y) | 0.000425 (instrument.profile.y) | 0.000425 (instrument.profile.y) | 0.000425 (instrument.profile.y) | 0.000425 (instrument.profile.y) | 0.000425 (instrument.profile.y) | 0.000425 (instrument.profile.y) | 1.14 (instrument.zero_shift) | 1.14 (instrument.zero_shift) | 1.14 (instrument.zero_shift) | 1.14 (instrument.zero_shift) | 1.14 (instrument.zero_shift) | 1.14 (instrument.zero_shift) | 1.14 (instrument.zero_shift) |
| 86 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000201 (instrument.profile.y) | 0.000201 (instrument.profile.y) | 0.000201 (instrument.profile.y) | 0.000201 (instrument.profile.y) | 0.000201 (instrument.profile.y) | 0.000201 (instrument.profile.y) | 0.000201 (instrument.profile.y) | 0.882 (phases.0.scale) | 0.882 (phases.0.scale) | 0.882 (phases.0.scale) | 0.882 (phases.0.scale) | 0.882 (phases.0.scale) | 0.882 (phases.0.scale) | 0.882 (phases.0.scale) |
| 87 | 0 | 0 | 0 | 0 | 6.06 (instrument.zero_shift) | 6.06 (instrument.zero_shift) | 0 | 0 | 6.06 (instrument.zero_shift) | 1.26 (instrument.zero_shift) ≠2 no-esd (phases.0.cell.b, phases.0.cell.c) | 1.26 (instrument.zero_shift) ≠2 no-esd (phases.0.cell.b, phases.0.cell.c) | 1.26 (instrument.zero_shift) ≠2 no-esd (phases.0.cell.b, phases.0.cell.c) | 1.26 (instrument.zero_shift) ≠2 no-esd (phases.0.cell.b, phases.0.cell.c) | 1.26 (instrument.zero_shift) ≠2 no-esd (phases.0.cell.b, phases.0.cell.c) | 7.47 (instrument.zero_shift) ≠2 no-esd (phases.0.cell.b, phases.0.cell.c) | 7.47 (instrument.zero_shift) ≠2 no-esd (phases.0.cell.b, phases.0.cell.c) | 1.54 (instrument.background.c0) | 1.54 (instrument.background.c0) | 1.54 (instrument.background.c0) | 1.54 (instrument.background.c0) | 1.54 (instrument.background.c0) | 6.06 (instrument.zero_shift) | 6.06 (instrument.zero_shift) |
| 88 | 0 | 0 | 0 | 0 | 0.000165 (instrument.background.c2) | 414 (phases.0.scale) +1 | 0 | 0 | 414 (phases.0.scale) +1 | 0.000165 (instrument.background.c2) | 0.000165 (instrument.background.c2) | 0.000165 (instrument.background.c2) | 0.000165 (instrument.background.c2) | 0.000165 (instrument.background.c2) | 0 | 414 (phases.0.scale) +1 | 0.828 (instrument.background.c0) | 0.828 (instrument.background.c0) | 0.828 (instrument.background.c0) | 0.828 (instrument.background.c0) | 0.828 (instrument.background.c0) | 0.828 (instrument.background.c0) | 40.2 (phases.0.scale) |
| 89 | 0 | 0 | 0 | 0 | 4.9e-07 (instrument.profile.y) | 421 (phases.0.scale) +1 | 0 | 0 | 421 (phases.0.scale) +1 | 0.000197 (instrument.background.c0) | 0.000197 (instrument.background.c0) | 0.000197 (instrument.background.c0) | 0.000197 (instrument.background.c0) | 0.000197 (instrument.background.c0) | 0.000197 (instrument.background.c0) | 421 (phases.0.scale) +1 | 3.47 (instrument.background.c0) | 3.47 (instrument.background.c0) | 3.47 (instrument.background.c0) | 3.47 (instrument.background.c0) | 3.47 (instrument.background.c0) | 3.47 (instrument.background.c0) | 41.2 (phases.0.scale) |
| 90 | 0 | 0 | 0 | 0 | 2.46e-08 (instrument.profile.u) | 422 (phases.0.scale) +1 | 0 | 0 | 422 (phases.0.scale) +1 | 0.00033 (instrument.profile.y) | 0.00033 (instrument.profile.y) | 0.00033 (instrument.profile.y) | 0.00033 (instrument.profile.y) | 0.00033 (instrument.profile.y) | 0.00033 (instrument.profile.y) | 422 (phases.0.scale) +1 | 3.36 (instrument.background.c0) | 3.36 (instrument.background.c0) | 3.36 (instrument.background.c0) | 3.36 (instrument.background.c0) | 3.36 (instrument.background.c0) | 3.36 (instrument.background.c0) | 41.2 (phases.0.scale) |
| 91 | 0 | 0 | 0 | 0 | 4.24e-08 (instrument.profile.u) | 413 (phases.0.scale) +1 | 0 | 0 | 413 (phases.0.scale) +1 | 0.000329 (instrument.background.c0) | 0.000329 (instrument.background.c0) | 0.000329 (instrument.background.c0) | 0.000329 (instrument.background.c0) | 0.000329 (instrument.background.c0) | 0.000329 (instrument.background.c0) | 413 (phases.0.scale) +1 | 1.33 (phases.0.scale) | 1.33 (phases.0.scale) | 1.33 (phases.0.scale) | 1.33 (phases.0.scale) | 1.33 (phases.0.scale) | 1.33 (phases.0.scale) | 41.4 (phases.0.scale) |
| 92 | 0 | 0 | 0 | 0 | 3.09e-07 (instrument.profile.u) | 428 (phases.0.scale) +1 | 0 | 0 | 428 (phases.0.scale) +1 | 0.000157 (instrument.background.c0) | 0.000157 (instrument.background.c0) | 0.000157 (instrument.background.c0) | 0.000157 (instrument.background.c0) | 0.000157 (instrument.background.c0) | 0.000157 (instrument.background.c0) | 428 (phases.0.scale) +1 | 2.46 (instrument.background.c0) | 2.46 (instrument.background.c0) | 2.46 (instrument.background.c0) | 2.46 (instrument.background.c0) | 2.46 (instrument.background.c0) | 2.46 (instrument.background.c0) | 42.5 (phases.0.scale) |
| 93 | 0 | 0 | 0 | 0 | 3.52e-07 (instrument.profile.v) | 421 (phases.0.scale) +1 | 0 | 0 | 421 (phases.0.scale) +1 | 0.000116 (instrument.profile.y) | 0.000116 (instrument.profile.y) | 0.000116 (instrument.profile.y) | 0.000116 (instrument.profile.y) | 0.000116 (instrument.profile.y) | 0.000116 (instrument.profile.y) | 421 (phases.0.scale) +1 | 0.789 (phases.0.scale) | 0.789 (phases.0.scale) | 0.789 (phases.0.scale) | 0.789 (phases.0.scale) | 0.789 (phases.0.scale) | 0.789 (phases.0.scale) | 42.9 (phases.0.scale) |
| 94 | 0 | 0 | 0 | 0 | 3.6e-08 (instrument.profile.u) | 406 (phases.0.scale) +1 | 0 | 0 | 406 (phases.0.scale) +1 | 0.000282 (instrument.profile.y) | 0.000282 (instrument.profile.y) | 0.000282 (instrument.profile.y) | 0.000282 (instrument.profile.y) | 0.000282 (instrument.profile.y) | 0.000282 (instrument.profile.y) | 406 (phases.0.scale) +1 | 1 (instrument.background.c0) | 1 (instrument.background.c0) | 1 (instrument.background.c0) | 1 (instrument.background.c0) | 1 (instrument.background.c0) | 1 (instrument.background.c0) | 43.2 (phases.0.scale) |
| 95 | 0 | 0 | 0 | 0 | 1.57e-07 (instrument.profile.y) | 415 (phases.0.scale) +1 | 0 | 0 | 415 (phases.0.scale) +1 | 0.000262 (instrument.profile.y) | 0.000262 (instrument.profile.y) | 0.000262 (instrument.profile.y) | 0.000262 (instrument.profile.y) | 0.000262 (instrument.profile.y) | 0.000262 (instrument.profile.y) | 415 (phases.0.scale) +1 | 1.64 (phases.0.cell.a) | 1.64 (phases.0.cell.a) | 1.64 (phases.0.cell.a) | 1.64 (phases.0.cell.a) | 1.64 (phases.0.cell.a) | 1.64 (phases.0.cell.a) | 43.1 (phases.0.scale) |
| 96 | 0 | 0 | 0 | 0 | 1.16e-07 (instrument.profile.u) | 420 (phases.0.scale) +1 | 0 | 0 | 420 (phases.0.scale) +1 | 0.000189 (instrument.background.c2) | 0.000189 (instrument.background.c2) | 0.000189 (instrument.background.c2) | 0.000189 (instrument.background.c2) | 0.000189 (instrument.background.c2) | 0.000189 (instrument.background.c2) | 420 (phases.0.scale) +1 | 1.78 (instrument.background.c0) | 1.78 (instrument.background.c0) | 1.78 (instrument.background.c0) | 1.78 (instrument.background.c0) | 1.78 (instrument.background.c0) | 1.78 (instrument.background.c0) | 43.9 (phases.0.scale) |
| 97 | 0 | 0 | 0 | 0 | 2.14e-07 (instrument.profile.v) | 425 (phases.0.scale) +1 | 0 | 0 | 425 (phases.0.scale) +1 | 0.000391 (instrument.profile.y) | 0.000391 (instrument.profile.y) | 0.000391 (instrument.profile.y) | 0.000391 (instrument.profile.y) | 0.000391 (instrument.profile.y) | 0.000391 (instrument.profile.y) | 425 (phases.0.scale) +1 | 2.77 (instrument.background.c0) | 2.77 (instrument.background.c0) | 2.77 (instrument.background.c0) | 2.77 (instrument.background.c0) | 2.77 (instrument.background.c0) | 2.77 (instrument.background.c0) | 44.5 (phases.0.scale) |
| 98 | 0 | 0 | 0 | 0 | 1.02e-07 (instrument.profile.u) | 421 (phases.0.scale) +1 | 0 | 0 | 421 (phases.0.scale) +1 | 0.000153 (instrument.profile.y) | 0.000153 (instrument.profile.y) | 0.000153 (instrument.profile.y) | 0.000153 (instrument.profile.y) | 0.000153 (instrument.profile.y) | 0.000153 (instrument.profile.y) | 421 (phases.0.scale) +1 | 2.78 (instrument.background.c0) | 2.78 (instrument.background.c0) | 2.78 (instrument.background.c0) | 2.78 (instrument.background.c0) | 2.78 (instrument.background.c0) | 2.78 (instrument.background.c0) | 44.4 (phases.0.scale) |
| 99 | 0 | 0 | 0 | 0 | 5.66e-08 (instrument.profile.w) | 432 (phases.0.scale) +1 | 0 | 0 | 432 (phases.0.scale) +1 | 0.000228 (instrument.background.c2) | 0.000228 (instrument.background.c2) | 0.000228 (instrument.background.c2) | 0.000228 (instrument.background.c2) | 0.000228 (instrument.background.c2) | 0.000228 (instrument.background.c2) | 432 (phases.0.scale) +1 | 2.51 (instrument.background.c0) | 2.51 (instrument.background.c0) | 2.51 (instrument.background.c0) | 2.51 (instrument.background.c0) | 2.51 (instrument.background.c0) | 2.51 (instrument.background.c0) | 45.1 (phases.0.scale) |
| 100 | 0 | 0 | 0 | 0 | 1.53e-07 (instrument.profile.y) | 425 (phases.0.scale) +1 | 0 | 0 | 425 (phases.0.scale) +1 | 7.29e-07 (instrument.profile.u) | 7.29e-07 (instrument.profile.u) | 7.29e-07 (instrument.profile.u) | 7.29e-07 (instrument.profile.u) | 7.29e-07 (instrument.profile.u) | 6.33e-07 (instrument.profile.u) | 425 (phases.0.scale) +1 | 1.65 (instrument.background.c0) | 1.65 (instrument.background.c0) | 1.65 (instrument.background.c0) | 1.65 (instrument.background.c0) | 1.65 (instrument.background.c0) | 1.65 (instrument.background.c0) | 46.3 (phases.0.scale) |
| 101 | 0 | 0 | 0 | 0 | 1.54e-08 (instrument.profile.u) | 418 (phases.0.scale) +1 | 0 | 0 | 418 (phases.0.scale) +1 | 0.000125 (instrument.background.c2) | 0.000125 (instrument.background.c2) | 0.000125 (instrument.background.c2) | 0.000125 (instrument.background.c2) | 0.000125 (instrument.background.c2) | 0.000125 (instrument.background.c2) | 418 (phases.0.scale) +1 | 2.44 (instrument.background.c0) | 2.44 (instrument.background.c0) | 2.44 (instrument.background.c0) | 2.44 (instrument.background.c0) | 2.44 (instrument.background.c0) | 2.44 (instrument.background.c0) | 46.8 (phases.0.scale) |
| 102 | 0 | 0 | 0 | 0 | 3.93e-08 (instrument.profile.u) | 410 (phases.0.scale) +1 | 0 | 0 | 410 (phases.0.scale) +1 | 7.4e-05 (instrument.background.c3) | 7.4e-05 (instrument.background.c3) | 7.4e-05 (instrument.background.c3) | 7.4e-05 (instrument.background.c3) | 7.4e-05 (instrument.background.c3) | 7.4e-05 (instrument.background.c3) | 410 (phases.0.scale) +1 | 2.97 (instrument.background.c0) | 2.97 (instrument.background.c0) | 2.97 (instrument.background.c0) | 2.97 (instrument.background.c0) | 2.97 (instrument.background.c0) | 2.97 (instrument.background.c0) | 46.8 (phases.0.scale) |
| 103 | 0 | 0 | 0 | 0 | 4.13e-08 (instrument.profile.u) | 414 (phases.0.scale) +1 | 0 | 0 | 414 (phases.0.scale) +1 | 7.63e-05 (instrument.profile.x) | 7.63e-05 (instrument.profile.x) | 7.63e-05 (instrument.profile.x) | 7.63e-05 (instrument.profile.x) | 7.63e-05 (instrument.profile.x) | 7.63e-05 (instrument.profile.x) | 414 (phases.0.scale) +1 | 2.29 (instrument.background.c0) | 2.29 (instrument.background.c0) | 2.29 (instrument.background.c0) | 2.29 (instrument.background.c0) | 2.29 (instrument.background.c0) | 2.29 (instrument.background.c0) | 47.4 (phases.0.scale) |
| 104 | 0 | 0 | 0 | 0 | 1.4e-07 (instrument.profile.u) | 411 (phases.0.scale) +1 | 0 | 0 | 411 (phases.0.scale) +1 | 0.00019 (instrument.background.c2) | 0.00019 (instrument.background.c2) | 0.00019 (instrument.background.c2) | 0.00019 (instrument.background.c2) | 0.00019 (instrument.background.c2) | 0.00019 (instrument.background.c2) | 411 (phases.0.scale) +1 | 1.05 (instrument.background.c0) | 1.05 (instrument.background.c0) | 1.05 (instrument.background.c0) | 1.05 (instrument.background.c0) | 1.05 (instrument.background.c0) | 1.05 (instrument.background.c0) | 47.8 (phases.0.scale) |
| 105 | 0 | 0 | 0 | 0 | 9e-08 (instrument.profile.w) | 410 (phases.0.scale) +1 | 0 | 0 | 410 (phases.0.scale) +1 | 7.92e-07 (instrument.profile.y) | 7.92e-07 (instrument.profile.y) | 7.92e-07 (instrument.profile.y) | 7.92e-07 (instrument.profile.y) | 7.92e-07 (instrument.profile.y) | 8.41e-07 (instrument.profile.y) | 410 (phases.0.scale) +1 | 2.34 (phases.0.scale) | 2.34 (phases.0.scale) | 2.34 (phases.0.scale) | 2.34 (phases.0.scale) | 2.34 (phases.0.scale) | 2.34 (phases.0.scale) | 49.1 (phases.0.scale) |
| 106 | 0 | 0 | 0 | 0 | 2.9e-08 (instrument.profile.w) | 414 (phases.0.scale) +1 | 0 | 0 | 414 (phases.0.scale) +1 | 0.000164 (instrument.background.c0) | 0.000164 (instrument.background.c0) | 0.000164 (instrument.background.c0) | 0.000164 (instrument.background.c0) | 0.000164 (instrument.background.c0) | 0.000164 (instrument.background.c0) | 414 (phases.0.scale) +1 | 1.41 (phases.0.cell.a) | 1.41 (phases.0.cell.a) | 1.41 (phases.0.cell.a) | 1.41 (phases.0.cell.a) | 1.41 (phases.0.cell.a) | 1.41 (phases.0.cell.a) | 48.6 (phases.0.scale) |
| 107 | 0 | 0 | 0 | 0 | 2.75e-08 (instrument.profile.u) | 412 (phases.0.scale) +1 | 0 | 0 | 412 (phases.0.scale) +1 | 0.000308 (instrument.background.c0) | 0.000308 (instrument.background.c0) | 0.000308 (instrument.background.c0) | 0.000308 (instrument.background.c0) | 0.000308 (instrument.background.c0) | 0.000308 (instrument.background.c0) | 412 (phases.0.scale) +1 | 3.42 (instrument.background.c0) | 3.42 (instrument.background.c0) | 3.42 (instrument.background.c0) | 3.42 (instrument.background.c0) | 3.42 (instrument.background.c0) | 3.42 (instrument.background.c0) | 49.2 (phases.0.scale) |
| 108 | 0 | 0 | 0 | 0 | 7.51e-07 (instrument.profile.u) | 416 (phases.0.scale) +1 | 0 | 0 | 416 (phases.0.scale) +1 | 4.31e-05 (instrument.background.c3) | 4.31e-05 (instrument.background.c3) | 4.31e-05 (instrument.background.c3) | 4.31e-05 (instrument.background.c3) | 4.31e-05 (instrument.background.c3) | 4.3e-05 (instrument.background.c3) | 416 (phases.0.scale) +1 | 2.52 (instrument.background.c0) | 2.52 (instrument.background.c0) | 2.52 (instrument.background.c0) | 2.52 (instrument.background.c0) | 2.52 (instrument.background.c0) | 2.52 (instrument.background.c0) | 49.6 (phases.0.scale) |
| 109 | 0 | 0 | 0 | 0 | 8.52e-06 (instrument.profile.u) | 405 (phases.0.scale) +1 | 0 | 0 | 405 (phases.0.scale) +1 | 0.000257 (instrument.profile.x) | 0.000257 (instrument.profile.x) | 0.000257 (instrument.profile.x) | 0.000257 (instrument.profile.x) | 0.000257 (instrument.profile.x) | 0.000257 (instrument.profile.x) | 405 (phases.0.scale) +1 | 2.2 (instrument.background.c0) | 2.2 (instrument.background.c0) | 2.2 (instrument.background.c0) | 2.2 (instrument.background.c0) | 2.2 (instrument.background.c0) | 2.2 (instrument.background.c0) | 49.9 (phases.0.scale) |
| 110 | 0 | 0 | 0 | 0 | 3.76e-08 (instrument.profile.w) | 414 (phases.0.scale) +1 | 0 | 0 | 414 (phases.0.scale) +1 | 1.46e-05 (instrument.background.c3) | 1.46e-05 (instrument.background.c3) | 1.46e-05 (instrument.background.c3) | 1.46e-05 (instrument.background.c3) | 1.46e-05 (instrument.background.c3) | 1.46e-05 (instrument.background.c3) | 414 (phases.0.scale) +1 | 2.29 (instrument.background.c0) | 2.29 (instrument.background.c0) | 2.29 (instrument.background.c0) | 2.29 (instrument.background.c0) | 2.29 (instrument.background.c0) | 2.29 (instrument.background.c0) | 50.1 (phases.0.scale) |
| 111 | 0 | 0 | 0 | 0 | 2.82e-07 (instrument.profile.w) | 411 (phases.0.scale) +1 | 0 | 0 | 411 (phases.0.scale) +1 | 8.63e-08 (instrument.profile.y) | 8.63e-08 (instrument.profile.y) | 8.63e-08 (instrument.profile.y) | 8.63e-08 (instrument.profile.y) | 8.63e-08 (instrument.profile.y) | 2.29e-07 (instrument.profile.w) | 411 (phases.0.scale) +1 | 2.11 (instrument.background.c0) | 2.11 (instrument.background.c0) | 2.11 (instrument.background.c0) | 2.11 (instrument.background.c0) | 2.11 (instrument.background.c0) | 2.11 (instrument.background.c0) | 51.8 (phases.0.scale) |
| 112 | 0 | 0 | 0 | 0 | 3.04e-08 (instrument.profile.y) | 414 (phases.0.scale) +1 | 0 | 0 | 414 (phases.0.scale) +1 | 0.000388 (instrument.background.c2) | 0.000388 (instrument.background.c2) | 0.000388 (instrument.background.c2) | 0.000388 (instrument.background.c2) | 0.000388 (instrument.background.c2) | 0.000388 (instrument.background.c2) | 414 (phases.0.scale) +1 | 2.27 (instrument.background.c0) | 2.27 (instrument.background.c0) | 2.27 (instrument.background.c0) | 2.27 (instrument.background.c0) | 2.27 (instrument.background.c0) | 2.27 (instrument.background.c0) | 52.2 (phases.0.scale) |
| 113 | 0 | 0 | 0 | 0 | 2.57e-08 (instrument.profile.y) | 406 (phases.0.scale) +1 | 0 | 0 | 406 (phases.0.scale) +1 | 2.15e-05 (instrument.profile.x) | 2.15e-05 (instrument.profile.x) | 2.15e-05 (instrument.profile.x) | 2.15e-05 (instrument.profile.x) | 2.15e-05 (instrument.profile.x) | 2.15e-05 (instrument.profile.x) | 406 (phases.0.scale) +1 | 1.43 (phases.0.scale) | 1.43 (phases.0.scale) | 1.43 (phases.0.scale) | 1.43 (phases.0.scale) | 1.43 (phases.0.scale) | 1.43 (phases.0.scale) | 52.3 (phases.0.scale) |
| 114 | 0 | 0 | 0 | 0 | 7.6e-08 (instrument.profile.u) | 414 (phases.0.scale) +1 | 0 | 0 | 414 (phases.0.scale) +1 | 0.000599 (instrument.profile.x) | 0.000599 (instrument.profile.x) | 0.000599 (instrument.profile.x) | 0.000599 (instrument.profile.x) | 0.000599 (instrument.profile.x) | 0.000599 (instrument.profile.x) | 414 (phases.0.scale) +1 | 2.55 (instrument.background.c0) | 2.55 (instrument.background.c0) | 2.55 (instrument.background.c0) | 2.55 (instrument.background.c0) | 2.55 (instrument.background.c0) | 2.55 (instrument.background.c0) | 53.3 (phases.0.scale) |
| 115 | 0 | 0 | 0 | 0 | 3.88e-08 (instrument.profile.v) | 417 (phases.0.scale) +1 | 0 | 0 | 417 (phases.0.scale) +1 | 0.000208 (instrument.background.c3) | 0.000208 (instrument.background.c3) | 0.000208 (instrument.background.c3) | 0.000208 (instrument.background.c3) | 0.000208 (instrument.background.c3) | 0.000208 (instrument.background.c3) | 417 (phases.0.scale) +1 | 1.15 (instrument.background.c0) | 1.15 (instrument.background.c0) | 1.15 (instrument.background.c0) | 1.15 (instrument.background.c0) | 1.15 (instrument.background.c0) | 1.15 (instrument.background.c0) | 53.6 (phases.0.scale) |
| 116 | 0 | 0 | 0 | 0 | 1.15e-07 (instrument.profile.u) | 419 (phases.0.scale) +1 | 0 | 0 | 419 (phases.0.scale) +1 | 0.000142 (instrument.background.c0) | 0.000142 (instrument.background.c0) | 0.000142 (instrument.background.c0) | 0.000142 (instrument.background.c0) | 0.000142 (instrument.background.c0) | 0.000142 (instrument.background.c0) | 419 (phases.0.scale) +1 | 2.22 (instrument.background.c0) | 2.22 (instrument.background.c0) | 2.22 (instrument.background.c0) | 2.22 (instrument.background.c0) | 2.22 (instrument.background.c0) | 2.22 (instrument.background.c0) | 54.2 (phases.0.scale) |
| 117 | 0 | 0 | 0 | 0 | 1.77e-07 (instrument.profile.v) | 417 (phases.0.scale) +1 | 0 | 0 | 417 (phases.0.scale) +1 | 5.48e-07 (instrument.profile.w) | 5.48e-07 (instrument.profile.w) | 5.48e-07 (instrument.profile.w) | 5.48e-07 (instrument.profile.w) | 5.48e-07 (instrument.profile.w) | 3.78e-07 (instrument.profile.w) | 417 (phases.0.scale) +1 | 0.891 (instrument.zero_shift) | 0.891 (instrument.zero_shift) | 0.891 (instrument.zero_shift) | 0.891 (instrument.zero_shift) | 0.891 (instrument.zero_shift) | 0.891 (instrument.zero_shift) | 54.1 (phases.0.scale) |
| 118 | 0 | 0 | 0 | 0 | 8.8e-08 (instrument.profile.u) | 416 (phases.0.scale) +1 | 0 | 0 | 416 (phases.0.scale) +1 | 0.000135 (instrument.background.c3) | 0.000135 (instrument.background.c3) | 0.000135 (instrument.background.c3) | 0.000135 (instrument.background.c3) | 0.000135 (instrument.background.c3) | 0.000135 (instrument.background.c3) | 416 (phases.0.scale) +1 | 2.4 (instrument.background.c0) | 2.4 (instrument.background.c0) | 2.4 (instrument.background.c0) | 2.4 (instrument.background.c0) | 2.4 (instrument.background.c0) | 2.4 (instrument.background.c0) | 54.8 (phases.0.scale) |
| 119 | 0 | 0 | 0 | 0 | 3.47e-07 (instrument.profile.u) | 417 (phases.0.scale) +1 | 0 | 0 | 417 (phases.0.scale) +1 | 0.000426 (instrument.background.c3) | 0.000426 (instrument.background.c3) | 0.000426 (instrument.background.c3) | 0.000426 (instrument.background.c3) | 0.000426 (instrument.background.c3) | 0.000426 (instrument.background.c3) | 417 (phases.0.scale) +1 | 1.22 (instrument.background.c0) | 1.22 (instrument.background.c0) | 1.22 (instrument.background.c0) | 1.22 (instrument.background.c0) | 1.22 (instrument.background.c0) | 1.22 (instrument.background.c0) | 55.1 (phases.0.scale) |
| 120 | 0 | 0 | 0 | 0 | 6.5e-08 (instrument.profile.u) | 434 (phases.0.scale) +1 | 0 | 0 | 434 (phases.0.scale) +1 | 0.000758 (instrument.profile.x) | 0.000758 (instrument.profile.x) | 0.000758 (instrument.profile.x) | 0.000758 (instrument.profile.x) | 0.000758 (instrument.profile.x) | 0.000758 (instrument.profile.x) | 434 (phases.0.scale) +1 | 2.6 (instrument.background.c0) | 2.6 (instrument.background.c0) | 2.6 (instrument.background.c0) | 2.6 (instrument.background.c0) | 2.6 (instrument.background.c0) | 2.6 (instrument.background.c0) | 55.4 (phases.0.scale) |
| 121 | 0 | 0 | 0 | 0 | 1.38e-07 (instrument.profile.v) | 409 (phases.0.scale) +1 | 0 | 0 | 409 (phases.0.scale) +1 | 0.000145 (instrument.profile.y) | 0.000145 (instrument.profile.y) | 0.000145 (instrument.profile.y) | 0.000145 (instrument.profile.y) | 0.000145 (instrument.profile.y) | 0.000145 (instrument.profile.y) | 409 (phases.0.scale) +1 | 2.16 (instrument.background.c0) | 2.16 (instrument.background.c0) | 2.16 (instrument.background.c0) | 2.16 (instrument.background.c0) | 2.16 (instrument.background.c0) | 2.16 (instrument.background.c0) | 56.8 (phases.0.scale) |
| 122 | 0 | 0 | 0 | 0 | 1.41e-07 (instrument.profile.v) | 422 (phases.0.scale) +1 | 0 | 0 | 422 (phases.0.scale) +1 | 9.65e-05 (instrument.profile.y) | 9.65e-05 (instrument.profile.y) | 9.65e-05 (instrument.profile.y) | 9.65e-05 (instrument.profile.y) | 9.65e-05 (instrument.profile.y) | 9.65e-05 (instrument.profile.y) | 422 (phases.0.scale) +1 | 1.87 (instrument.background.c0) | 1.87 (instrument.background.c0) | 1.87 (instrument.background.c0) | 1.87 (instrument.background.c0) | 1.87 (instrument.background.c0) | 1.87 (instrument.background.c0) | 57.4 (phases.0.scale) |
| 123 | 0 | 0 | 0 | 0 | 1.8e-07 (instrument.profile.y) | 423 (phases.0.scale) +1 | 0 | 0 | 423 (phases.0.scale) +1 | 0.00025 (instrument.profile.y) | 0.00025 (instrument.profile.y) | 0.00025 (instrument.profile.y) | 0.00025 (instrument.profile.y) | 0.00025 (instrument.profile.y) | 0.000251 (instrument.profile.y) | 423 (phases.0.scale) +1 | 1.64 (instrument.background.c0) | 1.64 (instrument.background.c0) | 1.64 (instrument.background.c0) | 1.64 (instrument.background.c0) | 1.64 (instrument.background.c0) | 1.64 (instrument.background.c0) | 58.4 (phases.0.scale) |
| 124 | 0 | 0 | 0 | 0 | 5.01e-08 (instrument.profile.w) | 410 (phases.0.scale) +1 | 0 | 0 | 410 (phases.0.scale) +1 | 1.97e-07 (instrument.profile.x) | 1.97e-07 (instrument.profile.x) | 1.97e-07 (instrument.profile.x) | 1.97e-07 (instrument.profile.x) | 1.97e-07 (instrument.profile.x) | 1.65e-07 (instrument.profile.x) | 410 (phases.0.scale) +1 | 2.12 (instrument.background.c0) | 2.12 (instrument.background.c0) | 2.12 (instrument.background.c0) | 2.12 (instrument.background.c0) | 2.12 (instrument.background.c0) | 2.12 (instrument.background.c0) | 57.7 (phases.0.scale) |
| 125 | 0 | 0 | 0 | 0 | 2.19e-07 (instrument.profile.y) | 384 (phases.0.scale) +1 | 0 | 0 | 384 (phases.0.scale) +1 | 0.000217 (instrument.profile.y) | 0.000217 (instrument.profile.y) | 0.000217 (instrument.profile.y) | 0.000217 (instrument.profile.y) | 0.000217 (instrument.profile.y) | 0.000217 (instrument.profile.y) | 384 (phases.0.scale) +1 | 1.85 (instrument.background.c0) | 1.85 (instrument.background.c0) | 1.85 (instrument.background.c0) | 1.85 (instrument.background.c0) | 1.85 (instrument.background.c0) | 1.85 (instrument.background.c0) | 58.6 (phases.0.scale) |
| 126 | 0 | 0 | 0 | 0 | 4.3e-07 (instrument.profile.u) | 370 (phases.0.scale) +1 | 0 | 0 | 370 (phases.0.scale) +1 | 0.000137 (instrument.profile.y) | 0.000137 (instrument.profile.y) | 0.000137 (instrument.profile.y) | 0.000137 (instrument.profile.y) | 0.000137 (instrument.profile.y) | 0.000137 (instrument.profile.y) | 370 (phases.0.scale) +1 | 2.12 (instrument.background.c0) | 2.12 (instrument.background.c0) | 2.12 (instrument.background.c0) | 2.12 (instrument.background.c0) | 2.12 (instrument.background.c0) | 2.12 (instrument.background.c0) | 58.4 (phases.0.scale) |
| 127 | 0 | 0 | 0 | 0 | 2.28e-08 (instrument.profile.v) | 317 (phases.0.scale) +1 | 0 | 0 | 317 (phases.0.scale) +1 | 0.000315 (instrument.profile.x) | 0.000315 (instrument.profile.x) | 0.000315 (instrument.profile.x) | 0.000315 (instrument.profile.x) | 0.000315 (instrument.profile.x) | 0.000315 (instrument.profile.x) | 317 (phases.0.scale) +1 | 0.821 (instrument.profile.w) | 0.821 (instrument.profile.w) | 0.821 (instrument.profile.w) | 0.821 (instrument.profile.w) | 0.821 (instrument.profile.w) | 0.821 (instrument.profile.w) | 60.7 (phases.0.scale) |
| 134 | 1.21e-07 (instrument.profile.y) | 1.21e-07 (instrument.profile.y) | 1.21e-07 (instrument.profile.y) | 1.21e-07 (instrument.profile.y) | 6.05e-08 (instrument.profile.u) | 8.4e-08 (instrument.profile.y) | 0 | 0 | 3.67e-08 (instrument.profile.y) | 6.38e-07 (instrument.profile.w) | 5.52e-07 (instrument.profile.u) | 5.52e-07 (instrument.profile.u) | 5.52e-07 (instrument.profile.u) | 5.52e-07 (instrument.profile.u) | 5.85e-07 (instrument.profile.w) | 5.68e-07 (instrument.profile.w) | 0.614 (instrument.profile.w) | 0.614 (instrument.profile.w) | 0.614 (instrument.profile.w) | 0.614 (instrument.profile.w) | 0.614 (instrument.profile.w) | 0.614 (instrument.profile.w) | 0.614 (instrument.profile.w) |
| 135 | 0.000238 (instrument.profile.y) | 0.000238 (instrument.profile.y) | 0.000238 (instrument.profile.y) | 0.000238 (instrument.profile.y) | 0 | 0.000238 (instrument.profile.y) | 0 | 0 | 4.81e-08 (instrument.profile.y) | 0 | 0.000238 (instrument.profile.y) | 0.000238 (instrument.profile.y) | 0.000238 (instrument.profile.y) | 0.000238 (instrument.profile.y) | 0 | 0.000238 (instrument.profile.y) | 0.621 (phases.0.cell.a) | 0.621 (phases.0.cell.a) | 0.621 (phases.0.cell.a) | 0.621 (phases.0.cell.a) | 0.621 (phases.0.cell.a) | 0.621 (phases.0.cell.a) | 0.621 (phases.0.cell.a) |
| 136 | 2.65e-07 (instrument.profile.u) | 2.65e-07 (instrument.profile.u) | 2.65e-07 (instrument.profile.u) | 2.65e-07 (instrument.profile.u) | 0 | 1.58e-07 (instrument.profile.y) | 0 | 0 | 1.65e-07 (instrument.profile.w) | 1.62e-05 (instrument.background.c3) | 1.62e-05 (instrument.background.c3) | 1.62e-05 (instrument.background.c3) | 1.62e-05 (instrument.background.c3) | 1.62e-05 (instrument.background.c3) | 1.62e-05 (instrument.background.c3) | 1.62e-05 (instrument.background.c3) | 0.422 (instrument.background.c0) | 0.422 (instrument.background.c0) | 0.422 (instrument.background.c0) | 0.422 (instrument.background.c0) | 0.422 (instrument.background.c0) | 0.422 (instrument.background.c0) | 0.422 (instrument.background.c0) |
| 137 | 0.000129 (instrument.profile.y) | 0.000129 (instrument.profile.y) | 0.000129 (instrument.profile.y) | 0.000129 (instrument.profile.y) | 0 | 0.000129 (instrument.profile.y) | 0 | 0 | 7.48e-08 (instrument.profile.y) | 0 | 0.000129 (instrument.profile.y) | 0.000129 (instrument.profile.y) | 0.000129 (instrument.profile.y) | 0.000129 (instrument.profile.y) | 0 | 0.000129 (instrument.profile.y) | 1.06 (phases.0.scale) | 1.06 (phases.0.scale) | 1.06 (phases.0.scale) | 1.06 (phases.0.scale) | 1.06 (phases.0.scale) | 1.06 (phases.0.scale) | 1.06 (phases.0.scale) |
| 138 | 2.3e-06 (instrument.background.c2) | 2.3e-06 (instrument.background.c2) | 2.3e-06 (instrument.background.c2) | 2.3e-06 (instrument.background.c2) | 0 | 2.32e-06 (instrument.background.c2) | 0 | 0 | 1.72e-07 (instrument.profile.v) | 0.00013 (instrument.profile.y) | 0.000131 (instrument.profile.y) | 0.000131 (instrument.profile.y) | 0.000131 (instrument.profile.y) | 0.000131 (instrument.profile.y) | 0.00013 (instrument.profile.y) | 0.000131 (instrument.profile.y) | 1.11 (instrument.background.c0) | 1.11 (instrument.background.c0) | 1.11 (instrument.background.c0) | 1.11 (instrument.background.c0) | 1.11 (instrument.background.c0) | 1.11 (instrument.background.c0) | 1.11 (instrument.background.c0) |
| 139 | 0.00026 (instrument.profile.x) | 0.00026 (instrument.profile.x) | 0.00026 (instrument.profile.x) | 0.00026 (instrument.profile.x) | 0 | 0.00026 (instrument.profile.x) | 0 | 0 | 2.96e-09 (instrument.zero_shift) | 0.000268 (instrument.profile.x) | 4.32e-05 (instrument.background.c0) | 4.32e-05 (instrument.background.c0) | 4.32e-05 (instrument.background.c0) | 4.32e-05 (instrument.background.c0) | 0.000268 (instrument.profile.x) | 4.32e-05 (instrument.background.c0) | 0.371 (instrument.profile.w) | 0.371 (instrument.profile.w) | 0.371 (instrument.profile.w) | 0.371 (instrument.profile.w) | 0.371 (instrument.profile.w) | 0.371 (instrument.profile.w) | 0.371 (instrument.profile.w) |
| 140 | 0.000718 (instrument.profile.y) | 0.000718 (instrument.profile.y) | 0.000718 (instrument.profile.y) | 0.000718 (instrument.profile.y) | 0 | 0.000718 (instrument.profile.y) | 0 | 0 | 1.53e-07 (instrument.profile.w) | 0 | 0.000718 (instrument.profile.y) | 0.000718 (instrument.profile.y) | 0.000718 (instrument.profile.y) | 0.000718 (instrument.profile.y) | 0 | 0.000718 (instrument.profile.y) | 0.989 (instrument.background.c0) | 0.989 (instrument.background.c0) | 0.989 (instrument.background.c0) | 0.989 (instrument.background.c0) | 0.989 (instrument.background.c0) | 0.989 (instrument.background.c0) | 0.989 (instrument.background.c0) |
| 141 | 2.43e-08 (instrument.profile.u) | 2.43e-08 (instrument.profile.u) | 2.43e-08 (instrument.profile.u) | 2.43e-08 (instrument.profile.u) | 0 | 2.1e-08 (instrument.profile.v) | 0 | 0 | 1.05e-08 (instrument.profile.y) | 0.000296 (instrument.profile.x) | 0.000296 (instrument.profile.x) | 0.000296 (instrument.profile.x) | 0.000296 (instrument.profile.x) | 0.000296 (instrument.profile.x) | 0.000296 (instrument.profile.x) | 0.000296 (instrument.profile.x) | 0.669 (instrument.background.c0) | 0.669 (instrument.background.c0) | 0.669 (instrument.background.c0) | 0.669 (instrument.background.c0) | 0.669 (instrument.background.c0) | 0.669 (instrument.background.c0) | 0.669 (instrument.background.c0) |
| 142 | 0.00067 (instrument.profile.y) | 0.00067 (instrument.profile.y) | 0.00067 (instrument.profile.y) | 0.00067 (instrument.profile.y) | 0 | 0.00067 (instrument.profile.y) | 0 | 0 | 1.04e-08 (instrument.profile.y) | 0 | 0.00067 (instrument.profile.y) | 0.00067 (instrument.profile.y) | 0.00067 (instrument.profile.y) | 0.00067 (instrument.profile.y) | 0 | 0.00067 (instrument.profile.y) | 0.596 (instrument.background.c0) | 0.596 (instrument.background.c0) | 0.596 (instrument.background.c0) | 0.596 (instrument.background.c0) | 0.596 (instrument.background.c0) | 0.596 (instrument.background.c0) | 0.596 (instrument.background.c0) |
| 143 | 0.000118 (instrument.profile.y) | 0.000118 (instrument.profile.y) | 0.000118 (instrument.profile.y) | 0.000118 (instrument.profile.y) | 0 | 0.000118 (instrument.profile.y) | 0 | 0 | 2.95e-07 (instrument.profile.u) | 0 | 0.000118 (instrument.profile.y) | 0.000118 (instrument.profile.y) | 0.000118 (instrument.profile.y) | 0.000118 (instrument.profile.y) | 0 | 0.000118 (instrument.profile.y) | 0.658 (phases.0.scale) | 0.658 (phases.0.scale) | 0.658 (phases.0.scale) | 0.658 (phases.0.scale) | 0.658 (phases.0.scale) | 0.658 (phases.0.scale) | 0.658 (phases.0.scale) |
| 144 | 4.81e-08 (instrument.profile.y) | 4.81e-08 (instrument.profile.y) | 4.81e-08 (instrument.profile.y) | 4.81e-08 (instrument.profile.y) | 0 | 4.19e-08 (instrument.profile.u) | 0 | 0 | 2.49e-08 (instrument.profile.y) | 6.56e-05 (instrument.profile.y) | 6.55e-05 (instrument.profile.y) | 6.55e-05 (instrument.profile.y) | 6.55e-05 (instrument.profile.y) | 6.55e-05 (instrument.profile.y) | 6.56e-05 (instrument.profile.y) | 6.56e-05 (instrument.profile.y) | 0.865 (instrument.background.c0) | 0.865 (instrument.background.c0) | 0.865 (instrument.background.c0) | 0.865 (instrument.background.c0) | 0.865 (instrument.background.c0) | 0.865 (instrument.background.c0) | 0.865 (instrument.background.c0) |
| 145 | 8.85e-07 (instrument.profile.w) | 8.85e-07 (instrument.profile.w) | 8.85e-07 (instrument.profile.w) | 8.85e-07 (instrument.profile.w) | 0 | 8.87e-07 (instrument.profile.w) | 0 | 0 | 2.53e-09 (instrument.profile.u) | 0.000793 (instrument.profile.y) | 0.000793 (instrument.profile.y) | 0.000793 (instrument.profile.y) | 0.000793 (instrument.profile.y) | 0.000793 (instrument.profile.y) | 0.000793 (instrument.profile.y) | 0.000793 (instrument.profile.y) | 0.413 (phases.0.scale) | 0.413 (phases.0.scale) | 0.413 (phases.0.scale) | 0.413 (phases.0.scale) | 0.413 (phases.0.scale) | 0.413 (phases.0.scale) | 0.413 (phases.0.scale) |
| 146 | 4.24e-05 (instrument.background.c2) | 4.24e-05 (instrument.background.c2) | 4.24e-05 (instrument.background.c2) | 4.24e-05 (instrument.background.c2) | 0 | 4.24e-05 (instrument.background.c2) | 0 | 0 | 6.61e-08 (instrument.profile.u) | 0 | 4.24e-05 (instrument.background.c2) | 4.24e-05 (instrument.background.c2) | 4.24e-05 (instrument.background.c2) | 4.24e-05 (instrument.background.c2) | 0 | 4.24e-05 (instrument.background.c2) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) |
| 147 | 0.000346 (instrument.profile.y) | 0.000346 (instrument.profile.y) | 0.000346 (instrument.profile.y) | 0.000346 (instrument.profile.y) | 0 | 0.000346 (instrument.profile.y) | 0 | 0 | 5.54e-08 (instrument.profile.y) | 0 | 0.000346 (instrument.profile.y) | 0.000346 (instrument.profile.y) | 0.000346 (instrument.profile.y) | 0.000346 (instrument.profile.y) | 0 | 0.000346 (instrument.profile.y) | 0.636 (phases.0.scale) | 0.636 (phases.0.scale) | 0.636 (phases.0.scale) | 0.636 (phases.0.scale) | 0.636 (phases.0.scale) | 0.636 (phases.0.scale) | 0.636 (phases.0.scale) |
| 148 | 1.56e-05 (instrument.background.c3) | 1.56e-05 (instrument.background.c3) | 1.56e-05 (instrument.background.c3) | 1.56e-05 (instrument.background.c3) | 0 | 1.56e-05 (instrument.background.c3) | 0 | 0 | 2.05e-08 (instrument.profile.u) | 0 | 1.56e-05 (instrument.background.c3) | 1.56e-05 (instrument.background.c3) | 1.56e-05 (instrument.background.c3) | 1.56e-05 (instrument.background.c3) | 0 | 1.56e-05 (instrument.background.c3) | 0.671 (instrument.background.c0) | 0.671 (instrument.background.c0) | 0.671 (instrument.background.c0) | 0.671 (instrument.background.c0) | 0.671 (instrument.background.c0) | 0.671 (instrument.background.c0) | 0.671 (instrument.background.c0) |
| 149 | 0.00017 (instrument.profile.x) | 0.00017 (instrument.profile.x) | 0.00017 (instrument.profile.x) | 0.00017 (instrument.profile.x) | 0 | 0.00017 (instrument.profile.x) | 0 | 0 | 2.89e-08 (instrument.profile.v) | 0 | 0.00017 (instrument.profile.x) | 0.00017 (instrument.profile.x) | 0.00017 (instrument.profile.x) | 0.00017 (instrument.profile.x) | 0 | 0.00017 (instrument.profile.x) | 0.321 (instrument.background.c0) | 0.321 (instrument.background.c0) | 0.321 (instrument.background.c0) | 0.321 (instrument.background.c0) | 0.321 (instrument.background.c0) | 0.321 (instrument.background.c0) | 0.321 (instrument.background.c0) |
| 150 | 2.42e-05 (instrument.background.c0) | 2.42e-05 (instrument.background.c0) | 2.42e-05 (instrument.background.c0) | 2.42e-05 (instrument.background.c0) | 0 | 2.42e-05 (instrument.background.c0) | 0 | 0 | 5.38e-09 (instrument.profile.w) | 0 | 2.42e-05 (instrument.background.c0) | 2.42e-05 (instrument.background.c0) | 2.42e-05 (instrument.background.c0) | 2.42e-05 (instrument.background.c0) | 0 | 2.42e-05 (instrument.background.c0) | 0.822 (instrument.background.c0) | 0.822 (instrument.background.c0) | 0.822 (instrument.background.c0) | 0.822 (instrument.background.c0) | 0.822 (instrument.background.c0) | 0.822 (instrument.background.c0) | 0.822 (instrument.background.c0) |
| 151 | 6.35e-05 (instrument.profile.x) | 6.35e-05 (instrument.profile.x) | 6.35e-05 (instrument.profile.x) | 6.35e-05 (instrument.profile.x) | 0 | 6.35e-05 (instrument.profile.x) | 0 | 0 | 5.99e-08 (instrument.profile.v) | 0 | 6.35e-05 (instrument.profile.x) | 6.35e-05 (instrument.profile.x) | 6.35e-05 (instrument.profile.x) | 6.35e-05 (instrument.profile.x) | 0 | 6.35e-05 (instrument.profile.x) | 0.793 (instrument.background.c0) | 0.793 (instrument.background.c0) | 0.793 (instrument.background.c0) | 0.793 (instrument.background.c0) | 0.793 (instrument.background.c0) | 0.793 (instrument.background.c0) | 0.793 (instrument.background.c0) |
| 152 | 8.99e-05 (instrument.profile.y) | 8.99e-05 (instrument.profile.y) | 8.99e-05 (instrument.profile.y) | 8.99e-05 (instrument.profile.y) | 0 | 8.99e-05 (instrument.profile.y) | 0 | 0 | 1.76e-08 (instrument.profile.u) | 0 | 8.99e-05 (instrument.profile.y) | 8.99e-05 (instrument.profile.y) | 8.99e-05 (instrument.profile.y) | 8.99e-05 (instrument.profile.y) | 0 | 8.99e-05 (instrument.profile.y) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) |
| 153 | 4.36e-08 (instrument.profile.w) | 4.36e-08 (instrument.profile.w) | 4.36e-08 (instrument.profile.w) | 4.36e-08 (instrument.profile.w) | 0 | 3.69e-08 (instrument.profile.w) | 0 | 0 | 2.11e-08 (instrument.profile.y) | 4.67e-05 (instrument.profile.x) | 4.67e-05 (instrument.profile.x) | 4.67e-05 (instrument.profile.x) | 4.67e-05 (instrument.profile.x) | 4.67e-05 (instrument.profile.x) | 4.67e-05 (instrument.profile.x) | 4.67e-05 (instrument.profile.x) | 0.778 (instrument.background.c0) | 0.778 (instrument.background.c0) | 0.778 (instrument.background.c0) | 0.778 (instrument.background.c0) | 0.778 (instrument.background.c0) | 0.778 (instrument.background.c0) | 0.778 (instrument.background.c0) |
| 154 | 1.03e-07 (instrument.profile.w) | 1.03e-07 (instrument.profile.w) | 1.03e-07 (instrument.profile.w) | 1.03e-07 (instrument.profile.w) | 0 | 8.66e-08 (instrument.profile.w) | 0 | 0 | 1.82e-08 (instrument.profile.u) | 0 | 1.03e-07 (instrument.profile.w) | 1.03e-07 (instrument.profile.w) | 1.03e-07 (instrument.profile.w) | 1.03e-07 (instrument.profile.w) | 0 | 8.66e-08 (instrument.profile.w) | 0.962 (instrument.background.c0) | 0.962 (instrument.background.c0) | 0.962 (instrument.background.c0) | 0.962 (instrument.background.c0) | 0.962 (instrument.background.c0) | 0.962 (instrument.background.c0) | 0.962 (instrument.background.c0) |
| 155 | 0.000642 (instrument.profile.y) | 0.000642 (instrument.profile.y) | 0.000642 (instrument.profile.y) | 0.000642 (instrument.profile.y) | 0 | 0.000643 (instrument.profile.y) | 0 | 0 | 5.96e-07 (instrument.profile.v) | 0 | 0.000642 (instrument.profile.y) | 0.000642 (instrument.profile.y) | 0.000642 (instrument.profile.y) | 0.000642 (instrument.profile.y) | 0 | 0.000643 (instrument.profile.y) | 0.766 (instrument.background.c0) | 0.766 (instrument.background.c0) | 0.766 (instrument.background.c0) | 0.766 (instrument.background.c0) | 0.766 (instrument.background.c0) | 0.766 (instrument.background.c0) | 0.766 (instrument.background.c0) |
| 156 | 3.99e-08 (instrument.profile.v) | 3.99e-08 (instrument.profile.v) | 3.99e-08 (instrument.profile.v) | 3.99e-08 (instrument.profile.v) | 0 | 6.74e-09 (instrument.profile.y) | 0 | 0 | 4.02e-08 (instrument.profile.v) | 3.46e-05 (instrument.background.c2) | 3.46e-05 (instrument.background.c2) | 3.46e-05 (instrument.background.c2) | 3.46e-05 (instrument.background.c2) | 3.46e-05 (instrument.background.c2) | 3.46e-05 (instrument.background.c2) | 3.46e-05 (instrument.background.c2) | 0.593 (instrument.background.c0) | 0.593 (instrument.background.c0) | 0.593 (instrument.background.c0) | 0.593 (instrument.background.c0) | 0.593 (instrument.background.c0) | 0.593 (instrument.background.c0) | 0.593 (instrument.background.c0) |
| 157 | 5.68e-05 (instrument.background.c2) | 5.68e-05 (instrument.background.c2) | 5.68e-05 (instrument.background.c2) | 5.68e-05 (instrument.background.c2) | 0 | 5.68e-05 (instrument.background.c2) | 0 | 0 | 2.76e-08 (instrument.profile.u) | 0 | 5.68e-05 (instrument.background.c2) | 5.68e-05 (instrument.background.c2) | 5.68e-05 (instrument.background.c2) | 5.68e-05 (instrument.background.c2) | 0 | 5.68e-05 (instrument.background.c2) | 0.935 (instrument.background.c0) | 0.935 (instrument.background.c0) | 0.935 (instrument.background.c0) | 0.935 (instrument.background.c0) | 0.935 (instrument.background.c0) | 0.935 (instrument.background.c0) | 0.935 (instrument.background.c0) |
| 158 | 1.55e-08 (instrument.profile.y) | 1.55e-08 (instrument.profile.y) | 1.55e-08 (instrument.profile.y) | 1.55e-08 (instrument.profile.y) | 0 | 1.28e-08 (instrument.profile.y) | 0 | 0 | 2.83e-08 (instrument.profile.y) | 6.82e-05 (instrument.profile.y) | 6.82e-05 (instrument.profile.y) | 6.82e-05 (instrument.profile.y) | 6.82e-05 (instrument.profile.y) | 6.82e-05 (instrument.profile.y) | 6.82e-05 (instrument.profile.y) | 6.82e-05 (instrument.profile.y) | 0.615 (phases.0.scale) | 0.615 (phases.0.scale) | 0.615 (phases.0.scale) | 0.615 (phases.0.scale) | 0.615 (phases.0.scale) | 0.615 (phases.0.scale) | 0.615 (phases.0.scale) |
| 159 | 2.17e-07 (instrument.profile.v) | 2.17e-07 (instrument.profile.v) | 2.17e-07 (instrument.profile.v) | 2.17e-07 (instrument.profile.v) | 0 | 1.53e-07 (instrument.profile.v) | 0 | 0 | 6.7e-08 (instrument.profile.u) | 1.65e-06 (instrument.background.c0) | 1.64e-06 (instrument.background.c0) | 1.64e-06 (instrument.background.c0) | 1.64e-06 (instrument.background.c0) | 1.64e-06 (instrument.background.c0) | 1.65e-06 (instrument.background.c0) | 1.64e-06 (instrument.background.c0) | 0.595 (instrument.background.c0) | 0.595 (instrument.background.c0) | 0.595 (instrument.background.c0) | 0.595 (instrument.background.c0) | 0.595 (instrument.background.c0) | 0.595 (instrument.background.c0) | 0.595 (instrument.background.c0) |
| 160 | 1.09e-07 (instrument.profile.u) | 1.09e-07 (instrument.profile.u) | 1.09e-07 (instrument.profile.u) | 1.09e-07 (instrument.profile.u) | 0 | 7.11e-08 (instrument.profile.u) | 0 | 0 | 1.8e-07 (instrument.profile.u) | 3.12e-05 (instrument.background.c3) | 3.12e-05 (instrument.background.c3) | 3.12e-05 (instrument.background.c3) | 3.12e-05 (instrument.background.c3) | 3.12e-05 (instrument.background.c3) | 3.12e-05 (instrument.background.c3) | 3.12e-05 (instrument.background.c3) | 0.747 (instrument.background.c0) | 0.747 (instrument.background.c0) | 0.747 (instrument.background.c0) | 0.747 (instrument.background.c0) | 0.747 (instrument.background.c0) | 0.747 (instrument.background.c0) | 0.747 (instrument.background.c0) |
| 161 | 1.17e-08 (instrument.profile.x) | 1.17e-08 (instrument.profile.x) | 1.17e-08 (instrument.profile.x) | 1.17e-08 (instrument.profile.x) | 0 | 2.73e-08 (instrument.profile.w) | 0 | 0 | 1.89e-08 (instrument.profile.v) | 3.02e-05 (instrument.profile.y) | 3.02e-05 (instrument.profile.y) | 3.02e-05 (instrument.profile.y) | 3.02e-05 (instrument.profile.y) | 3.02e-05 (instrument.profile.y) | 3.02e-05 (instrument.profile.y) | 3.02e-05 (instrument.profile.y) | 0.816 (instrument.background.c0) | 0.816 (instrument.background.c0) | 0.816 (instrument.background.c0) | 0.816 (instrument.background.c0) | 0.816 (instrument.background.c0) | 0.816 (instrument.background.c0) | 0.816 (instrument.background.c0) |
| 162 | 3.58e-09 (instrument.profile.y) | 3.58e-09 (instrument.profile.y) | 3.58e-09 (instrument.profile.y) | 3.58e-09 (instrument.profile.y) | 0 | 1.23e-08 (instrument.profile.w) | 0 | 0 | 1.16e-08 (instrument.profile.w) | 6.05e-05 (instrument.profile.x) | 6.05e-05 (instrument.profile.x) | 6.05e-05 (instrument.profile.x) | 6.05e-05 (instrument.profile.x) | 6.05e-05 (instrument.profile.x) | 6.05e-05 (instrument.profile.x) | 6.05e-05 (instrument.profile.x) | 0.726 (instrument.background.c0) | 0.726 (instrument.background.c0) | 0.726 (instrument.background.c0) | 0.726 (instrument.background.c0) | 0.726 (instrument.background.c0) | 0.726 (instrument.background.c0) | 0.726 (instrument.background.c0) |
| 163 | 4.32e-09 (instrument.profile.y) | 4.32e-09 (instrument.profile.y) | 4.32e-09 (instrument.profile.y) | 4.32e-09 (instrument.profile.y) | 0 | 1.44e-08 (instrument.profile.u) | 0 | 0 | 1.17e-08 (instrument.profile.u) | 0.000125 (instrument.profile.y) | 0.000125 (instrument.profile.y) | 0.000125 (instrument.profile.y) | 0.000125 (instrument.profile.y) | 0.000125 (instrument.profile.y) | 0.000125 (instrument.profile.y) | 0.000125 (instrument.profile.y) | 0.473 (instrument.background.c0) | 0.473 (instrument.background.c0) | 0.473 (instrument.background.c0) | 0.473 (instrument.background.c0) | 0.473 (instrument.background.c0) | 0.473 (instrument.background.c0) | 0.473 (instrument.background.c0) |
| 164 | 3.97e-06 (instrument.profile.y) | 3.97e-06 (instrument.profile.y) | 3.97e-06 (instrument.profile.y) | 3.97e-06 (instrument.profile.y) | 0 | 3.97e-06 (instrument.profile.y) | 0 | 0 | 1.66e-09 (instrument.profile.y) | 0 | 3.97e-06 (instrument.profile.y) | 3.97e-06 (instrument.profile.y) | 3.97e-06 (instrument.profile.y) | 3.97e-06 (instrument.profile.y) | 0 | 3.97e-06 (instrument.profile.y) | 0.832 (instrument.background.c0) | 0.832 (instrument.background.c0) | 0.832 (instrument.background.c0) | 0.832 (instrument.background.c0) | 0.832 (instrument.background.c0) | 0.832 (instrument.background.c0) | 0.832 (instrument.background.c0) |
| 165 | 4.79e-07 (instrument.profile.v) | 4.79e-07 (instrument.profile.v) | 4.79e-07 (instrument.profile.v) | 4.79e-07 (instrument.profile.v) | 0 | 1.79e-07 (instrument.profile.v) | 0 | 0 | 6.57e-07 (instrument.profile.v) | 7.95e-05 (instrument.profile.y) | 7.96e-05 (instrument.profile.y) | 7.96e-05 (instrument.profile.y) | 7.96e-05 (instrument.profile.y) | 7.96e-05 (instrument.profile.y) | 7.95e-05 (instrument.profile.y) | 7.95e-05 (instrument.profile.y) | 0.805 (instrument.background.c0) | 0.805 (instrument.background.c0) | 0.805 (instrument.background.c0) | 0.805 (instrument.background.c0) | 0.805 (instrument.background.c0) | 0.805 (instrument.background.c0) | 0.805 (instrument.background.c0) |
| 166 | 1.01e-08 (instrument.profile.u) | 1.01e-08 (instrument.profile.u) | 1.01e-08 (instrument.profile.u) | 1.01e-08 (instrument.profile.u) | 0 | 8.18e-09 (instrument.profile.y) | 0 | 0 | 9.02e-09 (instrument.profile.y) | 6.53e-05 (instrument.profile.y) | 6.53e-05 (instrument.profile.y) | 6.53e-05 (instrument.profile.y) | 6.53e-05 (instrument.profile.y) | 6.53e-05 (instrument.profile.y) | 6.53e-05 (instrument.profile.y) | 6.53e-05 (instrument.profile.y) | 0.808 (instrument.background.c0) | 0.808 (instrument.background.c0) | 0.808 (instrument.background.c0) | 0.808 (instrument.background.c0) | 0.808 (instrument.background.c0) | 0.808 (instrument.background.c0) | 0.808 (instrument.background.c0) |
| 167 | 2.65e-08 (instrument.profile.u) | 2.65e-08 (instrument.profile.u) | 2.65e-08 (instrument.profile.u) | 2.65e-08 (instrument.profile.u) | 0 | 1.09e-09 (instrument.profile.u) | 0 | 0 | 2.54e-08 (instrument.profile.u) | 0.000539 (instrument.profile.y) | 0.000539 (instrument.profile.y) | 0.000539 (instrument.profile.y) | 0.000539 (instrument.profile.y) | 0.000539 (instrument.profile.y) | 0.000539 (instrument.profile.y) | 0.000539 (instrument.profile.y) | 0.771 (instrument.background.c0) | 0.771 (instrument.background.c0) | 0.771 (instrument.background.c0) | 0.771 (instrument.background.c0) | 0.771 (instrument.background.c0) | 0.771 (instrument.background.c0) | 0.771 (instrument.background.c0) |
| 168 | 9.19e-09 (instrument.profile.w) | 9.19e-09 (instrument.profile.w) | 9.19e-09 (instrument.profile.w) | 9.19e-09 (instrument.profile.w) | 0 | 1.38e-08 (instrument.profile.y) | 0 | 0 | 7.49e-09 (instrument.profile.y) | 0.000128 (instrument.profile.x) | 0.000128 (instrument.profile.x) | 0.000128 (instrument.profile.x) | 0.000128 (instrument.profile.x) | 0.000128 (instrument.profile.x) | 0.000128 (instrument.profile.x) | 0.000128 (instrument.profile.x) | 1.03 (instrument.background.c0) | 1.03 (instrument.background.c0) | 1.03 (instrument.background.c0) | 1.03 (instrument.background.c0) | 1.03 (instrument.background.c0) | 1.03 (instrument.background.c0) | 1.03 (instrument.background.c0) |
| 169 | 8.36e-05 (instrument.profile.y) | 8.36e-05 (instrument.profile.y) | 8.36e-05 (instrument.profile.y) | 8.36e-05 (instrument.profile.y) | 0 | 8.36e-05 (instrument.profile.y) | 0 | 0 | 2.84e-08 (instrument.profile.u) | 0 | 8.36e-05 (instrument.profile.y) | 8.36e-05 (instrument.profile.y) | 8.36e-05 (instrument.profile.y) | 8.36e-05 (instrument.profile.y) | 0 | 8.36e-05 (instrument.profile.y) | 0.429 (instrument.background.c0) | 0.429 (instrument.background.c0) | 0.429 (instrument.background.c0) | 0.429 (instrument.background.c0) | 0.429 (instrument.background.c0) | 0.429 (instrument.background.c0) | 0.429 (instrument.background.c0) |
| 170 | 3.04e-09 (instrument.profile.y) | 3.04e-09 (instrument.profile.y) | 3.04e-09 (instrument.profile.y) | 3.04e-09 (instrument.profile.y) | 0 | 3.46e-09 (instrument.profile.u) | 0 | 0 | 5.38e-09 (instrument.profile.u) | 5.95e-05 (instrument.background.c0) | 5.95e-05 (instrument.background.c0) | 5.95e-05 (instrument.background.c0) | 5.95e-05 (instrument.background.c0) | 5.95e-05 (instrument.background.c0) | 5.95e-05 (instrument.background.c0) | 5.95e-05 (instrument.background.c0) | 0.848 (instrument.background.c0) | 0.848 (instrument.background.c0) | 0.848 (instrument.background.c0) | 0.848 (instrument.background.c0) | 0.848 (instrument.background.c0) | 0.848 (instrument.background.c0) | 0.848 (instrument.background.c0) |
| 171 | 3.2e-08 (instrument.profile.y) | 3.2e-08 (instrument.profile.y) | 3.2e-08 (instrument.profile.y) | 3.2e-08 (instrument.profile.y) | 0 | 3.25e-09 (instrument.profile.y) | 0 | 0 | 3.52e-08 (instrument.profile.y) | 3.85e-05 (instrument.profile.y) | 3.85e-05 (instrument.profile.y) | 3.85e-05 (instrument.profile.y) | 3.85e-05 (instrument.profile.y) | 3.85e-05 (instrument.profile.y) | 3.85e-05 (instrument.profile.y) | 3.85e-05 (instrument.profile.y) | 0.697 (instrument.background.c0) | 0.697 (instrument.background.c0) | 0.697 (instrument.background.c0) | 0.697 (instrument.background.c0) | 0.697 (instrument.background.c0) | 0.697 (instrument.background.c0) | 0.697 (instrument.background.c0) |
| 172 | 5.94e-07 (instrument.profile.v) | 5.94e-07 (instrument.profile.v) | 5.94e-07 (instrument.profile.v) | 5.94e-07 (instrument.profile.v) | 0 | 2.66e-07 (instrument.profile.v) | 0 | 0 | 3.28e-07 (instrument.profile.v) | 0.000391 (instrument.profile.x) | 0.00039 (instrument.profile.x) | 0.00039 (instrument.profile.x) | 0.00039 (instrument.profile.x) | 0.00039 (instrument.profile.x) | 0.000391 (instrument.profile.x) | 0.00039 (instrument.profile.x) | 0.633 (instrument.background.c0) | 0.633 (instrument.background.c0) | 0.633 (instrument.background.c0) | 0.633 (instrument.background.c0) | 0.633 (instrument.background.c0) | 0.633 (instrument.background.c0) | 0.633 (instrument.background.c0) |
| 173 | 5.4e-09 (instrument.profile.w) | 5.4e-09 (instrument.profile.w) | 5.4e-09 (instrument.profile.w) | 5.4e-09 (instrument.profile.w) | 0 | 1.94e-09 (instrument.profile.v) | 0 | 0 | 7.3e-09 (instrument.profile.v) | 0.00073 (instrument.profile.y) | 0.00073 (instrument.profile.y) | 0.00073 (instrument.profile.y) | 0.00073 (instrument.profile.y) | 0.00073 (instrument.profile.y) | 0.00073 (instrument.profile.y) | 0.00073 (instrument.profile.y) | 0.597 (instrument.background.c0) | 0.597 (instrument.background.c0) | 0.597 (instrument.background.c0) | 0.597 (instrument.background.c0) | 0.597 (instrument.background.c0) | 0.597 (instrument.background.c0) | 0.597 (instrument.background.c0) |
| 174 | 1.88e-08 (instrument.profile.u) | 1.88e-08 (instrument.profile.u) | 1.88e-08 (instrument.profile.u) | 1.88e-08 (instrument.profile.u) | 0 | 1.86e-08 (instrument.profile.u) | 0 | 0 | 5.73e-09 (instrument.profile.y) | 2.33e-05 (instrument.profile.y) | 2.33e-05 (instrument.profile.y) | 2.33e-05 (instrument.profile.y) | 2.33e-05 (instrument.profile.y) | 2.33e-05 (instrument.profile.y) | 2.33e-05 (instrument.profile.y) | 2.33e-05 (instrument.profile.y) | 1.04 (instrument.background.c0) | 1.04 (instrument.background.c0) | 1.04 (instrument.background.c0) | 1.04 (instrument.background.c0) | 1.04 (instrument.background.c0) | 1.04 (instrument.background.c0) | 1.04 (instrument.background.c0) |
| 175 | 0.000302 (instrument.profile.y) | 0.000302 (instrument.profile.y) | 0.000302 (instrument.profile.y) | 0.000302 (instrument.profile.y) | 0 | 0.000302 (instrument.profile.y) | 0 | 0 | 1.13e-08 (instrument.profile.u) | 0 | 0.000302 (instrument.profile.y) | 0.000302 (instrument.profile.y) | 0.000302 (instrument.profile.y) | 0.000302 (instrument.profile.y) | 0 | 0.000302 (instrument.profile.y) | 0.81 (instrument.background.c0) | 0.809 (instrument.background.c0) | 0.809 (instrument.background.c0) | 0.809 (instrument.background.c0) | 0.809 (instrument.background.c0) | 0.81 (instrument.background.c0) | 0.809 (instrument.background.c0) |
| 176 | 3.89e-09 (instrument.profile.u) | 3.89e-09 (instrument.profile.u) | 3.89e-09 (instrument.profile.u) | 3.89e-09 (instrument.profile.u) | 0 | 4.63e-09 (instrument.profile.y) | 0 | 0 | 4.42e-09 (instrument.profile.y) | 1.46e-05 (instrument.background.c2) | 1.46e-05 (instrument.background.c2) | 1.46e-05 (instrument.background.c2) | 1.46e-05 (instrument.background.c2) | 1.46e-05 (instrument.background.c2) | 1.46e-05 (instrument.background.c2) | 1.46e-05 (instrument.background.c2) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) |
| 177 | 2.46e-05 (instrument.profile.y) | 2.46e-05 (instrument.profile.y) | 2.46e-05 (instrument.profile.y) | 2.46e-05 (instrument.profile.y) | 0 | 2.46e-05 (instrument.profile.y) | 0 | 0 | 2.1e-08 (instrument.profile.v) | 0 | 2.46e-05 (instrument.profile.y) | 2.46e-05 (instrument.profile.y) | 2.46e-05 (instrument.profile.y) | 2.46e-05 (instrument.profile.y) | 0 | 2.46e-05 (instrument.profile.y) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) |
| 178 | 1.51e-08 (instrument.profile.w) | 1.51e-08 (instrument.profile.w) | 1.51e-08 (instrument.profile.w) | 1.51e-08 (instrument.profile.w) | 0 | 1.95e-08 (instrument.profile.w) | 0 | 0 | 4.69e-09 (instrument.profile.y) | 0.000121 (instrument.profile.x) | 0.000121 (instrument.profile.x) | 0.000121 (instrument.profile.x) | 0.000121 (instrument.profile.x) | 0.000121 (instrument.profile.x) | 0.000121 (instrument.profile.x) | 0.000121 (instrument.profile.x) | 0.795 (instrument.background.c0) | 0.795 (instrument.background.c0) | 0.795 (instrument.background.c0) | 0.795 (instrument.background.c0) | 0.795 (instrument.background.c0) | 0.795 (instrument.background.c0) | 0.795 (instrument.background.c0) |
| 179 | 9.19e-09 (instrument.profile.w) | 9.19e-09 (instrument.profile.w) | 9.19e-09 (instrument.profile.w) | 9.19e-09 (instrument.profile.w) | 0 | 8.69e-09 (instrument.profile.y) | 0 | 0 | 1.42e-09 (instrument.profile.u) | 0.000525 (instrument.profile.y) | 0.000525 (instrument.profile.y) | 0.000525 (instrument.profile.y) | 0.000525 (instrument.profile.y) | 0.000525 (instrument.profile.y) | 0.000525 (instrument.profile.y) | 0.000525 (instrument.profile.y) | 0.886 (instrument.background.c0) | 0.886 (instrument.background.c0) | 0.886 (instrument.background.c0) | 0.886 (instrument.background.c0) | 0.886 (instrument.background.c0) | 0.886 (instrument.background.c0) | 0.886 (instrument.background.c0) |
| 180 | 3.3e-08 (instrument.profile.w) | 3.3e-08 (instrument.profile.w) | 3.3e-08 (instrument.profile.w) | 3.3e-08 (instrument.profile.w) | 0 | 4.01e-08 (instrument.profile.w) | 0 | 0 | 7.38e-09 (instrument.profile.v) | 0 | 3.3e-08 (instrument.profile.w) | 3.3e-08 (instrument.profile.w) | 3.3e-08 (instrument.profile.w) | 3.3e-08 (instrument.profile.w) | 0 | 4.01e-08 (instrument.profile.w) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) |
| 181 | 2.08e-08 (instrument.profile.u) | 2.08e-08 (instrument.profile.u) | 2.08e-08 (instrument.profile.u) | 2.08e-08 (instrument.profile.u) | 0 | 6.64e-09 (instrument.profile.u) | 0 | 0 | 1.48e-08 (instrument.profile.v) | 0.000566 (instrument.profile.y) | 0.000566 (instrument.profile.y) | 0.000566 (instrument.profile.y) | 0.000566 (instrument.profile.y) | 0.000566 (instrument.profile.y) | 0.000566 (instrument.profile.y) | 0.000566 (instrument.profile.y) | 0.713 (instrument.background.c0) | 0.713 (instrument.background.c0) | 0.713 (instrument.background.c0) | 0.713 (instrument.background.c0) | 0.713 (instrument.background.c0) | 0.713 (instrument.background.c0) | 0.713 (instrument.background.c0) |
| 182 | 3.03e-06 (instrument.profile.y) | 3.03e-06 (instrument.profile.y) | 3.03e-06 (instrument.profile.y) | 3.03e-06 (instrument.profile.y) | 0 | 3.04e-06 (instrument.profile.y) | 0 | 0 | 1.98e-08 (instrument.profile.v) | 0 | 3.03e-06 (instrument.profile.y) | 3.03e-06 (instrument.profile.y) | 3.03e-06 (instrument.profile.y) | 3.03e-06 (instrument.profile.y) | 0 | 3.04e-06 (instrument.profile.y) | 0.878 (instrument.background.c0) | 0.878 (instrument.background.c0) | 0.878 (instrument.background.c0) | 0.878 (instrument.background.c0) | 0.878 (instrument.background.c0) | 0.878 (instrument.background.c0) | 0.878 (instrument.background.c0) |
| 183 | 0.00012 (instrument.profile.x) | 0.00012 (instrument.profile.x) | 0.00012 (instrument.profile.x) | 0.00012 (instrument.profile.x) | 0 | 0.00012 (instrument.profile.x) | 0 | 0 | 5.3e-09 (instrument.profile.y) | 0 | 0.00012 (instrument.profile.x) | 0.00012 (instrument.profile.x) | 0.00012 (instrument.profile.x) | 0.00012 (instrument.profile.x) | 0 | 0.00012 (instrument.profile.x) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) |
| 184 | 1.06e-05 (instrument.profile.y) | 1.06e-05 (instrument.profile.y) | 1.06e-05 (instrument.profile.y) | 1.06e-05 (instrument.profile.y) | 0 | 1.06e-05 (instrument.profile.y) | 0 | 0 | 1.79e-08 (instrument.profile.u) | 0 | 1.06e-05 (instrument.profile.y) | 1.06e-05 (instrument.profile.y) | 1.06e-05 (instrument.profile.y) | 1.06e-05 (instrument.profile.y) | 0 | 1.06e-05 (instrument.profile.y) | 0.786 (instrument.background.c0) | 0.786 (instrument.background.c0) | 0.786 (instrument.background.c0) | 0.786 (instrument.background.c0) | 0.786 (instrument.background.c0) | 0.786 (instrument.background.c0) | 0.786 (instrument.background.c0) |
| 185 | 7.48e-09 (instrument.profile.y) | 7.48e-09 (instrument.profile.y) | 7.48e-09 (instrument.profile.y) | 7.48e-09 (instrument.profile.y) | 0 | 9.07e-09 (instrument.profile.y) | 0 | 0 | 1.59e-09 (instrument.profile.y) | 3.21e-05 (instrument.background.c0) | 3.21e-05 (instrument.background.c0) | 3.21e-05 (instrument.background.c0) | 3.21e-05 (instrument.background.c0) | 3.21e-05 (instrument.background.c0) | 3.21e-05 (instrument.background.c0) | 3.21e-05 (instrument.background.c0) | 0.807 (instrument.background.c0) | 0.807 (instrument.background.c0) | 0.807 (instrument.background.c0) | 0.807 (instrument.background.c0) | 0.807 (instrument.background.c0) | 0.807 (instrument.background.c0) | 0.807 (instrument.background.c0) |
| 186 | 2.39e-05 (instrument.background.c0) | 2.39e-05 (instrument.background.c0) | 2.39e-05 (instrument.background.c0) | 2.39e-05 (instrument.background.c0) | 0 | 2.39e-05 (instrument.background.c0) | 0 | 0 | 4.05e-09 (phases.0.scale) | 0 | 2.39e-05 (instrument.background.c0) | 2.39e-05 (instrument.background.c0) | 2.39e-05 (instrument.background.c0) | 2.39e-05 (instrument.background.c0) | 0 | 2.39e-05 (instrument.background.c0) | 5.4 (phases.0.scale) | 5.4 (phases.0.scale) | 5.4 (phases.0.scale) | 5.4 (phases.0.scale) | 5.4 (phases.0.scale) | 5.4 (phases.0.scale) | 5.4 (phases.0.scale) |
| 187 | 2.73e-08 (phases.0.scale) | 2.73e-08 (phases.0.scale) | 2.73e-08 (phases.0.scale) | 2.73e-08 (phases.0.scale) | 0 | 1.85e-08 (phases.0.scale) | 0 | 0 | 8.78e-09 (phases.0.scale) | 0.000165 (phases.0.scale) | 0.000165 (phases.0.scale) | 0.000165 (phases.0.scale) | 0.000165 (phases.0.scale) | 0.000165 (phases.0.scale) | 0.000165 (phases.0.scale) | 0.000165 (phases.0.scale) | 5.35 (phases.0.scale) | 5.35 (phases.0.scale) | 5.35 (phases.0.scale) | 5.35 (phases.0.scale) | 5.35 (phases.0.scale) | 5.35 (phases.0.scale) | 5.35 (phases.0.scale) |
| 188 | 1.51e-07 (phases.0.cell.c) | 1.51e-07 (phases.0.cell.c) | 1.51e-07 (phases.0.cell.c) | 1.51e-07 (phases.0.cell.c) | 0 | 1.51e-07 (phases.0.cell.c) | 0 | 0 | 2.42e-09 (instrument.profile.u) | 4.93e-06 (instrument.background.c2) | 4.92e-06 (instrument.background.c2) | 4.92e-06 (instrument.background.c2) | 4.92e-06 (instrument.background.c2) | 4.92e-06 (instrument.background.c2) | 4.93e-06 (instrument.background.c2) | 4.92e-06 (instrument.background.c2) | 5.3 (phases.0.scale) | 5.3 (phases.0.scale) | 5.3 (phases.0.scale) | 5.3 (phases.0.scale) | 5.3 (phases.0.scale) | 5.3 (phases.0.scale) | 5.3 (phases.0.scale) |
| 189 | 3.39e-06 (phases.0.cell.c) | 3.39e-06 (phases.0.cell.c) | 3.39e-06 (phases.0.cell.c) | 3.39e-06 (phases.0.cell.c) | 0 | 3.38e-06 (phases.0.cell.c) | 0 | 0 | 9.94e-09 (phases.0.cell.c) | 0.000162 (phases.0.scale) | 0.000161 (phases.0.scale) | 0.000161 (phases.0.scale) | 0.000161 (phases.0.scale) | 0.000161 (phases.0.scale) | 0.000162 (phases.0.scale) | 0.000161 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) |
| 190 | 9.99e-09 (phases.0.cell.c) | 9.99e-09 (phases.0.cell.c) | 9.99e-09 (phases.0.cell.c) | 9.99e-09 (phases.0.cell.c) | 0 | 9.99e-09 (phases.0.cell.c) | 0 | 0 | 6.7e-09 (phases.0.scale) | 6.87e-05 (phases.0.scale) | 6.87e-05 (phases.0.scale) | 6.87e-05 (phases.0.scale) | 6.87e-05 (phases.0.scale) | 6.87e-05 (phases.0.scale) | 6.87e-05 (phases.0.scale) | 6.87e-05 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) |
| 191 | 8.19e-07 (phases.0.cell.c) | 8.19e-07 (phases.0.cell.c) | 8.19e-07 (phases.0.cell.c) | 8.19e-07 (phases.0.cell.c) | 0 | 8.19e-07 (phases.0.cell.c) | 0 | 0 | 2.91e-09 (instrument.profile.u) | 1.06e-06 (phases.0.cell.c) | 2.37e-07 (phases.0.cell.c) | 2.37e-07 (phases.0.cell.c) | 2.37e-07 (phases.0.cell.c) | 2.37e-07 (phases.0.cell.c) | 1.06e-06 (phases.0.cell.c) | 2.37e-07 (phases.0.cell.c) | 5.24 (phases.0.scale) | 5.24 (phases.0.scale) | 5.24 (phases.0.scale) | 5.24 (phases.0.scale) | 5.24 (phases.0.scale) | 5.24 (phases.0.scale) | 5.24 (phases.0.scale) |
| 192 | 8.02e-05 (instrument.background.c0) | 8.02e-05 (instrument.background.c0) | 8.02e-05 (instrument.background.c0) | 8.02e-05 (instrument.background.c0) | 0 | 8.02e-05 (instrument.background.c0) | 0 | 0 | 9.91e-09 (phases.0.cell.c) | 0 | 8.02e-05 (instrument.background.c0) | 8.02e-05 (instrument.background.c0) | 8.02e-05 (instrument.background.c0) | 8.02e-05 (instrument.background.c0) | 0 | 8.02e-05 (instrument.background.c0) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) |
| 193 | 1.76e-09 (instrument.profile.u) | 1.76e-09 (instrument.profile.u) | 1.76e-09 (instrument.profile.u) | 1.76e-09 (instrument.profile.u) | 0 | 2.21e-08 (phases.0.scale) | 0 | 0 | 2.27e-08 (phases.0.scale) | 5.47e-05 (instrument.background.c0) | 5.47e-05 (instrument.background.c0) | 5.47e-05 (instrument.background.c0) | 5.47e-05 (instrument.background.c0) | 5.47e-05 (instrument.background.c0) | 5.47e-05 (instrument.background.c0) | 5.47e-05 (instrument.background.c0) | 5.39 (phases.0.scale) | 5.39 (phases.0.scale) | 5.39 (phases.0.scale) | 5.39 (phases.0.scale) | 5.39 (phases.0.scale) | 5.39 (phases.0.scale) | 5.39 (phases.0.scale) |
| 194 | 5.9e-06 (phases.0.cell.c) | 5.9e-06 (phases.0.cell.c) | 5.9e-06 (phases.0.cell.c) | 5.9e-06 (phases.0.cell.c) | 0 | 5.9e-06 (phases.0.cell.c) | 0 | 0 | 2.26e-09 (phases.0.scale) | 7.68e-05 (instrument.background.c0) | 7.66e-05 (instrument.background.c0) | 7.66e-05 (instrument.background.c0) | 7.66e-05 (instrument.background.c0) | 7.66e-05 (instrument.background.c0) | 7.68e-05 (instrument.background.c0) | 7.66e-05 (instrument.background.c0) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) |
| 195 | 9.73e-09 (phases.0.cell.c) | 9.73e-09 (phases.0.cell.c) | 9.73e-09 (phases.0.cell.c) | 9.73e-09 (phases.0.cell.c) | 0 | 3.55e-09 (phases.0.scale) | 0 | 0 | 9.73e-09 (phases.0.cell.c) | 0.00022 (phases.0.scale) | 0.00022 (phases.0.scale) | 0.00022 (phases.0.scale) | 0.00022 (phases.0.scale) | 0.00022 (phases.0.scale) | 0.00022 (phases.0.scale) | 0.00022 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) |
| 196 | 5.69e-05 (phases.0.scale) | 5.69e-05 (phases.0.scale) | 5.69e-05 (phases.0.scale) | 5.69e-05 (phases.0.scale) | 0 | 5.69e-05 (phases.0.scale) | 0 | 0 | 1.11e-08 (phases.0.scale) | 0 | 5.69e-05 (phases.0.scale) | 5.69e-05 (phases.0.scale) | 5.69e-05 (phases.0.scale) | 5.69e-05 (phases.0.scale) | 0 | 5.69e-05 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) |
| 197 | 3.33e-09 (phases.0.scale) | 3.33e-09 (phases.0.scale) | 3.33e-09 (phases.0.scale) | 3.33e-09 (phases.0.scale) | 0 | 1.24e-08 (phases.0.scale) | 0 | 0 | 9.09e-09 (phases.0.scale) | 0.000317 (phases.0.scale) | 0.000317 (phases.0.scale) | 0.000317 (phases.0.scale) | 0.000317 (phases.0.scale) | 0.000317 (phases.0.scale) | 0.000317 (phases.0.scale) | 0.000317 (phases.0.scale) | 5.23 (phases.0.scale) | 5.23 (phases.0.scale) | 5.23 (phases.0.scale) | 5.23 (phases.0.scale) | 5.23 (phases.0.scale) | 5.23 (phases.0.scale) | 5.23 (phases.0.scale) |
| 198 | 4.26e-05 (phases.0.scale) | 4.26e-05 (phases.0.scale) | 4.26e-05 (phases.0.scale) | 4.26e-05 (phases.0.scale) | 0 | 4.26e-05 (phases.0.scale) | 0 | 0 | 9.78e-09 (phases.0.cell.c) | 0 | 4.26e-05 (phases.0.scale) | 4.26e-05 (phases.0.scale) | 4.26e-05 (phases.0.scale) | 4.26e-05 (phases.0.scale) | 0 | 4.26e-05 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) |
| 199 | 9.73e-09 (phases.0.scale) | 9.73e-09 (phases.0.scale) | 9.73e-09 (phases.0.scale) | 9.73e-09 (phases.0.scale) | 0 | 3.74e-09 (phases.0.scale) | 0 | 0 | 1.35e-08 (phases.0.scale) | 3.89e-05 (phases.0.scale) | 3.89e-05 (phases.0.scale) | 3.89e-05 (phases.0.scale) | 3.89e-05 (phases.0.scale) | 3.89e-05 (phases.0.scale) | 3.89e-05 (phases.0.scale) | 3.89e-05 (phases.0.scale) | 5.28 (phases.0.scale) | 5.28 (phases.0.scale) | 5.28 (phases.0.scale) | 5.28 (phases.0.scale) | 5.28 (phases.0.scale) | 5.28 (phases.0.scale) | 5.28 (phases.0.scale) |
| 200 | 7.3e-05 (phases.0.scale) | 7.3e-05 (phases.0.scale) | 7.3e-05 (phases.0.scale) | 7.3e-05 (phases.0.scale) | 0 | 7.3e-05 (phases.0.scale) | 0 | 0 | 7.08e-09 (phases.0.scale) | 0.000115 (phases.0.scale) | 0.000188 (phases.0.scale) | 0.000188 (phases.0.scale) | 0.000188 (phases.0.scale) | 0.000188 (phases.0.scale) | 0.000115 (phases.0.scale) | 0.000188 (phases.0.scale) | 5.05 (phases.0.scale) | 5.05 (phases.0.scale) | 5.05 (phases.0.scale) | 5.05 (phases.0.scale) | 5.05 (phases.0.scale) | 5.05 (phases.0.scale) | 5.05 (phases.0.scale) |
| 201 | 9.67e-09 (phases.0.cell.c) | 9.67e-09 (phases.0.cell.c) | 9.67e-09 (phases.0.cell.c) | 9.67e-09 (phases.0.cell.c) | 0 | 9.67e-09 (phases.0.cell.c) | 0 | 0 | 1.5e-09 (instrument.zero_shift) | 0.000151 (phases.0.scale) | 0.000151 (phases.0.scale) | 0.000151 (phases.0.scale) | 0.000151 (phases.0.scale) | 0.000151 (phases.0.scale) | 0.000151 (phases.0.scale) | 0.000151 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) |
| 202 | 0.000115 (phases.0.scale) | 0.000115 (phases.0.scale) | 0.000115 (phases.0.scale) | 0.000115 (phases.0.scale) | 0 | 0.000115 (phases.0.scale) | 0 | 0 | 2.2e-09 (instrument.zero_shift) | 0.000186 (phases.0.scale) | 8.87e-05 (phases.0.cell.c) | 8.87e-05 (phases.0.cell.c) | 8.87e-05 (phases.0.cell.c) | 8.87e-05 (phases.0.cell.c) | 0.000186 (phases.0.scale) | 8.87e-05 (phases.0.cell.c) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) |
| 203 | 8.47e-08 (phases.0.cell.c) | 8.47e-08 (phases.0.cell.c) | 8.47e-08 (phases.0.cell.c) | 8.47e-08 (phases.0.cell.c) | 0 | 8.47e-08 (phases.0.cell.c) | 0 | 0 | 4.2e-09 (phases.0.scale) | 0.000239 (phases.0.scale) | 0.000239 (phases.0.scale) | 0.000239 (phases.0.scale) | 0.000239 (phases.0.scale) | 0.000239 (phases.0.scale) | 0.000239 (phases.0.scale) | 0.000239 (phases.0.scale) | 5.17 (phases.0.scale) | 5.17 (phases.0.scale) | 5.17 (phases.0.scale) | 5.17 (phases.0.scale) | 5.17 (phases.0.scale) | 5.17 (phases.0.scale) | 5.17 (phases.0.scale) |
| 204 | 8.77e-05 (phases.0.scale) | 8.77e-05 (phases.0.scale) | 8.77e-05 (phases.0.scale) | 8.77e-05 (phases.0.scale) | 0 | 8.77e-05 (phases.0.scale) | 0 | 0 | 9.48e-09 (phases.0.cell.c) | 0 | 8.77e-05 (phases.0.scale) | 8.77e-05 (phases.0.scale) | 8.77e-05 (phases.0.scale) | 8.77e-05 (phases.0.scale) | 0 | 8.77e-05 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) |
| 205 | 2.15e-08 (phases.0.scale) | 2.15e-08 (phases.0.scale) | 2.15e-08 (phases.0.scale) | 2.15e-08 (phases.0.scale) | 0 | 2.38e-08 (phases.0.scale) | 0 | 0 | 9.69e-09 (phases.0.cell.c) | 1.31e-05 (phases.0.scale) | 1.31e-05 (phases.0.scale) | 1.31e-05 (phases.0.scale) | 1.31e-05 (phases.0.scale) | 1.31e-05 (phases.0.scale) | 1.31e-05 (phases.0.scale) | 1.31e-05 (phases.0.scale) | 4.95 (phases.0.scale) | 4.95 (phases.0.scale) | 4.95 (phases.0.scale) | 4.95 (phases.0.scale) | 4.95 (phases.0.scale) | 4.95 (phases.0.scale) | 4.95 (phases.0.scale) |
| 206 | 2.41e-06 (phases.0.scale) | 2.41e-06 (phases.0.scale) | 2.41e-06 (phases.0.scale) | 2.41e-06 (phases.0.scale) | 0 | 2.42e-06 (phases.0.scale) | 0 | 0 | 8.37e-09 (phases.0.scale) | 5.02e-05 (phases.0.scale) | 4.78e-05 (phases.0.scale) | 4.78e-05 (phases.0.scale) | 4.78e-05 (phases.0.scale) | 4.78e-05 (phases.0.scale) | 5.02e-05 (phases.0.scale) | 4.78e-05 (phases.0.scale) | 4.92 (phases.0.scale) | 4.92 (phases.0.scale) | 4.92 (phases.0.scale) | 4.92 (phases.0.scale) | 4.92 (phases.0.scale) | 4.92 (phases.0.scale) | 4.92 (phases.0.scale) |
| 207 | 0.000114 (phases.0.scale) | 0.000114 (phases.0.scale) | 0.000114 (phases.0.scale) | 0.000114 (phases.0.scale) | 0 | 0.000114 (phases.0.scale) | 0 | 0 | 1.24e-08 (phases.0.scale) | 0 | 0.000114 (phases.0.scale) | 0.000114 (phases.0.scale) | 0.000114 (phases.0.scale) | 0.000114 (phases.0.scale) | 0 | 0.000114 (phases.0.scale) | 4.96 (phases.0.scale) | 4.96 (phases.0.scale) | 4.96 (phases.0.scale) | 4.96 (phases.0.scale) | 4.96 (phases.0.scale) | 4.96 (phases.0.scale) | 4.96 (phases.0.scale) |
| 208 | 9.94e-09 (phases.0.scale) | 9.94e-09 (phases.0.scale) | 9.94e-09 (phases.0.scale) | 9.94e-09 (phases.0.scale) | 0 | 6.25e-09 (phases.0.scale) | 0 | 0 | 3.69e-09 (phases.0.scale) | 7.04e-05 (phases.0.scale) | 7.04e-05 (phases.0.scale) | 7.04e-05 (phases.0.scale) | 7.04e-05 (phases.0.scale) | 7.04e-05 (phases.0.scale) | 7.04e-05 (phases.0.scale) | 7.04e-05 (phases.0.scale) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) |
| 209 | 1.28e-08 (phases.0.scale) | 1.28e-08 (phases.0.scale) | 1.28e-08 (phases.0.scale) | 1.28e-08 (phases.0.scale) | 0 | 4.14e-09 (instrument.profile.u) | 0 | 0 | 1.2e-08 (phases.0.scale) | 1.85e-05 (phases.0.scale) | 1.86e-05 (phases.0.scale) | 1.86e-05 (phases.0.scale) | 1.86e-05 (phases.0.scale) | 1.86e-05 (phases.0.scale) | 1.85e-05 (phases.0.scale) | 1.85e-05 (phases.0.scale) | 4.86 (phases.0.scale) | 4.86 (phases.0.scale) | 4.86 (phases.0.scale) | 4.86 (phases.0.scale) | 4.86 (phases.0.scale) | 4.86 (phases.0.scale) | 4.86 (phases.0.scale) |
| 210 | 1.15e-08 (phases.0.scale) | 1.15e-08 (phases.0.scale) | 1.15e-08 (phases.0.scale) | 1.15e-08 (phases.0.scale) | 0 | 9.26e-09 (phases.0.cell.c) | 0 | 0 | 9.26e-09 (phases.0.cell.c) | 1.9e-06 (phases.0.cell.c) | 1.9e-06 (phases.0.cell.c) | 1.9e-06 (phases.0.cell.c) | 1.9e-06 (phases.0.cell.c) | 1.9e-06 (phases.0.cell.c) | 1.9e-06 (phases.0.cell.c) | 1.89e-06 (phases.0.cell.c) | 4.83 (phases.0.scale) | 4.83 (phases.0.scale) | 4.83 (phases.0.scale) | 4.83 (phases.0.scale) | 4.83 (phases.0.scale) | 4.83 (phases.0.scale) | 4.83 (phases.0.scale) |
| 211 | 9.29e-09 (phases.0.cell.c) | 9.29e-09 (phases.0.cell.c) | 9.29e-09 (phases.0.cell.c) | 9.29e-09 (phases.0.cell.c) | 0 | 9.29e-09 (phases.0.cell.c) | 0 | 0 | 4.38e-09 (instrument.zero_shift) | 0.000159 (phases.0.scale) | 0.000159 (phases.0.scale) | 0.000159 (phases.0.scale) | 0.000159 (phases.0.scale) | 0.000159 (phases.0.scale) | 0.000159 (phases.0.scale) | 0.000159 (phases.0.scale) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) |
| 212 | 2.16e-08 (phases.0.scale) | 2.16e-08 (phases.0.scale) | 2.16e-08 (phases.0.scale) | 2.16e-08 (phases.0.scale) | 0 | 1.09e-08 (instrument.zero_shift) | 0 | 0 | 1.95e-08 (phases.0.scale) | 7.85e-05 (phases.0.scale) | 7.85e-05 (phases.0.scale) | 7.85e-05 (phases.0.scale) | 7.85e-05 (phases.0.scale) | 7.85e-05 (phases.0.scale) | 7.85e-05 (phases.0.scale) | 7.85e-05 (phases.0.scale) | 5.02 (phases.0.scale) | 5.02 (phases.0.scale) | 5.02 (phases.0.scale) | 5.02 (phases.0.scale) | 5.02 (phases.0.scale) | 5.02 (phases.0.scale) | 5.02 (phases.0.scale) |
| 213 | 8.63e-05 (phases.0.cell.c) | 8.63e-05 (phases.0.cell.c) | 8.63e-05 (phases.0.cell.c) | 8.63e-05 (phases.0.cell.c) | 0 | 8.63e-05 (phases.0.cell.c) | 0 | 0 | 1.35e-08 (phases.0.scale) | 0 | 8.63e-05 (phases.0.cell.c) | 8.63e-05 (phases.0.cell.c) | 8.63e-05 (phases.0.cell.c) | 8.63e-05 (phases.0.cell.c) | 0 | 8.63e-05 (phases.0.cell.c) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) |
| 214 | 1.43e-08 (phases.0.scale) | 1.43e-08 (phases.0.scale) | 1.43e-08 (phases.0.scale) | 1.43e-08 (phases.0.scale) | 0 | 2e-08 (phases.0.scale) | 0 | 0 | 5.73e-09 (phases.0.scale) | 6.7e-06 (instrument.background.c2) | 6.69e-06 (instrument.background.c2) | 6.69e-06 (instrument.background.c2) | 6.69e-06 (instrument.background.c2) | 6.69e-06 (instrument.background.c2) | 6.7e-06 (instrument.background.c2) | 6.69e-06 (instrument.background.c2) | 4.8 (phases.0.scale) | 4.8 (phases.0.scale) | 4.8 (phases.0.scale) | 4.8 (phases.0.scale) | 4.8 (phases.0.scale) | 4.8 (phases.0.scale) | 4.8 (phases.0.scale) |
| 215 | 9.18e-09 (phases.0.cell.c) | 9.18e-09 (phases.0.cell.c) | 9.18e-09 (phases.0.cell.c) | 9.18e-09 (phases.0.cell.c) | 0 | 1.24e-09 (instrument.profile.u) | 0 | 0 | 9.18e-09 (phases.0.cell.c) | 4.2e-05 (instrument.background.c0) | 4.2e-05 (instrument.background.c0) | 4.2e-05 (instrument.background.c0) | 4.2e-05 (instrument.background.c0) | 4.2e-05 (instrument.background.c0) | 4.2e-05 (instrument.background.c0) | 4.2e-05 (instrument.background.c0) | 4.89 (phases.0.scale) | 4.89 (phases.0.scale) | 4.89 (phases.0.scale) | 4.89 (phases.0.scale) | 4.89 (phases.0.scale) | 4.89 (phases.0.scale) | 4.89 (phases.0.scale) |
| 216 | 3.03e-05 (phases.0.scale) | 3.03e-05 (phases.0.scale) | 3.03e-05 (phases.0.scale) | 3.03e-05 (phases.0.scale) | 0 | 3.03e-05 (phases.0.scale) | 0 | 0 | 6.55e-09 (phases.0.scale) | 7.65e-05 (phases.0.cell.c) | 5.63e-05 (phases.0.cell.c) | 5.63e-05 (phases.0.cell.c) | 5.63e-05 (phases.0.cell.c) | 5.63e-05 (phases.0.cell.c) | 7.65e-05 (phases.0.cell.c) | 5.63e-05 (phases.0.cell.c) | 4.88 (phases.0.scale) | 4.88 (phases.0.scale) | 4.88 (phases.0.scale) | 4.88 (phases.0.scale) | 4.88 (phases.0.scale) | 4.88 (phases.0.scale) | 4.88 (phases.0.scale) |
| 217 | 1.82e-08 (phases.0.cell.c) | 1.82e-08 (phases.0.cell.c) | 1.82e-08 (phases.0.cell.c) | 1.82e-08 (phases.0.cell.c) | 0 | 1.82e-08 (phases.0.cell.c) | 0 | 0 | 2.91e-09 (phases.0.scale) | 4.95e-05 (phases.0.scale) | 4.95e-05 (phases.0.scale) | 4.95e-05 (phases.0.scale) | 4.95e-05 (phases.0.scale) | 4.95e-05 (phases.0.scale) | 4.95e-05 (phases.0.scale) | 4.95e-05 (phases.0.scale) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) |
| 218 | 2.9e-06 (phases.0.cell.c) | 2.9e-06 (phases.0.cell.c) | 2.9e-06 (phases.0.cell.c) | 2.9e-06 (phases.0.cell.c) | 0 | 2.9e-06 (phases.0.cell.c) | 0 | 0 | 1.21e-08 (phases.0.scale) | 0 | 2.9e-06 (phases.0.cell.c) | 2.9e-06 (phases.0.cell.c) | 2.9e-06 (phases.0.cell.c) | 2.9e-06 (phases.0.cell.c) | 0 | 2.9e-06 (phases.0.cell.c) | 4.79 (phases.0.scale) | 4.79 (phases.0.scale) | 4.79 (phases.0.scale) | 4.79 (phases.0.scale) | 4.79 (phases.0.scale) | 4.79 (phases.0.scale) | 4.79 (phases.0.scale) |
| 219 | 2.7e-06 (instrument.background.c3) | 2.7e-06 (instrument.background.c3) | 2.7e-06 (instrument.background.c3) | 2.7e-06 (instrument.background.c3) | 0 | 2.71e-06 (instrument.background.c3) | 0 | 0 | 1.21e-08 (phases.0.scale) | 9.06e-09 (phases.0.cell.c) | 2.7e-06 (instrument.background.c3) | 2.7e-06 (instrument.background.c3) | 2.7e-06 (instrument.background.c3) | 2.7e-06 (instrument.background.c3) | 9.06e-09 (phases.0.cell.c) | 2.71e-06 (instrument.background.c3) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) |
| 220 | 7.25e-05 (phases.0.scale) | 7.25e-05 (phases.0.scale) | 7.25e-05 (phases.0.scale) | 7.25e-05 (phases.0.scale) | 0 | 7.24e-05 (phases.0.scale) | 0 | 0 | 1.89e-08 (phases.0.scale) | 0 | 7.25e-05 (phases.0.scale) | 7.25e-05 (phases.0.scale) | 7.25e-05 (phases.0.scale) | 7.25e-05 (phases.0.scale) | 0 | 7.24e-05 (phases.0.scale) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) |
| 221 | 9.03e-09 (phases.0.cell.c) | 9.03e-09 (phases.0.cell.c) | 9.03e-09 (phases.0.cell.c) | 9.03e-09 (phases.0.cell.c) | 0 | 1.13e-08 (phases.0.scale) | 0 | 0 | 9.03e-09 (phases.0.cell.c) | 7.95e-05 (instrument.background.c0) | 7.95e-05 (instrument.background.c0) | 7.95e-05 (instrument.background.c0) | 7.95e-05 (instrument.background.c0) | 7.95e-05 (instrument.background.c0) | 7.95e-05 (instrument.background.c0) | 7.95e-05 (instrument.background.c0) | 4.84 (phases.0.scale) | 4.84 (phases.0.scale) | 4.84 (phases.0.scale) | 4.84 (phases.0.scale) | 4.84 (phases.0.scale) | 4.84 (phases.0.scale) | 4.84 (phases.0.scale) |
| 222 | 8.96e-08 (phases.0.cell.c) | 8.96e-08 (phases.0.cell.c) | 8.96e-08 (phases.0.cell.c) | 8.96e-08 (phases.0.cell.c) | 0 | 8.96e-08 (phases.0.cell.c) | 0 | 0 | 5.47e-09 (phases.0.scale) | 2.26e-05 (instrument.background.c2) | 2.26e-05 (instrument.background.c2) | 2.26e-05 (instrument.background.c2) | 2.26e-05 (instrument.background.c2) | 2.26e-05 (instrument.background.c2) | 2.26e-05 (instrument.background.c2) | 2.26e-05 (instrument.background.c2) | 4.71 (phases.0.scale) | 4.71 (phases.0.scale) | 4.71 (phases.0.scale) | 4.71 (phases.0.scale) | 4.71 (phases.0.scale) | 4.71 (phases.0.scale) | 4.71 (phases.0.scale) |
| 223 | 9.06e-09 (phases.0.cell.c) | 9.06e-09 (phases.0.cell.c) | 9.06e-09 (phases.0.cell.c) | 9.06e-09 (phases.0.cell.c) | 0 | 9.06e-09 (phases.0.cell.c) | 0 | 0 | 5.73e-09 (phases.0.scale) | 6.07e-05 (instrument.background.c0) | 6.07e-05 (instrument.background.c0) | 6.07e-05 (instrument.background.c0) | 6.07e-05 (instrument.background.c0) | 6.07e-05 (instrument.background.c0) | 6.07e-05 (instrument.background.c0) | 6.07e-05 (instrument.background.c0) | 4.61 (phases.0.scale) | 4.61 (phases.0.scale) | 4.61 (phases.0.scale) | 4.61 (phases.0.scale) | 4.61 (phases.0.scale) | 4.61 (phases.0.scale) | 4.61 (phases.0.scale) |
| 224 | 2.5e-06 (phases.0.cell.c) | 2.5e-06 (phases.0.cell.c) | 2.5e-06 (phases.0.cell.c) | 2.5e-06 (phases.0.cell.c) | 0 | 2.49e-06 (phases.0.cell.c) | 0 | 0 | 1.19e-08 (phases.0.scale) | 2.49e-05 (phases.0.scale) | 2.54e-05 (phases.0.scale) | 2.54e-05 (phases.0.scale) | 2.54e-05 (phases.0.scale) | 2.54e-05 (phases.0.scale) | 2.49e-05 (phases.0.scale) | 2.53e-05 (phases.0.scale) | 4.67 (phases.0.scale) | 4.67 (phases.0.scale) | 4.67 (phases.0.scale) | 4.67 (phases.0.scale) | 4.67 (phases.0.scale) | 4.67 (phases.0.scale) | 4.67 (phases.0.scale) |
| 225 | 1.29e-08 (phases.0.scale) | 1.29e-08 (phases.0.scale) | 1.29e-08 (phases.0.scale) | 1.29e-08 (phases.0.scale) | 0 | 8.84e-09 (phases.0.cell.c) | 0 | 0 | 7.82e-09 (phases.0.scale) | 3.4e-05 (instrument.background.c0) | 3.4e-05 (instrument.background.c0) | 3.4e-05 (instrument.background.c0) | 3.4e-05 (instrument.background.c0) | 3.4e-05 (instrument.background.c0) | 3.4e-05 (instrument.background.c0) | 3.4e-05 (instrument.background.c0) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) |
| 226 | 1.08e-08 (phases.0.scale) | 1.08e-08 (phases.0.scale) | 1.08e-08 (phases.0.scale) | 1.08e-08 (phases.0.scale) | 0 | 1.14e-08 (phases.0.scale) | 0 | 0 | 8.79e-09 (phases.0.cell.c) | 5.7e-05 (phases.0.cell.c) | 5.7e-05 (phases.0.cell.c) | 5.7e-05 (phases.0.cell.c) | 5.7e-05 (phases.0.cell.c) | 5.7e-05 (phases.0.cell.c) | 5.7e-05 (phases.0.cell.c) | 5.7e-05 (phases.0.cell.c) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) |
| 227 | 2.86e-07 (phases.0.cell.c) | 2.86e-07 (phases.0.cell.c) | 2.86e-07 (phases.0.cell.c) | 2.86e-07 (phases.0.cell.c) | 0 | 2.86e-07 (phases.0.cell.c) | 0 | 0 | 9.33e-09 (phases.0.scale) | 5.09e-05 (phases.0.scale) | 5.09e-05 (phases.0.scale) | 5.09e-05 (phases.0.scale) | 5.09e-05 (phases.0.scale) | 5.09e-05 (phases.0.scale) | 5.09e-05 (phases.0.scale) | 5.09e-05 (phases.0.scale) | 4.65 (phases.0.scale) | 4.65 (phases.0.scale) | 4.65 (phases.0.scale) | 4.65 (phases.0.scale) | 4.65 (phases.0.scale) | 4.65 (phases.0.scale) | 4.65 (phases.0.scale) |
| 228 | 1.07e-08 (phases.0.scale) | 1.07e-08 (phases.0.scale) | 1.07e-08 (phases.0.scale) | 1.07e-08 (phases.0.scale) | 0 | 1.24e-08 (phases.0.scale) | 0 | 0 | 8.71e-09 (phases.0.cell.c) | 2.06e-05 (instrument.background.c0) | 2.06e-05 (instrument.background.c0) | 2.06e-05 (instrument.background.c0) | 2.06e-05 (instrument.background.c0) | 2.06e-05 (instrument.background.c0) | 2.06e-05 (instrument.background.c0) | 2.06e-05 (instrument.background.c0) | 4.78 (phases.0.scale) | 4.78 (phases.0.scale) | 4.78 (phases.0.scale) | 4.78 (phases.0.scale) | 4.78 (phases.0.scale) | 4.78 (phases.0.scale) | 4.78 (phases.0.scale) |
| 229 | 9.1e-09 (phases.0.scale) | 9.1e-09 (phases.0.scale) | 9.1e-09 (phases.0.scale) | 9.1e-09 (phases.0.scale) | 0 | 8.83e-09 (phases.0.scale) | 0 | 0 | 8.79e-09 (phases.0.cell.c) | 0.000147 (phases.0.scale) | 0.000147 (phases.0.scale) | 0.000147 (phases.0.scale) | 0.000147 (phases.0.scale) | 0.000147 (phases.0.scale) | 0.000147 (phases.0.scale) | 0.000147 (phases.0.scale) | 4.62 (phases.0.scale) | 4.62 (phases.0.scale) | 4.62 (phases.0.scale) | 4.62 (phases.0.scale) | 4.62 (phases.0.scale) | 4.62 (phases.0.scale) | 4.62 (phases.0.scale) |
| 230 | 2.02e-09 (instrument.zero_shift) | 2.02e-09 (instrument.zero_shift) | 2.02e-09 (instrument.zero_shift) | 2.02e-09 (instrument.zero_shift) | 0 | 1.64e-08 (phases.0.scale) | 0 | 0 | 1.6e-08 (phases.0.scale) | 0.000179 (phases.0.scale) | 0.000179 (phases.0.scale) | 0.000179 (phases.0.scale) | 0.000179 (phases.0.scale) | 0.000179 (phases.0.scale) | 0.000179 (phases.0.scale) | 0.000179 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) |
| 231 | 8.63e-09 (phases.0.cell.c) | 8.63e-09 (phases.0.cell.c) | 8.63e-09 (phases.0.cell.c) | 8.63e-09 (phases.0.cell.c) | 0 | 1.28e-08 (phases.0.scale) | 0 | 0 | 1.7e-08 (phases.0.scale) | 2.75e-05 (phases.0.scale) | 2.75e-05 (phases.0.scale) | 2.75e-05 (phases.0.scale) | 2.75e-05 (phases.0.scale) | 2.75e-05 (phases.0.scale) | 2.75e-05 (phases.0.scale) | 2.75e-05 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) |
| 232 | 3.88e-06 (instrument.background.c2) | 3.88e-06 (instrument.background.c2) | 3.88e-06 (instrument.background.c2) | 3.88e-06 (instrument.background.c2) | 0 | 3.88e-06 (instrument.background.c2) | 0 | 0 | 1.45e-09 (phases.0.scale) | 0.000146 (phases.0.scale) | 0.000149 (phases.0.scale) | 0.000149 (phases.0.scale) | 0.000149 (phases.0.scale) | 0.000149 (phases.0.scale) | 0.000146 (phases.0.scale) | 0.000149 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) |
| 233 | 8.7e-09 (phases.0.cell.c) | 8.7e-09 (phases.0.cell.c) | 8.7e-09 (phases.0.cell.c) | 8.7e-09 (phases.0.cell.c) | 0 | 8.7e-09 (phases.0.cell.c) | 0 | 0 | 7.88e-10 (phases.0.scale) | 0.000132 (phases.0.scale) | 0.000132 (phases.0.scale) | 0.000132 (phases.0.scale) | 0.000132 (phases.0.scale) | 0.000132 (phases.0.scale) | 0.000132 (phases.0.scale) | 0.000132 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) |
| 234 | 1.75e-08 (phases.0.scale) | 1.75e-08 (phases.0.scale) | 1.75e-08 (phases.0.scale) | 1.75e-08 (phases.0.scale) | 0 | 1.35e-08 (phases.0.scale) | 0 | 0 | 3.97e-09 (phases.0.scale) | 4.47e-05 (instrument.background.c2) | 4.47e-05 (instrument.background.c2) | 4.47e-05 (instrument.background.c2) | 4.47e-05 (instrument.background.c2) | 4.47e-05 (instrument.background.c2) | 4.47e-05 (instrument.background.c2) | 4.47e-05 (instrument.background.c2) | 4.56 (phases.0.scale) | 4.56 (phases.0.scale) | 4.56 (phases.0.scale) | 4.56 (phases.0.scale) | 4.56 (phases.0.scale) | 4.56 (phases.0.scale) | 4.56 (phases.0.scale) |
| 235 | 4.03e-07 (phases.0.cell.c) | 4.03e-07 (phases.0.cell.c) | 4.03e-07 (phases.0.cell.c) | 4.03e-07 (phases.0.cell.c) | 0 | 4.03e-07 (phases.0.cell.c) | 0 | 0 | 5.21e-09 (phases.0.scale) | 0.000102 (phases.0.scale) | 0.000102 (phases.0.scale) | 0.000102 (phases.0.scale) | 0.000102 (phases.0.scale) | 0.000102 (phases.0.scale) | 0.000102 (phases.0.scale) | 0.000102 (phases.0.scale) | 4.64 (phases.0.scale) | 4.64 (phases.0.scale) | 4.64 (phases.0.scale) | 4.64 (phases.0.scale) | 4.64 (phases.0.scale) | 4.64 (phases.0.scale) | 4.64 (phases.0.scale) |
| 236 | 2.63e-06 (instrument.background.c3) | 2.63e-06 (instrument.background.c3) | 2.63e-06 (instrument.background.c3) | 2.63e-06 (instrument.background.c3) | 0 | 2.63e-06 (instrument.background.c3) | 0 | 0 | 8.55e-09 (phases.0.cell.c) | 0.000295 (phases.0.scale) | 0.000296 (phases.0.scale) | 0.000296 (phases.0.scale) | 0.000296 (phases.0.scale) | 0.000296 (phases.0.scale) | 0.000295 (phases.0.scale) | 0.000296 (phases.0.scale) | 4.54 (phases.0.scale) | 4.54 (phases.0.scale) | 4.54 (phases.0.scale) | 4.54 (phases.0.scale) | 4.54 (phases.0.scale) | 4.54 (phases.0.scale) | 4.54 (phases.0.scale) |
| 237 | 2.84e-06 (phases.0.scale) | 2.84e-06 (phases.0.scale) | 2.84e-06 (phases.0.scale) | 2.84e-06 (phases.0.scale) | 0 | 2.83e-06 (phases.0.scale) | 0 | 0 | 1.07e-08 (phases.0.scale) | 9.16e-05 (phases.0.scale) | 9.44e-05 (phases.0.scale) | 9.44e-05 (phases.0.scale) | 9.44e-05 (phases.0.scale) | 9.44e-05 (phases.0.scale) | 9.16e-05 (phases.0.scale) | 9.44e-05 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) |
| 238 | 8.56e-09 (phases.0.cell.c) | 8.56e-09 (phases.0.cell.c) | 8.56e-09 (phases.0.cell.c) | 8.56e-09 (phases.0.cell.c) | 0 | 8.56e-09 (phases.0.cell.c) | 0 | 0 | 2.12e-09 (instrument.zero_shift) | 9.77e-05 (instrument.background.c0) | 9.77e-05 (instrument.background.c0) | 9.77e-05 (instrument.background.c0) | 9.77e-05 (instrument.background.c0) | 9.77e-05 (instrument.background.c0) | 9.77e-05 (instrument.background.c0) | 9.77e-05 (instrument.background.c0) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) |
| 239 | 2.56e-08 (phases.0.cell.c) | 2.56e-08 (phases.0.cell.c) | 2.56e-08 (phases.0.cell.c) | 2.56e-08 (phases.0.cell.c) | 0 | 2.56e-08 (phases.0.cell.c) | 0 | 0 | 1.49e-08 (phases.0.scale) | 0.000133 (phases.0.scale) | 0.000133 (phases.0.scale) | 0.000133 (phases.0.scale) | 0.000133 (phases.0.scale) | 0.000133 (phases.0.scale) | 0.000133 (phases.0.scale) | 0.000133 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) |
| 240 | 3.84e-05 (phases.0.cell.c) | 3.84e-05 (phases.0.cell.c) | 3.84e-05 (phases.0.cell.c) | 3.84e-05 (phases.0.cell.c) | 0 | 3.84e-05 (phases.0.cell.c) | 0 | 0 | 9.33e-09 (phases.0.scale) | 0 | 3.84e-05 (phases.0.cell.c) | 3.84e-05 (phases.0.cell.c) | 3.84e-05 (phases.0.cell.c) | 3.84e-05 (phases.0.cell.c) | 0 | 3.84e-05 (phases.0.cell.c) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) |
| 241 | 1.36e-07 (phases.0.cell.c) | 1.36e-07 (phases.0.cell.c) | 1.36e-07 (phases.0.cell.c) | 1.36e-07 (phases.0.cell.c) | 0 | 1.28e-07 (phases.0.cell.c) | 0 | 0 | 8.52e-09 (phases.0.cell.c) | 6.98e-05 (phases.0.cell.c) | 6.99e-05 (phases.0.cell.c) | 6.99e-05 (phases.0.cell.c) | 6.99e-05 (phases.0.cell.c) | 6.99e-05 (phases.0.cell.c) | 6.98e-05 (phases.0.cell.c) | 6.99e-05 (phases.0.cell.c) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) |
| 242 | 8.45e-09 (phases.0.cell.c) | 8.45e-09 (phases.0.cell.c) | 8.45e-09 (phases.0.cell.c) | 8.45e-09 (phases.0.cell.c) | 0 | 1.69e-08 (phases.0.cell.c) | 0 | 0 | 8.45e-09 (phases.0.cell.c) | 8.52e-05 (phases.0.cell.c) | 8.52e-05 (phases.0.cell.c) | 8.52e-05 (phases.0.cell.c) | 8.52e-05 (phases.0.cell.c) | 8.52e-05 (phases.0.cell.c) | 8.52e-05 (phases.0.cell.c) | 8.52e-05 (phases.0.cell.c) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) |
| 243 | 7.75e-06 (instrument.background.c2) | 7.75e-06 (instrument.background.c2) | 7.75e-06 (instrument.background.c2) | 7.75e-06 (instrument.background.c2) | 0 | 7.75e-06 (instrument.background.c2) | 0 | 0 | 8.82e-09 (phases.0.scale) | 0 | 7.75e-06 (instrument.background.c2) | 7.75e-06 (instrument.background.c2) | 7.75e-06 (instrument.background.c2) | 7.75e-06 (instrument.background.c2) | 0 | 7.75e-06 (instrument.background.c2) | 4.49 (phases.0.scale) | 4.49 (phases.0.scale) | 4.49 (phases.0.scale) | 4.49 (phases.0.scale) | 4.49 (phases.0.scale) | 4.49 (phases.0.scale) | 4.49 (phases.0.scale) |
| 244 | 6.01e-06 (phases.0.scale) | 6.01e-06 (phases.0.scale) | 6.01e-06 (phases.0.scale) | 6.01e-06 (phases.0.scale) | 0 | 6.01e-06 (phases.0.scale) | 0 | 0 | 8.39e-09 (phases.0.cell.c) | 6.63e-05 (instrument.background.c0) | 6.74e-05 (instrument.background.c0) | 6.74e-05 (instrument.background.c0) | 6.74e-05 (instrument.background.c0) | 6.74e-05 (instrument.background.c0) | 6.63e-05 (instrument.background.c0) | 6.74e-05 (instrument.background.c0) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) |
| 245 | 7.68e-05 (phases.0.scale) | 7.68e-05 (phases.0.scale) | 7.68e-05 (phases.0.scale) | 7.68e-05 (phases.0.scale) | 0 | 7.69e-05 (phases.0.scale) | 0 | 0 | 4.5e-08 (phases.0.scale) | 0 | 7.68e-05 (phases.0.scale) | 7.68e-05 (phases.0.scale) | 7.68e-05 (phases.0.scale) | 7.68e-05 (phases.0.scale) | 0 | 7.69e-05 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) |
| 246 | 5.52e-09 (phases.0.scale) | 5.52e-09 (phases.0.scale) | 5.52e-09 (phases.0.scale) | 5.52e-09 (phases.0.scale) | 0 | 4.05e-09 (instrument.profile.u) | 0 | 0 | 4.9e-09 (phases.0.scale) | 0.000129 (phases.0.scale) | 0.000129 (phases.0.scale) | 0.000129 (phases.0.scale) | 0.000129 (phases.0.scale) | 0.000129 (phases.0.scale) | 0.000129 (phases.0.scale) | 0.000129 (phases.0.scale) | 4.18 (phases.0.scale) | 4.18 (phases.0.scale) | 4.18 (phases.0.scale) | 4.18 (phases.0.scale) | 4.18 (phases.0.scale) | 4.18 (phases.0.scale) | 4.18 (phases.0.scale) |
| 247 | 1.66e-08 (phases.0.cell.c) | 1.66e-08 (phases.0.cell.c) | 1.66e-08 (phases.0.cell.c) | 1.66e-08 (phases.0.cell.c) | 0 | 8.29e-09 (phases.0.cell.c) | 0 | 0 | 8.29e-09 (phases.0.cell.c) | 0.000166 (phases.0.scale) | 0.000166 (phases.0.scale) | 0.000166 (phases.0.scale) | 0.000166 (phases.0.scale) | 0.000166 (phases.0.scale) | 0.000166 (phases.0.scale) | 0.000166 (phases.0.scale) | 4.37 (phases.0.scale) | 4.37 (phases.0.scale) | 4.37 (phases.0.scale) | 4.37 (phases.0.scale) | 4.37 (phases.0.scale) | 4.37 (phases.0.scale) | 4.37 (phases.0.scale) |

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref` the reference; truth the simulation.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound | ref | truth |
|---|---|---|---|---|---|---|---|---|---|---|
| 48 | `phases.0.cell.a` | 3.969078(33) | 3.969078(33) | 3.969078(33) | 3.969078(33) | 3.969078(33) | 3.969078(33) | 3.969078(33) | 3.969078(33) | 3.96909 |
| 48 | `phases.0.scale` | 0.00020045(45) | 0.00020045(45) | 0.00020045(45) | 0.00020045(45) | 0.00020045(45) | 0.00020045(45) | 0.00020045(45) | 0.00020045(45) | 0.0002 |
| 48 | `instrument.zero_shift` | 0.00592(10) | 0.00592(10) | 0.00592(10) | 0.00592(10) | 0.00592(10) | 0.00592(10) | 0.00592(10) | 0.00592(10) | 0.006 |
| 48 | `instrument.profile.w` | 0.000951(57) | 0.000951(57) | 0.000951(57) | 0.000951(57) | 0.000951(57) | 0.000951(57) | 0.000951(57) | 0.000951(57) | 0.001 |
| 48 | `instrument.background.c0` | 298.81(44) | 298.81(44) | 298.81(44) | 298.81(44) | 298.81(44) | 298.81(44) | 298.81(44) | 298.81(44) | 300 |
| 49 | `phases.0.cell.a` | 3.968987(33) | 3.968987(33) | 3.968987(33) | 3.968987(33) | 3.968987(33) | 3.968987(33) | 3.968987(33) | 3.968987(33) | 3.969 |
| 49 | `phases.0.scale` | 0.00019987(45) | 0.00019987(45) | 0.00019987(45) | 0.00019987(45) | 0.00019987(45) | 0.00019987(45) | 0.00019987(45) | 0.00019987(45) | 0.0002 |
| 49 | `instrument.zero_shift` | 0.00599(11) | 0.00599(11) | 0.00599(11) | 0.00599(11) | 0.00599(11) | 0.00599(11) | 0.00599(11) | 0.00599(11) | 0.006 |
| 49 | `instrument.profile.w` | 0.001005(58) | 0.001005(58) | 0.001005(58) | 0.001005(58) | 0.001005(58) | 0.001005(58) | 0.001005(58) | 0.001005(58) | 0.001 |
| 49 | `instrument.background.c0` | 299.02(44) | 299.02(44) | 299.02(44) | 299.02(44) | 299.02(44) | 299.02(44) | 299.02(44) | 299.02(44) | 300 |
| 50 | `phases.0.cell.a` | 3.968872(34) | 3.968872(34) | 3.968872(34) | 3.968872(34) | 3.968872(34) | 3.968872(34) | 3.968872(34) | 3.968872(34) | 3.9689 |
| 50 | `phases.0.scale` | 0.00019995(47) | 0.00019995(47) | 0.00019995(47) | 0.00019995(47) | 0.00019995(47) | 0.00019995(47) | 0.00019995(47) | 0.00019995(47) | 0.0002 |
| 50 | `instrument.zero_shift` | 0.00592(11) | 0.00592(11) | 0.00592(11) | 0.00592(11) | 0.00592(11) | 0.00592(11) | 0.00592(11) | 0.00592(11) | 0.006 |
| 50 | `instrument.profile.w` | 0.000953(60) | 0.000953(60) | 0.000953(60) | 0.000953(60) | 0.000953(60) | 0.000953(60) | 0.000953(60) | 0.000953(60) | 0.001 |
| 50 | `instrument.background.c0` | 449.48(53) | 449.48(53) | 449.48(53) | 449.48(53) | 449.48(53) | 449.48(53) | 449.48(53) | 449.48(53) | 450 |
| 51 | `phases.0.cell.a` | 3.968777(35) | 3.968777(35) | 3.968777(35) | 3.968777(35) | 3.968777(35) | 3.968777(35) | 3.968777(35) | 3.968777(35) | 3.96881 |
| 51 | `phases.0.scale` | 0.00020017(49) | 0.00020017(49) | 0.00020017(49) | 0.00020017(49) | 0.00020017(49) | 0.00020017(49) | 0.00020017(49) | 0.00020017(49) | 0.0002 |
| 51 | `instrument.zero_shift` | 0.00587(11) | 0.00587(11) | 0.00587(11) | 0.00587(11) | 0.00587(11) | 0.00587(11) | 0.00587(11) | 0.00587(11) | 0.006 |
| 51 | `instrument.profile.w` | 0.001022(62) | 0.001022(62) | 0.001022(62) | 0.001022(62) | 0.001022(62) | 0.001022(62) | 0.001022(62) | 0.001022(62) | 0.001 |
| 51 | `instrument.background.c0` | 448.91(55) | 448.91(55) | 448.91(55) | 448.91(55) | 448.91(55) | 448.91(55) | 448.91(55) | 448.91(55) | 450 |
| 52 | `phases.0.cell.a` | 3.968736(35) | 3.968736(35) | 3.968736(35) | 3.968736(35) | 3.968736(35) | 3.968736(35) | 3.968736(35) | 3.968736(35) | 3.96871 |
| 52 | `phases.0.scale` | 0.00020009(48) | 0.00020009(48) | 0.00020009(48) | 0.00020009(48) | 0.00020009(48) | 0.00020009(48) | 0.00020009(48) | 0.00020009(48) | 0.0002 |
| 52 | `instrument.zero_shift` | 0.00608(11) | 0.00608(11) | 0.00608(11) | 0.00608(11) | 0.00608(11) | 0.00608(11) | 0.00608(11) | 0.00608(11) | 0.006 |
| 52 | `instrument.profile.w` | 0.001065(61) | 0.001065(61) | 0.001065(61) | 0.001065(61) | 0.001065(61) | 0.001065(61) | 0.001065(61) | 0.001065(61) | 0.001 |
| 52 | `instrument.background.c0` | 448.57(54) | 448.57(54) | 448.57(54) | 448.57(54) | 448.57(54) | 448.57(54) | 448.57(54) | 448.57(54) | 450 |
| 85 | `phases.0.cell.a` | 3.965517(34) | 3.965517(34) | 3.965517(34) | 3.965517(34) | 3.965517(34) | 3.965517(34) | 3.965517(34) | 3.965517(34) | 3.96554 |
| 85 | `phases.0.scale` | 0.00020008(47) | 0.00020008(47) | 0.00020008(47) | 0.00020008(47) | 0.00020008(47) | 0.00020008(47) | 0.00020008(47) | 0.00020008(47) | 0.0002 |
| 85 | `instrument.zero_shift` | 0.00588(11) | 0.00588(11) | 0.00588(11) | 0.00588(11) | 0.00588(11) | 0.00588(11) | 0.00588(11) | 0.00588(11) | 0.006 |
| 85 | `instrument.profile.w` | 0.000989(59) | 0.000989(59) | 0.000989(59) | 0.000989(59) | 0.000989(59) | 0.000989(59) | 0.000989(59) | 0.000989(59) | 0.001 |
| 85 | `instrument.background.c0` | 449.47(53) | 449.47(53) | 449.47(53) | 449.47(53) | 449.47(53) | 449.47(53) | 449.47(53) | 449.47(53) | 450 |
| 86 | `phases.0.cell.a` | 3.965447(34) | 3.965447(34) | 3.965447(34) | 3.965447(34) | 3.965447(34) | 3.965447(34) | 3.965447(34) | 3.965447(34) | 3.96545 |
| 86 | `phases.0.scale` | 0.00020042(48) | 0.00020042(48) | 0.00020042(48) | 0.00020042(48) | 0.00020042(48) | 0.00020042(48) | 0.00020042(48) | 0.00020042(48) | 0.0002 |
| 86 | `instrument.zero_shift` | 0.00597(11) | 0.00597(11) | 0.00597(11) | 0.00597(11) | 0.00597(11) | 0.00597(11) | 0.00597(11) | 0.00597(11) | 0.006 |
| 86 | `instrument.profile.w` | 0.000960(60) | 0.000960(60) | 0.000960(60) | 0.000960(60) | 0.000960(60) | 0.000960(60) | 0.000960(60) | 0.000960(60) | 0.001 |
| 86 | `instrument.background.c0` | 449.58(54) | 449.58(54) | 449.58(54) | 449.58(54) | 449.58(54) | 449.58(54) | 449.58(54) | 449.58(54) | 450 |
| 87 | `phases.0.cell.a` | — | — | — | — | — | — | — | — | 3.96535 |
| 87 | `phases.0.scale` | 0.000000000(93) | 0.000000000(93) | 0.000000000(93) | 0.000000000(93) | 0.000000000(93) | 0.000000073(70) | 0.000000073(70) | 0.000000052(88) | 0 |
| 87 | `instrument.zero_shift` | 0.00597089 | 0.00597089 | 0.00597089 | 0.00597089 | 0.00597089 | -0.0231(48) | -0.0231(48) | 0.0119(47) | 0.006 |
| 87 | `instrument.profile.w` | 0.000960163 | 0.000960163 | 0.000960163 | 0.000960163 | 0.000960163 | 0.0001(18) | 0.0001(18) | 0.0014(63) | 0.001 |
| 87 | `instrument.background.c0` | 449.17(53) | 449.17(53) | 449.17(53) | 449.17(53) | 449.17(53) | 449.14(53) | 449.14(53) | 449.15(53) | 450 |
| 88 | `phases.0.cell.a` | 3.965228(35) | 3.965228(35) | 3.965228(35) | 3.965228(35) | 3.965228(35) | 3.965228(35) | — | 3.965228(35) | 3.96526 |
| 88 | `phases.0.scale` | 0.00019975(48) | 0.00019975(48) | 0.00019975(48) | 0.00019975(48) | 0.00019975(48) | 0.00019975(48) | 0.0000001(50) | 0.00019975(48) | 0.0002 |
| 88 | `instrument.zero_shift` | 0.00594(11) | 0.00594(11) | 0.00594(11) | 0.00594(11) | 0.00594(11) | 0.00594(11) | -0.02(36) | 0.00594(11) | 0.006 |
| 88 | `instrument.profile.w` | 0.000956(61) | 0.000956(61) | 0.000956(61) | 0.000956(61) | 0.000956(61) | 0.000956(61) | 0.000(99) | 0.000956(61) | 0.001 |
| 88 | `instrument.background.c0` | 449.55(54) | 449.55(54) | 449.55(54) | 449.55(54) | 449.55(54) | 449.55(54) | 449(16) | 449.55(54) | 450 |
| 89 | `phases.0.cell.a` | 3.965185(34) | 3.965185(34) | 3.965185(34) | 3.965185(34) | 3.965185(34) | 3.965185(34) | — | 3.965185(34) | 3.96516 |
| 89 | `phases.0.scale` | 0.00020012(48) | 0.00020012(48) | 0.00020012(48) | 0.00020012(48) | 0.00020012(48) | 0.00020012(48) | 0.0000001(49) | 0.00020012(48) | 0.0002 |
| 89 | `instrument.zero_shift` | 0.00610(11) | 0.00610(11) | 0.00610(11) | 0.00610(11) | 0.00610(11) | 0.00610(11) | -0.02(35) | 0.00610(11) | 0.006 |
| 89 | `instrument.profile.w` | 0.000939(60) | 0.000939(60) | 0.000939(60) | 0.000939(60) | 0.000939(60) | 0.000939(60) | 0.000(97) | 0.000939(60) | 0.001 |
| 89 | `instrument.background.c0` | 448.15(53) | 448.15(53) | 448.15(53) | 448.15(53) | 448.15(53) | 448.15(53) | 449(16) | 448.15(53) | 450 |
| 90 | `phases.0.cell.a` | 3.965076(34) | 3.965076(34) | 3.965076(34) | 3.965076(34) | 3.965076(34) | 3.965076(34) | — | 3.965076(34) | 3.96506 |
| 90 | `phases.0.scale` | 0.00020024(47) | 0.00020024(47) | 0.00020024(47) | 0.00020024(47) | 0.00020024(47) | 0.00020024(47) | 0.0000001(49) | 0.00020024(47) | 0.0002 |
| 90 | `instrument.zero_shift` | 0.00603(11) | 0.00603(11) | 0.00603(11) | 0.00603(11) | 0.00603(11) | 0.00603(11) | -0.02(35) | 0.00603(11) | 0.006 |
| 90 | `instrument.profile.w` | 0.001079(60) | 0.001079(60) | 0.001079(60) | 0.001079(60) | 0.001079(60) | 0.001079(60) | 0.000(97) | 0.001079(60) | 0.001 |
| 90 | `instrument.background.c0` | 448.21(53) | 448.21(53) | 448.21(53) | 448.21(53) | 448.21(53) | 448.21(53) | 449(16) | 448.21(53) | 450 |
| 91 | `phases.0.cell.a` | 3.964927(35) | 3.964927(35) | 3.964927(35) | 3.964927(35) | 3.964927(35) | 3.964927(35) | — | 3.964927(35) | 3.96497 |
| 91 | `phases.0.scale` | 0.00020065(49) | 0.00020065(49) | 0.00020065(49) | 0.00020065(49) | 0.00020065(49) | 0.00020065(49) | 0.0000001(48) | 0.00020065(49) | 0.0002 |
| 91 | `instrument.zero_shift` | 0.00590(11) | 0.00590(11) | 0.00590(11) | 0.00590(11) | 0.00590(11) | 0.00590(11) | -0.02(35) | 0.00590(11) | 0.006 |
| 91 | `instrument.profile.w` | 0.001053(61) | 0.001053(61) | 0.001053(61) | 0.001053(61) | 0.001053(61) | 0.001053(61) | 0.000(97) | 0.001053(61) | 0.001 |
| 91 | `instrument.background.c0` | 449.95(55) | 449.95(55) | 449.95(55) | 449.95(55) | 449.95(55) | 449.95(55) | 449(16) | 449.95(55) | 450 |
| 92 | `phases.0.cell.a` | 3.964862(34) | 3.964862(34) | 3.964862(34) | 3.964862(34) | 3.964862(34) | 3.964862(34) | — | 3.964862(34) | 3.96487 |
| 92 | `phases.0.scale` | 0.00020028(47) | 0.00020028(47) | 0.00020028(47) | 0.00020028(47) | 0.00020028(47) | 0.00020028(47) | 0.0000001(47) | 0.00020028(47) | 0.0002 |
| 92 | `instrument.zero_shift` | 0.00594(11) | 0.00594(11) | 0.00594(11) | 0.00594(11) | 0.00594(11) | 0.00594(11) | -0.02(34) | 0.00594(11) | 0.006 |
| 92 | `instrument.profile.w` | 0.001001(59) | 0.001001(59) | 0.001001(59) | 0.001001(59) | 0.001001(59) | 0.001001(59) | 0.000(93) | 0.001001(59) | 0.001 |
| 92 | `instrument.background.c0` | 448.71(53) | 448.71(53) | 448.71(53) | 448.71(53) | 448.71(53) | 448.71(53) | 449(16) | 448.71(53) | 450 |
| 93 | `phases.0.cell.a` | 3.964783(34) | 3.964783(34) | 3.964783(34) | 3.964783(34) | 3.964783(34) | 3.964783(34) | — | 3.964783(34) | 3.96478 |
| 93 | `phases.0.scale` | 0.00019963(47) | 0.00019963(47) | 0.00019963(47) | 0.00019963(47) | 0.00019963(47) | 0.00019963(47) | 0.0000001(47) | 0.00019963(47) | 0.0002 |
| 93 | `instrument.zero_shift` | 0.00605(11) | 0.00605(11) | 0.00605(11) | 0.00605(11) | 0.00605(11) | 0.00605(11) | -0.02(34) | 0.00605(11) | 0.006 |
| 93 | `instrument.profile.w` | 0.000982(60) | 0.000982(60) | 0.000982(60) | 0.000982(60) | 0.000982(60) | 0.000982(60) | 0.000(93) | 0.000982(60) | 0.001 |
| 93 | `instrument.background.c0` | 449.60(53) | 449.60(53) | 449.60(53) | 449.60(53) | 449.60(53) | 449.60(53) | 449(16) | 449.60(53) | 450 |
| 94 | `phases.0.cell.a` | 3.964678(35) | 3.964678(35) | 3.964678(35) | 3.964678(35) | 3.964678(35) | 3.964678(35) | — | 3.964678(35) | 3.96468 |
| 94 | `phases.0.scale` | 0.00019975(49) | 0.00019975(49) | 0.00019975(49) | 0.00019975(49) | 0.00019975(49) | 0.00019975(49) | 0.0000001(46) | 0.00019975(49) | 0.0002 |
| 94 | `instrument.zero_shift` | 0.00598(11) | 0.00598(11) | 0.00598(11) | 0.00598(11) | 0.00598(11) | 0.00598(11) | -0.02(33) | 0.00598(11) | 0.006 |
| 94 | `instrument.profile.w` | 0.000974(62) | 0.000974(62) | 0.000974(62) | 0.000974(62) | 0.000974(62) | 0.000974(62) | 0.000(94) | 0.000974(62) | 0.001 |
| 94 | `instrument.background.c0` | 449.44(55) | 449.44(55) | 449.44(55) | 449.44(55) | 449.44(55) | 449.44(55) | 449(16) | 449.44(55) | 450 |
| 95 | `phases.0.cell.a` | 3.964528(35) | 3.964528(35) | 3.964528(35) | 3.964528(35) | 3.964528(35) | 3.964528(35) | — | 3.964528(35) | 3.96458 |
| 95 | `phases.0.scale` | 0.00019953(48) | 0.00019953(48) | 0.00019953(48) | 0.00019953(48) | 0.00019953(48) | 0.00019953(48) | 0.0000001(46) | 0.00019953(48) | 0.0002 |
| 95 | `instrument.zero_shift` | 0.00588(11) | 0.00588(11) | 0.00588(11) | 0.00588(11) | 0.00588(11) | 0.00588(11) | -0.02(33) | 0.00588(11) | 0.006 |
| 95 | `instrument.profile.w` | 0.000978(61) | 0.000978(61) | 0.000978(61) | 0.000978(61) | 0.000978(61) | 0.000978(61) | 0.000(95) | 0.000978(61) | 0.001 |
| 95 | `instrument.background.c0` | 449.13(54) | 449.13(54) | 449.13(54) | 449.13(54) | 449.13(54) | 449.13(54) | 449(16) | 449.13(54) | 450 |
| 96 | `phases.0.cell.a` | 3.964471(34) | 3.964471(34) | 3.964471(34) | 3.964471(34) | 3.964471(34) | 3.964471(34) | — | 3.964471(34) | 3.96449 |
| 96 | `phases.0.scale` | 0.00020023(48) | 0.00020023(48) | 0.00020023(48) | 0.00020023(48) | 0.00020023(48) | 0.00020023(48) | 0.0000001(46) | 0.00020023(48) | 0.0002 |
| 96 | `instrument.zero_shift` | 0.00594(11) | 0.00594(11) | 0.00594(11) | 0.00594(11) | 0.00594(11) | 0.00594(11) | -0.02(33) | 0.00594(11) | 0.006 |
| 96 | `instrument.profile.w` | 0.001001(60) | 0.001001(60) | 0.001001(60) | 0.001001(60) | 0.001001(60) | 0.001001(60) | 0.000(93) | 0.001001(60) | 0.001 |
| 96 | `instrument.background.c0` | 449.05(53) | 449.05(53) | 449.05(53) | 449.05(53) | 449.05(53) | 449.05(53) | 449(16) | 449.05(53) | 450 |
| 97 | `phases.0.cell.a` | 3.964370(34) | 3.964370(34) | 3.964370(34) | 3.964370(34) | 3.964370(34) | 3.964370(34) | — | 3.964370(34) | 3.96439 |
| 97 | `phases.0.scale` | 0.00019978(47) | 0.00019978(47) | 0.00019978(47) | 0.00019978(47) | 0.00019978(47) | 0.00019978(47) | 0.0000001(45) | 0.00019978(47) | 0.0002 |
| 97 | `instrument.zero_shift` | 0.00593(11) | 0.00593(11) | 0.00593(11) | 0.00593(11) | 0.00593(11) | 0.00593(11) | -0.02(32) | 0.00593(11) | 0.006 |
| 97 | `instrument.profile.w` | 0.001019(59) | 0.001019(59) | 0.001019(59) | 0.001019(59) | 0.001019(59) | 0.001019(59) | 0.000(92) | 0.001019(59) | 0.001 |
| 97 | `instrument.background.c0` | 448.54(53) | 448.54(53) | 448.54(53) | 448.54(53) | 448.54(53) | 448.54(53) | 449(16) | 448.54(53) | 450 |
| 98 | `phases.0.cell.a` | 3.964227(34) | 3.964227(34) | 3.964227(34) | 3.964227(34) | 3.964227(34) | 3.964227(34) | — | 3.964227(34) | 3.9643 |
| 98 | `phases.0.scale` | 0.00020068(48) | 0.00020068(48) | 0.00020068(48) | 0.00020068(48) | 0.00020068(48) | 0.00020068(48) | 0.0000001(45) | 0.00020068(48) | 0.0002 |
| 98 | `instrument.zero_shift` | 0.00577(11) | 0.00577(11) | 0.00577(11) | 0.00577(11) | 0.00577(11) | 0.00577(11) | -0.02(32) | 0.00577(11) | 0.006 |
| 98 | `instrument.profile.w` | 0.001065(60) | 0.001065(60) | 0.001065(60) | 0.001065(60) | 0.001065(60) | 0.001065(60) | 0.000(93) | 0.001065(60) | 0.001 |
| 98 | `instrument.background.c0` | 448.51(53) | 448.51(53) | 448.51(53) | 448.51(53) | 448.51(53) | 448.51(53) | 449(16) | 448.51(53) | 450 |
| 99 | `phases.0.cell.a` | 3.964213(34) | 3.964213(34) | 3.964213(34) | 3.964213(34) | 3.964213(34) | 3.964213(34) | — | 3.964213(34) | 3.9642 |
| 99 | `phases.0.scale` | 0.00020104(47) | 0.00020104(47) | 0.00020104(47) | 0.00020104(47) | 0.00020104(47) | 0.00020104(47) | 0.0000001(44) | 0.00020104(47) | 0.0002 |
| 99 | `instrument.zero_shift` | 0.00604(10) | 0.00604(10) | 0.00604(10) | 0.00604(10) | 0.00604(10) | 0.00604(10) | -0.02(32) | 0.00604(10) | 0.006 |
| 99 | `instrument.profile.w` | 0.000903(59) | 0.000903(59) | 0.000903(59) | 0.000903(59) | 0.000903(59) | 0.000903(59) | 0.000(90) | 0.000903(59) | 0.001 |
| 99 | `instrument.background.c0` | 448.69(52) | 448.69(52) | 448.69(52) | 448.69(52) | 448.69(52) | 448.69(52) | 449(16) | 448.69(52) | 450 |
| 100 | `phases.0.cell.a` | 3.964121(34) | 3.964121(34) | 3.964121(34) | 3.964121(34) | 3.964121(34) | 3.964121(34) | — | 3.964121(34) | 3.9641 |
| 100 | `phases.0.scale` | 0.00019935(47) | 0.00019935(47) | 0.00019935(47) | 0.00019935(47) | 0.00019935(47) | 0.00019935(47) | 0.0000001(43) | 0.00019935(47) | 0.0002 |
| 100 | `instrument.zero_shift` | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | -0.02(31) | 0.00604(11) | 0.006 |
| 100 | `instrument.profile.w` | 0.000953(59) | 0.000953(59) | 0.000953(59) | 0.000953(59) | 0.000953(59) | 0.000953(59) | 0.000(89) | 0.000953(59) | 0.001 |
| 100 | `instrument.background.c0` | 449.13(53) | 449.13(53) | 449.13(53) | 449.13(53) | 449.13(53) | 449.13(53) | 449(16) | 449.13(53) | 450 |
| 101 | `phases.0.cell.a` | 3.964021(34) | 3.964021(34) | 3.964021(34) | 3.964021(34) | 3.964021(34) | 3.964021(34) | — | 3.964021(34) | 3.96401 |
| 101 | `phases.0.scale` | 0.00019970(48) | 0.00019970(48) | 0.00019970(48) | 0.00019970(48) | 0.00019970(48) | 0.00019970(48) | 0.0000001(43) | 0.00019970(48) | 0.0002 |
| 101 | `instrument.zero_shift` | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | -0.02(31) | 0.00604(11) | 0.006 |
| 101 | `instrument.profile.w` | 0.000976(60) | 0.000976(60) | 0.000976(60) | 0.000976(60) | 0.000976(60) | 0.000976(60) | 0.000(89) | 0.000976(60) | 0.001 |
| 101 | `instrument.background.c0` | 448.69(54) | 448.69(54) | 448.69(54) | 448.69(54) | 448.69(54) | 448.69(54) | 449(16) | 448.69(54) | 450 |
| 102 | `phases.0.cell.a` | 3.963916(35) | 3.963916(35) | 3.963916(35) | 3.963916(35) | 3.963916(35) | 3.963916(35) | — | 3.963916(35) | 3.96391 |
| 102 | `phases.0.scale` | 0.00019985(49) | 0.00019985(49) | 0.00019985(49) | 0.00019985(49) | 0.00019985(49) | 0.00019985(49) | 0.0000001(43) | 0.00019985(49) | 0.0002 |
| 102 | `instrument.zero_shift` | 0.00602(11) | 0.00602(11) | 0.00602(11) | 0.00602(11) | 0.00602(11) | 0.00602(11) | -0.02(31) | 0.00602(11) | 0.006 |
| 102 | `instrument.profile.w` | 0.001029(62) | 0.001029(62) | 0.001029(62) | 0.001029(62) | 0.001029(62) | 0.001029(62) | 0.000(89) | 0.001029(62) | 0.001 |
| 102 | `instrument.background.c0` | 448.37(55) | 448.37(55) | 448.37(55) | 448.37(55) | 448.37(55) | 448.37(55) | 449(16) | 448.37(55) | 450 |
| 103 | `phases.0.cell.a` | 3.963821(35) | 3.963821(35) | 3.963821(35) | 3.963821(35) | 3.963821(35) | 3.963821(35) | — | 3.963821(35) | 3.96382 |
| 103 | `phases.0.scale` | 0.00019989(48) | 0.00019989(48) | 0.00019989(48) | 0.00019989(48) | 0.00019989(48) | 0.00019989(48) | 0.0000001(42) | 0.00019989(48) | 0.0002 |
| 103 | `instrument.zero_shift` | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | -0.02(31) | 0.00604(11) | 0.006 |
| 103 | `instrument.profile.w` | 0.000958(61) | 0.000958(61) | 0.000958(61) | 0.000958(61) | 0.000958(61) | 0.000958(61) | 0.000(87) | 0.000958(61) | 0.001 |
| 103 | `instrument.background.c0` | 448.76(54) | 448.76(54) | 448.76(54) | 448.76(54) | 448.76(54) | 448.76(54) | 449(16) | 448.76(54) | 450 |
| 104 | `phases.0.cell.a` | 3.963692(35) | 3.963692(35) | 3.963692(35) | 3.963692(35) | 3.963692(35) | 3.963692(35) | — | 3.963692(35) | 3.96372 |
| 104 | `phases.0.scale` | 0.00020013(49) | 0.00020013(49) | 0.00020013(49) | 0.00020013(49) | 0.00020013(49) | 0.00020013(49) | 0.0000001(42) | 0.00020013(49) | 0.0002 |
| 104 | `instrument.zero_shift` | 0.00589(11) | 0.00589(11) | 0.00589(11) | 0.00589(11) | 0.00589(11) | 0.00589(11) | -0.02(30) | 0.00589(11) | 0.006 |
| 104 | `instrument.profile.w` | 0.001012(61) | 0.001012(61) | 0.001012(61) | 0.001012(61) | 0.001012(61) | 0.001012(61) | 0.000(87) | 0.001012(61) | 0.001 |
| 104 | `instrument.background.c0` | 449.42(55) | 449.42(55) | 449.42(55) | 449.42(55) | 449.42(55) | 449.42(55) | 449(16) | 449.42(55) | 450 |
| 105 | `phases.0.cell.a` | 3.963637(35) | 3.963637(35) | 3.963637(35) | 3.963637(35) | 3.963637(35) | 3.963637(35) | — | 3.963637(35) | 3.96363 |
| 105 | `phases.0.scale` | 0.00019887(48) | 0.00019887(48) | 0.00019887(48) | 0.00019887(48) | 0.00019887(48) | 0.00019887(48) | 0.0000001(41) | 0.00019887(48) | 0.0002 |
| 105 | `instrument.zero_shift` | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | -0.02(29) | 0.00604(11) | 0.006 |
| 105 | `instrument.profile.w` | 0.000924(61) | 0.000924(61) | 0.000924(61) | 0.000924(61) | 0.000924(61) | 0.000924(61) | 0.000(86) | 0.000924(61) | 0.001 |
| 105 | `instrument.background.c0` | 450.38(55) | 450.38(55) | 450.38(55) | 450.38(55) | 450.38(55) | 450.38(55) | 449(16) | 450.38(55) | 450 |
| 106 | `phases.0.cell.a` | 3.963579(35) | 3.963579(35) | 3.963579(35) | 3.963579(35) | 3.963579(35) | 3.963579(35) | — | 3.963579(35) | 3.96353 |
| 106 | `phases.0.scale` | 0.00020026(48) | 0.00020026(48) | 0.00020026(48) | 0.00020026(48) | 0.00020026(48) | 0.00020026(48) | 0.0000001(41) | 0.00020026(48) | 0.0002 |
| 106 | `instrument.zero_shift` | 0.00612(11) | 0.00612(11) | 0.00612(11) | 0.00612(11) | 0.00612(11) | 0.00612(11) | -0.02(30) | 0.00612(11) | 0.006 |
| 106 | `instrument.profile.w` | 0.001058(61) | 0.001058(61) | 0.001058(61) | 0.001058(61) | 0.001058(61) | 0.001058(61) | 0.000(85) | 0.001058(61) | 0.001 |
| 106 | `instrument.background.c0` | 449.32(54) | 449.32(54) | 449.32(54) | 449.32(54) | 449.32(54) | 449.32(54) | 449(16) | 449.32(54) | 450 |
| 107 | `phases.0.cell.a` | 3.963421(35) | 3.963421(35) | 3.963421(35) | 3.963421(35) | 3.963421(35) | 3.963421(35) | — | 3.963421(35) | 3.96343 |
| 107 | `phases.0.scale` | 0.00020039(49) | 0.00020039(49) | 0.00020039(49) | 0.00020039(49) | 0.00020039(49) | 0.00020039(49) | 0.0000001(41) | 0.00020039(49) | 0.0002 |
| 107 | `instrument.zero_shift` | 0.00598(11) | 0.00598(11) | 0.00598(11) | 0.00598(11) | 0.00598(11) | 0.00598(11) | -0.02(29) | 0.00598(11) | 0.006 |
| 107 | `instrument.profile.w` | 0.001044(61) | 0.001044(61) | 0.001044(61) | 0.001044(61) | 0.001044(61) | 0.001044(61) | 0.000(86) | 0.001044(61) | 0.001 |
| 107 | `instrument.background.c0` | 448.13(55) | 448.13(55) | 448.13(55) | 448.13(55) | 448.13(55) | 448.13(55) | 449(16) | 448.13(55) | 450 |
| 108 | `phases.0.cell.a` | 3.963393(35) | 3.963393(35) | 3.963393(35) | 3.963393(35) | 3.963393(35) | 3.963393(35) | — | 3.963393(35) | 3.96334 |
| 108 | `phases.0.scale` | 0.00020025(48) | 0.00020025(48) | 0.00020025(48) | 0.00020025(48) | 0.00020025(48) | 0.00020025(48) | 0.0000001(40) | 0.00020025(48) | 0.0002 |
| 108 | `instrument.zero_shift` | 0.00613(11) | 0.00613(11) | 0.00613(11) | 0.00613(11) | 0.00613(11) | 0.00613(11) | -0.02(29) | 0.00613(11) | 0.006 |
| 108 | `instrument.profile.w` | 0.000982(61) | 0.000982(61) | 0.000982(61) | 0.000982(61) | 0.000982(61) | 0.000982(61) | 0.000(85) | 0.000982(61) | 0.001 |
| 108 | `instrument.background.c0` | 448.64(54) | 448.64(54) | 448.64(54) | 448.64(54) | 448.64(54) | 448.64(54) | 449(16) | 448.64(54) | 450 |
| 109 | `phases.0.cell.a` | 3.963222(36) | 3.963222(36) | 3.963222(36) | 3.963222(36) | 3.963222(36) | 3.963222(36) | — | 3.963222(36) | 3.96324 |
| 109 | `phases.0.scale` | 0.00020078(50) | 0.00020078(50) | 0.00020078(50) | 0.00020078(50) | 0.00020078(50) | 0.00020078(50) | 0.0000001(40) | 0.00020078(50) | 0.0002 |
| 109 | `instrument.zero_shift` | 0.00590(11) | 0.00590(11) | 0.00590(11) | 0.00590(11) | 0.00590(11) | 0.00590(11) | -0.02(29) | 0.00590(11) | 0.006 |
| 109 | `instrument.profile.w` | 0.001010(62) | 0.001010(62) | 0.001010(62) | 0.001010(62) | 0.001010(62) | 0.001010(62) | 0.000(85) | 0.001010(62) | 0.001 |
| 109 | `instrument.background.c0` | 448.78(56) | 448.78(56) | 448.78(56) | 448.78(56) | 448.78(56) | 448.78(56) | 449(16) | 448.78(56) | 450 |
| 110 | `phases.0.cell.a` | 3.963115(35) | 3.963115(35) | 3.963115(35) | 3.963115(35) | 3.963115(35) | 3.963115(35) | — | 3.963115(35) | 3.96315 |
| 110 | `phases.0.scale` | 0.00020031(48) | 0.00020031(48) | 0.00020031(48) | 0.00020031(48) | 0.00020031(48) | 0.00020031(48) | 0.0000001(40) | 0.00020031(48) | 0.0002 |
| 110 | `instrument.zero_shift` | 0.00587(11) | 0.00587(11) | 0.00587(11) | 0.00587(11) | 0.00587(11) | 0.00587(11) | -0.02(29) | 0.00587(11) | 0.006 |
| 110 | `instrument.profile.w` | 0.001044(61) | 0.001044(61) | 0.001044(61) | 0.001044(61) | 0.001044(61) | 0.001044(61) | 0.000(85) | 0.001044(61) | 0.001 |
| 110 | `instrument.background.c0` | 448.76(54) | 448.76(54) | 448.76(54) | 448.76(54) | 448.76(54) | 448.76(54) | 449(16) | 448.76(54) | 450 |
| 111 | `phases.0.cell.a` | 3.963016(35) | 3.963016(35) | 3.963016(35) | 3.963016(35) | 3.963016(35) | 3.963016(35) | — | 3.963016(35) | 3.96305 |
| 111 | `phases.0.scale` | 0.00019981(49) | 0.00019981(49) | 0.00019981(49) | 0.00019981(49) | 0.00019981(49) | 0.00019981(49) | 0.0000001(39) | 0.00019981(49) | 0.0002 |
| 111 | `instrument.zero_shift` | 0.00589(11) | 0.00589(11) | 0.00589(11) | 0.00589(11) | 0.00589(11) | 0.00589(11) | -0.02(28) | 0.00589(11) | 0.006 |
| 111 | `instrument.profile.w` | 0.001006(61) | 0.001006(61) | 0.001006(61) | 0.001006(61) | 0.001006(61) | 0.001006(61) | 0.000(83) | 0.001006(61) | 0.001 |
| 111 | `instrument.background.c0` | 448.85(55) | 448.85(55) | 448.85(55) | 448.85(55) | 448.85(55) | 448.85(55) | 449(16) | 448.85(55) | 450 |
| 112 | `phases.0.cell.a` | 3.962952(35) | 3.962952(35) | 3.962952(35) | 3.962952(35) | 3.962952(35) | 3.962952(35) | — | 3.962952(35) | 3.96295 |
| 112 | `phases.0.scale` | 0.00019985(48) | 0.00019985(48) | 0.00019985(48) | 0.00019985(48) | 0.00019985(48) | 0.00019985(48) | 0.0000001(38) | 0.00019984(48) | 0.0002 |
| 112 | `instrument.zero_shift` | 0.00596(11) | 0.00596(11) | 0.00596(11) | 0.00596(11) | 0.00596(11) | 0.00596(11) | -0.02(28) | 0.00596(11) | 0.006 |
| 112 | `instrument.profile.w` | 0.001054(60) | 0.001054(60) | 0.001054(60) | 0.001054(60) | 0.001054(60) | 0.001054(60) | 0.000(84) | 0.001054(60) | 0.001 |
| 112 | `instrument.background.c0` | 448.77(54) | 448.77(54) | 448.77(54) | 448.77(54) | 448.77(54) | 448.77(54) | 449(16) | 448.77(54) | 450 |
| 113 | `phases.0.cell.a` | 3.962878(35) | 3.962878(35) | 3.962878(35) | 3.962878(35) | 3.962878(35) | 3.962878(35) | — | 3.962878(35) | 3.96286 |
| 113 | `phases.0.scale` | 0.00019930(49) | 0.00019930(49) | 0.00019930(49) | 0.00019930(49) | 0.00019930(49) | 0.00019930(49) | 0.0000001(38) | 0.00019930(49) | 0.0002 |
| 113 | `instrument.zero_shift` | 0.00608(11) | 0.00608(11) | 0.00608(11) | 0.00608(11) | 0.00608(11) | 0.00608(11) | -0.02(27) | 0.00608(11) | 0.006 |
| 113 | `instrument.profile.w` | 0.000991(62) | 0.000991(62) | 0.000991(62) | 0.000991(62) | 0.000991(62) | 0.000991(62) | 0.000(83) | 0.000991(62) | 0.001 |
| 113 | `instrument.background.c0` | 449.50(55) | 449.50(55) | 449.50(55) | 449.50(55) | 449.50(55) | 449.50(55) | 449(16) | 449.50(55) | 450 |
| 114 | `phases.0.cell.a` | 3.962787(35) | 3.962787(35) | 3.962787(35) | 3.962787(35) | 3.962787(35) | 3.962787(35) | — | 3.962787(35) | 3.96276 |
| 114 | `phases.0.scale` | 0.00020038(48) | 0.00020038(48) | 0.00020038(48) | 0.00020038(48) | 0.00020038(48) | 0.00020038(48) | 0.0000001(38) | 0.00020038(48) | 0.0002 |
| 114 | `instrument.zero_shift` | 0.00606(11) | 0.00606(11) | 0.00606(11) | 0.00606(11) | 0.00606(11) | 0.00606(11) | -0.02(27) | 0.00606(11) | 0.006 |
| 114 | `instrument.profile.w` | 0.001077(61) | 0.001077(61) | 0.001077(61) | 0.001077(61) | 0.001077(61) | 0.001077(61) | 0.000(82) | 0.001077(61) | 0.001 |
| 114 | `instrument.background.c0` | 448.62(54) | 448.62(54) | 448.62(54) | 448.62(54) | 448.62(54) | 448.62(54) | 449(16) | 448.62(54) | 450 |
| 115 | `phases.0.cell.a` | 3.962673(35) | 3.962673(35) | 3.962673(35) | 3.962673(35) | 3.962673(35) | 3.962673(35) | — | 3.962673(35) | 3.96267 |
| 115 | `phases.0.scale` | 0.00019969(48) | 0.00019969(48) | 0.00019969(48) | 0.00019969(48) | 0.00019969(48) | 0.00019969(48) | 0.0000001(37) | 0.00019969(48) | 0.0002 |
| 115 | `instrument.zero_shift` | 0.00597(11) | 0.00597(11) | 0.00597(11) | 0.00597(11) | 0.00597(11) | 0.00597(11) | -0.02(27) | 0.00597(11) | 0.006 |
| 115 | `instrument.profile.w` | 0.001027(61) | 0.001027(61) | 0.001027(61) | 0.001027(61) | 0.001027(61) | 0.001027(61) | 0.000(80) | 0.001027(61) | 0.001 |
| 115 | `instrument.background.c0` | 449.38(54) | 449.38(54) | 449.38(54) | 449.38(54) | 449.38(54) | 449.38(54) | 449(16) | 449.38(54) | 450 |
| 116 | `phases.0.cell.a` | 3.962597(34) | 3.962597(34) | 3.962597(34) | 3.962597(34) | 3.962597(34) | 3.962597(34) | — | 3.962597(34) | 3.96257 |
| 116 | `phases.0.scale` | 0.00020019(48) | 0.00020019(48) | 0.00020019(48) | 0.00020019(48) | 0.00020019(48) | 0.00020019(48) | 0.0000001(37) | 0.00020019(48) | 0.0002 |
| 116 | `instrument.zero_shift` | 0.00612(11) | 0.00612(11) | 0.00612(11) | 0.00612(11) | 0.00612(11) | 0.00612(11) | -0.02(26) | 0.00612(11) | 0.006 |
| 116 | `instrument.profile.w` | 0.001049(60) | 0.001049(60) | 0.001049(60) | 0.001049(60) | 0.001049(60) | 0.001049(60) | 0.000(81) | 0.001049(60) | 0.001 |
| 116 | `instrument.background.c0` | 448.81(54) | 448.81(54) | 448.81(54) | 448.81(54) | 448.81(54) | 448.81(54) | 449(16) | 448.81(54) | 450 |
| 117 | `phases.0.cell.a` | 3.962498(34) | 3.962498(34) | 3.962498(34) | 3.962498(34) | 3.962498(34) | 3.962498(34) | — | 3.962498(34) | 3.96247 |
| 117 | `phases.0.scale` | 0.00019961(48) | 0.00019961(48) | 0.00019961(48) | 0.00019961(48) | 0.00019961(48) | 0.00019961(48) | 0.0000001(37) | 0.00019961(48) | 0.0002 |
| 117 | `instrument.zero_shift` | 0.00610(11) | 0.00610(11) | 0.00610(11) | 0.00610(11) | 0.00610(11) | 0.00610(11) | -0.02(26) | 0.00610(11) | 0.006 |
| 117 | `instrument.profile.w` | 0.000993(60) | 0.000993(60) | 0.000993(60) | 0.000993(60) | 0.000993(60) | 0.000993(60) | 0.000(81) | 0.000993(60) | 0.001 |
| 117 | `instrument.background.c0` | 449.98(54) | 449.98(54) | 449.98(54) | 449.98(54) | 449.98(54) | 449.98(54) | 449(16) | 449.98(54) | 450 |
| 118 | `phases.0.cell.a` | 3.962429(35) | 3.962429(35) | 3.962429(35) | 3.962429(35) | 3.962429(35) | 3.962429(35) | — | 3.962429(35) | 3.96238 |
| 118 | `phases.0.scale` | 0.00020061(48) | 0.00020061(48) | 0.00020061(48) | 0.00020061(48) | 0.00020061(48) | 0.00020061(48) | 0.0000001(37) | 0.00020061(48) | 0.0002 |
| 118 | `instrument.zero_shift` | 0.00613(11) | 0.00613(11) | 0.00613(11) | 0.00613(11) | 0.00613(11) | 0.00613(11) | -0.02(26) | 0.00613(11) | 0.006 |
| 118 | `instrument.profile.w` | 0.000994(61) | 0.000994(61) | 0.000994(61) | 0.000994(61) | 0.000994(61) | 0.000994(61) | 0.000(80) | 0.000994(61) | 0.001 |
| 118 | `instrument.background.c0` | 448.70(54) | 448.70(54) | 448.70(54) | 448.70(54) | 448.70(54) | 448.70(54) | 449(16) | 448.70(54) | 450 |
| 119 | `phases.0.cell.a` | 3.962255(35) | 3.962255(35) | 3.962255(35) | 3.962255(35) | 3.962255(35) | 3.962255(35) | — | 3.962255(35) | 3.96228 |
| 119 | `phases.0.scale` | 0.00019949(48) | 0.00019949(48) | 0.00019949(48) | 0.00019949(48) | 0.00019949(48) | 0.00019949(48) | 0.0000001(36) | 0.00019949(48) | 0.0002 |
| 119 | `instrument.zero_shift` | 0.00587(11) | 0.00587(11) | 0.00587(11) | 0.00587(11) | 0.00587(11) | 0.00587(11) | -0.02(26) | 0.00587(11) | 0.006 |
| 119 | `instrument.profile.w` | 0.001042(61) | 0.001042(61) | 0.001042(61) | 0.001042(61) | 0.001042(61) | 0.001042(61) | 0.000(79) | 0.001042(61) | 0.001 |
| 119 | `instrument.background.c0` | 449.34(54) | 449.34(54) | 449.34(54) | 449.34(54) | 449.34(54) | 449.34(54) | 449(16) | 449.34(54) | 450 |
| 120 | `phases.0.cell.a` | 3.962195(33) | 3.962195(33) | 3.962195(33) | 3.962195(33) | 3.962195(33) | 3.962195(33) | — | 3.962195(33) | 3.96219 |
| 120 | `phases.0.scale` | 0.00019996(46) | 0.00019996(46) | 0.00019996(46) | 0.00019996(46) | 0.00019996(46) | 0.00019996(46) | 0.0000001(36) | 0.00019997(46) | 0.0002 |
| 120 | `instrument.zero_shift` | 0.00605(10) | 0.00605(10) | 0.00605(10) | 0.00605(10) | 0.00605(10) | 0.00605(10) | -0.02(26) | 0.00605(10) | 0.006 |
| 120 | `instrument.profile.w` | 0.001049(58) | 0.001049(58) | 0.001049(58) | 0.001049(58) | 0.001049(58) | 0.001049(58) | 0.000(81) | 0.001049(58) | 0.001 |
| 120 | `instrument.background.c0` | 448.66(52) | 448.66(52) | 448.66(52) | 448.66(52) | 448.66(52) | 448.66(52) | 449(16) | 448.66(52) | 450 |
| 121 | `phases.0.cell.a` | 3.962037(35) | 3.962037(35) | 3.962037(35) | 3.962037(35) | 3.962037(35) | 3.962037(35) | — | 3.962037(35) | 3.96209 |
| 121 | `phases.0.scale` | 0.00019934(49) | 0.00019934(49) | 0.00019934(49) | 0.00019934(49) | 0.00019934(49) | 0.00019934(49) | 0.0000001(35) | 0.00019934(49) | 0.0002 |
| 121 | `instrument.zero_shift` | 0.00582(11) | 0.00582(11) | 0.00582(11) | 0.00582(11) | 0.00582(11) | 0.00582(11) | -0.02(25) | 0.00582(11) | 0.006 |
| 121 | `instrument.profile.w` | 0.000969(62) | 0.000969(62) | 0.000969(62) | 0.000969(62) | 0.000969(62) | 0.000969(62) | 0.000(78) | 0.000969(62) | 0.001 |
| 121 | `instrument.background.c0` | 448.82(55) | 448.82(55) | 448.82(55) | 448.82(55) | 448.82(55) | 448.82(55) | 449(16) | 448.82(55) | 450 |
| 122 | `phases.0.cell.a` | 3.962006(34) | 3.962006(34) | 3.962006(34) | 3.962006(34) | 3.962006(34) | 3.962006(34) | — | 3.962006(34) | 3.96199 |
| 122 | `phases.0.scale` | 0.00019989(47) | 0.00019989(47) | 0.00019989(47) | 0.00019989(47) | 0.00019989(47) | 0.00019989(47) | 0.0000001(35) | 0.00019989(47) | 0.0002 |
| 122 | `instrument.zero_shift` | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | -0.02(25) | 0.00604(11) | 0.006 |
| 122 | `instrument.profile.w` | 0.000978(59) | 0.000978(59) | 0.000978(59) | 0.000978(59) | 0.000978(59) | 0.000978(59) | 0.000(78) | 0.000978(59) | 0.001 |
| 122 | `instrument.background.c0` | 449.01(53) | 449.01(53) | 449.01(53) | 449.01(53) | 449.01(53) | 449.01(53) | 449(16) | 449.01(53) | 450 |
| 123 | `phases.0.cell.a` | 3.961940(34) | 3.961940(34) | 3.961940(34) | 3.961940(34) | 3.961940(34) | 3.961940(34) | — | 3.961940(34) | 3.9619 |
| 123 | `phases.0.scale` | 0.00019990(47) | 0.00019990(47) | 0.00019990(47) | 0.00019990(47) | 0.00019990(47) | 0.00019990(47) | 0.0000001(34) | 0.00019990(47) | 0.0002 |
| 123 | `instrument.zero_shift` | 0.00612(11) | 0.00612(11) | 0.00612(11) | 0.00612(11) | 0.00612(11) | 0.00612(11) | -0.02(24) | 0.00612(11) | 0.006 |
| 123 | `instrument.profile.w` | 0.000903(60) | 0.000903(60) | 0.000903(60) | 0.000903(60) | 0.000903(60) | 0.000903(60) | 0.000(75) | 0.000903(60) | 0.001 |
| 123 | `instrument.background.c0` | 449.13(53) | 449.13(53) | 449.13(53) | 449.13(53) | 449.13(53) | 449.13(53) | 449(16) | 449.13(53) | 450 |
| 124 | `phases.0.cell.a` | 3.961830(35) | 3.961830(35) | 3.961830(35) | 3.961830(35) | 3.961830(35) | 3.961830(35) | — | 3.961830(35) | 3.9618 |
| 124 | `phases.0.scale` | 0.00020070(49) | 0.00020070(49) | 0.00020070(49) | 0.00020070(49) | 0.00020070(49) | 0.00020070(49) | 0.0000001(35) | 0.00020070(49) | 0.0002 |
| 124 | `instrument.zero_shift` | 0.00610(11) | 0.00610(11) | 0.00610(11) | 0.00610(11) | 0.00610(11) | 0.00610(11) | -0.02(25) | 0.00610(11) | 0.006 |
| 124 | `instrument.profile.w` | 0.001104(62) | 0.001104(62) | 0.001104(62) | 0.001104(62) | 0.001104(62) | 0.001104(62) | 0.000(79) | 0.001104(62) | 0.001 |
| 124 | `instrument.background.c0` | 448.84(55) | 448.84(55) | 448.84(55) | 448.84(55) | 448.84(55) | 448.84(55) | 449(16) | 448.84(55) | 450 |
| 125 | `phases.0.cell.a` | 3.961669(37) | 3.961669(37) | 3.961669(37) | 3.961669(37) | 3.961669(37) | 3.961669(37) | — | 3.961669(37) | 3.96171 |
| 125 | `phases.0.scale` | 0.00019989(52) | 0.00019989(52) | 0.00019989(52) | 0.00019989(52) | 0.00019989(52) | 0.00019989(52) | 0.0000001(34) | 0.00019989(52) | 0.0002 |
| 125 | `instrument.zero_shift` | 0.00591(12) | 0.00591(12) | 0.00591(12) | 0.00591(12) | 0.00591(12) | 0.00591(12) | -0.02(24) | 0.00591(12) | 0.006 |
| 125 | `instrument.profile.w` | 0.001098(66) | 0.001098(66) | 0.001098(66) | 0.001098(66) | 0.001098(66) | 0.001098(66) | 0.000(77) | 0.001098(66) | 0.001 |
| 125 | `instrument.background.c0` | 448.92(58) | 448.92(58) | 448.92(58) | 448.92(58) | 448.92(58) | 448.92(58) | 449(16) | 448.92(58) | 450 |
| 126 | `phases.0.cell.a` | 3.961629(39) | 3.961629(39) | 3.961629(39) | 3.961629(39) | 3.961629(39) | 3.961629(39) | — | 3.961629(39) | 3.96161 |
| 126 | `phases.0.scale` | 0.00020039(54) | 0.00020039(54) | 0.00020039(54) | 0.00020039(54) | 0.00020039(54) | 0.00020039(54) | 0.0000001(34) | 0.00020039(54) | 0.0002 |
| 126 | `instrument.zero_shift` | 0.00602(12) | 0.00602(12) | 0.00602(12) | 0.00602(12) | 0.00602(12) | 0.00602(12) | -0.02(24) | 0.00602(12) | 0.006 |
| 126 | `instrument.profile.w` | 0.001000(69) | 0.001000(69) | 0.001000(69) | 0.001000(69) | 0.001000(69) | 0.001000(69) | 0.000(77) | 0.001000(69) | 0.001 |
| 126 | `instrument.background.c0` | 448.72(61) | 448.72(61) | 448.72(61) | 448.72(61) | 448.72(61) | 448.72(61) | 449(16) | 448.72(61) | 450 |
| 127 | `phases.0.cell.a` | 3.961496(45) | 3.961496(45) | 3.961496(45) | 3.961496(45) | 3.961496(45) | 3.961496(45) | — | 3.961496(45) | 3.96151 |
| 127 | `phases.0.scale` | 0.00019960(63) | 0.00019960(63) | 0.00019960(63) | 0.00019960(63) | 0.00019960(63) | 0.00019960(63) | 0.0000001(33) | 0.00019960(63) | 0.0002 |
| 127 | `instrument.zero_shift` | 0.00596(14) | 0.00596(14) | 0.00596(14) | 0.00596(14) | 0.00596(14) | 0.00596(14) | -0.02(24) | 0.00596(14) | 0.006 |
| 127 | `instrument.profile.w` | 0.000935(79) | 0.000935(79) | 0.000935(79) | 0.000935(79) | 0.000935(79) | 0.000935(79) | 0.000(76) | 0.000935(79) | 0.001 |
| 127 | `instrument.background.c0` | 449.54(71) | 449.54(71) | 449.54(71) | 449.54(71) | 449.54(71) | 449.54(71) | 449(16) | 449.54(71) | 450 |
| 184 | `phases.0.cell.a` | 3.95605(26) | 3.95605(26) | 3.95605(26) | 3.95605(26) | 3.95605(26) | 3.95605(26) | 3.95605(26) | 3.95605(26) | 3.95604 |
| 184 | `phases.0.scale` | 0.0001984(36) | 0.0001984(36) | 0.0001984(36) | 0.0001984(36) | 0.0001984(36) | 0.0001984(36) | 0.0001984(36) | 0.0001984(36) | 0.0002 |
| 184 | `instrument.zero_shift` | 0.00597(81) | 0.00597(81) | 0.00597(81) | 0.00597(81) | 0.00597(81) | 0.00597(81) | 0.00597(81) | 0.00597(81) | 0.006 |
| 184 | `instrument.profile.w` | 0.00100(45) | 0.00100(45) | 0.00100(45) | 0.00100(45) | 0.00100(45) | 0.00100(45) | 0.00100(45) | 0.00100(45) | 0.001 |
| 184 | `instrument.background.c0` | 453.1(40) | 453.1(40) | 453.1(40) | 453.1(40) | 453.1(40) | 453.1(40) | 453.1(40) | 453.1(40) | 450 |
| 185 | `phases.0.cell.a` | 3.95590(27) | 3.95590(27) | 3.95590(27) | 3.95590(27) | 3.95590(27) | 3.95590(27) | 3.95590(27) | 3.95590(27) | 3.95595 |
| 185 | `phases.0.scale` | 0.0001990(37) | 0.0001990(37) | 0.0001990(37) | 0.0001990(37) | 0.0001990(37) | 0.0001990(37) | 0.0001990(37) | 0.0001990(37) | 0.0002 |
| 185 | `instrument.zero_shift` | 0.00583(84) | 0.00583(84) | 0.00583(84) | 0.00583(84) | 0.00583(84) | 0.00583(84) | 0.00583(84) | 0.00583(84) | 0.006 |
| 185 | `instrument.profile.w` | 0.00089(47) | 0.00089(47) | 0.00089(47) | 0.00089(47) | 0.00089(47) | 0.00089(47) | 0.00089(47) | 0.00089(47) | 0.001 |
| 185 | `instrument.background.c0` | 453.3(41) | 453.3(41) | 453.3(41) | 453.3(41) | 453.3(41) | 453.3(41) | 453.3(41) | 453.3(41) | 450 |
| 186 | `phases.0.cell.a` | 3.95296(98) | 3.95296(98) | 3.95296(98) | 3.95296(98) | 3.95296(98) | 3.95296(98) | 3.95296(98) | 3.95296(98) | — |
| 186 | `phases.0.scale` | 0.0001653(64) | 0.0001653(64) | 0.0001653(64) | 0.0001653(64) | 0.0001653(64) | 0.0001653(64) | 0.0001653(64) | 0.0001653(64) | 0.0002 |
| 186 | `instrument.zero_shift` | 0.0003(27) | 0.0003(27) | 0.0003(27) | 0.0003(27) | 0.0003(27) | 0.0003(27) | 0.0003(27) | 0.0003(27) | 0.006 |
| 186 | `instrument.profile.w` | 0.0000(23) | 0.0000(23) | 0.0000(23) | 0.0000(23) | 0.0000(23) | 0.0000(23) | 0.0000(23) | 0.0000(23) | 0.001 |
| 186 | `instrument.background.c0` | 451.0(68) | 451.0(68) | 451.0(68) | 451.0(68) | 451.0(68) | 451.0(68) | 451.0(68) | 451.0(68) | 450 |
| 187 | `phases.0.cell.a` | 3.95282(99) | 3.95282(99) | 3.95282(99) | 3.95282(99) | 3.95282(99) | 3.95282(99) | 3.95282(99) | 3.95282(99) | — |
| 187 | `phases.0.scale` | 0.0001653(65) | 0.0001653(65) | 0.0001653(65) | 0.0001653(65) | 0.0001653(65) | 0.0001653(65) | 0.0001653(65) | 0.0001653(65) | 0.0002 |
| 187 | `instrument.zero_shift` | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.006 |
| 187 | `instrument.profile.w` | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.001 |
| 187 | `instrument.background.c0` | 451.9(69) | 451.9(69) | 451.9(69) | 451.9(69) | 451.9(69) | 451.9(69) | 451.9(69) | 451.9(69) | 450 |
| 188 | `phases.0.cell.a` | 3.95268(99) | 3.95268(99) | 3.95268(99) | 3.95268(99) | 3.95268(99) | 3.95268(99) | 3.95268(99) | 3.95268(99) | — |
| 188 | `phases.0.scale` | 0.0001654(65) | 0.0001654(65) | 0.0001654(65) | 0.0001654(65) | 0.0001654(65) | 0.0001654(65) | 0.0001654(65) | 0.0001654(65) | 0.0002 |
| 188 | `instrument.zero_shift` | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.006 |
| 188 | `instrument.profile.w` | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.001 |
| 188 | `instrument.background.c0` | 450.8(70) | 450.8(70) | 450.8(70) | 450.8(70) | 450.8(70) | 450.8(70) | 450.8(70) | 450.8(70) | 450 |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, the arm's pair, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`; "pair" is the arm differing from this one by one switch (`PAIRED`).  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | pair: bit-identical, differ | differ from ref | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 248 | 115 | 35 (135, 137, 140, 142, 143, 146, 147, 148, 149, 150, 151, 152, …) | 0 | 114 (134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, …) | 248 | — | — | 1 (87) | 13034 | 4831 | 13034 / 14039 | 0.1-1.2 | 113 |
| status | 248 | 1 | 0 | 0 | 0 | 134 | 0 | — | 1 (87) | 3165 | 3062 | 3165 / 3516 | 0.1-0.7 | 44 |
| off | 248 | 1 | 0 | 0 | 114 (134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, …) | 134 | 0 | — | 1 (87) | 3165 | 3062 | 3165 / 3516 | 0.1-0.6 | 43 |
| status_maxiter | 248 | 1 | 0 | 0 | 0 | 134 | 0 | `status`: 248, 0 | 1 (87) | 3165 | 3062 | 3165 / 3516 | 0.1-0.6 | 45 |
| status_runaway | 248 | 1 | 0 | 0 | 0 | 134 | 0 | `status`: 248, 0 | 1 (87) | 3165 | 3062 | 3165 / 3516 | 0.1-0.7 | 44 |
| on_nobound | 248 | 115 | 36 (88, 135, 137, 140, 142, 143, 146, 147, 148, 149, 150, 151, …) | 0 | 114 (134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, …) | 200 | 1 (87) | — | 1 (87) | 13083 | 4943 | 13096 / 14048 | 0.1-1.7 | 130 |
| off_nobound | 248 | 0 | 0 | 0 | 149 (88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, …) | 87 | 41 (87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, …) | `off`: 87, 41 (87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, …) | 41 (87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, …) | 3906 | 3906 | 3906 / 3274 | 0.1-0.5 | 47 |
| ref | 248 | 0 | 0 | 0 | 0 | 36 | 1 (87) | — | — | 12667 | 12667 | 12667 / 12936 | 0.2-2.8 | 84 |

### Series-level codes

| code | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound |
|---|---|---|---|---|---|---|---|
| `SEQUENTIAL_DISCONTINUITY` | 2: phases.0.scale 86→87; instrument.background.c0 49→50 | 2: phases.0.scale 86→87; instrument.background.c0 49→50 | 2: phases.0.scale 86→87; instrument.background.c0 49→50 | 2: phases.0.scale 86→87; instrument.background.c0 49→50 | 2: phases.0.scale 86→87; instrument.background.c0 49→50 | 3: phases.0.scale 86→87; instrument.zero_shift 86→87; instrument.background.c0 49→50 | 4: phases.0.cell.a 86→128; phases.0.scale 86→87; instrument.zero_shift 86→87; instrument.background.c0 49→50 |
| `SEQUENTIAL_RESEED` | 35 | 0 | 0 | 0 | 0 | 36 | 0 |
| `SEQUENTIAL_RWP_OUTLIER` | 114 | 0 | 114 | 0 | 0 | 114 | 149 |

Failures (`SeriesFailure`): on 0, status 0, off 0, status_maxiter 0, status_runaway 0, on_nobound 0, off_nobound 0.

## planted perovskite cooling ramp, 248 patterns (synthetic), its null twin (same ramp, no event)

Protocol: tests/planted_series.py refine(): cubic_model(T0), plan='mccusker_default', refit='single', forward, x=T (K), carry=('*',), compiled tier OFF (numpy_path).  Arms: on, status, off, status_maxiter, status_runaway, on_nobound, off_nobound; reference `ref`; truth: the simulation.

248 patterns.  The ladder, codes and accepted-value tables carry the 0 where any two arms differ (rungs tried or kept, status, fence verdict, entry codes, or a value by > 0.1 esd) or an arm differs from `ref` by > 0.1 esd, plus every event pattern ±2; the key-value tables carry only the 0 of those where a value differs, plus the events ±2.  Every other pattern has the same rungs, status, verdict and codes in every arm and values within 0.1 esd of each other and of `ref`; all of them are in the JSON.  Distance from truth selects no row (every pattern is some esd from it).

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev | status_maxiter: rungs [kept] | status_maxiter: Rwp warm→kept | status_maxiter: fence | status_maxiter: nfev | status_runaway: rungs [kept] | status_runaway: Rwp warm→kept | status_runaway: fence | status_runaway: nfev | on_nobound: rungs [kept] | on_nobound: Rwp warm→kept | on_nobound: fence | on_nobound: nfev | off_nobound: rungs [kept] | off_nobound: Rwp warm→kept | off_nobound: fence | off_nobound: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound |
|---|---|---|---|---|---|---|---|

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, the arm's pair, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | status_maxiter vs on: worst |Δ|/esd (path) | status_runaway vs on: worst |Δ|/esd (path) | on_nobound vs on: worst |Δ|/esd (path) | off_nobound vs on: worst |Δ|/esd (path) | status_maxiter vs status | status_runaway vs status | off_nobound vs off | on vs ref | status vs ref | off vs ref | status_maxiter vs ref | status_runaway vs ref | on_nobound vs ref | off_nobound vs ref | on vs truth | status vs truth | off vs truth | status_maxiter vs truth | status_runaway vs truth | on_nobound vs truth | off_nobound vs truth |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref` the reference; truth the simulation.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound | ref | truth |
|---|---|---|---|---|---|---|---|---|---|---|

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, the arm's pair, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`; "pair" is the arm differing from this one by one switch (`PAIRED`).  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | pair: bit-identical, differ | differ from ref | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 248 | 0 | 0 | 0 | 0 | 248 | — | — | 0 | 2143 | 2143 | 2143 / 2607 | 0.1-0.4 | 42 |
| status | 248 | 0 | 0 | 0 | 0 | 248 | 0 | — | 0 | 2143 | 2143 | 2143 / 2607 | 0.1-0.5 | 44 |
| off | 248 | 0 | 0 | 0 | 0 | 248 | 0 | — | 0 | 2143 | 2143 | 2143 / 2607 | 0.1-0.5 | 43 |
| status_maxiter | 248 | 0 | 0 | 0 | 0 | 248 | 0 | `status`: 248, 0 | 0 | 2143 | 2143 | 2143 / 2607 | 0.1-0.4 | 43 |
| status_runaway | 248 | 0 | 0 | 0 | 0 | 248 | 0 | `status`: 248, 0 | 0 | 2143 | 2143 | 2143 / 2607 | 0.1-0.4 | 43 |
| on_nobound | 248 | 0 | 0 | 0 | 0 | 248 | 0 | — | 0 | 2143 | 2143 | 2143 / 2607 | 0.1-0.4 | 41 |
| off_nobound | 248 | 0 | 0 | 0 | 0 | 248 | 0 | `off`: 248, 0 | 0 | 2143 | 2143 | 2143 / 2607 | 0.1-0.4 | 39 |
| ref | 248 | 0 | 0 | 0 | 0 | 1 | 0 | — | — | 9913 | 9913 | 9913 / 10485 | 0.2-0.4 | 68 |

### Series-level codes

No series-level code in any arm.

Failures (`SeriesFailure`): on 0, status 0, off 0, status_maxiter 0, status_runaway 0, on_nobound 0, off_nobound 0.

## simulated trigger series: ten ZrMo₂O₈-shaped 4 165-point patterns, four phases, 100 ppm/step cell ramp (synthetic)

Protocol: examples/bench_refinement.py _trigger_series(): refine_sequential(plan=qpa_plan(), refit='single', first_rung_factor=FIRST_RUNG_FACTOR), carry=('*',), dispersion declined, compiled tier default.  Arms: on, status, off, status_maxiter, status_runaway, on_nobound, off_nobound; reference `ref`; truth: the simulation.

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev | status_maxiter: rungs [kept] | status_maxiter: Rwp warm→kept | status_maxiter: fence | status_maxiter: nfev | status_runaway: rungs [kept] | status_runaway: Rwp warm→kept | status_runaway: fence | status_runaway: nfev | on_nobound: rungs [kept] | on_nobound: Rwp warm→kept | on_nobound: fence | on_nobound: nfev | off_nobound: rungs [kept] | off_nobound: Rwp warm→kept | off_nobound: fence | off_nobound: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | p000 | c [c] | 0.0274 | — | 79 | c [c] | 0.0274 | — | 79 | c [c] | 0.0274 | — | 79 | c [c] | 0.0274 | — | 79 | c [c] | 0.0274 | — | 79 | c [c] | 0.0274 | — | 79 | c [c] | 0.0274 | — | 79 |
| 1 | p001 | w [w] | 0.0270 | 0.0343 | 21 | w [w] | 0.0270 | inf | 21 | w [w] | 0.0270 | 0.0343 | 21 | w [w] | 0.0270 | inf | 21 | w [w] | 0.0270 | inf | 21 | w [w] | 0.0270 | 0.0343 | 21 | w [w] | 0.0270 | 0.0343 | 21 |
| 2 | p002 | w [w] | 0.0272 | 0.0340 | 23 | w [w] | 0.0272 | inf | 23 | w [w] | 0.0272 | 0.0340 | 23 | w [w] | 0.0272 | inf | 23 | w [w] | 0.0272 | inf | 23 | w [w] | 0.0272 | 0.0340 | 23 | w [w] | 0.0272 | 0.0340 | 23 |
| 3 | p003 | w [w] | 0.0272 | 0.0340 | 21 | w [w] | 0.0272 | inf | 21 | w [w] | 0.0272 | 0.0340 | 21 | w [w] | 0.0272 | inf | 21 | w [w] | 0.0272 | inf | 21 | w [w] | 0.0272 | 0.0340 | 21 | w [w] | 0.0272 | 0.0340 | 21 |
| 4 | p004 | w [w] | 0.0266 | 0.0340 | 21 | w [w] | 0.0266 | inf | 21 | w [w] | 0.0266 | 0.0340 | 21 | w [w] | 0.0266 | inf | 21 | w [w] | 0.0266 | inf | 21 | w [w] | 0.0266 | 0.0340 | 21 | w [w] | 0.0266 | 0.0340 | 21 |
| 5 | p005 | w [w] | 0.0272 | 0.0340 | 19 | w [w] | 0.0272 | inf | 19 | w [w] | 0.0272 | 0.0340 | 19 | w [w] | 0.0272 | inf | 19 | w [w] | 0.0272 | inf | 19 | w [w] | 0.0272 | 0.0340 | 19 | w [w] | 0.0272 | 0.0340 | 19 |
| 6 | p006 | w [w] | 0.0271 | 0.0340 | 22 | w [w] | 0.0271 | inf | 22 | w [w] | 0.0271 | 0.0340 | 22 | w [w] | 0.0271 | inf | 22 | w [w] | 0.0271 | inf | 22 | w [w] | 0.0271 | 0.0340 | 22 | w [w] | 0.0271 | 0.0340 | 22 |
| 7 | p007 | w [w] | 0.0270 | 0.0340 | 23 | w [w] | 0.0270 | inf | 23 | w [w] | 0.0270 | 0.0340 | 23 | w [w] | 0.0270 | inf | 23 | w [w] | 0.0270 | inf | 23 | w [w] | 0.0270 | 0.0340 | 23 | w [w] | 0.0270 | 0.0340 | 23 |
| 8 | p008 | w [w] | 0.0272 | 0.0339 | 22 | w [w] | 0.0272 | inf | 22 | w [w] | 0.0272 | 0.0339 | 22 | w [w] | 0.0272 | inf | 22 | w [w] | 0.0272 | inf | 22 | w [w] | 0.0272 | 0.0339 | 22 | w [w] | 0.0272 | 0.0339 | 22 |
| 9 | p009 | w [w] | 0.0270 | 0.0339 | 24 | w [w] | 0.0270 | inf | 24 | w [w] | 0.0270 | 0.0339 | 24 | w [w] | 0.0270 | inf | 24 | w [w] | 0.0270 | inf | 24 | w [w] | 0.0270 | 0.0339 | 24 | w [w] | 0.0270 | 0.0339 | 24 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound |
|---|---|---|---|---|---|---|---|
| 0 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 1 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 2 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 3 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 4 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 5 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 6 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 7 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 8 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 9 | BACKGROUND_ABSORPTION, BISO_UNUSUALLY_LARGE, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, BISO_UNUSUALLY_LARGE, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, BISO_UNUSUALLY_LARGE, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, BISO_UNUSUALLY_LARGE, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, BISO_UNUSUALLY_LARGE, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, BISO_UNUSUALLY_LARGE, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, BISO_UNUSUALLY_LARGE, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, the arm's pair, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | status_maxiter vs on: worst |Δ|/esd (path) | status_runaway vs on: worst |Δ|/esd (path) | on_nobound vs on: worst |Δ|/esd (path) | off_nobound vs on: worst |Δ|/esd (path) | status_maxiter vs status | status_runaway vs status | off_nobound vs off | on vs ref | status vs ref | off vs ref | status_maxiter vs ref | status_runaway vs ref | on_nobound vs ref | off_nobound vs ref | on vs truth | status vs truth | off vs truth | status_maxiter vs truth | status_runaway vs truth | on_nobound vs truth | off_nobound vs truth |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6.03 (phases.1.cell.a) | 6.03 (phases.1.cell.a) | 6.03 (phases.1.cell.a) | 6.03 (phases.1.cell.a) | 6.03 (phases.1.cell.a) | 6.03 (phases.1.cell.a) | 6.03 (phases.1.cell.a) |
| 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.508 (phases.1.lor_size) | 0.508 (phases.1.lor_size) | 0.508 (phases.1.lor_size) | 0.508 (phases.1.lor_size) | 0.508 (phases.1.lor_size) | 0.508 (phases.1.lor_size) | 0.508 (phases.1.lor_size) | 6.52 (phases.0.cell.a) | 6.52 (phases.0.cell.a) | 6.52 (phases.0.cell.a) | 6.52 (phases.0.cell.a) | 6.52 (phases.0.cell.a) | 6.52 (phases.0.cell.a) | 6.52 (phases.0.cell.a) |
| 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.638 (phases.1.lor_size) | 0.638 (phases.1.lor_size) | 0.638 (phases.1.lor_size) | 0.638 (phases.1.lor_size) | 0.638 (phases.1.lor_size) | 0.638 (phases.1.lor_size) | 0.638 (phases.1.lor_size) | 6.89 (phases.1.cell.a) | 6.89 (phases.1.cell.a) | 6.89 (phases.1.cell.a) | 6.89 (phases.1.cell.a) | 6.89 (phases.1.cell.a) | 6.89 (phases.1.cell.a) | 6.89 (phases.1.cell.a) |
| 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.455 (instrument.profile.v) | 0.455 (instrument.profile.v) | 0.455 (instrument.profile.v) | 0.455 (instrument.profile.v) | 0.455 (instrument.profile.v) | 0.455 (instrument.profile.v) | 0.455 (instrument.profile.v) | 6.2 (phases.1.cell.a) | 6.2 (phases.1.cell.a) | 6.2 (phases.1.cell.a) | 6.2 (phases.1.cell.a) | 6.2 (phases.1.cell.a) | 6.2 (phases.1.cell.a) | 6.2 (phases.1.cell.a) |
| 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.646 (phases.1.lor_size) | 0.646 (phases.1.lor_size) | 0.646 (phases.1.lor_size) | 0.646 (phases.1.lor_size) | 0.646 (phases.1.lor_size) | 0.646 (phases.1.lor_size) | 0.646 (phases.1.lor_size) | 6.27 (phases.1.cell.a) | 6.27 (phases.1.cell.a) | 6.27 (phases.1.cell.a) | 6.27 (phases.1.cell.a) | 6.27 (phases.1.cell.a) | 6.27 (phases.1.cell.a) | 6.27 (phases.1.cell.a) |
| 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.602 (phases.1.lor_strain) | 0.602 (phases.1.lor_strain) | 0.602 (phases.1.lor_strain) | 0.602 (phases.1.lor_strain) | 0.602 (phases.1.lor_strain) | 0.602 (phases.1.lor_strain) | 0.602 (phases.1.lor_strain) | 7.41 (phases.1.cell.a) | 7.41 (phases.1.cell.a) | 7.41 (phases.1.cell.a) | 7.41 (phases.1.cell.a) | 7.41 (phases.1.cell.a) | 7.41 (phases.1.cell.a) | 7.41 (phases.1.cell.a) |
| 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.341 (phases.1.lor_size) | 0.341 (phases.1.lor_size) | 0.341 (phases.1.lor_size) | 0.341 (phases.1.lor_size) | 0.341 (phases.1.lor_size) | 0.341 (phases.1.lor_size) | 0.341 (phases.1.lor_size) | 7.42 (phases.1.cell.a) | 7.42 (phases.1.cell.a) | 7.42 (phases.1.cell.a) | 7.42 (phases.1.cell.a) | 7.42 (phases.1.cell.a) | 7.42 (phases.1.cell.a) | 7.42 (phases.1.cell.a) |
| 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.615 (phases.1.lor_size) | 0.615 (phases.1.lor_size) | 0.615 (phases.1.lor_size) | 0.615 (phases.1.lor_size) | 0.615 (phases.1.lor_size) | 0.615 (phases.1.lor_size) | 0.615 (phases.1.lor_size) | 6.5 (phases.1.cell.a) | 6.5 (phases.1.cell.a) | 6.5 (phases.1.cell.a) | 6.5 (phases.1.cell.a) | 6.5 (phases.1.cell.a) | 6.5 (phases.1.cell.a) | 6.5 (phases.1.cell.a) |
| 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.252 (phases.1.lor_size) | 0.252 (phases.1.lor_size) | 0.252 (phases.1.lor_size) | 0.252 (phases.1.lor_size) | 0.252 (phases.1.lor_size) | 0.252 (phases.1.lor_size) | 0.252 (phases.1.lor_size) | 6.98 (phases.0.cell.a) | 6.98 (phases.0.cell.a) | 6.98 (phases.0.cell.a) | 6.98 (phases.0.cell.a) | 6.98 (phases.0.cell.a) | 6.98 (phases.0.cell.a) | 6.98 (phases.0.cell.a) |
| 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.485 (phases.1.lor_strain) | 0.485 (phases.1.lor_strain) | 0.485 (phases.1.lor_strain) | 0.485 (phases.1.lor_strain) | 0.485 (phases.1.lor_strain) | 0.485 (phases.1.lor_strain) | 0.485 (phases.1.lor_strain) | 5.95 (phases.1.cell.a) | 5.95 (phases.1.cell.a) | 5.95 (phases.1.cell.a) | 5.95 (phases.1.cell.a) | 5.95 (phases.1.cell.a) | 5.95 (phases.1.cell.a) | 5.95 (phases.1.cell.a) |

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref` the reference; truth the simulation.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound | ref | truth |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | `phases.0.cell.a` | 9.13252(35) | 9.13252(35) | 9.13252(35) | 9.13252(35) | 9.13252(35) | 9.13252(35) | 9.13252(35) | 9.13252(35) | 9.1304 |
| 0 | `phases.1.cell.a` | 10.14149(40) | 10.14149(40) | 10.14149(40) | 10.14149(40) | 10.14149(40) | 10.14149(40) | 10.14149(40) | 10.14149(40) | 10.1391 |
| 0 | `phases.1.cell.c` | 11.71168(47) | 11.71168(47) | 11.71168(47) | 11.71168(47) | 11.71168(47) | 11.71168(47) | 11.71168(47) | 11.71168(47) | 11.7091 |
| 0 | `phases.2.cell.b` | 5.2119(12) | 5.2119(12) | 5.2119(12) | 5.2119(12) | 5.2119(12) | 5.2119(12) | 5.2119(12) | 5.2119(12) | 5.2116 |
| 0 | `phases.3.cell.b` | 13.8572(19) | 13.8572(19) | 13.8572(19) | 13.8572(19) | 13.8572(19) | 13.8572(19) | 13.8572(19) | 13.8572(19) | 13.855 |
| 0 | `phases.0.scale` | 0.0003980(13) | 0.0003980(13) | 0.0003980(13) | 0.0003980(13) | 0.0003980(13) | 0.0003980(13) | 0.0003980(13) | 0.0003980(13) | 0.0004 |
| 0 | `instrument.zero_shift` | 0.075(14) | 0.075(14) | 0.075(14) | 0.075(14) | 0.075(14) | 0.075(14) | 0.075(14) | 0.075(14) | 0 |
| 1 | `phases.0.cell.a` | 9.13357(35) | 9.13357(35) | 9.13357(35) | 9.13357(35) | 9.13357(35) | 9.13357(35) | 9.13357(35) | 9.13357(35) | 9.13131 |
| 1 | `phases.1.cell.a` | 10.14263(39) | 10.14263(39) | 10.14263(39) | 10.14263(39) | 10.14263(39) | 10.14263(39) | 10.14263(39) | 10.14263(39) | 10.1401 |
| 1 | `phases.1.cell.c` | 11.71304(46) | 11.71304(46) | 11.71304(46) | 11.71304(46) | 11.71304(46) | 11.71304(46) | 11.71304(46) | 11.71304(46) | 11.7103 |
| 1 | `phases.2.cell.b` | 5.2133(11) | 5.2133(11) | 5.2133(11) | 5.2133(11) | 5.2133(11) | 5.2133(11) | 5.2133(11) | 5.2133(11) | 5.21212 |
| 1 | `phases.3.cell.b` | 13.8569(17) | 13.8569(17) | 13.8569(17) | 13.8569(17) | 13.8569(17) | 13.8569(17) | 13.8569(17) | 13.8569(17) | 13.8564 |
| 1 | `phases.0.scale` | 0.0003986(13) | 0.0003986(13) | 0.0003986(13) | 0.0003986(13) | 0.0003986(13) | 0.0003986(13) | 0.0003986(13) | 0.0003986(13) | 0.0004 |
| 1 | `instrument.zero_shift` | 0.081(14) | 0.081(14) | 0.081(14) | 0.081(14) | 0.081(14) | 0.081(14) | 0.081(14) | 0.081(14) | 0 |
| 2 | `phases.0.cell.a` | 9.13455(35) | 9.13455(35) | 9.13455(35) | 9.13455(35) | 9.13455(35) | 9.13455(35) | 9.13455(35) | 9.13455(35) | 9.13223 |
| 2 | `phases.1.cell.a` | 10.14382(39) | 10.14382(39) | 10.14382(39) | 10.14382(39) | 10.14382(39) | 10.14382(39) | 10.14382(39) | 10.14381(39) | 10.1411 |
| 2 | `phases.1.cell.c` | 11.71430(47) | 11.71430(47) | 11.71430(47) | 11.71430(47) | 11.71430(47) | 11.71430(47) | 11.71430(47) | 11.71429(47) | 11.7114 |
| 2 | `phases.2.cell.b` | 5.2128(12) | 5.2128(12) | 5.2128(12) | 5.2128(12) | 5.2128(12) | 5.2128(12) | 5.2128(12) | 5.2128(12) | 5.21264 |
| 2 | `phases.3.cell.b` | 13.8571(17) | 13.8571(17) | 13.8571(17) | 13.8571(17) | 13.8571(17) | 13.8571(17) | 13.8571(17) | 13.8571(17) | 13.8578 |
| 2 | `phases.0.scale` | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0004 |
| 2 | `instrument.zero_shift` | 0.085(14) | 0.085(14) | 0.085(14) | 0.085(14) | 0.085(14) | 0.085(14) | 0.085(14) | 0.085(14) | 0 |
| 3 | `phases.0.cell.a` | 9.13527(35) | 9.13527(35) | 9.13527(35) | 9.13527(35) | 9.13527(35) | 9.13527(35) | 9.13527(35) | 9.13526(36) | 9.13314 |
| 3 | `phases.1.cell.a` | 10.14457(39) | 10.14457(39) | 10.14457(39) | 10.14457(39) | 10.14457(39) | 10.14457(39) | 10.14457(39) | 10.14456(40) | 10.1421 |
| 3 | `phases.1.cell.c` | 11.71520(47) | 11.71520(47) | 11.71520(47) | 11.71520(47) | 11.71520(47) | 11.71520(47) | 11.71520(47) | 11.71518(47) | 11.7126 |
| 3 | `phases.2.cell.b` | 5.2139(12) | 5.2139(12) | 5.2139(12) | 5.2139(12) | 5.2139(12) | 5.2139(12) | 5.2139(12) | 5.2139(12) | 5.21316 |
| 3 | `phases.3.cell.b` | 13.8601(18) | 13.8601(18) | 13.8601(18) | 13.8601(18) | 13.8601(18) | 13.8601(18) | 13.8601(18) | 13.8601(18) | 13.8592 |
| 3 | `phases.0.scale` | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0004 |
| 3 | `instrument.zero_shift` | 0.074(14) | 0.074(14) | 0.074(14) | 0.074(14) | 0.074(14) | 0.074(14) | 0.074(14) | 0.074(14) | 0 |
| 4 | `phases.0.cell.a` | 9.13619(34) | 9.13619(34) | 9.13619(34) | 9.13619(34) | 9.13619(34) | 9.13619(34) | 9.13619(34) | 9.13617(35) | 9.13405 |
| 4 | `phases.1.cell.a` | 10.14556(38) | 10.14556(38) | 10.14556(38) | 10.14556(38) | 10.14556(38) | 10.14556(38) | 10.14556(38) | 10.14555(39) | 10.1432 |
| 4 | `phases.1.cell.c` | 11.71653(46) | 11.71653(46) | 11.71653(46) | 11.71653(46) | 11.71653(46) | 11.71653(46) | 11.71653(46) | 11.71651(47) | 11.7138 |
| 4 | `phases.2.cell.b` | 5.2141(11) | 5.2141(11) | 5.2141(11) | 5.2141(11) | 5.2141(11) | 5.2141(11) | 5.2141(11) | 5.2141(11) | 5.21368 |
| 4 | `phases.3.cell.b` | 13.8612(17) | 13.8612(17) | 13.8612(17) | 13.8612(17) | 13.8612(17) | 13.8612(17) | 13.8612(17) | 13.8611(17) | 13.8605 |
| 4 | `phases.0.scale` | 0.0003978(13) | 0.0003978(13) | 0.0003978(13) | 0.0003978(13) | 0.0003978(13) | 0.0003978(13) | 0.0003978(13) | 0.0003977(13) | 0.0004 |
| 4 | `instrument.zero_shift` | 0.078(14) | 0.078(14) | 0.078(14) | 0.078(14) | 0.078(14) | 0.078(14) | 0.078(14) | 0.077(14) | 0 |
| 5 | `phases.0.cell.a` | 9.13743(34) | 9.13743(34) | 9.13743(34) | 9.13743(34) | 9.13743(34) | 9.13743(34) | 9.13743(34) | 9.13743(35) | 9.13497 |
| 5 | `phases.1.cell.a` | 10.14702(39) | 10.14702(39) | 10.14702(39) | 10.14702(39) | 10.14702(39) | 10.14702(39) | 10.14702(39) | 10.14702(39) | 10.1442 |
| 5 | `phases.1.cell.c` | 11.71797(46) | 11.71797(46) | 11.71797(46) | 11.71797(46) | 11.71797(46) | 11.71797(46) | 11.71797(46) | 11.71796(47) | 11.715 |
| 5 | `phases.2.cell.b` | 5.2161(11) | 5.2161(11) | 5.2161(11) | 5.2161(11) | 5.2161(11) | 5.2161(11) | 5.2161(11) | 5.2161(11) | 5.21421 |
| 5 | `phases.3.cell.b` | 13.8646(18) | 13.8646(18) | 13.8646(18) | 13.8646(18) | 13.8646(18) | 13.8646(18) | 13.8646(18) | 13.8646(18) | 13.8619 |
| 5 | `phases.0.scale` | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003976(13) | 0.0004 |
| 5 | `instrument.zero_shift` | 0.090(14) | 0.090(14) | 0.090(14) | 0.090(14) | 0.090(14) | 0.090(14) | 0.090(14) | 0.089(14) | 0 |
| 6 | `phases.0.cell.a` | 9.13835(34) | 9.13835(34) | 9.13835(34) | 9.13835(34) | 9.13835(34) | 9.13835(34) | 9.13835(34) | 9.13835(34) | 9.13588 |
| 6 | `phases.1.cell.a` | 10.14803(38) | 10.14803(38) | 10.14803(38) | 10.14803(38) | 10.14803(38) | 10.14803(38) | 10.14803(38) | 10.14803(38) | 10.1452 |
| 6 | `phases.1.cell.c` | 11.71916(46) | 11.71916(46) | 11.71916(46) | 11.71916(46) | 11.71916(46) | 11.71916(46) | 11.71916(46) | 11.71915(46) | 11.7161 |
| 6 | `phases.2.cell.b` | 5.2159(12) | 5.2159(12) | 5.2159(12) | 5.2159(12) | 5.2159(12) | 5.2159(12) | 5.2159(12) | 5.2159(12) | 5.21473 |
| 6 | `phases.3.cell.b` | 13.8647(17) | 13.8647(17) | 13.8647(17) | 13.8647(17) | 13.8647(17) | 13.8647(17) | 13.8647(17) | 13.8646(17) | 13.8633 |
| 6 | `phases.0.scale` | 0.0003979(13) | 0.0003979(13) | 0.0003979(13) | 0.0003979(13) | 0.0003979(13) | 0.0003979(13) | 0.0003979(13) | 0.0003979(13) | 0.0004 |
| 6 | `instrument.zero_shift` | 0.090(14) | 0.090(14) | 0.090(14) | 0.090(14) | 0.090(14) | 0.090(14) | 0.090(14) | 0.090(14) | 0 |
| 7 | `phases.0.cell.a` | 9.13899(34) | 9.13899(34) | 9.13899(34) | 9.13899(34) | 9.13899(34) | 9.13899(34) | 9.13899(34) | 9.13899(34) | 9.13679 |
| 7 | `phases.1.cell.a` | 10.14868(38) | 10.14868(38) | 10.14868(38) | 10.14868(38) | 10.14868(38) | 10.14868(38) | 10.14868(38) | 10.14869(38) | 10.1462 |
| 7 | `phases.1.cell.c` | 11.72007(46) | 11.72007(46) | 11.72007(46) | 11.72007(46) | 11.72007(46) | 11.72007(46) | 11.72007(46) | 11.72008(45) | 11.7173 |
| 7 | `phases.2.cell.b` | 5.2164(12) | 5.2164(12) | 5.2164(12) | 5.2164(12) | 5.2164(12) | 5.2164(12) | 5.2164(12) | 5.2164(12) | 5.21525 |
| 7 | `phases.3.cell.b` | 13.8666(17) | 13.8666(17) | 13.8666(17) | 13.8666(17) | 13.8666(17) | 13.8666(17) | 13.8666(17) | 13.8666(17) | 13.8647 |
| 7 | `phases.0.scale` | 0.0003974(13) | 0.0003974(13) | 0.0003974(13) | 0.0003974(13) | 0.0003974(13) | 0.0003974(13) | 0.0003974(13) | 0.0003974(13) | 0.0004 |
| 7 | `instrument.zero_shift` | 0.079(14) | 0.079(14) | 0.079(14) | 0.079(14) | 0.079(14) | 0.079(14) | 0.079(14) | 0.080(14) | 0 |
| 8 | `phases.0.cell.a` | 9.14014(35) | 9.14014(35) | 9.14014(35) | 9.14014(35) | 9.14014(35) | 9.14014(35) | 9.14014(35) | 9.14014(35) | 9.1377 |
| 8 | `phases.1.cell.a` | 10.14992(39) | 10.14992(39) | 10.14992(39) | 10.14992(39) | 10.14992(39) | 10.14992(39) | 10.14992(39) | 10.14992(39) | 10.1472 |
| 8 | `phases.1.cell.c` | 11.72156(47) | 11.72156(47) | 11.72156(47) | 11.72156(47) | 11.72156(47) | 11.72156(47) | 11.72156(47) | 11.72156(46) | 11.7185 |
| 8 | `phases.2.cell.b` | 5.2174(11) | 5.2174(11) | 5.2174(11) | 5.2174(11) | 5.2174(11) | 5.2174(11) | 5.2174(11) | 5.2174(11) | 5.21577 |
| 8 | `phases.3.cell.b` | 13.8680(18) | 13.8680(18) | 13.8680(18) | 13.8680(18) | 13.8680(18) | 13.8680(18) | 13.8680(18) | 13.8681(18) | 13.8661 |
| 8 | `phases.0.scale` | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0004 |
| 8 | `instrument.zero_shift` | 0.087(14) | 0.087(14) | 0.087(14) | 0.087(14) | 0.087(14) | 0.087(14) | 0.087(14) | 0.087(14) | 0 |
| 9 | `phases.0.cell.a` | 9.14066(35) | 9.14066(35) | 9.14066(35) | 9.14066(35) | 9.14066(35) | 9.14066(35) | 9.14066(35) | 9.14066(34) | 9.13862 |
| 9 | `phases.1.cell.a` | 10.15053(39) | 10.15053(39) | 10.15053(39) | 10.15053(39) | 10.15053(39) | 10.15053(39) | 10.15053(39) | 10.15054(38) | 10.1482 |
| 9 | `phases.1.cell.c` | 11.72223(46) | 11.72223(46) | 11.72223(46) | 11.72223(46) | 11.72223(46) | 11.72223(46) | 11.72223(46) | 11.72224(46) | 11.7196 |
| 9 | `phases.2.cell.b` | 5.2168(12) | 5.2168(12) | 5.2168(12) | 5.2168(12) | 5.2168(12) | 5.2168(12) | 5.2168(12) | 5.2168(12) | 5.21629 |
| 9 | `phases.3.cell.b` | 13.8677(17) | 13.8677(17) | 13.8677(17) | 13.8677(17) | 13.8677(17) | 13.8677(17) | 13.8677(17) | 13.8678(17) | 13.8675 |
| 9 | `phases.0.scale` | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0004 |
| 9 | `instrument.zero_shift` | 0.073(14) | 0.073(14) | 0.073(14) | 0.073(14) | 0.073(14) | 0.073(14) | 0.073(14) | 0.073(14) | 0 |

### Weight fractions, per pattern (wt %)

W(σ(W)) per arm.

| k | phase | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound | ref |
|---|---|---|---|---|---|---|---|---|---|
| 0 | sim-ZrMo2O8-cubic | 42.07(0.10) | 42.07(0.10) | 42.07(0.10) | 42.07(0.10) | 42.07(0.10) | 42.07(0.10) | 42.07(0.10) | 42.07(0.10) |
| 0 | sim-ZrMo2O8-trigonal | 54.91(0.12) | 54.91(0.12) | 54.91(0.12) | 54.91(0.12) | 54.91(0.12) | 54.91(0.12) | 54.91(0.12) | 54.91(0.12) |
| 0 | sim-ZrO2-baddeleyite | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) |
| 0 | sim-MoO3 | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) |
| 1 | sim-ZrMo2O8-cubic | 42.06(0.09) | 42.06(0.09) | 42.06(0.09) | 42.06(0.09) | 42.06(0.09) | 42.06(0.09) | 42.06(0.09) | 42.06(0.10) |
| 1 | sim-ZrMo2O8-trigonal | 54.94(0.11) | 54.94(0.11) | 54.94(0.11) | 54.94(0.11) | 54.94(0.11) | 54.94(0.11) | 54.94(0.11) | 54.94(0.11) |
| 1 | sim-ZrO2-baddeleyite | 1.11(0.09) | 1.11(0.09) | 1.11(0.09) | 1.11(0.09) | 1.11(0.09) | 1.11(0.09) | 1.11(0.09) | 1.11(0.09) |
| 1 | sim-MoO3 | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) |
| 2 | sim-ZrMo2O8-cubic | 42.06(0.10) | 42.06(0.10) | 42.06(0.10) | 42.06(0.10) | 42.06(0.10) | 42.06(0.10) | 42.06(0.10) | 42.06(0.10) |
| 2 | sim-ZrMo2O8-trigonal | 54.87(0.12) | 54.87(0.12) | 54.87(0.12) | 54.87(0.12) | 54.87(0.12) | 54.87(0.12) | 54.87(0.12) | 54.87(0.12) |
| 2 | sim-ZrO2-baddeleyite | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.16(0.09) |
| 2 | sim-MoO3 | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.08) |
| 3 | sim-ZrMo2O8-cubic | 42.03(0.10) | 42.03(0.10) | 42.03(0.10) | 42.03(0.10) | 42.03(0.10) | 42.03(0.10) | 42.03(0.10) | 42.03(0.10) |
| 3 | sim-ZrMo2O8-trigonal | 54.88(0.12) | 54.88(0.12) | 54.88(0.12) | 54.88(0.12) | 54.88(0.12) | 54.88(0.12) | 54.88(0.12) | 54.88(0.12) |
| 3 | sim-ZrO2-baddeleyite | 1.16(0.09) | 1.16(0.09) | 1.16(0.09) | 1.16(0.09) | 1.16(0.09) | 1.16(0.09) | 1.16(0.09) | 1.16(0.09) |
| 3 | sim-MoO3 | 1.94(0.07) | 1.94(0.07) | 1.94(0.07) | 1.94(0.07) | 1.94(0.07) | 1.94(0.07) | 1.94(0.07) | 1.93(0.07) |
| 4 | sim-ZrMo2O8-cubic | 42.01(0.09) | 42.01(0.09) | 42.01(0.09) | 42.01(0.09) | 42.01(0.09) | 42.01(0.09) | 42.01(0.09) | 42.01(0.10) |
| 4 | sim-ZrMo2O8-trigonal | 54.94(0.11) | 54.94(0.11) | 54.94(0.11) | 54.94(0.11) | 54.94(0.11) | 54.94(0.11) | 54.94(0.11) | 54.94(0.12) |
| 4 | sim-ZrO2-baddeleyite | 1.13(0.09) | 1.13(0.09) | 1.13(0.09) | 1.13(0.09) | 1.13(0.09) | 1.13(0.09) | 1.13(0.09) | 1.13(0.09) |
| 4 | sim-MoO3 | 1.92(0.07) | 1.92(0.07) | 1.92(0.07) | 1.92(0.07) | 1.92(0.07) | 1.92(0.07) | 1.92(0.07) | 1.91(0.07) |
| 5 | sim-ZrMo2O8-cubic | 42.02(0.10) | 42.02(0.10) | 42.02(0.10) | 42.02(0.10) | 42.02(0.10) | 42.02(0.10) | 42.02(0.10) | 42.02(0.10) |
| 5 | sim-ZrMo2O8-trigonal | 54.90(0.12) | 54.90(0.12) | 54.90(0.12) | 54.90(0.12) | 54.90(0.12) | 54.90(0.12) | 54.90(0.12) | 54.90(0.12) |
| 5 | sim-ZrO2-baddeleyite | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) |
| 5 | sim-MoO3 | 1.94(0.07) | 1.94(0.07) | 1.94(0.07) | 1.94(0.07) | 1.94(0.07) | 1.94(0.07) | 1.94(0.07) | 1.94(0.07) |
| 6 | sim-ZrMo2O8-cubic | 42.02(0.09) | 42.02(0.09) | 42.02(0.09) | 42.02(0.09) | 42.02(0.09) | 42.02(0.09) | 42.02(0.09) | 42.02(0.10) |
| 6 | sim-ZrMo2O8-trigonal | 54.93(0.11) | 54.93(0.11) | 54.93(0.11) | 54.93(0.11) | 54.93(0.11) | 54.93(0.11) | 54.93(0.11) | 54.93(0.11) |
| 6 | sim-ZrO2-baddeleyite | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) |
| 6 | sim-MoO3 | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) |
| 7 | sim-ZrMo2O8-cubic | 41.98(0.09) | 41.98(0.09) | 41.98(0.09) | 41.98(0.09) | 41.98(0.09) | 41.98(0.09) | 41.98(0.09) | 41.98(0.09) |
| 7 | sim-ZrMo2O8-trigonal | 54.96(0.11) | 54.96(0.11) | 54.96(0.11) | 54.96(0.11) | 54.96(0.11) | 54.96(0.11) | 54.96(0.11) | 54.96(0.11) |
| 7 | sim-ZrO2-baddeleyite | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) |
| 7 | sim-MoO3 | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) |
| 8 | sim-ZrMo2O8-cubic | 42.01(0.10) | 42.01(0.10) | 42.01(0.10) | 42.01(0.10) | 42.01(0.10) | 42.01(0.10) | 42.01(0.10) | 42.01(0.10) |
| 8 | sim-ZrMo2O8-trigonal | 54.94(0.12) | 54.94(0.12) | 54.94(0.12) | 54.94(0.12) | 54.94(0.12) | 54.94(0.12) | 54.94(0.12) | 54.93(0.12) |
| 8 | sim-ZrO2-baddeleyite | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) |
| 8 | sim-MoO3 | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) |
| 9 | sim-ZrMo2O8-cubic | 41.94(0.10) | 41.94(0.10) | 41.94(0.10) | 41.94(0.10) | 41.94(0.10) | 41.94(0.10) | 41.94(0.10) | 41.95(0.10) |
| 9 | sim-ZrMo2O8-trigonal | 55.00(0.12) | 55.00(0.12) | 55.00(0.12) | 55.00(0.12) | 55.00(0.12) | 55.00(0.12) | 55.00(0.12) | 55.00(0.12) |
| 9 | sim-ZrO2-baddeleyite | 1.17(0.09) | 1.17(0.09) | 1.17(0.09) | 1.17(0.09) | 1.17(0.09) | 1.17(0.09) | 1.17(0.09) | 1.17(0.09) |
| 9 | sim-MoO3 | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, the arm's pair, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`; "pair" is the arm differing from this one by one switch (`PAIRED`).  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | pair: bit-identical, differ | differ from ref | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 10 | 0 | 0 | 0 | 0 | 10 | — | — | 9 (1, 2, 3, 4, 5, 6, 7, 8, 9) | 275 | 275 | 275 / 286 | 8.8-13.9 | 103 |
| status | 10 | 0 | 0 | 0 | 0 | 10 | 0 | — | 9 (1, 2, 3, 4, 5, 6, 7, 8, 9) | 275 | 275 | 275 / 286 | 9.1-14.4 | 103 |
| off | 10 | 0 | 0 | 0 | 0 | 10 | 0 | — | 9 (1, 2, 3, 4, 5, 6, 7, 8, 9) | 275 | 275 | 275 / 286 | 9.1-13.7 | 102 |
| status_maxiter | 10 | 0 | 0 | 0 | 0 | 10 | 0 | `status`: 10, 0 | 9 (1, 2, 3, 4, 5, 6, 7, 8, 9) | 275 | 275 | 275 / 286 | 8.6-13.4 | 96 |
| status_runaway | 10 | 0 | 0 | 0 | 0 | 10 | 0 | `status`: 10, 0 | 9 (1, 2, 3, 4, 5, 6, 7, 8, 9) | 275 | 275 | 275 / 286 | 8.7-12.6 | 97 |
| on_nobound | 10 | 0 | 0 | 0 | 0 | 10 | 0 | — | 9 (1, 2, 3, 4, 5, 6, 7, 8, 9) | 275 | 275 | 275 / 286 | 8.8-13.8 | 102 |
| off_nobound | 10 | 0 | 0 | 0 | 0 | 10 | 0 | `off`: 10, 0 | 9 (1, 2, 3, 4, 5, 6, 7, 8, 9) | 275 | 275 | 275 / 286 | 8.5-14.4 | 100 |
| ref | 10 | 0 | 0 | 0 | 0 | 1 | 9 (1, 2, 3, 4, 5, 6, 7, 8, 9) | — | — | 792 | 792 | 792 / 804 | 18.8-21.7 | 204 |

### Series-level codes

| code | on | status | off | status_maxiter | status_runaway | on_nobound | off_nobound |
|---|---|---|---|---|---|---|---|
| `SEQUENTIAL_PERSISTENT_FINDING` | 34 | 34 | 34 | 34 | 34 | 34 | 34 |

Failures (`SeriesFailure`): on 0, status 0, off 0, status_maxiter 0, status_runaway 0, on_nobound 0, off_nobound 0.

## Cr₂WO₆ HB-2A pair, 4 K then 150 K (real, constant-wavelength neutron, λ 2.4067 Å)

Protocol: tests/test_magnetic_series.py::test_the_cr2wo6_pair_as_a_series_gives_the_single_pattern_verdicts: start = the 4 K nuclear fit of conftest.cr2wo6_nuclear with a 2 μB Cr moment (58.395), refine_sequential(plan=_plan(MAGNETIC_STAGES), x=[4, 150]), carry=('*',), refit='single', compiled tier OFF for the series (the nuclear setup fits run on the default path, as the fixture's do).  Arms: on, status, off, status_maxiter, status_runaway; reference `ref`.

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev | status_maxiter: rungs [kept] | status_maxiter: Rwp warm→kept | status_maxiter: fence | status_maxiter: nfev | status_runaway: rungs [kept] | status_runaway: Rwp warm→kept | status_runaway: fence | status_runaway: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 4K | c [c] | 0.1047 | — | 55 | c [c] | 0.1047 | — | 55 | c [c] | 0.1047 | — | 55 | c [c] | 0.1047 | — | 55 | c [c] | 0.1047 | — | 55 |
| 1 | 150K | w [w] | 0.0991 | 0.1309 | 427 | w [w] | 0.0991 | inf | 427 | w [w] | 0.0991 | 0.1309 | 427 | w [w] | 0.0991 | inf | 427 | w [w] | 0.0991 | inf | 427 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off | status_maxiter | status_runaway |
|---|---|---|---|---|---|
| 0 | CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, MOMENT_ANGLE_STATIONARY | CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, MOMENT_ANGLE_STATIONARY | CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, MOMENT_ANGLE_STATIONARY | CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, MOMENT_ANGLE_STATIONARY | CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, MOMENT_ANGLE_STATIONARY |
| 1 | BISO_NEGATIVE, CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, HIGH_CORRELATION | BISO_NEGATIVE, CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, HIGH_CORRELATION | BISO_NEGATIVE, CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, HIGH_CORRELATION | BISO_NEGATIVE, CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, HIGH_CORRELATION | BISO_NEGATIVE, CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, HIGH_CORRELATION |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, the arm's pair, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | status_maxiter vs on: worst |Δ|/esd (path) | status_runaway vs on: worst |Δ|/esd (path) | status_maxiter vs status | status_runaway vs status | on vs ref | status vs ref | off vs ref | status_maxiter vs ref | status_runaway vs ref |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00533 (instrument.profile.v) | 0.00533 (instrument.profile.v) | 0.00533 (instrument.profile.v) | 0.00533 (instrument.profile.v) | 0.00533 (instrument.profile.v) |

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref` the reference.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | status_maxiter | status_runaway | ref |
|---|---|---|---|---|---|---|---|
| 0 | `phases.0.atoms.1.moment.dof0` | 2.125(45) | 2.125(45) | 2.125(45) | 2.125(45) | 2.125(45) | 2.125(45) |
| 0 | `phases.0.cell.a` | 4.57750(18) | 4.57750(18) | 4.57750(18) | 4.57750(18) | 4.57750(18) | 4.57750(18) |
| 0 | `phases.0.cell.c` | 8.84169(44) | 8.84169(44) | 8.84169(44) | 8.84169(44) | 8.84169(44) | 8.84169(44) |
| 0 | `phases.0.scale` | 0.00848(21) | 0.00848(21) | 0.00848(21) | 0.00848(21) | 0.00848(21) | 0.00848(21) |
| 0 | `instrument.zero_shift` | 0.2011(38) | 0.2011(38) | 0.2011(38) | 0.2011(38) | 0.2011(38) | 0.2011(38) |
| 1 | `phases.0.atoms.1.moment.dof0` | 0(287) | 0(287) | 0(287) | 0(287) | 0(287) | 0(2151000000) |
| 1 | `phases.0.cell.a` | 4.57531(16) | 4.57531(16) | 4.57531(16) | 4.57531(16) | 4.57531(16) | 4.57531(16) |
| 1 | `phases.0.cell.c` | 8.85369(37) | 8.85369(37) | 8.85369(37) | 8.85369(37) | 8.85369(37) | 8.85369(37) |
| 1 | `phases.0.scale` | 0.00839(18) | 0.00839(18) | 0.00839(18) | 0.00839(18) | 0.00839(18) | 0.00839(18) |
| 1 | `instrument.zero_shift` | 0.2093(34) | 0.2093(34) | 0.2093(34) | 0.2093(34) | 0.2093(34) | 0.2093(34) |

### Moment evidence, per pattern (`SeriesEntry.magnetic`)

|μ| (esd) μB and `supported`, per site.

| k | site | on | status | off | status_maxiter | status_runaway | ref |
|---|---|---|---|---|---|---|---|
| 0 | Cr1 | 2.125(0.045) True | 2.125(0.045) True | 2.125(0.045) True | 2.125(0.045) True | 2.125(0.045) True | 2.125(0.045) True |
| 1 | Cr1 | 0.000(286.647) False | 0.000(286.647) False | 0.000(286.647) False | 0.000(286.647) False | 0.000(286.647) False | 0.000(2151316039.659) False |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, the arm's pair, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`; "pair" is the arm differing from this one by one switch (`PAIRED`).  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | pair: bit-identical, differ | differ from ref | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 2 | 0 | 0 | 0 | 0 | 2 | — | — | 0 | 482 | 482 | 704 / 627 | 7.6-9.3 | 17 |
| status | 2 | 0 | 0 | 0 | 0 | 2 | 0 | — | 0 | 482 | 482 | 704 / 627 | 7.5-9.3 | 17 |
| off | 2 | 0 | 0 | 0 | 0 | 2 | 0 | — | 0 | 482 | 482 | 704 / 627 | 7.2-9.0 | 16 |
| status_maxiter | 2 | 0 | 0 | 0 | 0 | 2 | 0 | `status`: 2, 0 | 0 | 482 | 482 | 704 / 627 | 7.3-8.8 | 16 |
| status_runaway | 2 | 0 | 0 | 0 | 0 | 2 | 0 | `status`: 2, 0 | 0 | 482 | 482 | 704 / 627 | 8.3-9.2 | 18 |
| ref | 2 | 0 | 0 | 0 | 0 | 1 | 0 | — | — | 170 | 170 | 392 / 376 | 1.6-9.0 | 11 |

### Series-level codes

| code | on | status | off | status_maxiter | status_runaway |
|---|---|---|---|---|---|
| `SEQUENTIAL_MOMENT_HOLD` | 1 | 1 | 1 | 1 | 1 |
| `SEQUENTIAL_MOMENT_ONSET` | 1 | 1 | 1 | 1 | 1 |

Failures (`SeriesFailure`): on 0, status 0, off 0, status_maxiter 0, status_runaway 0.

## tutorial 05's LaB6 ramp, 7 patterns 300-900 K (synthetic), the 700 K cell × 1.02

Protocol: examples/tutorials/05_sequential_fits.py series_jump / series_broken: refine_sequential(plan='mccusker_default', x=T, labels=scans), carry=('*',), refit='single', compiled tier default.  Arms: on, status, off, status_maxiter, status_runaway; reference `ref`; truth: the simulation.

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev | status_maxiter: rungs [kept] | status_maxiter: Rwp warm→kept | status_maxiter: fence | status_maxiter: nfev | status_runaway: rungs [kept] | status_runaway: Rwp warm→kept | status_runaway: fence | status_runaway: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | scan8 | c [c] | 0.0409 | — | 38 | c [c] | 0.0409 | — | 38 | c [c] | 0.0409 | — | 38 | c [c] | 0.0409 | — | 38 | c [c] | 0.0409 | — | 38 |
| 1 | scan9 | w [w] | 0.0409 | 0.0511 | 15 | w [w] | 0.0409 | inf | 15 | w [w] | 0.0409 | 0.0511 | 15 | w [w] | 0.0409 | inf | 15 | w [w] | 0.0409 | inf | 15 |
| 2 | scan10 | w [w] | 0.0399 | 0.0511 | 15 | w [w] | 0.0399 | inf | 15 | w [w] | 0.0399 | 0.0511 | 15 | w [w] | 0.0399 | inf | 15 | w [w] | 0.0399 | inf | 15 |
| 3 | scan11 | w [w] | 0.0405 | 0.0511 | 15 | w [w] | 0.0405 | inf | 15 | w [w] | 0.0405 | 0.0511 | 15 | w [w] | 0.0405 | inf | 15 | w [w] | 0.0405 | inf | 15 |
| 4 | scan12 | w [w] | 0.0390 | 0.0508 | 71 | w [w] | 0.0390 | inf | 71 | w [w] | 0.0390 | 0.0508 | 71 | w [w] | 0.0390 | inf | 71 | w [w] | 0.0390 | inf | 71 |
| 5 | scan13 | w [w] | 0.0402 | 0.0506 | 465 | w [w] | 0.0402 | inf | 465 | w [w] | 0.0402 | 0.0506 | 465 | w [w] | 0.0402 | inf | 465 | w [w] | 0.0402 | inf | 465 |
| 6 | scan14 | w [w] | 0.0404 | 0.0504 | 15 | w [w] | 0.0404 | inf | 15 | w [w] | 0.0404 | 0.0504 | 15 | w [w] | 0.0404 | inf | 15 | w [w] | 0.0404 | inf | 15 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off | status_maxiter | status_runaway |
|---|---|---|---|---|---|
| 0 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 1 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 2 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 3 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 4 | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED |
| 5 | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED, STAGE_MAX_ITER | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED, STAGE_MAX_ITER | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED, STAGE_MAX_ITER | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED, STAGE_MAX_ITER | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED, STAGE_MAX_ITER |
| 6 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, the arm's pair, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | status_maxiter vs on: worst |Δ|/esd (path) | status_runaway vs on: worst |Δ|/esd (path) | status_maxiter vs status | status_runaway vs status | on vs ref | status vs ref | off vs ref | status_maxiter vs ref | status_runaway vs ref | on vs truth | status vs truth | off vs truth | status_maxiter vs truth | status_runaway vs truth |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8.94 (instrument.background.c0) | 8.94 (instrument.background.c0) | 8.94 (instrument.background.c0) | 8.94 (instrument.background.c0) | 8.94 (instrument.background.c0) |
| 1 | 0 | 0 | 0 | 0 | 0 | 0 | 8.01e-07 (instrument.profile.u) | 8.01e-07 (instrument.profile.u) | 8.01e-07 (instrument.profile.u) | 8.01e-07 (instrument.profile.u) | 8.01e-07 (instrument.profile.u) | 6.68 (instrument.background.c0) | 6.68 (instrument.background.c0) | 6.68 (instrument.background.c0) | 6.68 (instrument.background.c0) | 6.68 (instrument.background.c0) |
| 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2.97e-07 (instrument.profile.v) | 2.97e-07 (instrument.profile.v) | 2.97e-07 (instrument.profile.v) | 2.97e-07 (instrument.profile.v) | 2.97e-07 (instrument.profile.v) | 6.66 (instrument.background.c0) | 6.66 (instrument.background.c0) | 6.66 (instrument.background.c0) | 6.66 (instrument.background.c0) | 6.66 (instrument.background.c0) |
| 3 | 0 | 0 | 0 | 0 | 0 | 0 | 6.51e-08 (instrument.profile.w) | 6.51e-08 (instrument.profile.w) | 6.51e-08 (instrument.profile.w) | 6.51e-08 (instrument.profile.w) | 6.51e-08 (instrument.profile.w) | 7.42 (instrument.background.c0) | 7.42 (instrument.background.c0) | 7.42 (instrument.background.c0) | 7.42 (instrument.background.c0) | 7.42 (instrument.background.c0) |
| 4 | 0 | 0 | 0 | 0 | 0 | 0 | 2.1 (instrument.background.c0) | 2.1 (instrument.background.c0) | 2.1 (instrument.background.c0) | 2.1 (instrument.background.c0) | 2.1 (instrument.background.c0) | 8.86 (instrument.background.c0) | 8.86 (instrument.background.c0) | 8.86 (instrument.background.c0) | 8.86 (instrument.background.c0) | 8.86 (instrument.background.c0) |
| 5 | 0 | 0 | 0 | 0 | 0 | 0 | 2.03 (instrument.background.c0) | 2.03 (instrument.background.c0) | 2.03 (instrument.background.c0) | 2.03 (instrument.background.c0) | 2.03 (instrument.background.c0) | 10.3 (instrument.background.c0) | 10.3 (instrument.background.c0) | 10.3 (instrument.background.c0) | 10.3 (instrument.background.c0) | 10.3 (instrument.background.c0) |
| 6 | 0 | 0 | 0 | 0 | 0 | 0 | 1.08e-07 (instrument.profile.u) | 1.08e-07 (instrument.profile.u) | 1.08e-07 (instrument.profile.u) | 1.08e-07 (instrument.profile.u) | 1.08e-07 (instrument.profile.u) | 8.28 (instrument.background.c0) | 8.28 (instrument.background.c0) | 8.28 (instrument.background.c0) | 8.28 (instrument.background.c0) | 8.28 (instrument.background.c0) |

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref` the reference; truth the simulation.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | status_maxiter | status_runaway | ref | truth |
|---|---|---|---|---|---|---|---|---|
| 0 | `phases.0.cell.a` | 4.1565938(43) | 4.1565938(43) | 4.1565938(43) | 4.1565938(43) | 4.1565938(43) | 4.1565938(43) | 4.1566 |
| 0 | `phases.0.scale` | 0.00049984(37) | 0.00049984(37) | 0.00049984(37) | 0.00049984(37) | 0.00049984(37) | 0.00049984(37) | 0.0005 |
| 0 | `instrument.zero_shift` | 0.007987(14) | 0.007987(14) | 0.007987(14) | 0.007987(14) | 0.007987(14) | 0.007987(14) | 0.008 |
| 0 | `instrument.profile.w` | 0.0002507(22) | 0.0002507(22) | 0.0002507(22) | 0.0002507(22) | 0.0002507(22) | 0.0002507(22) | 0.00025 |
| 0 | `instrument.background.c0` | 38.76(14) | 38.76(14) | 38.76(14) | 38.76(14) | 38.76(14) | 38.76(14) | 40 |
| 1 | `phases.0.cell.a` | 4.1586732(43) | 4.1586732(43) | 4.1586732(43) | 4.1586732(43) | 4.1586732(43) | 4.1586732(43) | 4.15868 |
| 1 | `phases.0.scale` | 0.00049969(38) | 0.00049969(38) | 0.00049969(38) | 0.00049969(38) | 0.00049969(38) | 0.00049969(38) | 0.0005 |
| 1 | `instrument.zero_shift` | 0.007986(14) | 0.007986(14) | 0.007986(14) | 0.007986(14) | 0.007986(14) | 0.007986(14) | 0.008 |
| 1 | `instrument.profile.w` | 0.0002511(22) | 0.0002511(22) | 0.0002511(22) | 0.0002511(22) | 0.0002511(22) | 0.0002511(22) | 0.00025 |
| 1 | `instrument.background.c0` | 39.06(14) | 39.06(14) | 39.06(14) | 39.06(14) | 39.06(14) | 39.06(14) | 40 |
| 2 | `phases.0.cell.a` | 4.1607616(41) | 4.1607616(41) | 4.1607616(41) | 4.1607616(41) | 4.1607616(41) | 4.1607616(41) | 4.16076 |
| 2 | `phases.0.scale` | 0.00049970(36) | 0.00049970(36) | 0.00049970(36) | 0.00049970(36) | 0.00049970(36) | 0.00049970(36) | 0.0005 |
| 2 | `instrument.zero_shift` | 0.008015(14) | 0.008015(14) | 0.008015(14) | 0.008015(14) | 0.008015(14) | 0.008015(14) | 0.008 |
| 2 | `instrument.profile.w` | 0.0002493(21) | 0.0002493(21) | 0.0002493(21) | 0.0002493(21) | 0.0002493(21) | 0.0002493(21) | 0.00025 |
| 2 | `instrument.background.c0` | 39.10(14) | 39.10(14) | 39.10(14) | 39.10(14) | 39.10(14) | 39.10(14) | 40 |
| 3 | `phases.0.cell.a` | 4.1628387(42) | 4.1628387(42) | 4.1628387(42) | 4.1628387(42) | 4.1628387(42) | 4.1628387(42) | 4.16283 |
| 3 | `phases.0.scale` | 0.00049963(36) | 0.00049963(36) | 0.00049963(36) | 0.00049963(36) | 0.00049963(36) | 0.00049963(36) | 0.0005 |
| 3 | `instrument.zero_shift` | 0.008018(14) | 0.008018(14) | 0.008018(14) | 0.008018(14) | 0.008018(14) | 0.008018(14) | 0.008 |
| 3 | `instrument.profile.w` | 0.0002521(21) | 0.0002521(21) | 0.0002521(21) | 0.0002521(21) | 0.0002521(21) | 0.0002521(21) | 0.00025 |
| 3 | `instrument.background.c0` | 38.99(14) | 38.99(14) | 38.99(14) | 38.99(14) | 38.99(14) | 38.99(14) | 40 |
| 4 | `phases.0.cell.a` | 4.2482085(41) | 4.2482085(41) | 4.2482085(41) | 4.2482085(41) | 4.2482085(41) | 4.2482085(40) | 4.24821 |
| 4 | `phases.0.scale` | 0.00049975(36) | 0.00049975(36) | 0.00049975(36) | 0.00049975(36) | 0.00049975(36) | 0.00049974(36) | 0.0005 |
| 4 | `instrument.zero_shift` | 0.007983(13) | 0.007983(13) | 0.007983(13) | 0.007983(13) | 0.007983(13) | 0.007983(13) | 0.008 |
| 4 | `instrument.profile.w` | 0.0002477(20) | 0.0002477(20) | 0.0002477(20) | 0.0002477(20) | 0.0002477(20) | 0.0002478(20) | 0.00025 |
| 4 | `instrument.background.c0` | 38.74(14) | 38.74(14) | 38.74(14) | 38.74(14) | 38.74(14) | 39.04(14) | 40 |
| 5 | `phases.0.cell.a` | 4.1669853(43) | 4.1669853(43) | 4.1669853(43) | 4.1669853(43) | 4.1669853(43) | 4.1669853(43) | 4.16699 |
| 5 | `phases.0.scale` | 0.00050002(37) | 0.00050002(37) | 0.00050002(37) | 0.00050002(37) | 0.00050002(37) | 0.00050001(37) | 0.0005 |
| 5 | `instrument.zero_shift` | 0.007977(14) | 0.007977(14) | 0.007977(14) | 0.007977(14) | 0.007977(14) | 0.007977(14) | 0.008 |
| 5 | `instrument.profile.w` | 0.0002494(22) | 0.0002494(22) | 0.0002494(22) | 0.0002494(22) | 0.0002494(22) | 0.0002495(22) | 0.00025 |
| 5 | `instrument.background.c0` | 38.56(14) | 38.56(14) | 38.56(14) | 38.56(14) | 38.56(14) | 38.85(14) | 40 |
| 6 | `phases.0.cell.a` | 4.1690659(42) | 4.1690659(42) | 4.1690659(42) | 4.1690659(42) | 4.1690659(42) | 4.1690659(42) | 4.16907 |
| 6 | `phases.0.scale` | 0.00049989(36) | 0.00049989(36) | 0.00049989(36) | 0.00049989(36) | 0.00049989(36) | 0.00049989(36) | 0.0005 |
| 6 | `instrument.zero_shift` | 0.007981(14) | 0.007981(14) | 0.007981(14) | 0.007981(14) | 0.007981(14) | 0.007981(14) | 0.008 |
| 6 | `instrument.profile.w` | 0.0002526(22) | 0.0002526(22) | 0.0002526(22) | 0.0002526(22) | 0.0002526(22) | 0.0002526(22) | 0.00025 |
| 6 | `instrument.background.c0` | 38.87(14) | 38.87(14) | 38.87(14) | 38.87(14) | 38.87(14) | 38.87(14) | 40 |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, the arm's pair, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`; "pair" is the arm differing from this one by one switch (`PAIRED`).  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | pair: bit-identical, differ | differ from ref | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 7 | 0 | 0 | 0 | 0 | 7 | — | — | 2 (4, 5) | 634 | 634 | 634 / 527 | 0.2-2.1 | 4 |
| status | 7 | 0 | 0 | 0 | 0 | 7 | 0 | — | 2 (4, 5) | 634 | 634 | 634 / 527 | 0.2-2.0 | 3 |
| off | 7 | 0 | 0 | 0 | 0 | 7 | 0 | — | 2 (4, 5) | 634 | 634 | 634 / 527 | 0.2-2.3 | 4 |
| status_maxiter | 7 | 0 | 0 | 0 | 0 | 7 | 0 | `status`: 7, 0 | 2 (4, 5) | 634 | 634 | 634 / 527 | 0.2-2.1 | 4 |
| status_runaway | 7 | 0 | 0 | 0 | 0 | 7 | 0 | `status`: 7, 0 | 2 (4, 5) | 634 | 634 | 634 / 527 | 0.2-2.4 | 4 |
| ref | 7 | 0 | 0 | 0 | 0 | 1 | 2 (4, 5) | — | — | 258 | 258 | 258 / 280 | 0.2-0.3 | 2 |

### Series-level codes

| code | on | status | off | status_maxiter | status_runaway |
|---|---|---|---|---|---|
| `SEQUENTIAL_DISCONTINUITY` | 3: phases.0.cell.a 3→4; phases.0.cell.b 3→4; phases.0.cell.c 3→4 | 3: phases.0.cell.a 3→4; phases.0.cell.b 3→4; phases.0.cell.c 3→4 | 3: phases.0.cell.a 3→4; phases.0.cell.b 3→4; phases.0.cell.c 3→4 | 3: phases.0.cell.a 3→4; phases.0.cell.b 3→4; phases.0.cell.c 3→4 | 3: phases.0.cell.a 3→4; phases.0.cell.b 3→4; phases.0.cell.c 3→4 |
| `SEQUENTIAL_PERSISTENT_FINDING` | 2 | 2 | 2 | 2 | 2 |

Failures (`SeriesFailure`): on 0, status 0, off 0, status_maxiter 0, status_runaway 0.

## tutorial 05's LaB6 ramp, 7 patterns 300-900 K (synthetic), the 700 K cell × 1.05

Protocol: examples/tutorials/05_sequential_fits.py series_jump / series_broken: refine_sequential(plan='mccusker_default', x=T, labels=scans), carry=('*',), refit='single', compiled tier default.  Arms: on, status, off, status_maxiter, status_runaway; reference `ref`; truth: the simulation.

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev | status_maxiter: rungs [kept] | status_maxiter: Rwp warm→kept | status_maxiter: fence | status_maxiter: nfev | status_runaway: rungs [kept] | status_runaway: Rwp warm→kept | status_runaway: fence | status_runaway: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | scan8 | c [c] | 0.0409 | — | 38 | c [c] | 0.0409 | — | 38 | c [c] | 0.0409 | — | 38 | c [c] | 0.0409 | — | 38 | c [c] | 0.0409 | — | 38 |
| 1 | scan9 | w [w] | 0.0409 | 0.0511 | 15 | w [w] | 0.0409 | inf | 15 | w [w] | 0.0409 | 0.0511 | 15 | w [w] | 0.0409 | inf | 15 | w [w] | 0.0409 | inf | 15 |
| 2 | scan10 | w [w] | 0.0399 | 0.0511 | 15 | w [w] | 0.0399 | inf | 15 | w [w] | 0.0399 | 0.0511 | 15 | w [w] | 0.0399 | inf | 15 | w [w] | 0.0399 | inf | 15 |
| 3 | scan11 | w [w] | 0.0405 | 0.0511 | 15 | w [w] | 0.0405 | inf | 15 | w [w] | 0.0405 | 0.0511 | 15 | w [w] | 0.0405 | inf | 15 | w [w] | 0.0405 | inf | 15 |
| 4 | scan12 | w→ws→c [c] | 0.9687→0.9687 | 0.0508* | 19 | w [w] | 0.9687 | inf | 5 | w [w] | 0.9687 | 0.0508* | 5 | w [w] | 0.9687 | inf | 5 | w [w] | 0.9687 | inf | 5 |
| 5 | scan13 | w [w] | 0.0402 | 0.0511 | 45 | w [w] | 0.0402 | inf | 35 | w [w] | 0.0402 | 0.0511 | 35 | w [w] | 0.0402 | inf | 35 | w [w] | 0.0402 | inf | 35 |
| 6 | scan14 | w [w] | 0.0404 | 0.0508 | 15 | w [w] | 0.0404 | inf | 15 | w [w] | 0.0404 | 0.0508 | 15 | w [w] | 0.0404 | inf | 15 | w [w] | 0.0404 | inf | 15 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off | status_maxiter | status_runaway |
|---|---|---|---|---|---|
| 0 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 1 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 2 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 3 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 4 | CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT, MODEL_FAR_FROM_DATA, PATTERN_UNDERSAMPLED, P_UNC, S_RESEED, S_RWP_OUTLIER | CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT, MODEL_FAR_FROM_DATA, PATTERN_UNDERSAMPLED, P_UNC | CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT, MODEL_FAR_FROM_DATA, PATTERN_UNDERSAMPLED, P_UNC, S_RWP_OUTLIER | CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT, MODEL_FAR_FROM_DATA, PATTERN_UNDERSAMPLED, P_UNC | CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT, MODEL_FAR_FROM_DATA, PATTERN_UNDERSAMPLED, P_UNC |
| 5 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 6 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, the arm's pair, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | status_maxiter vs on: worst |Δ|/esd (path) | status_runaway vs on: worst |Δ|/esd (path) | status_maxiter vs status | status_runaway vs status | on vs ref | status vs ref | off vs ref | status_maxiter vs ref | status_runaway vs ref | on vs truth | status vs truth | off vs truth | status_maxiter vs truth | status_runaway vs truth |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8.94 (instrument.background.c0) | 8.94 (instrument.background.c0) | 8.94 (instrument.background.c0) | 8.94 (instrument.background.c0) | 8.94 (instrument.background.c0) |
| 1 | 0 | 0 | 0 | 0 | 0 | 0 | 8.01e-07 (instrument.profile.u) | 8.01e-07 (instrument.profile.u) | 8.01e-07 (instrument.profile.u) | 8.01e-07 (instrument.profile.u) | 8.01e-07 (instrument.profile.u) | 6.68 (instrument.background.c0) | 6.68 (instrument.background.c0) | 6.68 (instrument.background.c0) | 6.68 (instrument.background.c0) | 6.68 (instrument.background.c0) |
| 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2.97e-07 (instrument.profile.v) | 2.97e-07 (instrument.profile.v) | 2.97e-07 (instrument.profile.v) | 2.97e-07 (instrument.profile.v) | 2.97e-07 (instrument.profile.v) | 6.66 (instrument.background.c0) | 6.66 (instrument.background.c0) | 6.66 (instrument.background.c0) | 6.66 (instrument.background.c0) | 6.66 (instrument.background.c0) |
| 3 | 0 | 0 | 0 | 0 | 0 | 0 | 6.51e-08 (instrument.profile.w) | 6.51e-08 (instrument.profile.w) | 6.51e-08 (instrument.profile.w) | 6.51e-08 (instrument.profile.w) | 6.51e-08 (instrument.profile.w) | 7.42 (instrument.background.c0) | 7.42 (instrument.background.c0) | 7.42 (instrument.background.c0) | 7.42 (instrument.background.c0) | 7.42 (instrument.background.c0) |
| 4 | 1.65e-10 (instrument.background.c0) ≠8 no-esd (instrument.profile.u, instrument.profile.v, instrument.profile.w, …) | 1.65e-10 (instrument.background.c0) ≠8 no-esd (instrument.profile.u, instrument.profile.v, instrument.profile.w, …) | 1.65e-10 (instrument.background.c0) ≠8 no-esd (instrument.profile.u, instrument.profile.v, instrument.profile.w, …) | 1.65e-10 (instrument.background.c0) ≠8 no-esd (instrument.profile.u, instrument.profile.v, instrument.profile.w, …) | 0 | 0 | 0 | 1.65e-10 (instrument.background.c0) ≠8 no-esd (instrument.profile.u, instrument.profile.v, instrument.profile.w, …) | 1.65e-10 (instrument.background.c0) ≠8 no-esd (instrument.profile.u, instrument.profile.v, instrument.profile.w, …) | 1.65e-10 (instrument.background.c0) ≠8 no-esd (instrument.profile.u, instrument.profile.v, instrument.profile.w, …) | 1.65e-10 (instrument.background.c0) ≠8 no-esd (instrument.profile.u, instrument.profile.v, instrument.profile.w, …) | 614 (phases.0.scale) | 668 (phases.0.scale) | 668 (phases.0.scale) | 668 (phases.0.scale) | 668 (phases.0.scale) |
| 5 | 3.26e-07 (instrument.profile.u) | 3.26e-07 (instrument.profile.u) | 3.26e-07 (instrument.profile.u) | 3.26e-07 (instrument.profile.u) | 0 | 0 | 2.47e-07 (instrument.profile.u) | 1.08e-07 (instrument.profile.w) | 1.08e-07 (instrument.profile.w) | 1.08e-07 (instrument.profile.w) | 1.08e-07 (instrument.profile.w) | 8.3 (instrument.background.c0) | 8.3 (instrument.background.c0) | 8.3 (instrument.background.c0) | 8.3 (instrument.background.c0) | 8.3 (instrument.background.c0) |
| 6 | 1.02e-07 (instrument.profile.v) | 1.02e-07 (instrument.profile.v) | 1.02e-07 (instrument.profile.v) | 1.02e-07 (instrument.profile.v) | 0 | 0 | 1.45e-07 (instrument.profile.u) | 2.46e-07 (instrument.profile.u) | 2.46e-07 (instrument.profile.u) | 2.46e-07 (instrument.profile.u) | 2.46e-07 (instrument.profile.u) | 8.28 (instrument.background.c0) | 8.28 (instrument.background.c0) | 8.28 (instrument.background.c0) | 8.28 (instrument.background.c0) | 8.28 (instrument.background.c0) |

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref` the reference; truth the simulation.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | status_maxiter | status_runaway | ref | truth |
|---|---|---|---|---|---|---|---|---|
| 0 | `phases.0.cell.a` | 4.1565938(43) | 4.1565938(43) | 4.1565938(43) | 4.1565938(43) | 4.1565938(43) | 4.1565938(43) | 4.1566 |
| 0 | `phases.0.scale` | 0.00049984(37) | 0.00049984(37) | 0.00049984(37) | 0.00049984(37) | 0.00049984(37) | 0.00049984(37) | 0.0005 |
| 0 | `instrument.zero_shift` | 0.007987(14) | 0.007987(14) | 0.007987(14) | 0.007987(14) | 0.007987(14) | 0.007987(14) | 0.008 |
| 0 | `instrument.profile.w` | 0.0002507(22) | 0.0002507(22) | 0.0002507(22) | 0.0002507(22) | 0.0002507(22) | 0.0002507(22) | 0.00025 |
| 0 | `instrument.background.c0` | 38.76(14) | 38.76(14) | 38.76(14) | 38.76(14) | 38.76(14) | 38.76(14) | 40 |
| 1 | `phases.0.cell.a` | 4.1586732(43) | 4.1586732(43) | 4.1586732(43) | 4.1586732(43) | 4.1586732(43) | 4.1586732(43) | 4.15868 |
| 1 | `phases.0.scale` | 0.00049969(38) | 0.00049969(38) | 0.00049969(38) | 0.00049969(38) | 0.00049969(38) | 0.00049969(38) | 0.0005 |
| 1 | `instrument.zero_shift` | 0.007986(14) | 0.007986(14) | 0.007986(14) | 0.007986(14) | 0.007986(14) | 0.007986(14) | 0.008 |
| 1 | `instrument.profile.w` | 0.0002511(22) | 0.0002511(22) | 0.0002511(22) | 0.0002511(22) | 0.0002511(22) | 0.0002511(22) | 0.00025 |
| 1 | `instrument.background.c0` | 39.06(14) | 39.06(14) | 39.06(14) | 39.06(14) | 39.06(14) | 39.06(14) | 40 |
| 2 | `phases.0.cell.a` | 4.1607616(41) | 4.1607616(41) | 4.1607616(41) | 4.1607616(41) | 4.1607616(41) | 4.1607616(41) | 4.16076 |
| 2 | `phases.0.scale` | 0.00049970(36) | 0.00049970(36) | 0.00049970(36) | 0.00049970(36) | 0.00049970(36) | 0.00049970(36) | 0.0005 |
| 2 | `instrument.zero_shift` | 0.008015(14) | 0.008015(14) | 0.008015(14) | 0.008015(14) | 0.008015(14) | 0.008015(14) | 0.008 |
| 2 | `instrument.profile.w` | 0.0002493(21) | 0.0002493(21) | 0.0002493(21) | 0.0002493(21) | 0.0002493(21) | 0.0002493(21) | 0.00025 |
| 2 | `instrument.background.c0` | 39.10(14) | 39.10(14) | 39.10(14) | 39.10(14) | 39.10(14) | 39.10(14) | 40 |
| 3 | `phases.0.cell.a` | 4.1628387(42) | 4.1628387(42) | 4.1628387(42) | 4.1628387(42) | 4.1628387(42) | 4.1628387(42) | 4.16283 |
| 3 | `phases.0.scale` | 0.00049963(36) | 0.00049963(36) | 0.00049963(36) | 0.00049963(36) | 0.00049963(36) | 0.00049963(36) | 0.0005 |
| 3 | `instrument.zero_shift` | 0.008018(14) | 0.008018(14) | 0.008018(14) | 0.008018(14) | 0.008018(14) | 0.008018(14) | 0.008 |
| 3 | `instrument.profile.w` | 0.0002521(21) | 0.0002521(21) | 0.0002521(21) | 0.0002521(21) | 0.0002521(21) | 0.0002521(21) | 0.00025 |
| 3 | `instrument.background.c0` | 38.99(14) | 38.99(14) | 38.99(14) | 38.99(14) | 38.99(14) | 38.99(14) | 40 |
| 4 | `phases.0.cell.a` | — | — | — | — | — | — | 4.37316 |
| 4 | `phases.0.scale` | 0.00000000(81) | 0.00000000(75) | 0.00000000(75) | 0.00000000(75) | 0.00000000(75) | 0.00000000(81) | 0.0005 |
| 4 | `instrument.zero_shift` | 0 | 0.00801768 | 0.00801768 | 0.00801768 | 0.00801768 | 0 | 0.008 |
| 4 | `instrument.profile.w` | 0.000375 | 0.000252163 | 0.000252163 | 0.000252163 | 0.000252163 | 0.000375 | 0.00025 |
| 4 | `instrument.background.c0` | 45.3(97) | 45.3(97) | 45.3(97) | 45.3(97) | 45.3(97) | 45.3(97) | 40 |
| 5 | `phases.0.cell.a` | 4.1669853(43) | 4.1669853(43) | 4.1669853(43) | 4.1669853(43) | 4.1669853(43) | 4.1669853(43) | 4.16699 |
| 5 | `phases.0.scale` | 0.00050001(37) | 0.00050001(37) | 0.00050001(37) | 0.00050001(37) | 0.00050001(37) | 0.00050001(37) | 0.0005 |
| 5 | `instrument.zero_shift` | 0.007977(14) | 0.007977(14) | 0.007977(14) | 0.007977(14) | 0.007977(14) | 0.007977(14) | 0.008 |
| 5 | `instrument.profile.w` | 0.0002495(22) | 0.0002495(22) | 0.0002495(22) | 0.0002495(22) | 0.0002495(22) | 0.0002495(22) | 0.00025 |
| 5 | `instrument.background.c0` | 38.85(14) | 38.85(14) | 38.85(14) | 38.85(14) | 38.85(14) | 38.85(14) | 40 |
| 6 | `phases.0.cell.a` | 4.1690659(42) | 4.1690659(42) | 4.1690659(42) | 4.1690659(42) | 4.1690659(42) | 4.1690659(42) | 4.16907 |
| 6 | `phases.0.scale` | 0.00049989(36) | 0.00049989(36) | 0.00049989(36) | 0.00049989(36) | 0.00049989(36) | 0.00049989(36) | 0.0005 |
| 6 | `instrument.zero_shift` | 0.007981(14) | 0.007981(14) | 0.007981(14) | 0.007981(14) | 0.007981(14) | 0.007981(14) | 0.008 |
| 6 | `instrument.profile.w` | 0.0002526(22) | 0.0002526(22) | 0.0002526(22) | 0.0002526(22) | 0.0002526(22) | 0.0002526(22) | 0.00025 |
| 6 | `instrument.background.c0` | 38.87(14) | 38.87(14) | 38.87(14) | 38.87(14) | 38.87(14) | 38.87(14) | 40 |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, the arm's pair, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`; "pair" is the arm differing from this one by one switch (`PAIRED`).  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | pair: bit-identical, differ | differ from ref | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 7 | 1 | 1 (4) | 0 | 1 (4) | 7 | — | — | 0 | 162 | 150 | 162 / 189 | 0.2-0.6 | 2 |
| status | 7 | 0 | 0 | 0 | 0 | 4 | 1 (4) | — | 1 (4) | 138 | 138 | 138 / 152 | 0.1-0.3 | 1 |
| off | 7 | 0 | 0 | 0 | 1 (4) | 4 | 1 (4) | — | 1 (4) | 138 | 138 | 138 / 152 | 0.1-0.3 | 1 |
| status_maxiter | 7 | 0 | 0 | 0 | 0 | 4 | 1 (4) | `status`: 7, 0 | 1 (4) | 138 | 138 | 138 / 152 | 0.1-0.3 | 1 |
| status_runaway | 7 | 0 | 0 | 0 | 0 | 4 | 1 (4) | `status`: 7, 0 | 1 (4) | 138 | 138 | 138 / 152 | 0.2-0.3 | 2 |
| ref | 7 | 0 | 0 | 0 | 0 | 2 | 0 | — | — | 212 | 212 | 212 / 239 | 0.2-0.3 | 2 |

### Series-level codes

| code | on | status | off | status_maxiter | status_runaway |
|---|---|---|---|---|---|
| `SEQUENTIAL_DISCONTINUITY` | 0 | 1: phases.0.scale 4→5 | 0 | 1: phases.0.scale 4→5 | 1: phases.0.scale 4→5 |
| `SEQUENTIAL_PERSISTENT_FINDING` | 2 | 2 | 2 | 2 | 2 |
| `SEQUENTIAL_RESEED` | 1 | 0 | 0 | 0 | 0 |
| `SEQUENTIAL_RWP_OUTLIER` | 1 | 0 | 1 | 0 | 0 |

Failures (`SeriesFailure`): on 0, status 0, off 0, status_maxiter 0, status_runaway 0.

