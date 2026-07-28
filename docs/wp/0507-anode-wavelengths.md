# WP-0507 — Additional anode wavelengths (Co/Cr/Fe/Mo/Ag)

Milestone: v0.5 · Status: 🔶 in progress
Depends on: —

## Goal

Lab data from a non-Cu anode is a one-argument change —
`Instrument.bragg_brentano(radiation="CoKa")` — not a hand-built `Source`, with
every wavelength on **one** consistent scale, and with the anode-dependent
checks that Cu currently gets for free (dispersion band, doublet edge guard,
Kβ / W Lα contamination) working off Cu too.

## Context

Today `_RADIATIONS` (`src/pxrdref/schemas/instrument.py`) carries only `CuKa`;
the code comment immediately above it already anticipates the others:

> Other anodes (Co, Mo, …) will be added once their values are transcribed
> and checked against Deslattes et al. (2003), Rev. Mod. Phys. 75, 35.

The Kα1/Kα2 **peak** wavelengths (not the centroid Kᾱ) are what the doublet
model wants. `bragg_brentano` already builds the two `EmissionLine`s and the
Kα2/Kα1 weight from whatever tuple it finds, so no forward-model change is
needed — this is a data-table extension plus the checks around it.

### The scale decision (settled 2026-07-28 — do not re-open casually)

**One column of one evaluation, for all six anodes: the NIST X-ray Transition
Energies Database (SRD 128) "Direct experimental" wavelength, KL3 = Kα1 and
KL2 = Kα2.** That database *is* the Deslattes et al. (2003) evaluation.

Mixing scales is the classic ~100 ppm cell error, and the anodes are sourced
from two different measurements *within* that evaluation (ref `7d` = Hölzer
1997 for the 3d metals, ref `5d` = Deslattes & Kessler 1985 for Mo/Ag), so
"same column" is the thing being asserted, not "same paper". What makes this
safe rather than a leap of faith: the database's Cu direct values are
**1.54059290 / 1.54442740**, i.e. bit-identical to the `CuKa` pair the repo has
shipped since v0.2 (documented there as the Hölzer peak values on the NIST
SRM 660c certificate scale). The existing entry is therefore *unchanged* by
this WP and doubles as the proof that the new rows are on its scale — a test
asserts exactly that.

The tempting alternative is Bearden (1967), which is what most textbooks and
several codes quote. It is a **different scale**: Bearden's Mo Kα2 = 0.713590
vs 0.713607 here (24 ppm) and Ag Kα1 = 0.5594075 vs 0.55942178 (26 ppm). Taking
Mo from Bearden while Cu stays on the Hölzer scale is precisely the failure
this WP exists to avoid.

Values, Å (direct experimental column; the digits given are the database's):

| anode | Kα1 (KL3)  | Kα2 (KL2) | ref |
|-------|------------|-----------|-----|
| Cr    | 2.2897260  | 2.2936510 | 7d  |
| Fe    | 1.9360410  | 1.9399730 | 7d  |
| Co    | 1.7889960  | 1.7928350 | 7d  |
| Cu    | 1.54059290 | 1.54442740| 7d  |
| Mo    | 0.70931715 | 0.713607  | 5d  |
| Ag    | 0.55942178 | 0.5638131 | 5d  |

Reproduce (the query is in the code comment too, so a future session can
re-derive rather than trust):

```sh
curl -s "https://physics.nist.gov/cgi-bin/XrayTrans/search.pl?download=tab&element=Mo&trans=KL2&trans=KL3&lower=&upper=&units=A"
```

### Things that are anode-dependent and currently Cu-shaped

- **`background/diagnostics.py` Kβ / W Lα contamination.** `_contamination_flags`
  returns `[]` outright unless the pattern's wavelength is within 0.01 Å of
  Cu Kα1, so every new anode this WP enables would get `contamination=[]` —
  which reads as "clean", not "not checked". Kβ1,3 comes from the same database
  column (KM3; for the 3d metals the direct value is the KM2,3 *blend*, which is
  what `_CU_KB` already is). W Lα1 is filament-derived, not anode-derived, so it
  applies to every anode.
- **`monochromator_two_theta`.** The docstring's "≈26.6° for graphite (002) with
  Cu Kα" is a Cu number; 2θ_m = 2·asin(λ/2d), d₍₀₀₂₎ ≈ 3.354 Å, so the same
  crystal is ≈12.1° at Mo Kα and K = 1/(1+cos²2θ_m) moves 0.500 → 0.511.
- **`ka2_ratio=0.5`** is the 2j+1 degeneracy ratio (4:2) and stays the right
  *seed* for any anode; it is refinable, and measured integrated ratios drift a
  few % above 0.5 with Z. Left alone, documented.

### Inherited

From **WP-0504** (anomalous f′/f″, landed 2026-07-27) — **check each new anode
against the dispersion table, not only against the wavelength references.**
Anomalous scattering is strongly anode-dependent, and an anode is routinely
*chosen* to sit on a particular side of a constituent's absorption edge:

* `crystallography/dispersion.py` bundles Cromer-Liberman over **3–70 keV**.
  Every anode in this WP's list is inside that band (Cr Kα1 = 5.415 keV lowest,
  Ag Kα1 = 22.16 keV highest), so no re-extraction is needed — but assert it,
  because the table *refuses* out-of-band rather than extrapolating.
