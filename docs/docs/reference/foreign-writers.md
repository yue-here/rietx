# Files written for other programs

This page gives what each of the four writers for other programs puts in its file, how it spells a species and a space group, and what it refuses: `write_topas_inp`, `write_fullprof_pcr`, `write_gsas_exp` and `write_gsas2_phase_cif`.

[How to open a GSAS, TOPAS or FullProf refinement and write one back](../guides/foreign.md) gives the procedure, and [Refinement files from other programs](foreign-files.md) gives the readers.
[Diagnostics: other programs' projects](diagnostics-projects.md) gives every code this page names.
The writers are declared provisional with the readers ({ref}`provisional-by-declaration`).

## Writing a file

Each writer is the inverse of its format's reader followed by `ProjectModel.to_structure`.
It writes the same phases, cells and atoms, plus the part a CIF cannot carry: each `Parameter.vary` as a refine flag in the format's own grammar.
TOPAS writes `@` or `!`, or a name after a fit.
FullProf writes one codeword number per free parameter and never a shared tie.
GSAS writes `Y` on the cell record and its `X`, `U` and `F` letters on a site's.

```python
import tempfile
from pathlib import Path

import rietx as rx
from rietx.examples import examples_dir

structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
out = Path(tempfile.mkdtemp())
notes = []
rx.write_topas_inp(structure, out / "fap.inp", diagnostics=notes)
rx.write_fullprof_pcr(structure, out / "fap.pcr", diagnostics=notes)
rx.write_gsas_exp(structure, out / "fap.EXP", title="fluorapatite", diagnostics=notes)
rx.write_gsas2_phase_cif(structure, out / "fap_gsas2.cif", diagnostics=notes)

for name in ("fap.inp", "fap.pcr", "fap.EXP"):
    back = rx.read_project_model(out / name).to_structure()
    print(name, back.phases[0].cell.a.value, len(back.phases[0].atoms))
print(sorted({note.code for note in notes}))
```

```text
fap.inp 9.3717 7
fap.pcr 9.3717 7
fap.EXP 9.3717 7
['GSAS2_CIF_FIELD_NOT_WRITTEN', 'GSAS_EXP_VALUE_NARROWED']
```

GSAS-II has no text project format, so its pair is a phase CIF and an instrument `.instprm`.
`Structure.from_cif` reads the CIF back.
[Instrument files](instrument-files.md#writing-an-instprm) gives `write_gsas2_instprm`.
This build writes no `.gpx`.

A writer refuses on the way out what its reader would refuse on the way in, so a file it writes reads back.
It refuses while the value is still in hand, rather than leaving a file on disk to fail in another program.
Each writer takes `diagnostics=`, and a list passed there collects what it wrote differently or could not write.

## Space groups

Every writer writes the space group as `get_spacegroup(phase.space_group).xhm()`, never the phase's stored spelling.
A setting a reader already resolved is then not written back as an ambiguous symbol.

- TOPAS spells every setting. Origin choice 1 is written with TOPAS's `S` suffix, since TOPAS stops on `:1`.
- GSAS spells every setting, because its `SG SYM` record takes the whole symbol, so the `:2` or `:R` suffix travels.
- FullProf's grammar has no origin or axis suffix, so a `.pcr` can state only the setting FullProf's bare-symbol convention prefers: origin choice 2, and rhombohedral axes only where the cell metric says so. A phase whose resolved setting differs, most often origin choice 1, is refused by name rather than written as the other setting.
- A phase on rhombohedral axes is written on hexagonal axes for FullProf and for GSAS-II, with the restated cell and coordinates. FullProf reads `R -3 c` as hexagonal whatever the cell says, and GSAS-II's CIF import refuses the rhombohedral setting. [`FULLPROF_RHOMBOHEDRAL_RESTATED`](diagnostics-projects.md#fullprof_rhombohedral_restated) and [`GSAS2_CIF_RHOMBOHEDRAL_RESTATED`](diagnostics-projects.md#gsas2_cif_rhombohedral_restated) report it.
- The GSAS-II CIF states the setting three times, as [GSAS-II phase CIF](#gsas-ii-phase-cif) describes.

A phase whose group is only its own list of operations, under a bracketed label, is refused by every writer, since each format states a group as a symbol.

## Species

No writer refuses a species for its charge.
Each writes the atom rietx computes, in its own program's spelling.

| rietx | TOPAS | FullProf X-ray | FullProf neutron | GSAS | GSAS-II CIF |
|---|---|---|---|---|---|
| `Zr4+` | `Zr+4` | `ZR+4` | `ZR` | `ZR+4` | `Zr4+` |
| `O2-` | `O-2` | `O-2` | `O` | `O-2` | `O2-` |
| `Cu+` | `Cu+1` | `CU+1` | `CU` | `CU+1` | `Cu1+` |
| `7Li` | `7Li` | refused | `LI7`, with a LINE-12 b | `LI_7` | refused |
| `7Li1+` | `7Li+1` | refused | `LI7`, with a LINE-12 b | `LI+1_7` | refused |
| `2H` | `2H` | refused | `H2`, with a LINE-12 b | `H_2` | `D` |
| `Fe+` | `Fe` | `FE` | `FE` | `FE` | `Fe` |

- TOPAS stops on the IUCr order rietx stores, so an ion is written sign first. An isotope keeps its leading mass number, which is TOPAS's order too.
- FullProf looks its two tables up differently. X-rays key the form factor on the element, the sign and the magnitude. Neutrons key b on the element alone, and FullProf stops on `O-2` in a neutron file, so the charge is not written.
- FullProf takes an isotope only in a neutron file, as a LINE-12 user scattering length: `7Li` is written `Typ LI7`, with `LI7 -0.222 0.0 0` (b in 10⁻¹² cm). A bare `LI7` would run at natural abundance with no message. An isotope in an X-ray file is refused, and so is one whose name does not fit LINE 12's four characters (`157Gd`).
- GSAS writes the manual's atom type `aasv_nnn`: the symbol in upper case, the valence sign first with its number, then `_` and the mass number. That spelling comes from the GSAS manual, and no GSAS run has checked it. The reader takes GSAS's `NI+2_58` back as `58Ni2+`.
- A one-charge ion is written with its digit, and each spelling reads back as `Cu1+`. The digit matters to GSAS-II, whose importer reads a bare `Cu+` as carbon.
- An ion rietx's table does not carry, such as `Fe+` or `S2-`, is computed as the neutral atom, so the file states the neutral element. [`TOPAS_SPECIES_WRITTEN_NEUTRAL`](diagnostics-projects.md#topas_species_written_neutral), [`FULLPROF_SPECIES_WRITTEN_NEUTRAL`](diagnostics-projects.md#fullprof_species_written_neutral), [`GSAS_EXP_SPECIES_WRITTEN_NEUTRAL`](diagnostics-projects.md#gsas_exp_species_written_neutral) and [`GSAS2_CIF_SPECIES_WRITTEN_NEUTRAL`](diagnostics-projects.md#gsas2_cif_species_written_neutral) name each such label. A FullProf neutron file writes the element for every ion and names none.
- A moment-bearing site keeps its magnetic ion in TOPAS (`Fe4+` → `Fe+4`), since TOPAS takes the magnetic form factor from the `occ` species.

## Magnetic phases and propagation vectors

`write_topas_inp` writes a magnetic phase ([Structure files](structure-files.md#writing-a-magnetic-phase)).
The other three writers refuse a phase carrying `Phase.magnetic_symmetry` or a site moment, by name, because none of their programs would read the moments back.
GSAS-II 5.6.3's CIF import was measured to drop the magCIF loops without a warning.
`Structure.to_cif` writes the magCIF.

All four writers refuse a phase carrying a propagation vector (`Phase.propagation_vector`), since none of their files would read back with its k.
No CIF this package writes carries a nuclear phase's k either, so the `Structure`'s own JSON (`Structure.model_dump_json`) is the export that keeps one.

## TOPAS input files

`write_topas_inp(structure, path)` writes each phase as a `str` with each `Parameter.vary` as stored.
A moment's modulus is free when any of its components is.
A site near a special position is written on it, because TOPAS reads the ICSD's `x 0.3333` as a general position and generates too many atoms.
The stored coordinate is not changed.

An anisotropic site is written as `u11` to `u23` beside a held `beq`, the form the reader builds with `aniso=True`.
A phase's size and strain widths and its Stephens anisotropic-strain block are written as `lor_fwhm` and `gauss_fwhm` equations over `H`, `K`, `L`, `D_spacing` and `Th`.
TOPAS folds them by convolution into whatever peak type the input carries.
On a tetragonal test case TOPAS 6's calculated pattern then agrees with rietx's to 2 × 10⁻³ of the strongest peak, and a file stating only the isotropic widths misses by 3 × 10⁻².
The remaining difference is between two pseudo-Voigt approximations: TOPAS's convolution onto its peak type, and rietx's TCH blend.

### Refined parameters and ties

A plan replaces the vary flags at each stage, so after `ref.fit(data, plan=...)` the fitted structure carries each flag as the input had it.
A file written from it alone states almost nothing refinable.
The free set and the ties are in `Refinement.parameters()`, so pass the refinement as `free=`:

<!-- api-doc: no-exec — needs a fitted Refinement and writes a file -->
```python
rx.write_topas_inp(ref.fitted_structure, "refined.inp", free=ref,
                   scale="topas", instrument=ref.fitted_instrument)
```

In TOPAS a name is itself the refine flag (Technical Reference § 2.1).
So each free parameter is written under a name derived from its path (`Ba1_x`, `Fe1_biso`, `p0_scale`), and each tie as TOPAS states one (§ 2.3):

- a `tie_equal` group is one name written at every member;
- any other affine tie is an equation over its source's name (`beq = 2.0*B1_biso - 0.7;`);
- a coordinate refined through its site-symmetry degree of freedom is named after the coordinate;
- a source that no written value carries alone is declared with `prm`.

Each free parameter's finite bounds are written as `min` and `max`, since TOPAS's own default windows are not rietx's.
`free=` also takes a `RefinementResult` or a list of paths.
Those carry the free set and no ties, so each copy of a tied value is written as its own parameter, and the file's header says so.
A `RefinementResult` lists a tied copy beside the free parameters without its equation.
A symmetry tie, such as a cubic cell's `b` and `c` or a special position's coordinates, is derived again from the structure and written from its source.
A copy made by `Refinement.tie` is written as its own refined parameter.

`scale="topas"` writes the scale in TOPAS's convention, and the header says so.
That is rietx's scale × 100 for constant-wavelength neutrons, because TOPAS states |F|² in barn and rietx in fm².
For X-rays it is × K, because TOPAS's `LP_Factor` is rietx's Lp divided by the polarisation constant K.
The neutron factor was measured against TOPAS 6 output, and `tests/data/topas_export_nacl_neutron_ycalc.txt` is what a test holds rietx to.
The X-ray factor is the Technical Reference's definition, and no TOPAS output in the tree checks it yet.
`scale="topas"` needs `instrument=`, which says which radiation it is.
`scale="rietx"` writes rietx's own number and says in the header that it is not TOPAS's.

Without `free=`, `scale=`, `instrument=` or `pattern=` the writer writes the plain form above.
`p1_expand` (`False`, `True` or `"auto"`) restates a magnetic phase in P1, and anything else, such as `1` or `np.True_`, raises.
[Structure files](structure-files.md#writing-a-magnetic-phase) gives what each value writes.

### Whole TOPAS input

With `pattern=` as well as `instrument=`, `write_topas_inp` writes a file TOPAS runs as it stands.
The data go beside it as `<stem>.xye`: 2θ, the intensity and the σ rietx fits with, from the first to the last fitted point.
The `xdd` block describes them, with every term rietx fits written from TOPAS's documented keywords and checked against TOPAS 6 at zero cycles (`tests/test_topas_whole_input.py`).

| rietx | Written as |
|---|---|
| σ | `weighting = 1 / SigmaYobs^2;` |
| emission lines | `lam` with one `la lo lh` per line |
| neutron source, polarisation K | `neutron_data` and `LP_Factor(90)`; for X-rays `LP_Factor(c)` with cos² c = (1 − K)/K |
| `zero_shift` | `th2_offset` |
| `sample_displacement` | `th2_offset = -2*Rad*(sd)*Cos(Th)/Rs;` |
| Chebyshev background | `bkg`, the same series on the same range |
| P-spline background | one `fit_obj` per B-spline basis function, and its smoothing penalty as `penalty` terms with `pen_weight = 1;` |
| TCHZ profile, sample broadening | `peak_type pv`, with rietx's width laws as `pv_fwhm` and `pv_lor` equations |
| FCJ axial divergence (S/L, H/L) | `Finger_et_al(2·S/L·Rs, 2·H/L·Rs)` |
| Sabine extinction | a `scale_pks` equation over TOPAS's own \|F\|²: × 100 for neutrons (barn to fm²), × 1 for X-rays (electrons² in both programs), each measured against TOPAS |
| excluded regions inside the range | `exclude` |

Three entries differ from what a TOPAS user would write by hand, each for a measured reason.

The P-spline background is written as itself, with its penalty.
A Chebyshev series refitted to it is a different background with no penalty, and a TOPAS refinement from that lands on another minimum, with the background taking up structure.
On the published 300 K Ba₂FeSbSe₅ neutron pattern (Maier *et al.*, *Phys. Rev. B* 103, 054115 (2021)) it reached Rwp 4.30 % against rietx's 4.73 %, with the scale 7 % low and every B at zero.
TOPAS weighs a penalty by an adaptive factor unless `pen_weight` fixes it (Technical Reference, equation 4-7).
With it fixed, TOPAS's penalty sum at zero cycles equals rietx's to seven figures.

The profile is written as equations rather than `TCHZ_Peak_Type`, so the cubic η term is TCH's 0.11116, the value rietx uses.
The Technical Reference prints 0.1116.

`convolution_step` is set to give 16 calculation points across the narrowest FWHM.
On a 0.1° neutron grid with FCJ asymmetry, TOPAS's default left 6 % of the peak away from rietx.

At zero cycles TOPAS and rietx then agree to a few 10⁻³ of the largest peak.
A refinement in TOPAS from the written file lands on rietx's answer: on the same paper's 300 K and 1.5 K patterns, Rwp agreed within 0.006 % and every refined parameter within 0.42 combined esd.
What remains is TOPAS's own arithmetic: it integrates whole Lorentzian tails where rietx's windows hold 98 % of the area, and it averages the calculated pattern over the data step.

A whole input states the sample widths once, folded into `pv_fwhm` and `pv_lor`, with no `lor_fwhm` or `gauss_fwhm` line beside them.
It writes the extinction, and a magnetic-only width as a nuclear `str` and a `mag_only` one.
On a neutron pattern a moment-bearing site's species is written as its ion (`occ Fe+3` for species `Fe` with moment ion `Fe3+`), because TOPAS takes the magnetic form factor from the `occ` species, and a neutron's nuclear scattering length is the element's whatever the charge.

A term with no TOPAS statement here is refused by name rather than dropped:

- a peak shape other than the TCHZ pseudo-Voigt, such as the exact Voigt;
- a Stephens anisotropic-strain block (write without `instrument=` to have it as `str`-level equations);
- a background other than the Chebyshev and P-spline ones;
- a polarisation K outside 1/2 to 1, which has no `LP_Factor` angle;
- a sample transparency or a capillary offset;
- an absorption correction (`mu_r`, `mu_t`) or surface roughness;
- a λ/n harmonic, and a declared extra component;
- a phase with both a magnetic-only width and extinction, since rietx's one Sabine factor on the summed |F|² has no two-`str` statement in TOPAS.

### Terms a TOPAS file omits

A `str` written without `instrument=` does not state a phase's magnetic-only widths, its extinction, a preferred orientation with r ≠ 1 or a spherical-harmonics texture.
TOPAS then computes the phase without them.
[`TOPAS_FIELD_NOT_WRITTEN`](diagnostics-projects.md#topas_field_not_written) names each one.
A whole input writes the extinction and the magnetic-only widths, so it names only the preferred orientation and the texture.

The writer also refuses what the `.inp` grammar cannot carry: a phase name with a double quote or a line break, a site label or species with whitespace or a single quote (which opens a TOPAS comment), and a non-finite value.

## FullProf input files

`write_fullprof_pcr(structure, path, instrument=instrument)` writes a `.pcr` that FullProf runs.

FullProf will not run a file without widths and a radiation, so these come from `instrument=`:

- the wavelengths, with `Job = 1` for a neutron source;
- the widths as FullProf's TCH pseudo-Voigt (`Npr = 7`), each phase's own sample broadening added, and FullProf's X and Y letters swapped onto rietx's strain and size terms;
- on an X-ray file, rietx's own anomalous dispersion, as one LINE-12 `nam f′ f″ 2` per `Typ`. Without it FullProf applies its own f′ and f″, which were measured against FullProf 8.20 to differ from rietx's away from Cu Kα.

Without `instrument=` the file states Cu Kα1 and Kα2 and a default `ProfileTCHZ()`'s widths, since zero widths stop FullProf.
The dispersion is then taken at Cu Kα, so an element with an absorption edge there, such as Eu or Ho, is refused until an instrument with its own wavelength is passed.
A dispersion override, or `dispersion=None`, is refused at write, because this module's reader would refuse the file.

The fitted 2θ range, the background and every control and output switch are protocol that `to_structure` never reads into a `Structure`.
The writer fills them with inert placeholders (a two-point flat background and one cycle) to keep the file complete.
A `.pcr` is positional, so every line the reader expects has to exist even where a `Structure` carries nothing for it.

FullProf's `Occ` is written from each site's multiplicity, which is the fully occupied value, so a partly occupied site is refused.
Each free parameter gets its own codeword number, `10·n + 1`.

`write_zero_shift=True` writes `instrument.zero_shift` as the `.pcr`'s `Zero`, in degrees 2θ with rietx's sign, as measured against FullProf 8.20.
Without it a non-zero zero shift is refused.

Refused by name, because the file would state a different profile from rietx's:

- an exact Voigt shape, a Stephens strain block, axial divergence and harmonics;
- a third emission line, a first line of weight 0, and a negative second weight (a negative `Ratio` is FullProf's flag for a second U, V, W block);
- a non-finite wavelength, weight or width.

Refused away from its off state, because the file writes the term at FullProf's identity:

- a sample displacement or transparency, and a capillary offset;
- absorption and surface roughness;
- a polarisation other than K = 0.5;
- a declared extra component, such as a hump or a peak;
- preferred orientation with r ≠ 1, a spherical-harmonics texture, and extinction.

The writer also refuses an anisotropic site, because `to_structure` declines to assume FullProf's convention for the anisotropic β values on the way in.
A blank phase name, a line break in a name, a comment marker (`!`, `#` or `<--`) in a name, label or species, and whitespace in a label or species are refused, since each would shift every later field of the positional file.

## GSAS experiment files

`write_gsas_exp(structure, path, title=)` writes a `.EXP` with no histograms, which is what a GSAS experiment file looks like before any data is loaded.
The instrument, the wavelengths, the profile and background coefficients, the excluded regions and the phase scale are not written.

A `.EXP` is read by column rather than by token.
A value whose shortest exact decimal fits its ten columns crosses untouched.
One that does not is written to the precision the field holds, and [`GSAS_EXP_VALUE_NARROWED`](diagnostics-projects.md#gsas_exp_value_narrowed) names it once for the file.
The displacement is always in that second class: GSAS stores `Uiso` and rietx stores `Biso`, and the 8π² between them turns a two-character `Biso` into a `Uiso` no ten-column field holds exactly.
Ten columns keep it to about seven significant figures, five orders below the esd a refinement reports, and two figures better than the six decimals GSAS itself writes.

GSAS states one refine flag for a whole cell and one for a site's three coordinates, each meaning "refine as symmetry permits".
A structure whose six cell flags, or three coordinate flags, disagree is written free, and [`GSAS_EXP_REFINE_FLAG_MERGED`](diagnostics-projects.md#gsas_exp_refine_flag_merged) names the group.
The file then still says the cell refined, and you learn which held parameter it frees.

Refused by name:

- more than 9 phases, or more than 999 sites in one phase, the limits of the format's own records;
- an anisotropic site, since no file here settles GSAS's off-diagonal convention;
- a blank site label, and a label with whitespace at either end or longer than eight characters;
- a non-finite value.

## GSAS-II phase CIF

`write_gsas2_phase_cif(structure, path)` writes the CIF GSAS-II's own importer reads.
It keeps B (`_atom_site_B_iso_or_equiv`) where every other CIF from rietx writes U, and writes an anisotropic site as `Uani` with the `_atom_site_aniso_` loop.

It states the setting three times.
GSAS-II resolves a bare two-origin symbol such as `F d -3 m` to origin choice 2 and calls choice 1 a setting not compatible with it.
gemmi, and so rietx, resolves the same string to choice 1.
No single symbol satisfies both, so each tag carries the spelling its own reader takes:

| Tag | Holds | Read by |
|---|---|---|
| `_symmetry_space_group_name_H-M` | the bare symbol | GSAS-II, first; it sets a colon-suffixed symbol to `P 1` |
| `_space_group_name_H-M_alt` | the resolved `xhm()` | gemmi, which prefers it when both are present |
| `_space_group_symop_operation_xyz` | the operations themselves | both; GSAS-II checks its reading of the symbol against them |

[`GSAS2_CIF_SETTING_IN_OPERATORS`](diagnostics-projects.md#gsas2_cif_setting_in_operators) names a phase whose symbol is ambiguous.
[`GSAS2_CIF_FIELD_NOT_WRITTEN`](diagnostics-projects.md#gsas2_cif_field_not_written) names what a CIF cannot state: the refine flags, the phase scale and the sample broadening, and a Stephens block, a preferred orientation, a texture, extinction or restraints where the structure has them.

GSAS-II keeps an isotope as a per-type choice in the phase's General data, which no CIF tag reaches, and its importer reads `7Li` as hydrogen and says so only on its console.
So an isotope other than deuterium is refused by name: write the element, then choose the isotope in GSAS-II.
`2H` is written `D`, the one isotope label GSAS-II takes, and [`GSAS2_CIF_DEUTERIUM_AS_D`](diagnostics-projects.md#gsas2_cif_deuterium_as_d) names every such site, since GSAS-II's D has b = 6.681 fm against the 6.671 fm (Sears) rietx uses.

A label or species that is blank or holds whitespace, and a non-finite value, are refused, since a CIF loop carries a label and a species as bare values.

## Fields no writer carries

No `to_structure` builds these from its file, so no writer writes them back for the reader to find:

- the emission profile and the instrument geometry, since no reader returns an `Instrument`, except where a TOPAS or FullProf writer is given `instrument=`;
- cell and site bound windows, except the `min` and `max` a TOPAS file written with `free=` states.
