//! The model kernels of rietx (WP-1940, from WP-1939's spike).  numba
//! compiled them until WP-1940, from `rietx/model/_kernels_numba.py`, and
//! these matched it bit for bit on all five wheel platforms.
//!
//! `rietx/model/compiled.py` owns the loading, the fallback and every rule
//! about when these run; read its docstring first.  What is here is only the
//! arithmetic, and this header is its contract.  The signatures are the ones
//! `compiled.py` calls, positionally.
//!
//! **Every expression is a transcription, not a derivation.**  Each one
//! mirrors, operation for operation and association for association, the
//! numpy expression it replaces in `model/profiles/pseudovoigt.py` and
//! `model/forward.py`.  Where the two profile spellings differ they differ in
//! exactly one place, the Gaussian exponent: `-4ln2·(x/Γ)²` in the forward
//! against `((-4ln2)·u)·u` in the derivative bases.  That difference is the
//! whole of the `spell` argument.  The Lorentzian is common to both, because
//! `(4·u)·u` and `4·(u·u)` are bit-equal: multiplying by a power of two is
//! exact.
//!
//! So the review question for any edit here is not "is this the right
//! formula" but "is this the same rounding as the numpy line it copies".
//! Rewriting `a * b * c` as `a * (b * c)` is a real change, and
//! `tests/test_compiled_kernels.py` is what says so.  rustc never contracts a
//! multiply and an add into one fused operation, so the source order is the
//! rounding order.
//!
//! Two shapes are load-bearing, and both were measured (WP-1939's file):
//!
//! - **Outputs are raw pointers, not `PyReadwriteArray`.**  `compiled._spread`
//!   calls one kernel from several threads on the *same* output array with
//!   disjoint row ranges, and rust-numpy's borrow tracker refuses a second
//!   writable borrow of an array while the first is live.  Disjoint rows make
//!   the writes race-free; a pointer says so instead of handing two threads
//!   aliasing `&mut` slices.
//! - **Each loop is a free function taking its inputs as slice arguments and
//!   its outputs as pointers by value.**  Written as a closure over captured
//!   references, every store through an `f64` pointer could (Rust having no
//!   type-based alias analysis) have moved a captured slice's pointer, so LLVM
//!   reloaded them each iteration: the scatter ran at 0.59× numba that way.
//!
//! **Every argument is checked before the GIL is released**, where numba
//! trusted `compiled.py`.  The checks are what make the raw writes sound, so
//! each binding runs all of them and a refusal is a `ValueError` naming the
//! argument:
//!
//! - an output plane shares no byte with another output or with any input,
//!   because a raw write into memory a live slice covers is undefined
//!   behaviour (`disjoint`);
//! - every plane is C-contiguous and has the shape its loop indexes it by:
//!   the outputs `x`'s, the node planes `phi`'s (`pl`, `same_shape`);
//! - every row index and window width the call touches is in range before the
//!   loops convert it with `as usize`, which would wrap a negative one
//!   (`check_rows`, `check_windows`);
//! - no row appears twice in `rows`, because `compiled._spread` hands disjoint
//!   ranges of one `rows` to concurrent calls, and a repeated row would be
//!   written by two threads at once (`check_rows`).
//!
//! The loops keep their slice bounds checks too; WP-1939 measured no speed in
//! removing them.

