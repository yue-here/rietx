"""CIF import/export via gemmi (MPL-2.0 dependency, isolated to this module)."""

from __future__ import annotations

import math
import re
from pathlib import Path

import gemmi

from ..schemas.common import Diagnostic, Parameter
from ..schemas.structure import AnisoU, Atom, Cell, Phase, Structure
from . import magcif
from .adp import U_NAMES, u_equivalent
from .symmetry import OperatorGroup, snap_diagnostics, split_group_label


def _strip_su(value: str) -> float:
    """Parse a CIF number, dropping the standard uncertainty: '10.257(1)' → 10.257."""
    return float(re.sub(r"\(\d+\)", "", value))


#: Largest disagreement between a stored cell angle and the value its space
#: group fixes that :func:`structure_from_cif` will **correct and record**
#: rather than leave for ``ParameterTable`` to refuse (WP-1028 §(j)).
#:
#: Chosen by what the two cases look like, not by comfort.  Below it the
#: deviation is the size of a *reported* angle — an experimenter quoting a
#: refined β = 90.002(3) under an orthorhombic symbol is reporting a
#: measurement, not a mistake, and at 0.1° the d-spacing consequence is 830 ppm
#: (linear in the deviation; see ``symmetry.SYMMETRY_ANGLE_TOL_DEG``, which
#: sizes it at 8.3 ppm per 1e-3°).  Above it the disagreement is *structural* —
#: the case WP-1036 found in the wild was a monoclinic β = 93.2° under an
#: orthorhombic symbol, 3.2° out — and there the symbol and the angle
#: contradict each other with no way for a reader to know which is wrong.  So a
#: large deviation is left exactly as written and still raises where it always
#: did, because choosing between "the angle is wrong" and "the symbol is wrong"
#: is the caller's to make.
CIF_ANGLE_CORRECT_MAX_DEG = 0.1

#: the grammar both form-factor lookups parse: an element symbol plus an
#: optional *trailing* charge (``Cl1-``) — see ``scattering.normalize_species``
#: and ``dispersion.normalize_element``, which share it deliberately
_CANONICAL_SPECIES = re.compile(r"^([A-Za-z]{1,2})(\d*[+-])?$")
_SIGN_FIRST_CHARGE = re.compile(r"^([A-Za-z]{1,2})([+-])(\d+)$")
_SITE_LABEL = re.compile(r"^([A-Za-z]{1,2})(\d+)$")


def _correct_symmetry_angles(sg, angles: dict[str, float], path: str,
                             diagnostics: list[Diagnostic] | None,
                             ) -> dict[str, float]:
    """Snap a symmetry-fixed cell angle onto its exact value, recording it.

    ``ParameterTable`` **refuses** a symmetry-fixed angle that disagrees with
    its space group, and rightly: it has no diagnostics channel, so an edit
    there could not be made visible, and an invisible edit to a stored cell is
    worse than a raise (WP-1036).  A *reader* does have that channel, which is
    why the correction belongs here — the same argument, and the same
    mechanism, as :func:`normalize_cif_species` one field over.

    Only deviations up to :data:`CIF_ANGLE_CORRECT_MAX_DEG` are corrected.  A
    larger one is left exactly as written, so it still raises where it always
    did: past that size the symbol and the angle contradict each other, and
    which of the two is wrong is not a reader's call.
    """
    from .symmetry import SYMMETRY_ANGLE_TOL_DEG, cell_constraints

    out = dict(angles)
    for name, target in cell_constraints(sg).fixed_angles.items():
        delta = out[name] - target
        if abs(delta) <= SYMMETRY_ANGLE_TOL_DEG:
            continue
        if abs(delta) > CIF_ANGLE_CORRECT_MAX_DEG:
            continue                      # structural disagreement — leave it
        out[name] = target
        if diagnostics is not None:
            diagnostics.append(Diagnostic(
                level="warning", code="CIF_CELL_ANGLE_CORRECTED",
                where=[f"phases.0.cell.{name}"],
                message=(f"{path} stores {name} = {angles[name]}° under space "
                         f"group {sg.xhm()!r}, whose symmetry fixes it at "
                         f"{target}°; read as {target}° "
                         f"({delta:+.6g}° corrected)"),
                suggestion="the deviation is information about the specimen or "
                           "the refinement that produced this file, not noise: "
                           "if it is real, the symmetry is lower than the "
                           "symbol claims and the phase wants the space group "
                           "that leaves this angle free",
            ))
    return out