* `dispersion.resolve` **raises** when the Kα1/Kα2 pair straddles an absorption
  edge of a constituent, because the two lines then cannot share one |F|².
  20 eV is a narrow window at Cu, but the gap grows with the anode and real
  cases exist: **Eu at Cu Kα**, and **Ru at Ag Kα** (ΔE = 173 eV, with Ru's K
  edge between the lines). A per-anode test that checks only wavelengths will
  not see this; add a smoke test that `resolve` succeeds at each new anode.
* The **`DISPERSION_NEGLECTED` diagnostic fires per wavelength**, so its
  message changes with the anode — Fe at Co Kα (6.93 keV, just below the Fe K
  edge at 7.11 keV) is a far larger correction than Fe at Mo Kα. Expect it in
  any new anode's acceptance output.

## Non-goals

- **Kβ as a modelled emission line.** Kβ stays out of the `_RADIATIONS` tuples
  (filtered or monochromated away in essentially every lab setup, and
  `dispersion.LINE_DISPERSION_TOL` refuses it anyway at ~860 eV from Kα). It
  appears here only as a *contamination-check* wavelength.
- **A real non-Cu acceptance dataset.** The repo has no Co/Mo/Ag pattern; this
  WP ships the table and its checks, not a new measured-Rwp claim.
- **An anode-aware monochromator helper.** Documented formula only; a
  `monochromator="graphite"` shortcut is API surface for another day.

## Tasks

- [x] Expand this stub into a full WP before writing code
- [ ] Transcribe Cr/Fe/Co/Mo/Ag Kα1,Kα2 into `_RADIATIONS`, each with its
      source in the comment; Cu unchanged
- [ ] Lookup/round-trip test per anode; the Cu-unchanged scale assertion; the
      doublet weight and polarization defaults checked off Cu
- [ ] Kα1-only variants (`"CuKa1"`, `"MoKa1"`, …) derived from the same tuples,
      for Ge(111)/Johansson-monochromated lab data
- [ ] Per-anode dispersion smoke test (see `### Inherited`): every anode inside
      the bundled 3–70 keV band, and `dispersion.resolve` not refusing the
      doublet for the test structures
- [ ] Generalize the Kβ / W Lα contamination check off Cu

## Acceptance

`Instrument.bragg_brentano(radiation="MoKa")` (and Co/Cr/Fe/Ag) returns a
two-line source with the transcribed wavelengths; a lookup test pins each
value to its cited source, and the Cu pair is asserted byte-for-byte unchanged.

```sh
.venv/bin/python -m pytest tests/test_lab_instrument.py tests/test_dispersion.py \
    tests/test_background_auto.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- NIST **X-ray Transition Energies Database**, SRD 128 —
  <https://physics.nist.gov/PhysRefData/XrayTrans/>; the evaluation is
  Deslattes, Kessler, Indelicato, de Billy, Lindroth & Anton (2003),
  *Rev. Mod. Phys.* **75**, 35–99.
- Ref `7d` in that database: Hölzer, Fritsch, Deutsch, Härtwig & Förster (1997),
  *Phys. Rev. A* **56**, 4554–4568 (Cr/Fe/Co/Cu Kα and Kβ).
- Ref `5d`: Deslattes & Kessler, in *Atomic Inner-Shell Physics*, ed. Crasemann
  (Plenum, 1985), 181–235 (Mo/Ag Kα, Kβ jointly with Bearden 1967 = ref `1`).
- Bearden (1967), *Rev. Mod. Phys.* **39**, 78–124 — the *other* scale, and the
  W Lα1 contamination wavelength already in `background/diagnostics.py`.

## Handover log

- **2026-07-28** — stub expanded into this file. **Done**: the scale decision
  (one database column for all six anodes, with the shipped Cu pair
  bit-identical to it — that is the whole safety argument, read it before
  touching a digit) and the two anode-shaped gaps found while scoping it: the
  contamination check bails off Cu, and the graphite-monochromator angle in the
  docstring is a Cu number. **In flight**: the table itself. **Next**: tasks
  2–6 below, in order.
- **2026-07-23** — created as a stub during the cross-code review that landed
  WP-0506; the wavelengths are documentation-checked but not yet transcribed.