use numpy::{
    Element, PyArray1, PyArray2, PyArrayMethods, PyReadonlyArray1, PyReadonlyArray2,
    PyUntypedArrayMethods,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::f64::consts::{LN_2, PI};

const K4LN2: f64 = 4.0 * LN_2;

/// The kernel interface number: the crate's major version, so rietx's
/// `rietx-kernels>=N,<N+1` pin and this integer cannot disagree.
const KERNEL_ABI: u32 = match u32::from_str_radix(env!("CARGO_PKG_VERSION_MAJOR"), 10) {
    Ok(v) => v,
    Err(_) => panic!("the crate's major version is not an integer"),
};

/// `compiled.SPELL_FORWARD` and `compiled.SPELL_BASIS`.
const SPELLS: [i64; 2] = [0, 1];

fn err<T>(msg: impl Into<String>) -> PyResult<T> {
    Err(PyValueError::new_err(msg.into()))
}

// --- the checks ----------------------------------------------------------

/// A raw output pointer that may cross into `Python::detach`.
#[derive(Clone, Copy)]
struct P(*mut f64);
unsafe impl Send for P {}
unsafe impl Sync for P {}
impl P {
    /// a method, so a closure captures the Send wrapper and not its field
    fn get(self) -> *mut f64 {
        self.0
    }
}

/// The bytes `[start, end)` one contiguous buffer occupies.
type Span = (usize, usize);

fn span<T>(s: &[T]) -> Span {
    let a = s.as_ptr() as usize;
    (a, a + std::mem::size_of_val(s))
}

/// Do two buffers share a byte?  An empty one shares none.
fn overlap(a: Span, b: Span) -> bool {
    a.0 < a.1 && b.0 < b.1 && a.0 < b.1 && b.0 < a.1
}

/// Refuse an output sharing memory with another output or with an input.
fn disjoint(outs: &[Span], ins: &[Span]) -> PyResult<()> {
    for (i, &a) in outs.iter().enumerate() {
        if outs[i + 1..].iter().any(|&b| overlap(a, b)) {
            return err("two output planes share memory");
        }
        if ins.iter().any(|&b| overlap(a, b)) {
            return err("an output plane shares memory with an input");
        }
    }
    Ok(())
}

/// An output plane as a raw pointer and its span, checked as numba and
/// Cython checked one: C-contiguous, writeable, and `x`'s shape.  The loops
/// write through the pointer at `x`'s indices, and `x`'s slices are
/// bounds-checked, so the shape check is what keeps every write inside it.
fn out2(name: &str, a: &Bound<'_, PyArray2<f64>>, like: [usize; 2]) -> PyResult<(P, Span)> {
    if !a.is_c_contiguous() {
        return err(format!("{name} must be C-contiguous"));
    }
    if unsafe { (*a.as_array_ptr()).flags } & numpy::npyffi::NPY_ARRAY_WRITEABLE == 0 {
        return err(format!("{name} must be writeable"));
    }
    if a.shape() != like {
        return err(format!("{name} has shape {:?}, x has {like:?}", a.shape()));
    }
    let p = a.data();
    Ok((P(p), (p as usize, p as usize + a.len() * size_of::<f64>())))
}

fn sl<'a, T: Element>(a: &'a PyReadonlyArray1<'_, T>) -> PyResult<&'a [T]> {
    a.as_slice().map_err(|e| PyValueError::new_err(e.to_string()))
}

/// A read-only plane as (slice, shape).  C-contiguous only: rust-numpy's
/// `as_slice` also accepts a Fortran-ordered array, which the loops'
/// `row * width + column` would read transposed.
fn pl<'a>(name: &str, a: &'a PyReadonlyArray2<'_, f64>) -> PyResult<(&'a [f64], [usize; 2])> {
    if !a.is_c_contiguous() {
        return err(format!("{name} must be C-contiguous"));
    }
    let s = a.shape();
    Ok((a.as_slice().map_err(|e| PyValueError::new_err(e.to_string()))?, [s[0], s[1]]))
}

/// Each node plane has `phi`'s shape.  The loops index all of them with
/// `phi`'s width, where numba read each with its own.
fn same_shape(phi: [usize; 2], planes: &[(&str, [usize; 2])]) -> PyResult<()> {
    for (name, s) in planes {
        if *s != phi {
            return err(format!("{name} has shape {s:?}, phi has {phi:?}"));
        }
    }
    Ok(())
}

/// Each array has one entry per row of the reference, `of` with `n` rows.
fn per_row(n: usize, of: &str, arrays: &[(&str, usize)]) -> PyResult<()> {
    for (name, len) in arrays {
        if *len != n {
            return err(format!("{name} has {len} rows or entries, {of} has {n}"));
        }
    }
    Ok(())
}