def normalize_cif_species(species: str) -> tuple[str, str | None]:
    """Map the two wild CIF type-symbol forms onto the canonical grammar.

    Both form-factor lookups parse an element symbol with an optional
    *trailing* charge (``"Cl1-"``); two forms found in real repositories fail
    that grammar: a **sign-first charge** (``"O-2"``, ``"Ni+3"`` — ICSD
    exports) and a **site label in the type-symbol column** (``"O1"``,
    ``"Cl1"`` — AMCSD-derived files).  This rewrites those onto the canonical
    form, keeping the ion when one was written (``"O-2"`` → ``"O2-"``, so an
    ionic f₀ still resolves) and only when the result actually resolves in
    the Waasmaier-Kirfel table — a symbol this function cannot help
    (``"Wat"``, ``"D"``) passes through verbatim to fail with the lookup's
    own message rather than be half-rewritten.

    Returns ``(species, note)`` where ``note`` names the form that was
    rewritten, or is ``None`` when the input is untouched.  Lives here rather
    than in the lookups because the CIF reader is where a substitution can be
    recorded as provenance; ``scattering.normalize_species`` and
    ``dispersion.normalize_element`` stay strict for hand-built structures.
    """
    from .scattering import normalize_species

    s = species.strip()
    if _CANONICAL_SPECIES.match(s):
        return species, None
    if m := _SIGN_FIRST_CHARGE.match(s):
        candidate = f"{m.group(1).capitalize()}{m.group(3)}{m.group(2)}"
        note = "sign-first charge"
    elif m := _SITE_LABEL.match(s):
        candidate = m.group(1).capitalize()
        note = "site label in the type-symbol column"
    else:
        return species, None
    try:
        normalize_species(candidate)
    except KeyError:
        return species, None
    return candidate, note


def species_spelling_hint(species: str) -> str:
    """A refusal-message suffix naming the spelling that would resolve, or ``""``.

    Only the **sign-first charge** form (``"O-2"``, ``"Cu+1"`` — what ICSD
    exports and TOPAS writes) earns a hint: it is by far the commonest wild
    spelling reaching a hand-built structure, and the fix is unambiguous
    (``O2-``, ``Cu1+``).  Everything else returns empty — a three-letter typo
    (``"Wat"``) or a bare label (``"O1"``) has no single obvious correction to
    offer.

    Delegates to :func:`normalize_cif_species` rather than matching the pattern
    again, so the rewrite is **resolved before it is offered**.  Matching alone
    would hand out spellings that fail exactly as the input did — ``"Xx+2"`` →
    ``"Xx2+"`` is no more readable than ``"Xx+2"``, and ``"Og+2"`` → ``"Og2+"``
    names a real element with no row in either table — sending the caller to
    edit a file for nothing.  The two functions then cannot disagree on the same
    input, because there is one decision, made once.

    The division of labour across that one decision:
    :func:`normalize_cif_species` *repairs* this form at read (with a
    ``CIF_SPECIES_NORMALISED`` diagnostic to record it, per ``io/CLAUDE.md``:
    repair only where you can say that you did), and the model-compile boundary
    — which has no diagnostics channel, so it raises rather than repairs —
    reuses the same resolved candidate only to *name* the fix in its refusal.

        >>> species_spelling_hint("Cu+1")
        '; the charge is written after the digits, so Cu1+'
        >>> species_spelling_hint("Xx+2"), species_spelling_hint("O1")
        ('', '')
    """
    candidate, note = normalize_cif_species(species)
    if note != "sign-first charge":
        return ""
    return f"; the charge is written after the digits, so {candidate}"


