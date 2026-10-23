"""Riding hydrogens on a rigid body: which X–H length, for which radiation (WP-1810).

A hydrogen in a rigid body rides with it: its template point is fixed relative
to its parent atom, so it adds no parameter.  What has to be chosen is the
**length** of the parent–H vector, and the right one depends on what the data
measure:

* **X-ray** data see the hydrogen's electron density, which the bond pulls
  toward the parent, so the refined X–H is 0.1–0.15 Å shorter than the
  internuclear distance.  The convention is SHELXL's riding-model defaults
  (Sheldrick 2015, *Acta Cryst.* C71, 3–8, and the SHELXL ``AFIX``/``HFIX``
  documentation it describes): aromatic and sp² C–H 0.93 Å, tertiary C–H
  0.98, CH₂ 0.97, CH₃ 0.96, hydroxyl O–H 0.82, N–H 0.86 Å.  These are the
  room-temperature defaults a molecular template usually carries.
* **Neutron** data see the nucleus, so the length is the internuclear mean:
  Allen, Watson, Brammer, Orpen & Taylor, *International Tables for
  Crystallography* Vol. C (2006), § 9.5, Table 9.5.1.1 (pp. 801, 808), whose
  X–H rows are from neutron structures only (its Note 21) and uncorrected for
  libration: aromatic C–H 1.083, C=C–H 1.077, X₃C–H 1.099, X₂C–H₂ 1.092,
  C–CH₃ 1.059, alcohol O–H 0.967, acid O–H 1.015, X₂N–H 1.009 Å (the H—N(3)
  row, n = 95, Note 21).  The table's X₃N⁺–H row (1.033 Å, n = 87) is not
  typed: the X-ray column has no ammonium length to pair it with.  The
  pairing of ``NH`` is itself a choice: SHELXL's 0.86 Å is its planar N–H
  (``AFIX 43``), while X₂N–H does not restrict the nitrogen's hybridisation.
  It is a fair pair for a riding default, not a like-for-like row.
* **A joint X-ray + neutron fit takes the neutron lengths**: the hydrogen's
  scattering signal is in the neutron histogram (a design choice of this
  package), and the X-ray pattern barely constrains it.  So
  :func:`riding_radiation` answers ``"neutron"`` whenever any histogram is
  neutron.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import numpy as np

#: X–H lengths (Å) by bond class and radiation; see the module docstring for
#: the source of each column.  ``None`` = no tabulated value: refused (no entry is ``None`` today).
RIDING_LENGTHS: dict[str, dict[str, float | None]] = {
    "xray": {"aromatic_CH": 0.93, "sp2_CH": 0.93, "CH": 0.98, "CH2": 0.97,
             "CH3": 0.96, "OH": 0.82, "acid_OH": 0.82, "NH": 0.86},
    "neutron": {"aromatic_CH": 1.083, "sp2_CH": 1.077, "CH": 1.099, "CH2": 1.092,
                "CH3": 1.059, "OH": 0.967, "acid_OH": 1.015, "NH": 1.009},
}


#: Å: an H closer than this to its parent gives no parent→H direction
RIDING_MIN_SEPARATION = 1e-6


def riding_radiation(instruments) -> str:
    """``"neutron"`` if any histogram is a neutron one, else ``"xray"``.

    One instrument or several (a joint fit).  A joint X-ray + neutron fit
    takes the neutron lengths, where the hydrogen signal is.
    """
    if not isinstance(instruments, Iterable) or hasattr(instruments, "source"):
        instruments = [instruments]
    kinds = {getattr(ins.source, "kind", "xray_cw") for ins in instruments}
    return "neutron" if any(k.startswith("neutron") for k in kinds) else "xray"


def riding_length(bond_class: str, radiation: str) -> float:
    """The X–H length (Å) for ``bond_class`` under ``radiation``."""
    try:
        value = RIDING_LENGTHS[radiation][bond_class]
    except KeyError:
        raise ValueError(
            f"no riding-H length for class {bond_class!r} under {radiation!r}; "
            f"classes: {sorted(RIDING_LENGTHS['xray'])}, radiations: "
            f"{sorted(RIDING_LENGTHS)}") from None
    if value is None:
        raise ValueError(
            f"{bond_class!r} has no tabulated {radiation} length in the source "
            "this table is typed from; give the length explicitly")
    return float(value)


def set_riding_lengths(body, classes: Mapping[str, str], radiation: str):
    """A copy of ``body`` with each riding H at its class's length from its parent.

    ``classes`` maps an H label to its bond class (``"CH3"``, ``"OH"``, …).
    The parent is the nearest template atom that is neither in ``classes`` nor
    already in ``body.riding`` (the template carries no species, so a label is
    what marks an H), and the H moves along the parent→H direction only, so
    every angle about the parent is kept.  An H label that is not a body atom,
    and an H that sits on its parent (no direction to keep), are refused by
    name.  The H labels are recorded in ``RigidBody.riding``, which is what the
    CIF writer flags ``R``/``calc``; the copy is validated, as a constructed
    body is.
    """
    from ..schemas.structure import RigidBody

    labels = list(body.atoms)
    unknown = sorted(set(classes) - set(labels))
    if unknown:
        raise ValueError(f"rigid body {body.name!r} has no atoms {unknown}")
    pts = np.asarray(body.template, dtype=np.float64).copy()
    heavy = [i for i, lab in enumerate(labels)
             if lab not in classes and lab not in body.riding]
    if not heavy:
        raise ValueError(f"rigid body {body.name!r} has no parent atom for its H")
    for h, cls in classes.items():
        length = riding_length(cls, radiation)
        i = labels.index(h)
        d = np.linalg.norm(pts[heavy] - pts[i], axis=1)
        parent = heavy[int(np.argmin(d))]
        v = pts[i] - pts[parent]
        norm = float(np.linalg.norm(v))
        if not norm > RIDING_MIN_SEPARATION:
            raise ValueError(
                f"rigid body {body.name!r}: {h!r} sits on its parent "
                f"{labels[parent]!r} ({norm:.3g} Å apart), so it has no "
                "direction to ride along")
        pts[i] = pts[parent] + v / norm * length
    riding = sorted(set(body.riding) | set(classes), key=labels.index)
    return RigidBody.model_validate({
        **body.model_dump(),
        "template": [tuple(float(c) for c in p) for p in pts], "riding": riding})