fn index(v: i64, below: usize, what: &str) -> PyResult<usize> {
    match usize::try_from(v) {
        Ok(u) if u < below => Ok(u),
        _ => err(format!("{what} {v} outside 0..{below}")),
    }
}

/// The rows a call may touch: each a row of `x` (`n` rows, `w` wide), each
/// window inside it, and none listed twice.  The whole of `rows` is checked,
/// never only `rows[lo..hi]`: concurrent calls share one `rows` with
/// disjoint ranges, and a row repeated across two ranges is a data race no
/// single range can see.  `width` was checked by `per_row`.
fn check_rows(rows: &[i64], width: &[i64], lo: usize, hi: usize, n: usize, w: usize)
              -> PyResult<()> {
    if lo > hi || hi > rows.len() {
        return err(format!("row range {lo}..{hi} outside 0..{}", rows.len()));
    }
    let mut seen = vec![false; n];
    for &j in rows {
        let u = index(j, n, "row")?;
        if std::mem::replace(&mut seen[u], true) {
            return err(format!("row {j} appears twice in rows"));
        }
        index(width[u], w + 1, "window width")?;
    }
    Ok(())
}

/// The scatter's windows: `i0[r]..i1[r]` inside `y` and no wider than any
/// plane it reads.
fn check_windows(i0: &[i64], i1: &[i64], n_y: usize, w_min: usize) -> PyResult<()> {
    for (&a, &b) in i0.iter().zip(i1) {
        let a = index(a, n_y + 1, "window start")?;
        let b = index(b, n_y + 1, "window end")?;
        if b < a || b - a > w_min {
            return err(format!("window {a}..{b} is not inside y or a plane"));
        }
    }
    Ok(())
}

fn check_spell(spell: i64) -> PyResult<()> {
    if SPELLS.contains(&spell) { Ok(()) } else { err(format!("spell {spell} is not 0 or 1")) }
}

// --- the loops ---------------------------------------------------------

#[allow(clippy::too_many_arguments)]
fn accum_loop(y: &mut [f64], i0: &[i64], i1: &[i64], c0: &[f64], p0: &[f64], w0: usize,
              c1: &[f64], p1: &[f64], w1: usize, c2: &[f64], p2: &[f64], w2: usize,
              c3: &[f64], p3: &[f64], w3: usize, n_terms: i64) {
    for r in 0..i0.len() {
        let b = i0[r] as usize;
        let w = (i1[r] - i0[r]) as usize;
        let ys = &mut y[b..b + w];
        match n_terms {
            1 => {
                let a0 = c0[r];
                let q0 = &p0[r * w0..r * w0 + w];
                for p in 0..w {
                    ys[p] += a0 * q0[p];
                }
            }
            2 => {
                let (a0, a1) = (c0[r], c1[r]);
                let (q0, q1) = (&p0[r * w0..r * w0 + w], &p1[r * w1..r * w1 + w]);
                for p in 0..w {
                    ys[p] += a0 * q0[p];
                    ys[p] += a1 * q1[p];
                }
            }
            3 => {
                let (a0, a1, a2) = (c0[r], c1[r], c2[r]);
                let (q0, q1, q2) = (&p0[r * w0..r * w0 + w], &p1[r * w1..r * w1 + w],
                                    &p2[r * w2..r * w2 + w]);
                for p in 0..w {
                    ys[p] += a0 * q0[p];
                    ys[p] += a1 * q1[p];
                    ys[p] += a2 * q2[p];
                }
            }
            _ => {
                let (a0, a1, a2, a3) = (c0[r], c1[r], c2[r], c3[r]);
                let (q0, q1, q2, q3) = (&p0[r * w0..r * w0 + w], &p1[r * w1..r * w1 + w],
                                        &p2[r * w2..r * w2 + w], &p3[r * w3..r * w3 + w]);
                for p in 0..w {
                    ys[p] += a0 * q0[p];
                    ys[p] += a1 * q1[p];
                    ys[p] += a2 * q2[p];
                    ys[p] += a3 * q3[p];
                }
            }
        }
    }
}

