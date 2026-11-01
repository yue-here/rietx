"""The fits behind `docs/docs/guides/hump.md`: the Kapton capillary's halo as one declared hump.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: APS 11-BM's scan of NIST SRM 640c silicon in a Kapton capillary (run
4918), fetched by `rietx.examples.fetch` on first use.
"""

# guide: start

import rietx as rx
from rietx.examples import fetch
from rietx.schemas.instrument import HUMP_FWHM_MIN

data = rx.read_pattern(fetch("11BM_Si640c.xy"))


def silicon():
    """SRM 640c at its certified lattice parameter, 5.4311946 Å."""
    a = rx.Parameter(value=5.4311946)
    right = rx.Parameter(value=90.0)
    return rx.Structure(phases=[rx.Phase(
        name="Si", space_group="F d -3 m :2",
        cell=rx.Cell(a=a, b=a, c=a, alpha=right, beta=right, gamma=right),
        scale=rx.Parameter(value=3e-4, min=0.0),
        atoms=[rx.Atom(label="Si", species="Si", x=rx.Parameter(value=0.125),
                       y=rx.Parameter(value=0.125), z=rx.Parameter(value=0.125),
                       biso=rx.Parameter(value=0.44, min=0.0))])])


def halo():
    """Seeded where the empty capillary's scan peaks, near 5° 2θ."""
    return rx.HumpComponent(
        label="Kapton halo",
        position=rx.Parameter(value=5.0, unit="deg"),
        height=rx.Parameter(value=50.0, min=0.0, unit="counts"),
        fwhm=rx.Parameter(value=2.0, min=HUMP_FWHM_MIN, unit="deg"))


def fit_with(n_terms, humps):
    instrument = rx.Instrument.debye_scherrer(wavelength=0.412359)
    instrument.background = rx.BackgroundChebyshev.with_terms(n_terms)
    instrument.extra_components = humps
    ref = rx.Refinement(silicon(), instrument)
    ref.hold("phases.0.cell.*")
    return ref.fit(data, plan="mccusker_structural", two_theta_limits=(1.997, 49.996))


bisos = {}
for label, n_terms, humps in [("3 terms", 3, []), ("3 terms + hump", 3, [halo()]),
                              ("6 terms", 6, [])]:
    biso = bisos[label] = fit_with(n_terms, humps).parameter("phases.0.atoms.0.biso")
    print(f"{label:<15} Biso {biso.value:.3f} ± {biso.stderr:.3f} Å²")
# guide: end

# guide: hump start
humps = {}
for n_terms in (3, 6):
    result = fit_with(n_terms, [halo()])
    position, fwhm = humps[n_terms] = tuple(
        result.parameter(f"instrument.extra_components.0.{name}") for name in ("position", "fwhm"))
    print(f"{n_terms} terms: hump at {position.value:.2f} ± {position.stderr:.2f}°, "
          f"FWHM {fwhm.value:.2f} ± {fwhm.stderr:.2f}°")
# guide: hump end

# compiled path, 2026-10-21, darwin/arm64: Biso 0.4434(999), 0.4456(177),
# 0.4482(394); hump 4.161(104)° FWHM 5.586(252)°, 5.238(40)° FWHM 1.912(105)°
def rounded(p, digits):
    return round(p.value, digits), round(p.stderr, digits)


assert [rounded(b, 3) for b in bisos.values()] == [(0.443, 0.100), (0.446, 0.018), (0.448, 0.039)]
assert [rounded(p, 2) for p in humps[3]] == [(4.16, 0.10), (5.59, 0.25)]
assert [rounded(p, 2) for p in humps[6]] == [(5.24, 0.04), (1.91, 0.11)]
