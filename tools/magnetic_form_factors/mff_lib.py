"""Shared pieces of the magnetic form-factor regeneration: input decks, output
readers, the radial transform, Brown's analytic form and the tail blend.

Nothing here runs a code; ``regenerate.py`` does.  The two codes are
R. D. Cowan's RCN (Mod 36.2.5, unmodified source) and GRASP2018; neither is
part of rietx.

* **RCN decks** (``rcn_deck``): the HF control card of the RCN write-up
  § II-B(1) (Cowan's sample ``in36k`` values except IREL and CORRF), one
  configuration card and, for a term-specific run, the LS-term card of
  § II-G (term energy relative to E_av in F^k, G^k).
* **RCN radial functions** (``read_tape2``): RCN writes every P_nl(r) on its
  own mesh to the unformatted file ``tape2n`` (one record per configuration,
  ``NORBPT = -9`` on the control card asks for all orbitals).  Reading that
  record needs no change to RCN.
* **GRASP2018 inputs** (``grasp_inputs``): the stdin of rnucleus,
  rcsfgenerate, rangular, rwfnestimate and rmcdhf for a single-configuration
  Dirac-Fock run, average level: EOL over every level of every J block with
  standard weights.  ``read_rwfn`` reads ``rwfn.out``.
* **Transform** (``density_transform``): the radial density splined onto a
  uniform 2e-4 bohr mesh, Simpson's rule, renormalised to 1,
  <j_n>(s) = int rho(r) j_n(4 pi s r a0) dr with a0 = 0.529177 A.  For a
  Dirac-Fock shell rho = sum_j (2j+1)(P^2 + Q^2) / sum_j (2j+1) over
  j = l -/+ 1/2 (``shell_density``).
"""

from __future__ import annotations

import csv
import struct
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.special import spherical_jn

HERE = Path(__file__).resolve().parent
CURVES_CSV = HERE / "curves.csv"
ERRORS_CSV = HERE / "brown_fit_errors.csv"

A0 = 0.529177  # bohr in angstrom
S = np.round(np.arange(601) * 0.01, 2)  # s = 0-6 at 0.01 (the data file's grid)
S_D32 = np.round(np.arange(1201) * 0.005, 3)  # the ten D32 tables, 0-6 at 0.005
S_END = {"3d": 1.5, "4d": 1.5, "4f": 1.2, "5f": 1.5}
BLEND_WIDTH = 0.2

#: Brown's fitting grid per family (ITC Vol. C sec. 4.4.5, p. 461): 3d/4d at
#: 0.05 to 1.5; rare earths at 0.05 to 0.5 then 0.1 to 1.2 (Freeman & Desclaux
#: 1979 Table 7); actinides the same pattern to 1.5 (Desclaux & Freeman 1978).
BROWN_GRID = {
    "3d": np.round(np.arange(31) * 0.05, 2),
    "4d": np.round(np.arange(31) * 0.05, 2),
    "4f": np.round(np.r_[np.arange(10) * 0.05, 0.5 + np.arange(8) * 0.1], 2),
    "5f": np.round(np.r_[np.arange(10) * 0.05, 0.5 + np.arange(11) * 0.1], 2),
}

ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII"}
SYMBOL = {21: "Sc", 22: "Ti", 23: "V", 24: "Cr", 25: "Mn", 26: "Fe", 27: "Co",
          28: "Ni", 29: "Cu", 39: "Y", 40: "Zr", 41: "Nb", 42: "Mo", 43: "Tc",
          44: "Ru", 45: "Rh", 46: "Pd", 58: "Ce", 59: "Pr", 60: "Nd", 62: "Sm",
          63: "Eu", 64: "Gd", 65: "Tb", 66: "Dy", 67: "Ho", 68: "Er", 69: "Tm",
          70: "Yb", 92: "U", 93: "Np", 94: "Pu", 95: "Am"}


def load_curves(path: Path = CURVES_CSV) -> dict[str, dict]:
    """curves.csv -> {key: row}, in file order."""
    with open(path, newline="") as fh:
        return {r["key"]: r for r in csv.DictReader(fh)}


# ------------------------------------------------------------------ RCN deck