#[allow(clippy::too_many_arguments)]
unsafe fn omega_sym_loop(out: *mut f64, ow: usize, x: &[f64], xw: usize, rows: &[i64],
                         pos: &[f64], w1: &[f64], w2: &[f64], width: &[i64], spell: i64,
                         lo: usize, hi: usize) {
    let srp = (LN_2 / PI).sqrt();
    for r in lo..hi {
        let j = rows[r] as usize;
        let (g, e, p) = (w1[j], w2[j], pos[j]);
        let n = width[j] as usize;
        let xs = &x[j * xw..j * xw + n];
        let o = unsafe { out.add(j * ow) };
        for c in 0..n {
            let u = (xs[c] - p) / g;
            let uu = u * u;
            let ex = if spell == 0 { -K4LN2 * uu } else { (-K4LN2 * u) * u };
            let lor = (2.0 / (PI * g)) / (1.0 + 4.0 * uu);
            let gau = (2.0 / g) * srp * ex.exp();
            unsafe { *o.add(c) = e * lor + (1.0 - e) * gau };
        }
    }
}

#[allow(clippy::too_many_arguments)]
unsafe fn omega_fcj_loop(out: *mut f64, ow: usize, x: &[f64], xw: usize, rows: &[i64],
                         w1: &[f64], w2: &[f64], width: &[i64], phi: &[f64], om: &[f64],
                         nn: usize, spell: i64, lo: usize, hi: usize) {
    let srp = (LN_2 / PI).sqrt();
    for r in lo..hi {
        let j = rows[r] as usize;
        let (g, e) = (w1[j], w2[j]);
        let n = width[j] as usize;
        let xs = &x[j * xw..j * xw + n];
        let (ph, wt) = (&phi[r * nn..r * nn + nn], &om[r * nn..r * nn + nn]);
        let o = unsafe { out.add(j * ow) };
        for c in 0..n {
            let xv = xs[c];
            let mut s = 0.0;
            for m in 0..nn {
                let u = (xv - ph[m]) / g;
                let uu = u * u;
                let ex = if spell == 0 { -K4LN2 * uu } else { (-K4LN2 * u) * u };
                let lor = (2.0 / (PI * g)) / (1.0 + 4.0 * uu);
                let gau = (2.0 / g) * srp * ex.exp();
                s += wt[m] * (e * lor + (1.0 - e) * gau);
            }
            unsafe { *o.add(c) = s };
        }
    }
}

#[allow(clippy::too_many_arguments)]
unsafe fn bases_sym_loop(o_om: *mut f64, o_dp: *mut f64, o_dg: *mut f64, o_de: *mut f64,
                         ow: usize, x: &[f64], xw: usize, rows: &[i64], pos: &[f64],
                         w1: &[f64], w2: &[f64], width: &[i64], lo: usize, hi: usize) {
    let srp = (LN_2 / PI).sqrt();
    for r in lo..hi {
        let j = rows[r] as usize;
        let (g, e, p) = (w1[j], w2[j], pos[j]);
        let n = width[j] as usize;
        let xs = &x[j * xw..j * xw + n];
        let k = j * ow;
        for c in 0..n {
            let u = (xs[c] - p) / g;
            let den = 1.0 + 4.0 * u * u;
            let lor = (2.0 / (PI * g)) / den;
            let gau = (2.0 / g) * srp * ((-K4LN2 * u) * u).exp();
            let dl_dx = -lor * (8.0 * u / g) / den;
            let dg_dx = -gau * (2.0 * K4LN2 * u / g);
            let dl_dg = (lor / g) * (8.0 * u * u / den - 1.0);
            let dg_dg = (gau / g) * (2.0 * K4LN2 * u * u - 1.0);
            unsafe {
                *o_om.add(k + c) = e * lor + (1.0 - e) * gau;
                *o_dp.add(k + c) = -(e * dl_dx + (1.0 - e) * dg_dx);
                *o_dg.add(k + c) = e * dl_dg + (1.0 - e) * dg_dg;
                *o_de.add(k + c) = lor - gau;
            }
        }
    }
}

