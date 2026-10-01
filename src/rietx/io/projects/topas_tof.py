"""Time-of-flight datasets in a TOPAS ``.inp``: read into a rietx bank, and written back.

:func:`~rietx.io.projects.topas.read_topas_inp` recognises a time-of-flight
dataset by the constructs it states (``TopasModel.time_of_flight``). This module
is the other half: what each construct **means**, mapped onto
:class:`~rietx.schemas.instrument.TOFSource` and
:class:`~rietx.schemas.instrument.ProfileTOF`, and the inverse, a rietx bank
written as a ``.inp`` TOPAS v6 runs.

**Where every mapping comes from.** The Technical Reference states the
time-of-flight macros' signatures and one line each (§19.3.11) and the
``pk_xo`` relation tof = t0 + t1·d + t2·d² (§5.2). What the macros *do* it does
not state, and this module never reads a macro body — so each law below was
**measured against TOPAS v6 output** on synthetic files, black box, and is
quoted with its measurement in ``tests/data/README.md`` § TOPAS time of flight:

* ``TOF_x_axis_calibration(t0, ·, t1, ·, t2, ·)`` places a reflection at
  t0 + t1·d + t2·d² exactly: TZERO, DIFC, DIFA;
* ``TOF_PV(fw, F, lor, η, t1)`` is a pseudo-Voigt of FWHM 10⁻⁵·F·t1·d and
  Lorentzian fraction η, constant in d;
* ``TOF_Exponential(a0, ·, a1, ·, w, t1, ±)`` is an exponential of rate
  ln(1000)·(a0 + a1/d^w)/t1 on the late (``+``) or early (``−``) side;
* ``exp_conv_const c`` is an exponential of rate −ln(0.001)/c, late for c > 0;
* the un-weighted stack of one early and one late exponential (``push_peak``
  … ``add_pop_1st_2nd_peak``) is the same back-to-back pulse as the two in
  series, to TOPAS's own 1e-3 truncation: the components are not unit-area,
  so their sum is Von Dreele, Jorgensen & Windsor's (1982) eq. 10, the
  β:α-weighted sum of the two one-sided convolutions;
* ``scale_pks = D_spacing^4;`` multiplies by d⁴ exactly, and TOPAS's
  reflection intensity is then rietx's times 0.01/sin θ_bank — b² in barn
  where rietx's are in fm², and rietx's sin θ_bank, which TOPAS has no term
  for;
* ``bkg`` is rietx's shifted Chebyshev on [start_X, finish_X];
* juxtaposition is ``*`` at the same rank, left to right; ``^`` is
  right-associative and binds tighter than a unary minus.

**Representable is decided by evaluation, not by spelling.** A width or a
rate may be written through a macro, a ``local`` or an equation, so the reader
samples the law the file states over d and asks whether rietx's law
reproduces it exactly — α(d) = α₀ + α₁/d on the early side, β(d) = β₀ + β₁/d⁴
on the late side, and a TCH pseudo-Voigt whose σ²(d) = σ₀ + σ₁d² + σ₂d⁴ and
γ(d) = γ₀ + γ₁d + γ₂d² give the file's FWHM and η. It is exact or it is
refused by name: nothing is fitted, so nothing is approximated.

**What is refused, and why each cannot be carried**, all by name
(:attr:`TopasTOFBank.refused`):

* a second exponential on one side, or a side with none — rietx's peak is
  one back-to-back pair, and a one-sided shape is a different function, not a
  nearby one;
* a **weighted** peak stack (``scale_top_peak`` or ``set_top_peak_area`` on a
  member) — a back-to-back pair with a step at the junction, a different kind;
  the **un-weighted** stack ``push_peak`` / one exponential /
  ``bring_2nd_peak_to_top`` / the other / ``add_pop_1st_2nd_peak`` (the
  beamline ``GSAS_btb`` form) *is* the back-to-back pulse and is read as one
  (measured below);
* a ``user_defined_convolution``, a ``hat``, a moderator term in a user macro,
  and every other convolution keyword — no rietx counterpart;
* a ``scale_pks`` other than ``D_spacing^4`` (a refined power, an absorption
  exponential, a channel-width ratio) and its absence — rietx's intensity is
  d⁴·sin θ_bank and the other factors it applies are computed, never refined;
* a width or rate law that rietx's law does not reproduce; ``peak_type``
  other than ``pv``; ``more_accurate_Voigt`` (TOPAS then convolves an exact
  Voigt, rietx's is TCH's);
* magnetic sites, crystallite-size macros, and anything a user macro *with
  arguments* states — the reader does not substitute arguments.

**The bank angle is not in the file.** TOPAS's intensity carries no sin θ_bank
(measured above), so the angle cannot be read off the ``.inp`` and is the
caller's to give (:func:`to_tof_refinement`'s ``two_theta_bank_deg``). The
writer records it in a comment for a person; the reader does not parse
comments.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace

import numpy as np

from ...schemas.common import Parameter
from . import topas as _topas
from .topas import TopasInpError

#: −ln(0.001): TOPAS's exponentials are parameterised by where they reach 10⁻³.
LN1000 = math.log(1000.0)
#: b² in barn per b² in fm² — the unit factor between the two codes' |F|².
BARN_PER_FM2 = 0.01
#: The TCH coefficients rietx's pseudo-Voigt uses (Thompson, Cox & Hastings,
#: 1987, *J. Appl. Cryst.* **20**, 79, eqs. 4-5), restated so a ``.inp`` can
#: carry the same Γ and η as an equation.
_TCH_GAMMA = (2.69269, 2.42843, 4.47163, 0.07842)
_TCH_ETA = (1.36603, -0.47719, 0.11116)
_SQRT_8LN2 = math.sqrt(8.0 * math.log(2.0))
#: Where a law is sampled to decide whether rietx's reproduces it: the d range
#: of every bank in the archive and beyond, so a term that matters anywhere a
#: reflection could be is seen.
_D_SAMPLES = np.geomspace(0.25, 8.0, 17)
#: How closely rietx's law must reproduce the file's, relative. Evaluation is
#: double precision end to end, so this is rounding, not tolerance.
_EXACT = 1e-9


# ----------------------------------------------------------------- equations

class _Eq:
    """A TOPAS equation as TOPAS evaluates it (measured, module docstring).

    Numbers, names, ``+ - * / ^``, juxtaposition, parentheses and the
    functions ``Ln Exp Sqrt Sin Cos Tan ArcTan Abs``; ``Pi``. A name resolves
    through ``names`` (a value, or the text of an equation that is itself
    evaluated), and ``D_spacing`` through ``d``. Anything else — an unknown
    name, ``If``, ``Get``, a reserved parameter other than ``D_spacing`` — is
    :class:`_Unreadable`, so a caller refuses rather than guesses.
    """

    _TOKEN = re.compile(r"\s*(?:(?P<num>\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?)"
                        r"|(?P<name>[A-Za-z_]\w*)|(?P<op>[-+*/^(),]))")
    _FUNCS = {"Ln": math.log, "Exp": math.exp, "Sqrt": math.sqrt,
              "Sin": math.sin, "Cos": math.cos, "Tan": math.tan,
              "ArcTan": math.atan, "Abs": abs}
    _CONSTS = {"Pi": math.pi}

    def __init__(self, text: str, names: dict, depth: int = 0):
        self.toks, pos = [], 0
        text = text.strip().rstrip(";")
        while pos < len(text):
            m = self._TOKEN.match(text, pos)
            if not m or m.end() == pos:
                raise _Unreadable(f"`{text}` holds {text[pos:pos + 12]!r}")
            pos = m.end()
            if m["num"] is not None:
                self.toks.append(("num", float(m["num"])))
            elif m["name"] is not None:
                self.toks.append(("name", m["name"]))
            elif m["op"]:
                self.toks.append(("op", m["op"]))
        self.text, self.names, self.depth = text, names, depth

    def __call__(self, d: float) -> float:
        self.i, self.d = 0, d
        v = self._sum()
        if self.i != len(self.toks):
            raise _Unreadable(f"`{self.text}` does not parse as one equation")
        return v

    def _peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def _sum(self):
        v = self._product()
        while self._peek() in (("op", "+"), ("op", "-")):
            op = self.toks[self.i][1]
            self.i += 1
            w = self._product()
            v = v + w if op == "+" else v - w
        return v

    def _product(self):
        v = self._unary()
        while True:
            kind, val = self._peek()
            if (kind, val) in (("op", "*"), ("op", "/")):
                self.i += 1
                w = self._unary()
                v = v * w if val == "*" else v / w
            elif kind in ("num", "name") or (kind, val) == ("op", "("):
                v = v * self._unary()           # juxtaposition: `a b` is a*b
            else:
                return v

    def _unary(self):
        if self._peek() == ("op", "-"):
            self.i += 1
            return -self._unary()
        if self._peek() == ("op", "+"):
            self.i += 1
            return self._unary()
        return self._power()

    def _power(self):
        base = self._atom()
        if self._peek() == ("op", "^"):
            self.i += 1
            return base ** self._unary()        # right-associative, above unary −
        return base

    def _atom(self):
        kind, val = self._peek()
        self.i += 1
        if kind == "num":
            return val
        if kind == "op" and val == "(":
            v = self._sum()
            if self._peek() != ("op", ")"):
                raise _Unreadable(f"`{self.text}` has an unclosed parenthesis")
            self.i += 1
            return v
        if kind == "name":
            if val == "D_spacing":
                return self.d
            if val in self._FUNCS and self._peek() == ("op", "("):
                self.i += 1
                v = self._sum()
                if self._peek() != ("op", ")"):
                    raise _Unreadable(f"`{self.text}`: {val}( is not closed")
                self.i += 1
                return self._FUNCS[val](v)
            if val in self._CONSTS:
                return self._CONSTS[val]
            if val in self.names:
                got = self.names[val]
                if isinstance(got, str):
                    if self.depth > 20:
                        raise _Unreadable(f"`{val}` is defined in terms of itself")
                    return _Eq(got, self.names, self.depth + 1)(self.d)
                if got is None:
                    raise _Unreadable(f"`{val}` has no value this reader can read")
                return float(got)
            raise _Unreadable(f"`{val}` is not a name this reader can resolve")
        raise _Unreadable(f"`{self.text}` ends early")


class _Unreadable(ValueError):
    """An equation this module will not evaluate; the caller names it."""


def _law(text: str, names: dict):
    """``text`` as a function of d, or ``None`` with the reason."""
    try:
        f = _Eq(text, names)
        f(1.0)
        return f, None
    except (_Unreadable, ZeroDivisionError, OverflowError, ValueError) as exc:
        return None, str(exc)


def _exact_fit(values: np.ndarray, basis: list) -> np.ndarray | None:
    """Coefficients of ``values`` on ``basis`` (functions of d), or ``None``
    where the basis does not reproduce them to :data:`_EXACT`."""
    a = np.column_stack([b(_D_SAMPLES) for b in basis])
    coef, *_ = np.linalg.lstsq(a, values, rcond=None)
    scale = max(np.max(np.abs(values)), 1e-300)
    if np.max(np.abs(a @ coef - values)) > _EXACT * scale:
        return None
    coef[np.abs(coef) < 1e-14 * scale] = 0.0
    return coef


def _tch_inverse(fwhm: float, eta: float) -> tuple[float, float]:
    """The (Γ_G, Γ_L) whose TCH blend is (Γ, η) — the inverse of
    :func:`~rietx.model.profiles.pseudovoigt.tch_gamma_eta`."""
    if eta <= 0.0:
        return fwhm, 0.0
    e1, e2, e3 = _TCH_ETA
    lo, hi = 0.0, 1.0
    for _ in range(200):                        # η(q) is increasing on [0, 1]
        q = 0.5 * (lo + hi)
        if e1 * q + e2 * q * q + e3 * q ** 3 < eta:
            lo = q
        else:
            hi = q
    gl = 0.5 * (lo + hi) * fwhm
    c1, c2, c3, c4 = _TCH_GAMMA

    def gamma5(gg):
        return (gg ** 5 + c1 * gg ** 4 * gl + c2 * gg ** 3 * gl ** 2
                + c3 * gg ** 2 * gl ** 3 + c4 * gg * gl ** 4 + gl ** 5)
    lo, hi = 0.0, fwhm
    for _ in range(200):                        # Γ⁵ is increasing in Γ_G
        mid = 0.5 * (lo + hi)
        if gamma5(mid) < fwhm ** 5:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi), gl


# ---------------------------------------------------------- the bank, as read

@dataclass
class TopasTOFBank:
    """What one time-of-flight dataset states, read toward a rietx bank.

    ``calibration`` holds ``tzero``/``difc``/``difa``/``difb`` and
    ``profile`` the :class:`~rietx.schemas.instrument.ProfileTOF` fields,
    each a :class:`~rietx.schemas.Parameter` carrying the file's refine flag
    where it stated one. ``sources`` says which construct each came from.
    ``refused`` is ``(construct, why)`` for everything rietx cannot carry —
    empty means the bank reads whole.
    """

    dataset: int | None
    constructs: tuple = ()
    calibration: dict = field(default_factory=dict)
    profile: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)
    lorentz_d4: bool = False
    background: list = field(default_factory=list)
    start_x: float | None = None
    finish_x: float | None = None
    tof_lam: float | None = None
    #: ``extra_X_left``/``extra_X_right`` where the file states them — how far
    #: outside the range TOPAS generates reflections (default 0.5).
    extra_x: tuple | None = None
    refused: list = field(default_factory=list)

    def refuse(self, construct: str, why: str) -> None:
        if (construct, why) not in self.refused:
            self.refused.append((construct, why))


#: Convolutions rietx's TOF peak has no counterpart for: the reference's
#: ``Tcomm_1`` convolution list.  The peak-stack keywords are not here: the
#: un-weighted stack is the back-to-back pulse (:func:`_read_stack`), and a
#: weighted one is refused there by name.
_UNCARRIED_SHAPE = ("user_defined_convolution", "hat", "num_hats",
                    "stacked_hats_conv", "one_on_x_conv", "circles_conv",
                    "ft_conv", "axial_conv", "lpsd_th2_angular_range_degrees",
                    "gauss_fwhm", "lor_fwhm", "modify_peak", "more_accurate_Voigt",
                    "numerical_lor_gauss_conv", "th2_offset", "capillary_diameter_mm")
_UNCARRIED_MACROS = ("TOF_CS_L", "TOF_CS_G")
_UNCARRIED_MODEL = ("mlx", "mly", "mlz", "mag_space_group", "pdf_data",
                    "rigid", "spherical_harmonics_hkl")


#: The peak-stack keywords (reference § 6.3).  The first three build the
#: un-weighted stack this reader accepts; the last two weight one member.
_STACK_WORDS = ("push_peak", "bring_2nd_peak_to_top", "add_pop_1st_2nd_peak",
                "scale_top_peak", "set_top_peak_area")
_STACK_TOKEN = re.compile(r"\b(push_peak|bring_2nd_peak_to_top|add_pop_1st_2nd_peak"
                          r"|scale_top_peak|set_top_peak_area|exp_conv_const"
                          r"|TOF_Exponential|TOF_PV|pv_fwhm|pv_lor)\b")


def _read_stack(bank, text) -> None:
    """Accept the un-weighted two-exponential peak stack, refuse every other.

    The one form read: ``push_peak``, one exponential, ``bring_2nd_peak_to_top``,
    one exponential, ``add_pop_1st_2nd_peak`` — each exponential on its own
    stack member, nothing else inside the stack.  Its two exponentials are then
    read by side exactly as the series form's are, so one must be early and one
    late.  Measured against TOPAS v6 (``tests/data/tof/topas_stack/``): that
    stack equals the back-to-back pulse to TOPAS's 1e-3 truncation, and equals
    the same two exponentials in series; with ``scale_top_peak 3`` on a member
    it is a weighted pair, which rietx's peak is not.
    """
    if not re.search(r"\b(?:" + "|".join(_STACK_WORDS) + r")\b", text):
        return
    for kw in ("scale_top_peak", "set_top_peak_area"):
        if re.search(rf"\b{kw}\b", text):
            bank.refuse(kw, "a weighted peak stack is a back-to-back pair with "
                        "a step at the junction, a different kind from "
                        "rietx's one pair")
            return
    seq = [m[1] for m in _STACK_TOKEN.finditer(text)]
    try:
        i = seq.index("push_peak")
    except ValueError:
        bank.refuse("peak stack", "a stack operation with no push_peak")
        return
    inner = seq[i:i + 5]
    is_exp = ("exp_conv_const", "TOF_Exponential")
    if (seq.count("push_peak") != 1 or len(inner) != 5
            or inner[2] != "bring_2nd_peak_to_top"
            or inner[4] != "add_pop_1st_2nd_peak"
            or inner[1] not in is_exp or inner[3] not in is_exp
            or seq.count("bring_2nd_peak_to_top") != 1
            or seq.count("add_pop_1st_2nd_peak") != 1):
        bank.refuse("peak stack", "only push_peak / one exponential / "
                    "bring_2nd_peak_to_top / one exponential / "
                    "add_pop_1st_2nd_peak is the back-to-back pulse; this "
                    "stack is another shape")
        return
    bank.sources["peak stack"] = "push_peak/bring_2nd_peak_to_top/add_pop_1st_2nd_peak"


def _macro_calls(text: str, name: str) -> list[list[str]]:
    """The argument lists of every ``name(...)`` call in ``text``, split at
    top-level commas."""
    out = []
    for m in re.finditer(rf"\b{name}\s*\(", text):
        depth, i, args, cur = 1, m.end(), [], []
        while i < len(text) and depth:
            ch = text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if not depth:
                    break
            if ch == "," and depth == 1:
                args.append("".join(cur).strip())
                cur = []
            else:
                cur.append(ch)
            i += 1
        args.append("".join(cur).strip())
        out.append(args)
    return out


def _pair(c: str, v: str, symbols) -> "_topas._Read | None":
    """A TOPAS ``(c, v)`` macro argument pair — a parameter's name or flag,
    then its value — read through the reader's one value grammar."""
    return _topas._read_tail(f"{c} {v}", symbols)