def _gemmi_or_value_error(call, path: str, what: str):
    """Run a gemmi call, converting **any** exception into a named ``ValueError``.

    `io/CLAUDE.md`'s rule for every reader in this package: it raises
    ``ValueError``/``OSError`` and **names the file**, never its parser's
    exception. gemmi's small-structure reader breaks that on a file that is not
    a CIF at all — an empty or truncated one raises a bare
    ``IndexError('vector')`` from the C++ side, which is a traceback on an API
    caller and a 500 on the GUI's upload route rather than "this file could not
    be read".

    Found by WP-1328's truncation arm in ``tests/test_readers_robust.py``,
    which until then covered the *pattern* readers only — so the structure
    reader had never been handed a file cut mid-token. Pre-existing: measured
    identically on the parent commit, on a plain nuclear CIF, so it is nothing
    the magnetic arm introduced.
    """
    try:
        return call()
    except (ValueError, OSError) as exc:
        raise type(exc)(f"{path}: {what}: {exc}") from exc
    except Exception as exc:                        # noqa: BLE001 - the point
        raise ValueError(
            f"{path}: {what}: {type(exc).__name__}: {exc} — this file does not "
            f"read as a CIF (an empty, truncated or non-CIF file reaches here)"
        ) from exc


def _magnetic_content(text: str) -> bool:
    """Whether a CIF's text states a magnetic construct of any kind.

    The gate on the magnetic arm of :func:`structure_from_cif`, and a
    deliberately *textual* test: it decides whether this file is one the
    magnetic vocabulary applies to at all, so a nuclear CIF takes exactly the
    path it always did — including a displacively modulated one, whose average
    structure this reader has always returned and which is WP-1319's to fence,
    not this rung's.
    """
    if re.search(r"(?m)^\s*_atom_site_moment[._]", text):
        return True
    if re.search(r"(?m)^\s*_space_group_(?:symop_)?magn[._]", text):
        return True
    return bool(re.search(r"(?m)^\s*_space_group\.magn_", text))


