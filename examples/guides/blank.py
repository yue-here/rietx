"""The fits behind `docs/docs/guides/blank.md`: a measured empty capillary held under the pattern.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: APS 11-BM's scan of NIST SRM 640c silicon in a Kapton capillary (run
4918) and the same capillary scanned empty (run 4736), fetched by
`rietx.examples.fetch` on first use.
"""

# guide: start

import rietx as rx
from rietx.examples import fetch

data = rx.read_pattern(fetch("11BM_Si640c.xy"))
blank = rx.read_pattern(fetch("11BM_Kapton.xy"))


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


def fit_with(background, hold=()):
    instrument = rx.Instrument.debye_scherrer(wavelength=0.412359)
    instrument.background = background
    ref = rx.Refinement(silicon(), instrument)
    ref.hold(["phases.0.cell.*", *hold])
    return ref, ref.fit(data, plan="mccusker_default", two_theta_limits=(1.997, 49.996))


background = rx.BackgroundFixedPlusChebyshev.from_pattern(
    blank, n_terms=3, vary_scale=True, source="APS 11-BM run 4736, empty Kapton capillary")
ref, result = fit_with(background)

scale = result.parameter("instrument.background.scale")
print(f"blank scale {scale.value:.2f} ± {scale.stderr:.2f}")
# guide: end

# guide: order start
six = rx.BackgroundFixedPlusChebyshev.from_pattern(blank, n_terms=6, vary_scale=True)
_, result6 = fit_with(six)
scale6 = result6.parameter("instrument.background.scale")
print(f"with 6 terms: blank scale {scale6.value:.2f} ± {scale6.stderr:.2f}")
# guide: order end

# guide: hold start
fixed = rx.BackgroundFixedPlusChebyshev.from_pattern(blank, n_terms=3)
held_ref, _ = fit_with(fixed, hold=["instrument.background.scale"])
print("held scale", held_ref.fitted_instrument.background.scale.value)
# guide: hold end

# compiled path 0.8418 ± 0.0175, 0.6914 ± 0.0301 (2026-10-21, darwin/arm64)
assert result.status == result6.status == "converged"
assert round(scale.value, 2) == 0.84 and round(scale.stderr, 2) == 0.02
assert round(scale6.value, 2) == 0.69 and round(scale6.stderr, 2) == 0.03
assert held_ref.fitted_instrument.background.scale.value == 1.0
assert background.fixed_sigma is not None
assert ref.fitted_instrument.background.fixed_source == "APS 11-BM run 4736, empty Kapton capillary"

# Built with vary_scale=False and not held, the scale refines anyway: the
# preset's background stage frees `instrument.background.*`, which reaches it.
loose_ref, _ = fit_with(rx.BackgroundFixedPlusChebyshev.from_pattern(blank, n_terms=3))
assert round(loose_ref.fitted_instrument.background.scale.value, 2) == 0.84