def control_card(irel: int, corrf: float) -> str:
    """HF control card (IHF = 2) in the columns of the RCN write-up
    § II-B(1); Cowan's sample in36k values except IREL and CORRF."""
    s = [" "] * 75

    def put(a: int, b: int, text: str) -> None:
        assert len(text) <= b - a + 1, (text, a, b)
        s[a - 1:b] = list(text.rjust(b - a + 1))

    put(1, 1, "2")            # ITPOW: print <r^m>
    put(4, 5, "-9")           # NORBPT: write every orbital to tape2n
    put(9, 10, "2")           # IHF = 2: Hartree-Fock
    put(14, 15, "10")         # TOLSTB
    put(16, 20, "0.2")        # TOLKM2
    put(21, 30, "5.e-08")     # TOLEND
    put(31, 40, "1.e-11")     # THRESH
    put(41, 42, "-2")         # KUTD
    put(46, 46, str(irel))    # IREL: 0 = HF, 1 = HFR (mass-velocity + Darwin)
    put(47, 48, "90")         # MAXIT
    put(51, 55, "1.0")        # EXF10
    put(56, 60, "0.65")       # EXFM1
    put(61, 65, "0.0")        # EMX
    put(66, 70, f"{corrf:.1f}")  # CORRF
    put(71, 75, "-6")         # IW6
    return "".join(s)


#: Hund term of d^n relative to E_av, (name, F^2 coefficient, F^4 coefficient)
#: (Racah forms minus E_av(d^n); particle-hole conjugates share them).
_D_HUND = {2: ("3F", -58 / 441, 5 / 441), 8: ("3F", -58 / 441, 5 / 441),
           3: ("4F", -31 / 147, -10 / 147), 7: ("4F", -31 / 147, -10 / 147),
           4: ("5D", -5 / 21, -5 / 21), 6: ("5D", -5 / 21, -5 / 21),
           5: ("6S", -25 / 63, -25 / 63)}
#: Non-Hund d^2 (= d^8) terms relative to E_av.
_D2_OTHER = {"1D": (-13 / 441, 50 / 441), "3P": (77 / 441, -70 / 441),
             "1G": (50 / 441, 15 / 441)}
_S_CORE = {1: 0.5, 9: 0.5, 2: 1.0, 8: 1.0, 3: 1.5, 7: 1.5, 4: 2.0, 6: 2.0, 5: 2.5}


def term_card(orbitals: str, shell: str, term: str):
    """(name, [(coef, 'F'|'G', k, nl, nl), ...]) for an LS-term run, or None
    for the configuration average (``term == 'avg'``).

    Hund term of the open d shell; with one electron in the outer s shell,
    the high-spin d^n s term (d^n card plus -(S_core/5) G^2(d,s); for the
    single-term d^1 and d^9 shells the G^2 entry alone, d^9 s 3D); a non-Hund
    d^2/d^8 term by name.  The name the card produces must equal ``term``.
    """
    if term == "avg":
        return None
    occ = {o[:2]: int(o[2:]) for o in orbitals.split()}
    nd = occ[shell]
    if term in _D2_OTHER and nd in (2, 8):
        f2, f4 = _D2_OTHER[term]
        return term, [(f2, "F", 2, shell, shell), (f4, "F", 4, shell, shell)]
    s1 = [k for k, v in occ.items() if k.endswith("s") and v == 1]
    if nd in (1, 9) and s1:  # d1, d9: one term, 2D at E_av, so no F^k card; only the d-s coupling
        name, ints = "2D", []
    else:
        name, f2, f4 = _D_HUND[nd]
        ints = [(f2, "F", 2, shell, shell), (f4, "F", 4, shell, shell)]
    if s1:
        s_core = _S_CORE[nd]
        name = f"{int(2 * (s_core + 0.5) + 1)}{name[1]}"
        ints.append((-s_core / 5.0, "G", 2, shell, s1[0]))
    if name != term:
        raise ValueError(f"{orbitals}: card gives term {name}, curves.csv says {term}")
    return name, ints


def config_card(z: int, q: int, orbitals: str, term) -> str:
    """Configuration card, followed by the LS-term card(s) of § II-G when
    ``term`` is given."""
    label = f"{SYMBOL[z]} {ROMAN[q + 1]}"
    card = f"{' ' if term is None else 1}{z:4d}   {q + 1:2d}{label:<15}   {orbitals}"
    if term is None:
        return card
    name, ints = term

    def ent(c, fg, k, a, b):
        cs = f"{c:9.6f}"
        assert len(cs) == 9, cs
        return f"{cs}{fg}{k}({a:>3},{b:>3})"

    lines = [card, f"{label[:7]:<7}{name:<3}{len(ints):5d}     "
             + "".join(ent(*x) for x in ints[:3])]
    rest = ints[3:]
    while rest:
        lines.append("".join(ent(*x) for x in rest[:4]))
        rest = rest[4:]
    return "\n".join(lines)