def structure_from_cif(path: str, *, phase_name: str | None = None,
                       aniso: bool = False,
                       moment_ions: dict[str, str] | None = None,
                       moment_g: dict[str, float] | None = None,
                       nuclear_group: str = "auto",
                       diagnostics: list[Diagnostic] | None = None) -> Structure:
    """Read the first data block of a CIF into a single-phase :class:`Structure`.

    Uses gemmi's small-molecule reader, which resolves the space group from
    the recorded H-M (or Hall) symbol and carries fractional coordinates,
    occupancies, and isotropic/equivalent displacement parameters.

    ``aniso=True`` keeps ``_atom_site_aniso_U_ij`` as an
    :class:`~rietx.schemas.structure.AnisoU` block on each site that has
    one, instead of collapsing it to U_eq.  It is opt-in for the same reason
    the schema field is: reading a file must not silently change which
    parameters a refinement plan will free.  Sites without an aniso loop keep
    their isotropic value either way, so a mixed file yields a mixed
    structure.

    Species are passed through :func:`normalize_cif_species`, so the two wild
    type-symbol forms (``"O1"``, ``"O-2"``) arrive refinable instead of
    failing at the first stage compile.  Pass ``diagnostics=`` a list to
    record what changed: each distinct rewritten form appends one
    ``CIF_SPECIES_NORMALISED`` diagnostic naming the substitution, with
    ``where`` carrying every affected atom path.

    A **bracketed** H-M label beside an operation loop is a phase carrying its
    own operation list (what :func:`write_structure_block` writes for one), and
    comes back as that list in the file's order under that label — never as
    whatever symbol gemmi finds for the operations, which would drop the label
    and reorder the list a symmetry code indexes.

    **A magCIF** — a file carrying ``_space_group_symop_magn_operation.xyz``
    and an ``_atom_site_moment`` loop, which is what MAGNDATA, ISODISTORT and
    k-SUBGROUPSMAG emit — arrives as WP-1327's model: the operator list with
    its time-reversal signs on ``Phase.magnetic_symmetry``, the moments in
    crystal-axis components on the sites they name, and the BNS/OG symbol as
    metadata.  The nuclear space group's type comes from
    ``_parent_space_group.name_H-M_alt``, because a magCIF has no ordinary
    ``_space_group_name_H-M_alt`` at all and gemmi therefore resolves no space
    group for one; its setting is checked against the file's own operators
    (:func:`~rietx.crystallography.magcif.resolve_nuclear_symmetry`).  Two magnetic constructs are **refused by name** rather than
    half-read: a modulated structure (any ``_atom_site_moment_Fourier`` or
    special-function loop) and a structure stated in a *supercell* of its
    parent (the generic commensurate k ≠ 0 record) — see
    :mod:`rietx.crystallography.magcif`, which owns the vocabulary and both
    refusals.

    ``moment_ions`` and ``moment_g`` state, per site label, the two quantities
    no magnetic dictionary carries: the ion whose form factor the moment
    scatters with (``{"Mn1": "Mn3+"}``) and the Landé g a 4f moment needs.
    Where ``moment_ions`` says nothing the site's own type symbol is used and a
    ``CIF_MAGNETIC_ION_UNCHARGED`` diagnostic reports it, because MAGNDATA
    writes a bare ``Mn`` for a site that is chemically Mn³⁺ and the two form
    factors differ.  A key of either that names no ``_atom_site_moment`` row is
    refused (:class:`~rietx.crystallography.magcif.MagCifError`), since a
    misspelled label would leave its site on that default in silence.

    ``nuclear_group`` chooses which group a magCIF's atom *positions* refine
    under (the moments always refine under the file's magnetic group).
    ``"auto"`` takes the highest tabulated group the file's atoms satisfy — the
    parent where it contains the file's operators and keeps every site's
    orbit, reported by ``CIF_MAGNETIC_NUCLEAR_GROUP``, else the file's own
    family group, reported by ``CIF_MAGNETIC_NUCLEAR_SETTING`` (issue #457) —
    in its tabulated setting, or, where no tabulated setting has exactly its
    operations, as its own operation list under a bracketed label
    (``Phase.symmetry_operations``); ``"file"`` always takes the file's own group; ``"parent"`` always takes the
    parent and raises by name where it cannot carry the file's atoms.  It acts
    where the nuclear group is derived from ``_parent_space_group``, and a file
    with no magnetic block ignores it
    (:func:`~rietx.crystallography.magcif.resolve_nuclear_symmetry`).
    """
    if nuclear_group not in magcif.NUCLEAR_GROUP_CHOICES:
        raise ValueError(
            f"nuclear_group={nuclear_group!r}: expected one of "
            f"{', '.join(map(repr, magcif.NUCLEAR_GROUP_CHOICES))}")
    small = _gemmi_or_value_error(
        lambda: gemmi.read_small_structure(path), path,
        "could not be read as a small-molecule CIF")
    if not small.sites:
        raise ValueError(f"no atom sites found in {path}")
    text = Path(path).read_text(encoding="utf-8", errors="replace")

    # The magnetic arm's two refusals run **before** anything is built and
    # whether or not the file also states an ordinary space group: a magCIF
    # from ISODISTORT can carry both, and a refusal that fires only on the
    # branch where the nuclear symbol is missing is a construct dropped
    # exactly where the file was most complete.
    block = None
    magnetic_symmetry = None
    if _magnetic_content(text):
        block = _gemmi_or_value_error(
            lambda: gemmi.cif.read(path).sole_block(), path,
            "states a magnetic construct and has no single data block")
        magcif.refuse_modulation(text, path)
        magcif.refuse_a_magnetic_supercell(block, text, path)
        magnetic_symmetry = magcif.read_magnetic_symmetry(
            block, text, path, diagnostics=diagnostics)

    listed = None
    if split_group_label(small.spacegroup_hm or "") is not None and small.symops:
        listed = [str(op) for op in small.symops]
    sg = (OperatorGroup(label=small.spacegroup_hm.strip(), xyz=tuple(listed))
          if listed else small.spacegroup)
    if sg is None:
        # fall back on the raw H-M string in the file, then on the magCIF
        # parent symbol: a magCIF states no ordinary H-M symbol at all — the
        # magnetic block replaces it — so gemmi resolves no space group for
        # one, and the *nuclear* group is the parent's.  The magnetic operator
        # list cannot supply it: a type-III group is an index-2 subgroup of the
        # parent, so the nuclear symmetry is strictly higher than the
        # operators state.
        doc_block = block if block is not None else _gemmi_or_value_error(
            lambda: gemmi.cif.read(path).sole_block(), path,
            "has no single data block to read a space group from")
        hm = (doc_block.find_value("_symmetry_space_group_name_H-M")
              or doc_block.find_value("_space_group_name_H-M_alt")
              or (magcif.parent_space_group(doc_block) if block is not None
                  else None))
        if hm is None and block is not None:
            raise magcif.MagCifError(
                f"{path} states a magnetic structure and no space group this "
                f"reader can resolve: neither an ordinary "
                f"_space_group_name_H-M_alt nor the magCIF "
                f"_parent_space_group.name_H-M_alt. The magnetic operator list "
                f"alone cannot supply it — a type-III magnetic group is an "
                f"index-2 subgroup of the parent, so the nuclear symmetry is "
                f"strictly *higher* than the operators state, and a phase "
                f"built from them would carry the wrong absences and the wrong "
                f"site multiplicities.")
        if hm is None:
            raise ValueError(f"CIF {path} has no resolvable space group")
        if block is not None and magnetic_symmetry is not None:
            # The nuclear group of a magCIF is derived from the file's own
            # magnetic operators (time reversal dropped), never from the H-M
            # symbol alone: gemmi's tabulated operator set for a symbol can
            # sit at a different origin than the setting this file's cell,
            # coordinates and moments are actually stated in (measured on
            # Ima2/space group 46). The parent is kept where it contains the
            # file's operators and gives every site its own orbit; otherwise the
            # tabulated setting the operators state is taken, or else the
            # file's own operation list under a bracketed label (magcif.resolve_nuclear_symmetry, tier 3).
            sg = magcif.resolve_nuclear_symmetry(
                hm, magnetic_symmetry, path, diagnostics=diagnostics,
                nuclear_group=nuclear_group,
                sites=[(site.label, (site.fract.x, site.fract.y, site.fract.z))
                       for site in small.sites])
            if isinstance(sg, OperatorGroup):
                listed = list(sg.xyz)
        else:
            sg = gemmi.find_spacegroup_by_name(hm.strip("'\""))
            if sg is None:
                raise ValueError(f"unrecognised space group {hm!r} in {path}")

    cell = small.cell
    atoms: list[Atom] = []
    rewrites: dict[str, tuple[str, str, list[str]]] = {}
    for j, site in enumerate(small.sites):
        has_aniso = site.aniso.nonzero()
        u_iso = site.u_iso
        if not u_iso:
            # U_eq from the trace is an approximation (the exact form weights
            # by the metric — adp.u_equivalent); it only feeds the isotropic
            # fallback, where the tensor is being discarded anyway
            u_eq = (site.aniso.u11 + site.aniso.u22 + site.aniso.u33) / 3.0
            u_iso = u_eq if u_eq > 0 else 0.5 / (8.0 * math.pi ** 2)
        b_iso = u_iso * 8.0 * math.pi ** 2
        raw = site.type_symbol or site.element.name
        species, note = normalize_cif_species(raw)
        if note is not None:
            rewrites.setdefault(raw, (species, note, []))[2].append(
                f"phases.0.atoms.{j}.species")
        atoms.append(Atom(
            label=site.label,
            species=species,
            x=Parameter(value=site.fract.x),
            y=Parameter(value=site.fract.y),
            z=Parameter(value=site.fract.z),
            occ=Parameter(value=site.occ if site.occ else 1.0, min=0.0, max=1.5),
            biso=Parameter(value=b_iso, min=0.0, max=25.0, unit="A^2"),
            aniso=(AnisoU.from_values([site.aniso.u11, site.aniso.u22, site.aniso.u33,
                                       site.aniso.u12, site.aniso.u13, site.aniso.u23])
                   if aniso and has_aniso else None),
        ))

    if diagnostics is not None:
        for raw, (canonical, note, where) in rewrites.items():
            diagnostics.append(Diagnostic(
                level="info", code="CIF_SPECIES_NORMALISED",
                message=(f"species {raw!r} in {path} read as "
                         f"{canonical!r} ({note})"),
                where=where))
        diagnostics.extend(snap_diagnostics(
            sg, [(a.label, (a.x.value, a.y.value, a.z.value)) for a in atoms],
            source=path, prefix="phases.0"))

    angles = {"alpha": cell.alpha, "beta": cell.beta, "gamma": cell.gamma}
    angles = _correct_symmetry_angles(sg, angles, path, diagnostics)

    if block is not None:
        cell6 = (cell.a, cell.b, cell.c,
                 angles["alpha"], angles["beta"], angles["gamma"])
        written_ions, written_g = magcif.read_private_moment_items(block)
        ions = {**written_ions, **(moment_ions or {})}
        g_factors = {**written_g, **(moment_g or {})}
        moments = magcif.read_moments(block, cell6, path, ions=ions,
                                      g_factors=g_factors)
        by_label = {a.label: (j, a) for j, a in enumerate(atoms)}
        unmatched = sorted(set(moments) - set(by_label))
        if unmatched:
            raise magcif.MagCifError(
                f"{path}: the _atom_site_moment loop names "
                f"{', '.join(repr(u) for u in unmatched)}, which is not an "
                f"_atom_site_label in this block "
                f"({', '.join(repr(k) for k in by_label)}). A moment whose "
                f"site cannot be found is refused rather than dropped — it is "
                f"the whole magnetic contribution of that site.")
        # A caller's key that names no moment row is a misspelling, and a
        # misspelled ion would leave its site on the neutral atom's form
        # factor with nothing said -- the TOPAS arm refuses a misspelled
        # phase name for the same reason (review of #478, follow-up)
        for argument, stated in (("moment_ions", moment_ions),
                                 ("moment_g", moment_g)):
            stray = sorted(set(stated or {}) - set(moments))
            if stray:
                raise magcif.MagCifError(
                    f"{path}: {argument} names "
                    f"{', '.join(repr(k) for k in stray)}, which "
                    f"{'is' if len(stray) == 1 else 'are'} not a label in this "
                    f"file's _atom_site_moment loop "
                    f"({', '.join(repr(k) for k in moments) or 'no moments'}). "
                    f"A misspelled label would leave that site's moment on the "
                    f"file's own default with nothing said, so it is refused.")
        if moments and magnetic_symmetry is None:
            raise magcif.MagCifError(
                f"{path} states moments on "
                f"{', '.join(repr(k) for k in moments)} and no "
                f"_space_group_symop_magn_operation.xyz loop. A moment is only "
                f"meaningful under a magnetic space group — it is what gives "
                f"the moment an allowed subspace and an orbit — so the "
                f"operator list is not optional here.")
        from .magnetic import form_factor

        assumed_ions: dict[str, tuple[str, str]] = {}
        assumed_g: dict[str, float] = {}
        for label, (moment, _row) in moments.items():
            j, atom = by_label[label]
            # The ion is the one quantity a magCIF cannot state (there is no
            # such item in ``cif_mag.dic``), so it falls back on the site's own
            # type symbol and ``magnetic_diagnostics`` reports that it did. A
            # bare element symbol this table cannot resolve *neutrally* -- every
            # lanthanide/actinide it carries only ionic <j0> curves for -- gets
            # one further fallback: the element's majority oxidation state that
            # is magnetic (WP-1327 D1; issue-magnetic-form-factor option (b)),
            # reported as MAGNETIC_ION_ASSUMED rather than
            # CIF_MAGNETIC_ION_UNCHARGED, since it is a stronger substitution
            # than the neutral-atom one.
            ion = moment.ion or atom.species
            g = moment.g
            if not moment.ion and not form_factor.has_ion(ion):
                assumed = form_factor.resolve_assumed_ion(ion)
                if assumed is not None:
                    assumed_ions[label] = assumed
                    ion = assumed[0]
                    # g is the second quantity magCIF cannot state, and the
                    # same reasoning applies one step further: an ion this
                    # module *assumed* (never one a caller stated) that turns
                    # out to need an explicit g (every lanthanide/actinide
                    # here does) gets its free-ion Hund's-rule g_J defaulted
                    # too, rather than refusing on a quantity the file could
                    # never have carried either way (WP-1327 D-lande-g).
                    if g is None and form_factor.needs_explicit_g(ion):
                        default_g = form_factor.assumed_lande_g(ion)
                        if default_g is not None:
                            assumed_g[label] = default_g
                            g = default_g
            atoms[j] = atom.model_copy(update={
                "moment": moment.model_copy(update={"ion": ion, "g": g})})
        if diagnostics is not None and magnetic_symmetry is not None:
            diagnostics.extend(magcif.magnetic_diagnostics(
                path, {k: (atoms[by_label[k][0]].moment, row)
                       for k, (_m, row) in moments.items()},
                magnetic_symmetry,
                {a.label: (j, a) for j, a in enumerate(atoms)}, cell6,
                assumed_ions=assumed_ions, assumed_g=assumed_g))

    phase = Phase(
        name=phase_name or (small.name or "phase_1"),
        space_group=sg.xhm(),
        symmetry_operations=listed,
        cell=Cell(
            # bounds deliberately left open: a cell length's default window
            # is anchored per stage on the value that stage starts from
            # (params.vector.cell_window), and a finite bound here would read
            # as a claim by the caller and suppress it.  0.1 Å was never a
            # meaningful floor anyway — cell_window's is 1.5 Å.
            a=Parameter(value=cell.a),
            b=Parameter(value=cell.b),
            c=Parameter(value=cell.c),
            alpha=Parameter(value=angles["alpha"]),
            beta=Parameter(value=angles["beta"]),
            gamma=Parameter(value=angles["gamma"]),
        ),
        atoms=atoms,
        magnetic_symmetry=magnetic_symmetry,
    )
    return Structure(phases=[phase])