#[allow(clippy::too_many_arguments)]
unsafe fn bases_fcj_loop(o: [*mut f64; 6], ow: usize, x: &[f64], xw: usize, rows: &[i64],
                         w1: &[f64], w2: &[f64], width: &[i64], phi: &[f64], om: &[f64],
                         dphi: &[f64], dom: &[f64], dphi_sl: &[f64], dom_sl: &[f64],
                         dphi_hl: &[f64], dom_hl: &[f64], nn: usize, has_ax: bool,
                         lo: usize, hi: usize) {
    let [o_om, o_dp, o_dg, o_de, o_sl, o_hl] = o;
    let srp = (LN_2 / PI).sqrt();
    for r in lo..hi {
        let j = rows[r] as usize;
        let (g, e) = (w1[j], w2[j]);
        let n = width[j] as usize;
        let xs = &x[j * xw..j * xw + n];
        let b = r * nn;
        let (ph, wt, dph, dw) = (&phi[b..b + nn], &om[b..b + nn], &dphi[b..b + nn],
                                 &dom[b..b + nn]);
        let k = j * ow;
        for c in 0..n {
            let xv = xs[c];
            let (mut s_om, mut s_dg, mut s_de) = (0.0, 0.0, 0.0);
            let (mut a_pos, mut b_pos) = (0.0, 0.0);
            let (mut a_sl, mut b_sl, mut a_hl, mut b_hl) = (0.0, 0.0, 0.0, 0.0);
            for m in 0..nn {
                let u = (xv - ph[m]) / g;
                let den = 1.0 + 4.0 * u * u;
                let lor = (2.0 / (PI * g)) / den;
                let gau = (2.0 / g) * srp * ((-K4LN2 * u) * u).exp();
                let pv = e * lor + (1.0 - e) * gau;
                let dl_dx = -lor * (8.0 * u / g) / den;
                let dg_dx = -gau * (2.0 * K4LN2 * u / g);
                let ddx = e * dl_dx + (1.0 - e) * dg_dx;
                let dl_dg = (lor / g) * (8.0 * u * u / den - 1.0);
                let dg_dg = (gau / g) * (2.0 * K4LN2 * u * u - 1.0);
                let w = wt[m];
                s_om += w * pv;
                s_dg += w * (e * dl_dg + (1.0 - e) * dg_dg);
                s_de += w * (lor - gau);
                a_pos += dw[m] * pv;
                b_pos += (w * dph[m]) * ddx;
                if has_ax {
                    a_sl += dom_sl[b + m] * pv;
                    b_sl += (w * dphi_sl[b + m]) * ddx;
                    a_hl += dom_hl[b + m] * pv;
                    b_hl += (w * dphi_hl[b + m]) * ddx;
                }
            }
            unsafe {
                *o_om.add(k + c) = s_om;
                *o_dg.add(k + c) = s_dg;
                *o_de.add(k + c) = s_de;
                *o_dp.add(k + c) = a_pos - b_pos;
                if has_ax {
                    *o_sl.add(k + c) = a_sl - b_sl;
                    *o_hl.add(k + c) = a_hl - b_hl;
                }
            }
        }
    }
}

// --- the bindings ------------------------------------------------------