def rcn_deck(row: dict) -> str:
    """The whole RCN input file (in36) for one curves.csv row."""
    term = term_card(row["orbitals"], row["shell"], row["term"])
    cards = [control_card(int(row["irel"]), float(row["corrf"])),
             config_card(int(row["Z"]), int(row["q"]), row["orbitals"], term),
             "   -1", ""]
    return "\n".join(cards)


# ------------------------------------------------------------------ RCN output

_KO, _KMSH = 20, 1801  # RCN's array bounds (parameter statement)


def _records(path: Path):
    """Fortran unformatted sequential records (4-byte little-endian markers)."""
    b = Path(path).read_bytes()
    i = 0
    while i < len(b):
        (n,) = struct.unpack("<i", b[i:i + 4])
        yield b[i + 4:i + 4 + n]
        (m,) = struct.unpack("<i", b[i + 4 + n:i + 8 + n])
        if m != n:
            raise ValueError(f"{path}: record marker mismatch")
        i += 8 + n


def read_tape2(path: Path) -> list[dict]:
    """RCN's tape2n: per configuration, the record written at the end of the
    SCF (nnn, l, wwnl, ncspvs, vprm, conf, nconf, iz, z, ion, irel, hxid, mesh,
    c, idb, exf, corrf, kut, npar, nlbcd, nnlz, nkkk, ee, ee8, norb, r, ru,
    pnl(1:kmsh, ns:ncspvs), iw6).  Returns dicts with conf, iz, ion, irel,
    r (bohr) and {orbital label: P(r)} on RCN's mesh."""
    out = []
    for rec in _records(path):
        o = 0

        def take(fmt, rec=rec):
            nonlocal o
            v = struct.unpack_from("<" + fmt, rec, o)
            o += struct.calcsize("<" + fmt)
            return v

        take(f"{_KO}i")
        take(f"{_KO}i")
        take(f"{_KO}d")
        (ncspvs,) = take("i")
        take("50d")
        conf = rec[o:o + 18].decode()
        o += 18
        _, iz = take("2i")
        take("d")
        ion, irel = take("2i")
        take("d")
        (mesh,) = take("i")
        take("d")
        take("i")
        take("2d")
        take("2i")
        labels = rec[o:o + 8 * _KO].decode()
        o += 8 * _KO
        take(f"{2 * _KO}i")
        take(f"{_KO + 1}d")
        (norb,) = take("i")
        r = np.frombuffer(rec, "<f8", _KMSH, o)[:mesh].copy()
        o += 16 * _KMSH  # r, ru
        p = np.frombuffer(rec, "<f8", _KMSH * norb, o).reshape(norb, _KMSH)
        o += 8 * _KMSH * norb
        take("i")
        if o != len(rec) or norb != ncspvs:
            raise ValueError(f"{path}: unexpected tape2n record layout")
        names = [labels[8 * k:8 * k + 8].strip() for k in range(ncspvs)]
        out.append(dict(conf=conf.strip(), iz=iz, ion=ion, irel=irel, r=r,
                        p={nm: p[k, :mesh].copy() for k, nm in enumerate(names)}))
    return out


# ------------------------------------------------------------------ GRASP2018

def grasp_spec(row: dict) -> dict:
    """Core, configuration and active set of a single open 4f or 5f shell."""
    z, q = int(row["Z"]), int(row["q"])
    if z < 90:  # [Kr]4d10 5s2 5p6 4f^n
        n = z - 54 - q
        return dict(n=n, core=5, conf=f"4f({n},i)", active="5s,5p,4d,4f", nl=(4, 3))
    n = z - 86 - q  # [Xe]4f14 5d10 6s2 6p6 5f^n
    return dict(n=n, core=6, conf=f"5f({n},i)", active="6s,6p,5d,5f", nl=(5, 3))