def format_su(value: float, esd: float | None, *, decimals: int = 6) -> str:
    """A number with its standard uncertainty in ``value(su)`` notation.

    The su carries **two significant figures** and the value is quoted to
    exactly that precision — ``4.59370(25)``, not ``4.593700(250)`` — the
    crystallographic convention (IUCr; Schwarzenbach et al., 1989, Acta Cryst.
    A45, 63): an esd of 2.5·10⁻⁴ says the sixth decimal is not knowledge.  The
    esd therefore sets the number of decimals; ``decimals`` governs only the
    no-esd case.

    Three traps this handles:

    - **Decade boundary.**  An esd like 0.0999 rounds *up* to two figures as
      ``100``; that is renormalised to ``0.10`` → ``value(10)`` with one fewer
      decimal, never the spurious three-figure ``(100)``.
    - **esd ≥ 1.**  The value loses decimals and the su keeps its trailing
      magnitude: 123.4 ± 2.5 → ``123.4(25)``; 12345 ± 250 → ``12340(250)``.
    - **No esd** (``None``, non-positive, or non-finite — a fixed parameter or
      one the fit could not estimate): the plain number is written, never an
      implied uncertainty.
    """
    if esd is None or not (esd > 0.0) or not math.isfinite(esd):
        return f"{value:.{decimals}f}"
    p = math.floor(math.log10(esd))       # decade of the esd's leading digit
    ndp = 1 - p                            # decimals so the su shows two figures
    su = round(esd * 10 ** ndp)            # 2-figure integer, normally 10..99
    if su >= 100:                          # rounded up across a decade (99.6→100)
        su //= 10
        ndp -= 1
    if su <= 0:                            # esd underflowed the printable range
        return f"{value:.{decimals}f}"
    if ndp > 0:
        return f"{value:.{ndp}f}({su})"
    scale = 10 ** (-ndp)                    # esd ≥ ~10: su carries trailing zeros
    return f"{round(value / scale) * scale:.0f}({su * scale})"