/// The bit-identical scatter, `compiled.accumulate`'s kernel.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn accum(
    py: Python<'_>,
    y: &Bound<'_, PyArray1<f64>>,
    i0: PyReadonlyArray1<'_, i64>,
    i1: PyReadonlyArray1<'_, i64>,
    c0: PyReadonlyArray1<'_, f64>,
    p0: PyReadonlyArray2<'_, f64>,
    c1: PyReadonlyArray1<'_, f64>,
    p1: PyReadonlyArray2<'_, f64>,
    c2: PyReadonlyArray1<'_, f64>,
    p2: PyReadonlyArray2<'_, f64>,
    c3: PyReadonlyArray1<'_, f64>,
    p3: PyReadonlyArray2<'_, f64>,
    n_terms: i64,
) -> PyResult<()> {
    // never split across threads (compiled.accumulate calls it once a part),
    // so the output can be an ordinary checked borrow
    let mut y = y.try_readwrite().map_err(|e| PyValueError::new_err(format!("y: {e}")))?;
    let ys = y.as_slice_mut().map_err(|e| PyValueError::new_err(e.to_string()))?;
    let (i0, i1) = (sl(&i0)?, sl(&i1)?);
    let (c0, c1, c2, c3) = (sl(&c0)?, sl(&c1)?, sl(&c2)?, sl(&c3)?);
    let ((p0, s0), (p1, s1), (p2, s2), (p3, s3)) =
        (pl("p0", &p0)?, pl("p1", &p1)?, pl("p2", &p2)?, pl("p3", &p3)?);
    let n_live = match usize::try_from(n_terms) {
        Ok(n @ 1..=4) => n,
        _ => return err(format!("n_terms {n_terms} outside 1..=4")),
    };
    if i1.len() != i0.len() {
        return err(format!("i0 has {} entries, i1 {}", i0.len(), i1.len()));
    }
    let terms = [("c0", "p0", c0, s0), ("c1", "p1", c1, s1), ("c2", "p2", c2, s2),
                 ("c3", "p3", c3, s3)];
    let mut w_min = usize::MAX;
    for &(cn, pn, c, s) in &terms[..n_live] {
        per_row(i0.len(), "i0", &[(cn, c.len()), (pn, s[0])])?;
        w_min = w_min.min(s[1]);
    }
    check_windows(i0, i1, ys.len(), w_min)?;
    disjoint(&[span(ys)], &[span(i0), span(i1), span(c0), span(p0), span(c1), span(p1),
                            span(c2), span(p2), span(c3), span(p3)])?;
    let (w0, w1, w2, w3) = (s0[1], s1[1], s2[1], s3[1]);
    py.detach(|| accum_loop(ys, i0, i1, c0, p0, w0, c1, p1, w1, c2, p2, w2, c3, p3, w3, n_terms));
    Ok(())
}

/// Ω on symmetric rows `rows[lo..hi]`, in the spelling `spell` names.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn omega_sym(
    py: Python<'_>,
    out: &Bound<'_, PyArray2<f64>>,
    x: PyReadonlyArray2<'_, f64>,
    rows: PyReadonlyArray1<'_, i64>,
    pos: PyReadonlyArray1<'_, f64>,
    w1: PyReadonlyArray1<'_, f64>,
    w2: PyReadonlyArray1<'_, f64>,
    width: PyReadonlyArray1<'_, i64>,
    spell: i64,
    lo: usize,
    hi: usize,
) -> PyResult<()> {
    let (x, [n, xw]) = pl("x", &x)?;
    let (o, os) = out2("out", out, [n, xw])?;
    let (rows, pos, w1, w2, width) = (sl(&rows)?, sl(&pos)?, sl(&w1)?, sl(&w2)?, sl(&width)?);
    per_row(n, "x", &[("pos", pos.len()), ("w1", w1.len()), ("w2", w2.len()), ("width", width.len())])?;
    check_rows(rows, width, lo, hi, n, xw)?;
    check_spell(spell)?;
    disjoint(&[os], &[span(x), span(rows), span(pos), span(w1), span(w2), span(width)])?;
    py.detach(|| unsafe { omega_sym_loop(o.get(), xw, x, xw, rows, pos, w1, w2, width, spell, lo, hi) });
    Ok(())
}