def _param(read, unit: str | None = None) -> Parameter:
    vary = bool(read.vary) if read.vary is not None else False
    return Parameter(value=float(read.value), vary=vary, unit=unit)


def _keyword_values(text: str, keyword: str) -> list[str]:
    """Every value ``keyword`` states in ``text``: an equation's text, or the
    value token(s) after it."""
    out = []
    for m in re.finditer(rf"\b{keyword}\b", text):
        tail = text[m.end():]
        if (eq := re.match(r"\s*(?:[@!]\s*)?(?:[A-Za-z_]\w*\s*)?=([^;]*);", tail)):
            out.append(eq.group(1))
        elif (val := re.match(r"\s*(?:[@!]\s*)?(?:[A-Za-z_]\w*\s+)?"
                              r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", tail)):
            out.append(val.group(1))
        else:
            out.append(None)
    return out


def read_tof_banks(stripped: str, active: str, time_of_flight: dict) -> dict:
    """One :class:`TopasTOFBank` per time-of-flight dataset of ``active``."""
    quoted = re.sub(r'"[^"\n]*"', lambda m: _topas._blank(m.group()), active)
    bodies = {}
    for m in _topas._MACRO_DEF.finditer(stripped):
        head = re.match(r"macro\s*(\w*)\s*(\([^)]*\))?", m.group())
        if head[1]:
            bodies[head[1]] = (_topas._brace_body(stripped, m.end() - 1),
                               bool(head[2] and head[2].strip("() \t")))
    file_reads = _topas._symbol_reads(active)
    starts = [o.start() for o in _topas._BLOCK.finditer(active)
              if o["kw"] in _topas._DATASET_OPENERS]
    banks = {}
    for k, constructs in time_of_flight.items():
        if k is None or k >= len(starts):
            bank = TopasTOFBank(dataset=k, constructs=constructs)
            bank.refuse("dataset", "the time-of-flight constructs sit outside "
                        "every dataset this reader can see")
            banks[k] = bank
            continue
        end = starts[k + 1] if k + 1 < len(starts) else len(active)
        banks[k] = _read_bank(k, constructs, quoted[starts[k]:end],
                              bodies, file_reads)
    return banks


def _with_macros(bank, text, bodies) -> str:
    """``text`` with the body of every argument-free user macro it invokes
    appended; one *with* arguments that states a time-of-flight construct is
    refused by name, its arguments not being substituted here."""
    out = text
    for name, (body, has_args) in bodies.items():
        if re.search(rf"\b{re.escape(name)}\b", text):
            if has_args and (_topas._TOF_CONSTRUCT.search(body) or any(
                    re.search(rf"\b{kw}\b", body)
                    for kw in _UNCARRIED_SHAPE + _STACK_WORDS + (
                        "exp_conv_const", "pv_fwhm", "pv_lor", "scale_pks"))):
                bank.refuse(f"macro {name}(…)",
                            "a user macro with arguments states this bank's "
                            "peak shape or calibration, and its arguments are "
                            "not substituted here")
            elif not has_args:
                out += "\n" + body
    return out


def _read_bank(k, constructs, span, bodies, file_reads) -> TopasTOFBank:
    """One dataset, read **phase by phase**: a dataset-level card reaches every
    phase and a phase-level one only its own, so each phase is read as the
    dataset's head plus its own block, and the bank is what they agree on —
    rietx's profile and calibration belong to the bank, so phases that state
    different ones are refused rather than one picked."""
    bank = TopasTOFBank(dataset=k, constructs=constructs)
    blocks = [o for o in _topas._BLOCK.finditer(span)
              if o["kw"] not in _topas._DATASET_OPENERS]
    head = span[:blocks[0].start()] if blocks else span
    chunks = [span[o.start():(blocks[i + 1].start() if i + 1 < len(blocks)
                             else len(span))]
              for i, o in enumerate(blocks) if o["kw"] == "str"] or [""]
    whole = _with_macros(bank, span, bodies)
    span_reads = _topas._symbol_reads(whole)
    reads = {**file_reads, **span_reads}
    names = {n: (r.value if r.value is not None else r.expr) for n, r in reads.items()}
    # A declaration whose equation reaches `D_spacing` has no value until a
    # reflection gives it one, so the reader's symbol table leaves it out; the
    # equation itself is what a law here evaluates.
    for m in re.finditer(r"\b(?:prm|local)\s*[!@]?\s*([A-Za-z_]\w*)\s*=([^;]*);",
                         whole):
        if names.get(m[1]) is None:
            names[m[1]] = m[2]
    symbols = {n: r.value for n, r in reads.items() if r.value is not None}

    for kw in _UNCARRIED_SHAPE + _UNCARRIED_MODEL:
        if re.search(rf"\b{kw}\b", whole):
            bank.refuse(kw, "rietx's time-of-flight bank has no counterpart")
    for mac in _UNCARRIED_MACROS:
        if re.search(rf"\b{mac}\s*\(", whole):
            bank.refuse(mac, "rietx's time-of-flight bank has no counterpart")
    if re.search(r"\bTOF_GSAS\s*\(", whole):
        bank.refuse("TOF_GSAS", "a GSAS-format data file is not read through "
                    "this reader")
    for m in re.finditer(r"\bpeak_type\s+(\w+)", whole):
        if m[1] != "pv":
            bank.refuse(f"peak_type {m[1]}", "the pseudo-Voigt is the only "
                        "shape rietx's time-of-flight peak blends")
    if re.search(r"\b(?:la|lo|lh|lg)\s+[-+\d.@!]", whole):
        bank.refuse("lam", "an emission profile on a time-of-flight bank "
                    "offsets every peak by its `lo` (measured)")

    per_phase = []
    for chunk in chunks:
        one = TopasTOFBank(dataset=k)
        text = _with_macros(one, head + "\n" + chunk, bodies)
        _read_calibration(one, text, names, symbols, reads)
        _read_scale(one, text)
        _read_shape(one, text, names, symbols)
        per_phase.append(one)
    for one in per_phase:
        for c, why in one.refused:
            bank.refuse(c, why)
    first = per_phase[0]
    for one in per_phase[1:]:
        for attr in ("calibration", "profile"):
            a, b = getattr(first, attr), getattr(one, attr)
            same = a.keys() == b.keys() and all(
                math.isclose(float(getattr(a[x], "value", a[x])),
                             float(getattr(b[x], "value", b[x])),
                             rel_tol=_EXACT, abs_tol=1e-300) for x in a)
            if not same:
                bank.refuse(f"per-phase {attr}", "the phases of this dataset "
                            "state different ones, and rietx's belongs to the "
                            "bank")
    bank.calibration, bank.profile = first.calibration, first.profile
    bank.sources = first.sources
    bank.lorentz_d4 = all(one.lorentz_d4 for one in per_phase)
    _profile_flags(bank, [span_reads, file_reads])

    if m := re.search(rf"\bstart_X\s+({_topas._NUM})", head):
        bank.start_x = float(m[1])
    if m := re.search(rf"\bfinish_X\s+({_topas._NUM})", head):
        bank.finish_x = float(m[1])
    if m := re.search(rf"\bTOF_LAM\s*\(\s*({_topas._NUM})", whole):
        bank.tof_lam = float(m[1])
    left = re.search(rf"\bextra_X_left\s+({_topas._NUM})", head)
    right = re.search(rf"\bextra_X_right\s+({_topas._NUM})", head)
    if left or right:
        bank.extra_x = (float(left[1]) if left else 0.5,
                        float(right[1]) if right else 0.5)
    if m := re.search(rf"\bbkg\s*(?P<flag>[@!])?(?P<vals>(?:\s*{_topas._NUM}`?(?:_{_topas._NUM})?)+)", head):
        # `[bkg [@] # # #...]`: one flag for every coefficient (reference § 5.1)
        vary = m["flag"] == "@" or "`" in m["vals"]
        bank.background = [Parameter(value=float(v), vary=vary) for v in re.findall(
            rf"({_topas._NUM})`?(?:_{_topas._NUM})?", m["vals"])]
    return bank


def _read_calibration(bank, text, names, symbols, reads) -> None:
    calls = _macro_calls(text, "TOF_x_axis_calibration")
    pk = _keyword_values(text, "pk_xo")
    if len(calls) + len(pk) > 1:
        bank.refuse("TOF_x_axis_calibration / pk_xo",
                    "the peak position is stated more than once")
        return
    if calls:
        args = calls[0]
        if len(args) != 6:
            bank.refuse("TOF_x_axis_calibration", f"takes 6 arguments, the file "
                        f"gives {len(args)}")
            return
        reads = [_pair(args[i], args[i + 1], symbols) for i in (0, 2, 4)]
        if any(r is None or r.value is None for r in reads):
            bank.refuse("TOF_x_axis_calibration", "an argument does not read")
            return
        for key, r, unit in zip(("tzero", "difc", "difa"), reads,
                                ("us", "us/A", "us/A^2")):
            bank.calibration[key] = _param(r, unit)
        bank.calibration["difb"] = Parameter(value=0.0, vary=False, unit="us*A")
        bank.sources["calibration"] = "TOF_x_axis_calibration"
        # the name each argument carries, so TOF_PV/TOF_Exponential can be
        # checked against the bank's own DIFC
        bank.sources["difc_name"] = reads[1].name
        return
    if pk and pk[0] is not None:
        law, why = _law(pk[0], names)
        if law is None:
            bank.refuse("pk_xo", why)
            return
        vals = np.array([law(d) for d in _D_SAMPLES])
        coef = _exact_fit(vals, [np.ones_like, lambda d: d, lambda d: d * d,
                                 lambda d: 1.0 / d])
        if coef is None:
            bank.refuse("pk_xo", f"`{pk[0].strip()}` is not t0 + t1·d + t2·d² "
                        f"+ t3/d")
            return
        decl = _term_flags(pk[0], reads)
        for key, c, unit in zip(("tzero", "difc", "difa", "difb"), coef,
                                ("us", "us/A", "us/A^2", "us*A")):
            read = decl.get(key)
            if read is not None and read.value is not None and math.isclose(
                    read.value, c, rel_tol=_EXACT, abs_tol=_EXACT):
                # the declared number, which the evaluation has just confirmed
                bank.calibration[key] = Parameter(value=float(read.value),
                                                  vary=bool(read.vary), unit=unit)
            else:
                bank.calibration[key] = Parameter(value=float(c), vary=False,
                                                  unit=unit)
        bank.sources["calibration"] = "pk_xo"
        return
    bank.refuse("calibration", "no TOF_x_axis_calibration or pk_xo this "
                "reader can find, so no reflection has a flight time")


def _term_flags(expr: str, reads: dict) -> dict:
    """The declaration behind each calibration term, where ``expr`` is the plain
    sum ``t0 + t1 D_spacing + t2 D_spacing^2 [+ t3 / D_spacing]`` of declared
    names (how the archive's macros write it); empty for any other spelling,
    whose values still read and whose flags are then not the file's to give."""
    pat = {"difa": r"([A-Za-z_]\w*)\s*\*?\s*D_spacing\s*\^\s*2",
           "difb": r"([A-Za-z_]\w*)\s*/\s*D_spacing",
           "difc": r"([A-Za-z_]\w*)\s*\*?\s*D_spacing",
           "tzero": r"([A-Za-z_]\w*)"}
    flags = {}
    for term in re.split(r"\s*\+\s*", expr.strip()):
        for key, rx in pat.items():
            if (m := re.fullmatch(rx, term.strip())) and m[1] in reads:
                if key in flags:
                    return {}
                flags[key] = reads[m[1]]
                break
        else:
            return {}
    return flags


def _read_scale(bank, text) -> None:
    for expr in _keyword_values(text, "scale_pks"):
        e = (expr or "").replace(" ", "")
        if e == "D_spacing^4":
            bank.lorentz_d4 = True
        else:
            bank.refuse(f"scale_pks = {(expr or '').strip()}",
                        "rietx's time-of-flight intensity is d⁴·sin θ_bank, and "
                        "the corrections it applies beside that are computed, "
                        "never refined")
    if not bank.lorentz_d4:
        bank.refuse("scale_pks = D_spacing^4", "absent, so TOPAS's intensity "
                    "carries no d⁴ and rietx's always does")


def _read_shape(bank, text, names, symbols) -> None:
    difc = bank.calibration.get("difc")
    difc_name = bank.sources.get("difc_name")
    t1_value = difc.value if difc is not None else None

    def t1_of(arg: str) -> float | None:
        a = arg.strip().lstrip("!@").strip()
        if difc_name and a == difc_name:
            return t1_value
        return symbols.get(a)

    # widths: TOF_PV, or pv_fwhm / pv_lor stated directly
    fwhm_law = eta_law = None
    pvs = _macro_calls(text, "TOF_PV")
    fw_direct = [v for v in _keyword_values(text, "pv_fwhm") if v is not None]
    lor_direct = [v for v in _keyword_values(text, "pv_lor") if v is not None]
    if len(pvs) + len(fw_direct) > 1 or len(lor_direct) > 1:
        bank.refuse("pseudo-Voigt", "the width is stated more than once")
    elif pvs:
        args = pvs[0]
        fw, lor = (_pair(args[0], args[1], symbols), _pair(args[2], args[3], symbols)) \
            if len(args) == 5 else (None, None)
        t1 = t1_of(args[4]) if len(args) == 5 else None
        if fw is None or lor is None or fw.value is None or lor.value is None or t1 is None:
            bank.refuse("TOF_PV", "its arguments, or the calibration constant it "
                        "names, do not read")
        else:
            f, e = float(fw.value), float(lor.value)
            fwhm_law = lambda d, f=f, t1=t1: 1e-5 * f * t1 * d  # noqa: E731
            eta_law = lambda d, e=e: e                            # noqa: E731
            bank.sources["widths"] = "TOF_PV"
    elif fw_direct:
        fl, why = _law(fw_direct[0], names)
        el, why2 = _law(lor_direct[0], names) if lor_direct else ((lambda d: 0.0), None)
        if fl is None or el is None:
            bank.refuse("pv_fwhm / pv_lor", why or why2)
        else:
            fwhm_law, eta_law = fl, el
            bank.sources["widths"] = "pv_fwhm/pv_lor"
    else:
        bank.refuse("peak width", "no TOF_PV or pv_fwhm this reader can find")
    if fwhm_law is not None:
        _widths_to_profile(bank, fwhm_law, eta_law)

    # exponentials: TOF_Exponential and exp_conv_const, by side — in series,
    # or as the two members of an un-weighted peak stack
    _read_stack(bank, text)
    sides: dict[str, list] = {"early": [], "late": []}
    for args in _macro_calls(text, "TOF_Exponential"):
        if len(args) != 7:
            bank.refuse("TOF_Exponential", f"takes 7 arguments, the file gives {len(args)}")
            continue
        a0, a1 = _pair(args[0], args[1], symbols), _pair(args[2], args[3], symbols)
        try:
            w = float(args[4])
        except ValueError:
            w = symbols.get(args[4].strip())
        t1 = t1_of(args[5])
        side = {"+": "late", "-": "early"}.get(args[6].strip())
        if None in (a0, a1, w, t1, side) or a0.value is None or a1.value is None:
            bank.refuse("TOF_Exponential", "its arguments, or the calibration "
                        "constant it names, do not read")
            continue
        sides[side].append(lambda d, a=a0.value, b=a1.value, w=w, t1=t1:
                           LN1000 * (a + b / d ** w) / t1)
    for expr in _keyword_values(text, "exp_conv_const"):
        law, why = _law(expr, names) if expr is not None else (None, "no value")
        if law is None:
            bank.refuse("exp_conv_const", why)
            continue
        c1 = law(1.0)
        side = "late" if c1 > 0 else "early"
        sides[side].append(lambda d, law=law: LN1000 / abs(law(d)))
    for side, keys, basis in (("early", ("alpha0", "alpha1"), lambda d: 1.0 / d),
                              ("late", ("beta0", "beta1"), lambda d: 1.0 / d ** 4)):
        if len(sides[side]) != 1:
            bank.refuse(f"{side}-side exponential",
                        f"the file states {len(sides[side])}, and rietx's peak "
                        f"is one back-to-back pair: one rise, one decay")
            continue
        vals = np.array([sides[side][0](d) for d in _D_SAMPLES])
        coef = _exact_fit(vals, [np.ones_like, basis])
        if coef is None:
            law = "α₀ + α₁/d" if side == "early" else "β₀ + β₁/d⁴"
            bank.refuse(f"{side}-side exponential", f"its rate is not {law}")
            continue
        for key, c in zip(keys, coef):
            bank.profile[key] = float(c)
    bank.sources["exponentials"] = "TOF_Exponential/exp_conv_const"


def _profile_flags(bank, scopes) -> None:
    """Turn the profile's numbers into :class:`Parameter` objects, carrying a
    refine flag where the file declared the coefficient under its
    :class:`~rietx.schemas.instrument.ProfileTOF` name with a ``_<tag>``
    suffix and the same value — how :func:`from_tof` writes them. A
    coefficient derived from a macro's arguments (``TOF_PV``'s width, say) has
    no one declaration whose flag it is, and arrives held."""
    out = {}
    for key, value in bank.profile.items():
        vary = False
        candidates = [(n, r) for scope in scopes for n, r in scope.items()]
        for name, read in candidates:
            if (name.startswith(key + "_") and read.value is not None
                    and math.isclose(read.value, value, rel_tol=_EXACT,
                                     abs_tol=1e-300)):
                # the file's own number for it, which evaluation has just
                # confirmed: the law sampled and fitted agrees to rounding, and
                # the declaration *is* the statement
                value, vary = float(read.value), bool(read.vary)
                break
        out[key] = Parameter(value=value, vary=vary)
    bank.profile = out


def _widths_to_profile(bank, fwhm_law, eta_law) -> None:
    try:
        pairs = [_tch_inverse(fwhm_law(d), eta_law(d)) for d in _D_SAMPLES]
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        bank.refuse("peak width", str(exc))
        return
    gg = np.array([p[0] for p in pairs])
    gl = np.array([p[1] for p in pairs])
    sig = _exact_fit(gg ** 2 / (8.0 * math.log(2.0)),
                     [np.ones_like, lambda d: d ** 2, lambda d: d ** 4])
    gam = (np.zeros(3) if not gl.any() else
           _exact_fit(gl, [np.ones_like, lambda d: d, lambda d: d ** 2]))
    if sig is None or gam is None:
        bank.refuse("peak width", "the FWHM and Lorentzian fraction the file "
                    "states are not a TCH pseudo-Voigt of σ² = σ₀ + σ₁d² + σ₂d⁴ "
                    "and γ = γ₀ + γ₁d + γ₂d²")
        return
    if np.any(sig < -_EXACT * max(np.max(np.abs(sig)), 1e-300)):
        bank.refuse("peak width", "the Gaussian variance law has a negative term")
        return
    for key, c in zip(("sig0", "sig1", "sig2"), sig):
        bank.profile[key] = max(float(c), 0.0)
    for key, c in zip(("gam0", "gam1", "gam2"), gam):
        bank.profile[key] = float(c)


# ------------------------------------------------------------ building rietx

def to_tof_refinement(model, *, dataset: int, two_theta_bank_deg: float):
    """``(Structure, Instrument)`` for one time-of-flight dataset.

    Refuses by name, listing every construct rietx cannot carry
    (:attr:`TopasTOFBank.refused`). The phase scale is converted on the way
    in, S_rietx = S_TOPAS · 0.01 / sin θ_bank (module docstring), which is
    why the bank angle — not in the file — is required.
    """
    from ...schemas.instrument import BackgroundChebyshev, Instrument, ProfileTOF

    bank = getattr(model, "tof_banks", {}).get(dataset)
    if bank is None:
        raise TopasInpError(f"{model.path or '<model>'}: dataset {dataset} is not "
                            f"a time-of-flight dataset of this file "
                            f"({sorted(model.time_of_flight, key=str)})")
    if bank.refused:
        raise TopasInpError(
            f"{model.path or '<model>'}: dataset {dataset} states "
            + "; ".join(f"`{c}` ({why})" for c, why in bank.refused)
            + ". Each is refused rather than approximated: read "
              "`model.tof_banks` for what the file states.")
    if not 0.0 < two_theta_bank_deg < 180.0:
        raise ValueError(f"two_theta_bank_deg must lie in (0, 180), got "
                         f"{two_theta_bank_deg}")
    template = ProfileTOF()
    profile = ProfileTOF(**{k: v.model_copy(update={
        "unit": getattr(template, k).unit, "min": getattr(template, k).min,
        "max": getattr(template, k).max})
        for k, v in bank.profile.items()})
    cal = bank.calibration
    # built from the bare numbers, so each constant takes TOFSource's own unit
    # and bounds (DIFC's floor among them), and only the flag is the file's
    instrument = Instrument.tof_neutron_bank(
        cal["difc"].value, two_theta_bank_deg=two_theta_bank_deg,
        difa=cal["difa"].value, tzero=cal["tzero"].value,
        difb=cal["difb"].value, profile=profile)
    src = instrument.source
    instrument = instrument.model_copy(update={"source": src.model_copy(update={
        key: getattr(src, key).model_copy(update={"vary": cal[key].vary})
        for key in ("difc", "difa", "tzero", "difb")})})
    if bank.background:
        instrument = instrument.model_copy(update={"background": BackgroundChebyshev(
            coefficients=list(bank.background))})
    factor = BARN_PER_FM2 / math.sin(math.radians(two_theta_bank_deg / 2.0))
    flat = replace(model, time_of_flight={})
    structure = _topas.to_structure(flat, dataset=dataset)
    phases = []
    for ph in structure.phases:
        s = ph.scale
        phases.append(ph.model_copy(update={"scale": s.model_copy(update={
            "value": s.value * factor,
            "min": s.min * factor if math.isfinite(s.min) else s.min,
            "max": s.max * factor if math.isfinite(s.max) else s.max})}))
    return structure.model_copy(update={"phases": phases}), instrument


# ----------------------------------------------------------------- writing

def _fmt(x: float) -> str:
    if not math.isfinite(x):
        raise ValueError(f"{x!r} cannot be written to a TOPAS `.inp`")
    return repr(float(x))


def _flagged(name: str, p: Parameter) -> str:
    return f"{'@' if p.vary else '!'}{name} {_fmt(p.value)}"


def from_tof(structure, instrument, *, data_file: str, x_range: tuple | None = None,
             tof_lam: float = 0.001, tag: str = "b0", iters: int | None = None,
             convolution_step: int | None = None,
             extra_x: tuple | None = None) -> str:
    """A ``.inp`` for one rietx time-of-flight bank, in the form TOPAS v6
    runs (an ``xdd`` with ``neutron_data``, ``TOF_LAM``, the calibration,
    ``scale_pks = D_spacing^4;`` and ``peak_type pv``, never ``fp`` or
    ``xo_Is``).

    The peak is written as TOPAS's pseudo-Voigt with its FWHM and η given as
    the TCH equations of rietx's σ²(d) and γ(d), convolved with one early and
    one late exponential whose rates are rietx's α(d) and β(d); every profile
    and calibration constant is a declared ``prm`` carrying its refine flag,
    so :func:`read_tof_banks` reads the same numbers back. The phase scale is
    S_TOPAS = S_rietx·sin θ_bank/0.01. Refused: an incident spectrum
    (``ITYP`` ≠ 0), an absorption or extinction correction, and a zero-width
    peak — none has a counterpart this writer can state.
    """
    src = instrument.source
    if getattr(src, "kind", None) != "neutron_tof":
        raise ValueError("from_tof writes a neutron time-of-flight bank only")
    if src.incident_spectrum.itype != 0:
        raise ValueError("an incident spectrum (ITYP ≠ 0) has no TOPAS "
                         "counterpart this writer can state")
    if instrument.geometry.mu_r is not None or instrument.geometry.capillary_radius_mm:
        raise ValueError("an absorption correction has no TOPAS counterpart "
                         "this writer can state")
    pr = src.profile_tof
    sig = [pr.sig0, pr.sig1, pr.sig2]
    gam = [pr.gam0, pr.gam1, pr.gam2]
    if all(p.value == 0.0 for p in sig + gam):
        raise ValueError("a zero-width peak cannot be written: TOPAS's "
                         "pseudo-Voigt needs a positive FWHM")
    sin_t = math.sin(math.radians(src.two_theta_bank_deg / 2.0))
    t = tag
    lines = [f"' Written by rietx.io.projects.topas_tof.from_tof; bank angle "
             f"2θ = {src.two_theta_bank_deg!r}° (TOPAS states none)"]
    if iters is not None:
        lines.append(f"iters {int(iters)}")
    if src.difb.value != 0.0:
        # `pk_xo` written by hand names its constants, so they are declared;
        # `TOF_x_axis_calibration` declares its own and a second declaration is
        # an error in TOPAS ("defined more than once")
        for key in ("tzero", "difc", "difa", "difb"):
            lines.append(f"prm {_flagged(f'{key}_{t}', getattr(src, key))}")
    fmt = "xye_format" if data_file.lower().endswith(".xye") else ""
    lines.append(f'xdd "{data_file}" {fmt}'.rstrip())
    lines.append("   neutron_data")
    for key in ("alpha0", "alpha1", "beta0", "beta1", "sig0", "sig1", "sig2",
                "gam0", "gam1", "gam2"):
        lines.append(f"   prm {_flagged(f'{key}_{t}', getattr(pr, key))}")
    lines.append(f"   TOF_LAM({_fmt(tof_lam)})")
    if convolution_step is not None:
        lines.append(f"   convolution_step {int(convolution_step)}")
    if x_range is not None:
        lines.append(f"   start_X {_fmt(x_range[0])}")
        lines.append(f"   finish_X {_fmt(x_range[1])}")
        left, right = extra_x if extra_x is not None else _extra_x(src, x_range)
        lines.append(f"   extra_X_left {_fmt(left)}")
        lines.append(f"   extra_X_right {_fmt(right)}")
    bkg = getattr(instrument.background, "coefficients", None)
    if bkg is None:
        raise ValueError("only a Chebyshev background has a TOPAS `bkg` "
                         "counterpart (measured: the same basis on "
                         "[start_X, finish_X])")
    if bkg:
        if len({c.vary for c in bkg}) > 1:
            raise ValueError("TOPAS's `bkg` takes one refine flag for every "
                             "coefficient (`[bkg [@] # # #...]`), and this "
                             "background frees some and holds others")
        lines.append(f"   bkg {'@ ' if bkg[0].vary else ''}"
                     + " ".join(_fmt(c.value) for c in bkg))
    if src.difb.value == 0.0:
        cal = ", ".join(_flagged(f"{key}_{t}", getattr(src, key)).replace(" ", ", ")
                        for key in ("tzero", "difc", "difa"))
        lines.append(f"   TOF_x_axis_calibration({cal})")
    else:
        lines.append(f"   pk_xo = tzero_{t} + difc_{t} D_spacing + difa_{t} "
                     f"D_spacing^2 + difb_{t} / D_spacing;")
    lines.append("   scale_pks = D_spacing^4;")
    lorentzian = any(p.value != 0.0 for p in gam)
    exps = [f"      exp_conv_const = Ln(0.001) / (alpha0_{t} + alpha1_{t} / D_spacing);",
            f"      exp_conv_const = -Ln(0.001) / (beta0_{t} + beta1_{t} / D_spacing^4);"]
    phase_text = _topas.from_structure(_scaled(structure, sin_t / BARN_PER_FM2))
    n_phase = 0
    for line in phase_text.splitlines()[1:]:
        lines.append("   " + line)
        if line.strip().startswith("scale "):
            lines.extend(["      peak_type pv",
                          *_width_lines(t, f"{t}_{n_phase}", lorentzian), *exps])
            n_phase += 1
    return "\n".join(lines) + "\n"


#: e-folds of an exponential tail rietx's frozen window keeps: −ln(1e-4), its
#: per-wing area tolerance (``model.forward_tof``'s TOF_WINDOW_AREA_TOL).
_TAIL_EFOLDS = -math.log(1e-4)


def _extra_x(src, x_range) -> tuple[float, float]:
    """How far outside ``x_range`` TOPAS must generate reflections for the
    pattern to hold what rietx's does.

    TOPAS generates a reflection only within ``extra_X_left``/``extra_X_right``
    of the range (reference: "the extra x-axis range for hkl generation",
    default 0.5), while rietx keeps one whose frozen window reaches into it —
    so a peak just below ``start_X`` sends its decay tail in on the rietx side
    and is missing on the TOPAS side (measured: 6e-3 of the maximum at the
    edge of a synthetic bank). The extra range is that window at the range's
    ends: the late tail (β) of a reflection below the start, the early tail
    (α) of one above the finish, each with six Gaussian σ.
    """
    pr = src.profile_tof
    out = []
    for x, rate in ((x_range[0], "beta"), (x_range[1], "alpha")):
        d = float(src.d_from_tof(x))
        a = pr.alpha0.value + pr.alpha1.value / d
        b = pr.beta0.value + pr.beta1.value / d ** 4
        sig2 = pr.sig0.value + pr.sig1.value * d ** 2 + pr.sig2.value * d ** 4
        gam = pr.gam0.value + pr.gam1.value * d + pr.gam2.value * d ** 2
        r = b if rate == "beta" else a
        out.append(_TAIL_EFOLDS / r + 6.0 * math.sqrt(max(sig2, 0.0)) + 10.0 * abs(gam))
    return out[0], out[1]


def _poly(terms) -> str:
    """``c₁ t₁ + c₂ t₂ …`` with each sign written once: TOPAS refuses ``+ -c``
    ("Invalid equation", measured), where this module's own evaluator would
    have read it."""
    out = ""
    for c, t in terms:
        sign = "-" if c < 0 else "+"
        mag = "" if abs(c) == 1.0 else f"{_fmt(abs(c))} "
        out += (f"{'-' if sign == '-' else ''}" if not out else f" {sign} ") + f"{mag}{t}"
    return out


def _width_lines(t: str, local: str, lorentzian: bool) -> list[str]:
    """``pv_fwhm``/``pv_lor`` as the TCH blend of σ²(d) and γ(d), in the bank's
    declared coefficients (``*_<t>``) through locals named for this phase
    (``*_<local>``) — a local belongs to its block, and two phases are two."""
    gg = (f"Sqrt(8 Ln(2) (sig0_{t} + sig1_{t} D_spacing^2 + sig2_{t} "
          f"D_spacing^4))")
    if not lorentzian:
        # γ ≡ 0 is the Gaussian shape exactly (Γ = Γ_G, η = 0), as rietx selects it
        return [f"      pv_fwhm = {gg};", "      pv_lor 0"]
    gl = f"(gam0_{t} + gam1_{t} D_spacing + gam2_{t} D_spacing^2)"
    c1, c2, c3, c4 = _TCH_GAMMA
    e1, e2, e3 = _TCH_ETA
    g, lz, fw, q = (f"gG_{local}", f"gL_{local}", f"fw_{local}", f"q_{local}")
    big = "(" + _poly(((1.0, f"{g}^5"), (c1, f"{g}^4 {lz}"), (c2, f"{g}^3 {lz}^2"),
                       (c3, f"{g}^2 {lz}^3"), (c4, f"{g} {lz}^4"),
                       (1.0, f"{lz}^5"))) + ")^0.2"
    return [f"      local !{g} = {gg};", f"      local !{lz} = {gl};",
            f"      local !{fw} = {big};", f"      local !{q} = {lz} / {fw};",
            f"      pv_fwhm = {fw};",
            f"      pv_lor = {_poly(((e1, q), (e2, f'{q}^2'), (e3, f'{q}^3')))};"]


def _scaled(structure, factor: float):
    phases = []
    for ph in structure.phases:
        if ph.extinction is not None and ph.extinction.value != 0.0:
            raise ValueError(f"phase {ph.name!r}: an extinction correction has "
                             f"no TOPAS counterpart this writer can state")
        s = ph.scale
        phases.append(ph.model_copy(update={"scale": s.model_copy(update={
            "value": s.value * factor,
            "min": s.min * factor if math.isfinite(s.min) else s.min,
            "max": s.max * factor if math.isfinite(s.max) else s.max})}))
    return structure.model_copy(update={"phases": phases})