def _fmt(p: Parameter, decimals: int) -> str:
    """A CIF number from a :class:`Parameter`, su included when known."""
    return format_su(p.value, p.stderr, decimals=decimals)


def write_structure_block(block, phase: Phase, *,
                          moment_magnitude_esds: dict[str, float] | None = None,
                          ) -> None:
    """Write one phase's cell, sites and ADP loops into a gemmi CIF ``block``.

    A phase carrying its own operation list also gets a
    ``_space_group_symop_operation_xyz`` loop in its own order, which
    :func:`structure_from_cif` reads back under the bracketed label.

    Anisotropic sites get an ``_atom_site_aniso_*`` loop in the CIF U^ij
    convention — the same numbers :class:`~rietx.schemas.structure.AnisoU`
    stores — and their ``_atom_site_B_iso_or_equiv`` carries the equivalent
    B_eq = 8π²·U_eq computed from the tensor and cell, so a reader that
    ignores the aniso loop still sees the right isotropic magnitude rather
    than a stale starting estimate.  Standard uncertainties are written for
    any parameter whose ``stderr`` is set (see
    ``ParameterTable.apply_to_models``).  Shared with the refinement exporter
    (``io/exporters.py``), which appends refinement + pattern loops to the
    same block.
    """
    c = phase.cell
    cell6 = c.lengths_angles()
    for name in ("a", "b", "c"):
        block.set_pair(f"_cell_length_{name}", _fmt(getattr(c, name), 6))
    for name in ("alpha", "beta", "gamma"):
        block.set_pair(f"_cell_angle_{name}", _fmt(getattr(c, name), 4))
    block.set_pair("_symmetry_space_group_name_H-M", gemmi.cif.quote(phase.space_group))
    if phase.symmetry_operations is not None:
        # the list is the group, in the order a symmetry code indexes; a
        # bracketed label alone names nothing a reader can expand.  The
        # refinement exporter's geometry loop rewrites the same loop from the
        # same list (``resolve_group``), so the two cannot disagree.
        ops = block.init_loop("_space_group_symop_", ["id", "operation_xyz"])
        for idx, triplet in enumerate(phase.symmetry_operations):
            ops.add_row([str(idx + 1), gemmi.cif.quote(triplet)])
    loop = block.init_loop("_atom_site_", [
        "label", "type_symbol", "fract_x", "fract_y", "fract_z",
        "occupancy", "B_iso_or_equiv", "adp_type",
    ])
    for a in phase.atoms:
        if a.aniso is None:
            b_eq, kind = _fmt(a.biso, 4), "Biso"
        else:
            b_eq = f"{8.0 * math.pi ** 2 * u_equivalent(a.aniso.values(), cell6):.4f}"
            kind = "Uani"
        loop.add_row([
            a.label, a.species,
            _fmt(a.x, 6), _fmt(a.y, 6), _fmt(a.z, 6),
            _fmt(a.occ, 4), b_eq, kind,
        ])
    aniso = [a for a in phase.atoms if a.aniso is not None]
    if aniso:
        uloop = block.init_loop("_atom_site_aniso_", [
            "label", "U_11", "U_22", "U_33", "U_12", "U_13", "U_23",
        ])
        for a in aniso:
            uloop.add_row([a.label] + [_fmt(getattr(a.aniso, n), 5)
                                       for n in U_NAMES])
    # The magnetic half, when the phase carries one: the operator and centring
    # loops, the BNS/OG metadata, the parent k, and the moments with their esds
    # (``crystallography.magcif``).  Nothing at all is written for a phase with
    # no ``magnetic_symmetry``, so every file this writer produced before this
    # rung is byte-identical — the one property a writer change inside a
    # function shared by ``structure_to_cif`` and the refinement exporter has
    # to have.
    magcif.write_magnetic_block(block, phase,
                                magnitude_esds=moment_magnitude_esds)


def structure_to_cif(structure: Structure, path: str) -> None:
    """Write phases to a minimal CIF (cell, positions, occupancies, ADPs).

    One data block per phase.  See :func:`write_structure_block` for the ADP
    and standard-uncertainty conventions.
    """
    doc = gemmi.cif.Document()
    for phase in structure.phases:
        block = doc.add_new_block(re.sub(r"\W+", "_", phase.name))
        write_structure_block(block, phase)
    doc.write_file(path)