/// Node-weighted Ω on one FCJ bucket's rows `rows[lo..hi]`; `phi` and `om`
/// are bucket-local.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn omega_fcj(
    py: Python<'_>,
    out: &Bound<'_, PyArray2<f64>>,
    x: PyReadonlyArray2<'_, f64>,
    rows: PyReadonlyArray1<'_, i64>,
    w1: PyReadonlyArray1<'_, f64>,
    w2: PyReadonlyArray1<'_, f64>,
    width: PyReadonlyArray1<'_, i64>,
    phi: PyReadonlyArray2<'_, f64>,
    om: PyReadonlyArray2<'_, f64>,
    spell: i64,
    lo: usize,
    hi: usize,
) -> PyResult<()> {
    let (x, [n, xw]) = pl("x", &x)?;
    let (o, os) = out2("out", out, [n, xw])?;
    let (rows, w1, w2, width) = (sl(&rows)?, sl(&w1)?, sl(&w2)?, sl(&width)?);
    let ((phi, sp), (om, so)) = (pl("phi", &phi)?, pl("om", &om)?);
    per_row(n, "x", &[("w1", w1.len()), ("w2", w2.len()), ("width", width.len())])?;
    per_row(rows.len(), "rows", &[("phi", sp[0])])?;
    same_shape(sp, &[("om", so)])?;
    check_rows(rows, width, lo, hi, n, xw)?;
    check_spell(spell)?;
    disjoint(&[os], &[span(x), span(rows), span(w1), span(w2), span(width), span(phi),
                      span(om)])?;
    let nn = sp[1];
    py.detach(|| unsafe {
        omega_fcj_loop(o.get(), xw, x, xw, rows, w1, w2, width, phi, om, nn, spell, lo, hi)
    });
    Ok(())
}

/// Ω and its three partials on symmetric rows `rows[lo..hi]`.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn bases_sym(
    py: Python<'_>,
    omega: &Bound<'_, PyArray2<f64>>,
    d_pos: &Bound<'_, PyArray2<f64>>,
    d_gamma: &Bound<'_, PyArray2<f64>>,
    d_eta: &Bound<'_, PyArray2<f64>>,
    x: PyReadonlyArray2<'_, f64>,
    rows: PyReadonlyArray1<'_, i64>,
    pos: PyReadonlyArray1<'_, f64>,
    w1: PyReadonlyArray1<'_, f64>,
    w2: PyReadonlyArray1<'_, f64>,
    width: PyReadonlyArray1<'_, i64>,
    lo: usize,
    hi: usize,
) -> PyResult<()> {
    let (x, [n, xw]) = pl("x", &x)?;
    let s = [n, xw];
    let ((a, sa), (b, sb), (c, sc), (d, sd)) = (out2("omega", omega, s)?, out2("d_pos", d_pos, s)?,
                                                out2("d_gamma", d_gamma, s)?, out2("d_eta", d_eta, s)?);
    let (rows, pos, w1, w2, width) = (sl(&rows)?, sl(&pos)?, sl(&w1)?, sl(&w2)?, sl(&width)?);
    per_row(n, "x", &[("pos", pos.len()), ("w1", w1.len()), ("w2", w2.len()), ("width", width.len())])?;
    check_rows(rows, width, lo, hi, n, xw)?;
    disjoint(&[sa, sb, sc, sd], &[span(x), span(rows), span(pos), span(w1), span(w2),
                                  span(width)])?;
    py.detach(|| unsafe {
        bases_sym_loop(a.get(), b.get(), c.get(), d.get(), xw, x, xw, rows, pos, w1, w2, width, lo, hi)
    });
    Ok(())
}