def j2_range(n: int, ell: int = 3) -> tuple[int, int]:
    """(2J_min, 2J_max) of l^n (l = ``ell``), by M_J state counting; every 2J between
    them (in steps of 2) must occur."""
    mj2 = [m for j2 in (2 * ell - 1, 2 * ell + 1) for m in range(-j2, j2 + 1, 2)]
    cnt = Counter(sum(c) for c in combinations(mj2, n))
    js = [m for m in sorted(cnt) if m >= 0 and cnt[m] - cnt.get(m + 2, 0) > 0]
    if js != list(range(js[0], js[-1] + 1, 2)):
        raise ValueError(f"l^{n}: J values not contiguous")
    return js[0], js[-1]


def grasp_inputs(row: dict) -> dict[str, str]:
    """{program: stdin} for the five GRASP2018 programs, in run order.

    ``row['blocks']`` holds the CSF count of each J block (rcsfgenerate's
    output, checked by the driver); ``row['start']`` is ``TF`` (Thomas-Fermi
    estimate) or the key of a converged neighbour whose rwfn.out is copied in
    as start.w."""
    d = grasp_spec(row)
    lo, hi = j2_range(d["n"])
    a = int(row["A"])
    sizes = [int(x) for x in row["blocks"].split()]
    lev = "".join(f"1-{n}\n" if n > 1 else "1\n" for n in sizes)
    weights = "5\n" if sum(sizes) > 1 else ""
    est = "y\n2\n*\n" if row["start"] == "TF" else "y\n1\nstart.w\n*\n"
    return {
        "rnucleus": f"{row['Z']}\n{a}\nn\n{float(a)}\n0\n0\n0\n",
        "rcsfgenerate": f"*\n{d['core']}\n{d['conf']}\n\n{d['active']}\n{lo},{hi}\n0\nn\n",
        "rangular": "y\n",
        "rwfnestimate": est,
        "rmcdhf": f"y\n{lev}{weights}*\n*\n200\n",
    }