/// Every basis plane for one FCJ bucket's rows `rows[lo..hi]`, in one pass
/// over the nodes.  Without `has_ax` the four axial node planes and the two
/// axial outputs are placeholders, neither read nor written nor checked.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn bases_fcj(
    py: Python<'_>,
    omega: &Bound<'_, PyArray2<f64>>,
    d_pos: &Bound<'_, PyArray2<f64>>,
    d_gamma: &Bound<'_, PyArray2<f64>>,
    d_eta: &Bound<'_, PyArray2<f64>>,
    d_sl: &Bound<'_, PyArray2<f64>>,
    d_hl: &Bound<'_, PyArray2<f64>>,
    x: PyReadonlyArray2<'_, f64>,
    rows: PyReadonlyArray1<'_, i64>,
    w1: PyReadonlyArray1<'_, f64>,
    w2: PyReadonlyArray1<'_, f64>,
    width: PyReadonlyArray1<'_, i64>,
    phi: PyReadonlyArray2<'_, f64>,
    om: PyReadonlyArray2<'_, f64>,
    dphi: PyReadonlyArray2<'_, f64>,
    dom: PyReadonlyArray2<'_, f64>,
    dphi_sl: PyReadonlyArray2<'_, f64>,
    dom_sl: PyReadonlyArray2<'_, f64>,
    dphi_hl: PyReadonlyArray2<'_, f64>,
    dom_hl: PyReadonlyArray2<'_, f64>,
    has_ax: bool,
    lo: usize,
    hi: usize,
) -> PyResult<()> {
    let (x, [n, xw]) = pl("x", &x)?;
    let s = [n, xw];
    let ((a, sa), (b, sb), (c, sc), (d, sd)) = (out2("omega", omega, s)?, out2("d_pos", d_pos, s)?,
                                                out2("d_gamma", d_gamma, s)?, out2("d_eta", d_eta, s)?);
    let mut outs = vec![sa, sb, sc, sd];
    let (sl_o, hl_o) = if has_ax {
        let ((p, sp), (q, sq)) = (out2("d_sl", d_sl, s)?, out2("d_hl", d_hl, s)?);
        outs.extend([sp, sq]);
        (p, q)
    } else {
        (P(std::ptr::null_mut()), P(std::ptr::null_mut()))
    };
    let (rows, w1, w2, width) = (sl(&rows)?, sl(&w1)?, sl(&w2)?, sl(&width)?);
    let ((phi, sp), (om, so), (dphi, sdp), (dom, sdo)) =
        (pl("phi", &phi)?, pl("om", &om)?, pl("dphi", &dphi)?, pl("dom", &dom)?);
    let ((dphi_sl, s1), (dom_sl, s2), (dphi_hl, s3), (dom_hl, s4)) =
        (pl("dphi_sl", &dphi_sl)?, pl("dom_sl", &dom_sl)?, pl("dphi_hl", &dphi_hl)?,
         pl("dom_hl", &dom_hl)?);
    per_row(n, "x", &[("w1", w1.len()), ("w2", w2.len()), ("width", width.len())])?;
    per_row(rows.len(), "rows", &[("phi", sp[0])])?;
    same_shape(sp, &[("om", so), ("dphi", sdp), ("dom", sdo)])?;
    let mut ins = vec![span(x), span(rows), span(w1), span(w2), span(width), span(phi),
                       span(om), span(dphi), span(dom)];
    if has_ax {
        same_shape(sp, &[("dphi_sl", s1), ("dom_sl", s2), ("dphi_hl", s3), ("dom_hl", s4)])?;
        ins.extend([span(dphi_sl), span(dom_sl), span(dphi_hl), span(dom_hl)]);
    }
    check_rows(rows, width, lo, hi, n, xw)?;
    disjoint(&outs, &ins)?;
    let nn = sp[1];
    py.detach(|| unsafe {
        bases_fcj_loop([a.get(), b.get(), c.get(), d.get(), sl_o.get(), hl_o.get()], xw, x, xw,
                       rows, w1, w2, width, phi, om, dphi, dom, dphi_sl, dom_sl, dphi_hl, dom_hl,
                       nn, has_ax, lo, hi)
    });
    Ok(())
}

#[pymodule]
fn rietx_kernels(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("KERNEL_ABI", KERNEL_ABI)?;
    m.add_function(wrap_pyfunction!(accum, m)?)?;
    m.add_function(wrap_pyfunction!(omega_sym, m)?)?;
    m.add_function(wrap_pyfunction!(omega_fcj, m)?)?;
    m.add_function(wrap_pyfunction!(bases_sym, m)?)?;
    m.add_function(wrap_pyfunction!(bases_fcj, m)?)?;
    Ok(())
}