def block_sizes(rcsf: Path) -> list[int]:
    """CSFs per J block of an rcsf file (3 lines per CSF, ' *' separators)."""
    sizes, cur = [], 0
    for ln in Path(rcsf).read_text().splitlines()[5:]:
        if ln.strip() == "*":
            sizes.append(cur // 3)
            cur = 0
        elif ln.strip():
            cur += 1
    sizes.append(cur // 3)
    return sizes


def read_rwfn(path: Path) -> list[dict]:
    """GRASP's rwfn.out: 'G92RWF', then per orbital (n, kappa, e, mf),
    (p0, P(1:mf), Q(1:mf)), r(1:mf)."""
    recs = list(_records(path))
    if recs[0][:6] != b"G92RWF":
        raise ValueError(f"{path}: not a GRASP radial wavefunction file")
    out = []
    for k in range(1, len(recs), 3):
        n, kap, _, mf = struct.unpack("<iidi", recs[k])
        arr = np.frombuffer(recs[k + 1], dtype="<f8")
        r = np.frombuffer(recs[k + 2], dtype="<f8")
        out.append(dict(n=n, kappa=kap, l=kap if kap > 0 else -kap - 1,
                        j2=2 * abs(kap) - 1, r=r.copy(), p=arr[1:1 + mf].copy(),
                        q=arr[1 + mf:].copy()))
    return out


# ------------------------------------------------------------------ transform

def simpson_w(rr: np.ndarray) -> np.ndarray:
    assert rr.size % 2 == 1
    w = np.full(rr.size, 1.0)
    w[1:-1:2], w[2:-1:2] = 4.0, 2.0
    return w * (rr[1] - rr[0]) / 3.0


def fine_radial(r, p, dr=2e-4, tail=1e-14):
    """P(r) splined from the code's mesh onto a uniform odd mesh from 0 to two
    mesh points past the last P^2 > tail."""
    keep = np.concatenate([[True], np.diff(r) > 0])
    r, p = r[keep], p[keep]
    big = np.nonzero(p * p > tail)[0]
    rmax = r[min(big[-1] + 2, len(r) - 1)]
    rr = np.arange(0.0, rmax + dr, dr)
    if rr.size % 2 == 0:
        rr = rr[:-1]
    pp = CubicSpline(r, p)(rr)
    pp[0] = 0.0
    return rr, pp


def shell_density(spinors: list[dict], n: int, ell: int, dr=2e-4, tail=1e-14):
    """(2j+1)-weighted P^2 + Q^2 of shell nl over j = l -/+ 1/2, on a uniform
    odd mesh; normalised by the weight sum."""
    sp = [s for s in spinors if s["n"] == n and s["l"] == ell]
    rmax = 0.0
    for s in sp:
        big = np.nonzero(s["p"] ** 2 + s["q"] ** 2 > tail)[0]
        rmax = max(rmax, s["r"][min(big[-1] + 2, len(s["r"]) - 1)])
    rr = np.arange(0.0, rmax + dr, dr)
    if rr.size % 2 == 0:
        rr = rr[:-1]
    rho, wsum = np.zeros_like(rr), 0.0
    for s in sp:
        keep = np.concatenate([[True], np.diff(s["r"]) > 0])
        r, p, q = s["r"][keep], s["p"][keep], s["q"][keep]
        m = r <= rmax * 1.5 + 1.0
        pp, qq = CubicSpline(r[m], p[m])(rr), CubicSpline(r[m], q[m])(rr)
        pp[0] = qq[0] = 0.0
        rho += (s["j2"] + 1.0) * (pp * pp + qq * qq)
        wsum += s["j2"] + 1.0
    return rr, rho / wsum


def density_transform(rr, rho, s=S, ns=(0, 2, 4), chunk=40) -> dict:
    """{n: <j_n>(s)} = int rho(r) j_n(4 pi s r a0) dr (Simpson, rho
    renormalised to 1), plus 'norm_raw'."""
    w = simpson_w(rr)
    norm = float(np.sum(w * rho))
    p2w = rho / norm * w
    out = {"norm_raw": norm}
    for n in ns:
        out[n] = np.empty(s.size)
    for i in range(0, s.size, chunk):
        x = 4.0 * np.pi * np.outer(s[i:i + chunk], rr * A0)
        for n in ns:
            with np.errstate(all="ignore"):  # spurious FP flags from some BLAS
                out[n][i:i + chunk] = spherical_jn(n, x) @ p2w
    for n in ns:
        if not np.all(np.isfinite(out[n])):
            raise FloatingPointError(f"<j{n}> not finite")
    return out


# ------------------------------------------------------------------ Brown, blend

def brown7(coef, s, order: int):
    """Brown's form A e^{-a s^2} + B e^{-b s^2} + C e^{-c s^2} + D, times s^2
    for <j2> and higher."""
    A, a, B, b, C, c, D = coef
    s2 = np.asarray(s) ** 2
    v = A * np.exp(-a * s2) + B * np.exp(-b * s2) + C * np.exp(-c * s2) + D
    return v * s2 if order > 0 else v


def smoothstep(t):
    """C2 quintic 10t^3 - 15t^4 + 6t^5 on [0, 1]."""
    t = np.clip(t, 0.0, 1.0)
    return t * t * t * (t * (6.0 * t - 15.0) + 10.0)


def blend(s, fit, tail, s_end, width=BLEND_WIDTH):
    """Brown's fit up to s_end, the computed curve past s_end + width, and
    (1 - w) fit + w tail between, w = smoothstep((s - s_end) / width)."""
    w = smoothstep((np.asarray(s) - s_end) / width)
    return (1.0 - w) * np.asarray(fit) + w * np.asarray(tail)


def family_of(label: str) -> str:
    el = label.rstrip("+0123456789")
    if el in ("U", "Np", "Pu", "Am"):
        return "5f"
    if el in ("Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd"):
        return "4d"
    if el in ("Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu"):
        return "3d"
    return "4f"


def read_long(paths) -> dict[str, dict[str, np.ndarray]]:
    """Long CSVs (label, order, s, value, ...) on s = 0-6 / 0.01 ->
    {label: {order: values}}."""
    acc: dict = {}
    for path in paths:
        with open(path, newline="") as fh:
            for r in csv.DictReader(fh):
                acc.setdefault(r["label"], {}).setdefault(r["order"], []).append(
                    (round(float(r["s"]) * 100), float(r["value"])))
    out = {}
    for lab, orders in acc.items():
        out[lab] = {}
        for o, pts in orders.items():
            pts.sort()
            if [k for k, _ in pts] != list(range(601)):
                raise ValueError(f"{lab} {o}: not on s = 0-6 at 0.01")
            out[lab][o] = np.array([v for _, v in pts])
    return out
