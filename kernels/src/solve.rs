//! The structure-solution engine's two kernels (1.4.0, #562; WP number
//! pending): the replica-batched per-atom orbit sums of the structure factor,
//! with their one-site twin, and the minimum-image contact term.  numba
//! compiled them in the engine's spike, and these are transcriptions of those
//! two `njit` functions.
//!
//! **The orbit sums.**  For reflection n, replica r and site j,
//!
//! ```text
//! S_j(h_n) = Σ_{m ∈ orbit(j)} exp(2πi (Q[n,m]·x_j + HT[n,m]))
//! ```
//!
//! with `Q[n,m] = R_mᵀ h_n` (the reciprocal-space action is the transposed
//! rotation) and `HT[n,m] = h_n·t_m`, both frozen by the caller.  Site j's
//! images are `img_lo[j]..img_hi[j]` along the m axis.  The phase is summed
//! as written, `((Q0·x0 + Q1·x1) + Q2·x2) + HT`, then multiplied by 2π, and
//! the real and imaginary sums run over m in order.  `cos` and `sin` are the
//! platform C library's through Rust's `f64` methods, as numba's were, so the
//! numba kernel is matched to the bit wherever the two link one libm, and
//! the numpy expression (which runs numpy's own vectorised `cos`/`sin` and
//! sums along an axis pairwise) to the stated 1e-13 relative bar.
//!
//! The loops are serial over the reflection range `[lo, hi)`, which is what
//! `compiled._spread` splits: every output element `[r, a, n]` belongs to
//! exactly one n, so disjoint ranges write disjoint elements.  A repeated
//! entry of `atoms` is harmless, its outputs being indexed by position in
//! `atoms`, never by site.
//!
//! **The contact term.**  For replica r, every atom a of the moved site
//! `moved[r]` is set against every atom b, over the 27 cells around the
//! minimum image, skipping only a against itself in its own cell:
//! `Σ w·((r0 − d)/σ)²` over images closer than r0, where w is `w_same` for b
//! in the moved site and 1 otherwise.  The minimum image is
//! `d − floor(d + ½)`, which differs from `np.round` (half to even) only on
//! an exact half.  The metric form is summed as written.  Its loop is serial
//! over the replica range `[lo, hi)`, each replica one output element.
//!
//! **The 27 cells are a bound, and the kernel refuses past it.**  A sphere of
//! radius r spans |x_k| ≤ r·√(G*_kk) along fractional axis k (the plane
//! spacing is 1/√(G*_kk), G* = G⁻¹), and a minimum-image component already
//! lies in [−½, ½), so the shifts needed are |n_k| ≤ ⌊r·√(G*_kk) + ½⌋.  The
//! loop's ±1 holds every contact closer than the largest r0 exactly while
//! that is at most 1 on every axis, r0 under 1.5 plane spacings.  Past it a
//! thin cell, or a large r0, would lose contacts in silence, so
//! `check_cells` refuses, with the bound and the words of the numpy
//! `site_clash` in the engine's `chemistry.py` (#1016), and the engine can
//! treat both refusals alike.  It sits here and not in `compiled.py`
//! because the limit is this loop's, and the wheel's function is callable
//! without the wrapper.  G* comes from the cofactors here and from
//! `np.linalg.inv` there, so the two can disagree only within a few ulps of
//! the bound.
//!
//! The checks are `lib.rs`'s, by name and before the GIL is released: every
//! plane C-contiguous and of the shape the loops index it by, every index in
//! range, every output writeable and disjoint from every other array.

use numpy::ndarray::Dimension;
use numpy::{
    Element, PyArray, PyArray1, PyArray2, PyArray3, PyArrayMethods, PyReadonlyArray,
    PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArray3, PyUntypedArrayMethods,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::{disjoint, err, index, span, Span, P};

/// 2π: the spike's kernel spelled the literal `6.283185307179586`, which is
/// `TAU` to the bit (and clippy refuses the literal).
const TWO_PI: f64 = std::f64::consts::TAU;

/// A read-only array as a slice, checked C-contiguous; returns its shape.
fn ro<'a, T: Element, D: Dimension>(
    name: &str,
    a: &'a PyReadonlyArray<'_, T, D>,
) -> PyResult<(&'a [T], Vec<usize>)> {
    if !a.is_c_contiguous() {
        return err(format!("{name} must be C-contiguous"));
    }
    let v = a.as_slice().map_err(|e| PyValueError::new_err(format!("{name}: {e}")))?;
    Ok((v, a.shape().to_vec()))
}

/// An output array as a raw pointer and its span: C-contiguous, writeable,
/// and of shape `like`.
fn out<D: Dimension>(name: &str, a: &Bound<'_, PyArray<f64, D>>, like: &[usize])
                     -> PyResult<(P<f64>, Span)> {
    if !a.is_c_contiguous() {
        return err(format!("{name} must be C-contiguous"));
    }
    if unsafe { (*a.as_array_ptr()).flags } & numpy::npyffi::NPY_ARRAY_WRITEABLE == 0 {
        return err(format!("{name} must be writeable"));
    }
    if a.shape() != like {
        return err(format!("{name} has shape {:?}, the kernel writes {like:?}", a.shape()));
    }
    let p = a.data();
    Ok((P(p), (p as usize, p as usize + a.len() * size_of::<f64>())))
}

fn shape_is(name: &str, got: &[usize], want: &[usize]) -> PyResult<()> {
    if got != want {
        return err(format!("{name} has shape {got:?}, the kernel reads {want:?}"));
    }
    Ok(())
}

/// `r` to three significant figures, as Python's `{:.3g}` writes a distance
/// of order ångströms: no trailing zeros, no exponent.
fn sig3(r: f64) -> String {
    if r == 0.0 || !r.is_finite() {
        return format!("{r}");
    }
    let decimals = (2 - r.abs().log10().floor() as i32).max(0) as usize;
    let s = format!("{r:.decimals$}");
    if s.contains('.') { s.trim_end_matches('0').trim_end_matches('.').to_string() } else { s }
}

/// Refuse a metric `g` (row-major 3 × 3) and contact radii `r0` for which
/// the 27 cells around a minimum image would miss a contact: the module
/// header's bound, ⌊r·√(G*_kk) + ½⌋ ≤ 1 on every axis for r the largest r0.
fn check_cells(g: &[f64], r0: &[f64]) -> PyResult<()> {
    if let Some(v) = r0.iter().find(|v| !v.is_finite()) {
        return err(format!("r0 holds {v}, not a finite distance"));
    }
    let r = r0.iter().copied().fold(0.0, f64::max);
    // the loop reads the upper triangle and the cofactors below read both, so
    // a bound computed for another matrix than the loop's must not pass
    let scale = g[0].abs().max(g[4].abs()).max(g[8].abs());
    for (a, b) in [(1, 3), (2, 6), (5, 7)] {
        if !((g[a] - g[b]).abs() <= 1e-12 * scale) {
            return err("g is not a symmetric metric tensor");
        }
    }
    // Sylvester's criterion, then the diagonal of G* = G⁻¹ from cofactors
    let c00 = g[4] * g[8] - g[5] * g[7];
    let c11 = g[0] * g[8] - g[2] * g[6];
    let c22 = g[0] * g[4] - g[1] * g[3];
    let det = g[0] * c00 - g[1] * (g[3] * g[8] - g[5] * g[6]) + g[2] * (g[3] * g[7] - g[4] * g[6]);
    if !(g[0] > 0.0 && c22 > 0.0 && det > 0.0 && c00 > 0.0 && c11 > 0.0) {
        return err("g is not a positive-definite metric tensor");
    }
    if [c00, c11, c22].iter().any(|&c| (r * (c / det).sqrt() + 0.5).floor() > 1.0) {
        return err(format!("r0 up to {} Å reaches past the 27 cells around a minimum image \
                            in this cell; the term would miss contacts", sig3(r)));
    }
    Ok(())
}

fn range(lo: usize, hi: usize, n: usize, what: &str) -> PyResult<()> {
    if lo > hi || hi > n {
        return err(format!("{what} range {lo}..{hi} outside 0..{n}"));
    }
    Ok(())
}

/// The orbit tables `Q` (N, M, 3) and `HT` (N, M), the coordinates `xyz`
/// (R, S, 3) and each site's image range inside `0..M`: returns
/// (N, M, R, S).
fn orbit_tables(q: &[usize], ht: &[usize], xyz: &[usize], img_lo: &[i64], img_hi: &[i64])
                -> PyResult<(usize, usize, usize, usize)> {
    if q.len() != 3 || q[2] != 3 {
        return err(format!("Q has shape {q:?}, the kernel reads (N, M, 3)"));
    }
    let (n, m) = (q[0], q[1]);
    shape_is("HT", ht, &[n, m])?;
    if xyz.len() != 3 || xyz[2] != 3 {
        return err(format!("xyz has shape {xyz:?}, the kernel reads (R, S, 3)"));
    }
    let (r, s) = (xyz[0], xyz[1]);
    if img_lo.len() != s || img_hi.len() != s {
        return err(format!("img_lo has {} entries and img_hi {}, xyz has {s} sites",
                           img_lo.len(), img_hi.len()));
    }
    for (j, (&a, &b)) in img_lo.iter().zip(img_hi).enumerate() {
        let a = index(a, m + 1, "image start")?;
        let b = index(b, m + 1, "image end")?;
        if b < a {
            return err(format!("site {j}'s images {a}..{b} run backwards"));
        }
    }
    Ok((n, m, r, s))
}

/// One site's orbit sum at one reflection, the spike's inner loop.
#[inline(always)]
fn orbit_one(qn: &[f64], htn: &[f64], x0: f64, x1: f64, x2: f64, lo: usize, hi: usize)
             -> (f64, f64) {
    let mut re = 0.0;
    let mut im = 0.0;
    for m in lo..hi {
        let ph = TWO_PI * (qn[3 * m] * x0 + qn[3 * m + 1] * x1 + qn[3 * m + 2] * x2 + htn[m]);
        re += ph.cos();
        im += ph.sin();
    }
    (re, im)
}

#[allow(clippy::too_many_arguments)]
unsafe fn orbit_sums_loop(o_re: *mut f64, o_im: *mut f64, q: &[f64], ht: &[f64], xyz: &[f64],
                          img_lo: &[i64], img_hi: &[i64], atoms: &[i64], n_refl: usize,
                          n_img: usize, n_rep: usize, n_site: usize, lo: usize, hi: usize) {
    let n_at = atoms.len();
    for n in lo..hi {
        let qn = &q[n * n_img * 3..(n + 1) * n_img * 3];
        let htn = &ht[n * n_img..(n + 1) * n_img];
        for r in 0..n_rep {
            for (ja, &j) in atoms.iter().enumerate() {
                let j = j as usize;
                let x = &xyz[(r * n_site + j) * 3..(r * n_site + j) * 3 + 3];
                let (re, im) = orbit_one(qn, htn, x[0], x[1], x[2], img_lo[j] as usize,
                                         img_hi[j] as usize);
                let k = (r * n_at + ja) * n_refl + n;
                unsafe {
                    *o_re.add(k) = re;
                    *o_im.add(k) = im;
                }
            }
        }
    }
}

#[allow(clippy::too_many_arguments)]
unsafe fn orbit_sums_one_loop(o_re: *mut f64, o_im: *mut f64, q: &[f64], ht: &[f64],
                              xyz: &[f64], img_lo: &[i64], img_hi: &[i64], atom_of_rep: &[i64],
                              n_refl: usize, n_img: usize, n_site: usize, lo: usize, hi: usize) {
    for n in lo..hi {
        let qn = &q[n * n_img * 3..(n + 1) * n_img * 3];
        let htn = &ht[n * n_img..(n + 1) * n_img];
        for (r, &j) in atom_of_rep.iter().enumerate() {
            let j = j as usize;
            let x = &xyz[(r * n_site + j) * 3..(r * n_site + j) * 3 + 3];
            let (re, im) = orbit_one(qn, htn, x[0], x[1], x[2], img_lo[j] as usize,
                                     img_hi[j] as usize);
            let k = r * n_refl + n;
            unsafe {
                *o_re.add(k) = re;
                *o_im.add(k) = im;
            }
        }
    }
}

#[allow(clippy::too_many_arguments)]
unsafe fn clash_loop(o: *mut f64, pos: &[f64], site_of: &[i64], moved: &[i64], g: &[f64],
                     r0: &[f64], n_sites: usize, sigma: f64, w_same: f64, n_at: usize,
                     lo: usize, hi: usize) {
    let (g00, g11, g22) = (g[0], g[4], g[8]);
    let (g01, g02, g12) = (g[1], g[2], g[5]);
    for r in lo..hi {
        let p = &pos[r * n_at * 3..(r + 1) * n_at * 3];
        let mv = moved[r];
        let mut e = 0.0;
        for a in 0..n_at {
            if site_of[a] != mv {
                continue;
            }
            let sa = site_of[a] as usize;
            for b in 0..n_at {
                let w = if site_of[b] == mv { w_same } else { 1.0 };
                let rr = r0[sa * n_sites + site_of[b] as usize];
                let mut d0 = p[3 * b] - p[3 * a];
                let mut d1 = p[3 * b + 1] - p[3 * a + 1];
                let mut d2 = p[3 * b + 2] - p[3 * a + 2];
                d0 -= (d0 + 0.5).floor();
                d1 -= (d1 + 0.5).floor();
                d2 -= (d2 + 0.5).floor();
                for i in -1i32..2 {
                    for j in -1i32..2 {
                        for k in -1i32..2 {
                            if a == b && i == 0 && j == 0 && k == 0 {
                                continue;
                            }
                            let x0 = d0 + i as f64;
                            let x1 = d1 + j as f64;
                            let x2 = d2 + k as f64;
                            let q = g00 * x0 * x0 + g11 * x1 * x1 + g22 * x2 * x2
                                + 2.0 * (g01 * x0 * x1 + g02 * x0 * x2 + g12 * x1 * x2);
                            let dist = if q > 0.0 { q.sqrt() } else { 0.0 };
                            if dist < rr {
                                let ov = (rr - dist) / sigma;
                                e += w * ov * ov;
                            }
                        }
                    }
                }
            }
        }
        unsafe { *o.add(r) = e };
    }
}

// --- the bindings ------------------------------------------------------

/// Every listed site's orbit sums, `s_re`/`s_im[r, a, n]` for site
/// `atoms[a]` of replica r, on reflections `lo..hi`.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub(crate) fn solve_orbit_sums(
    py: Python<'_>,
    s_re: &Bound<'_, PyArray3<f64>>,
    s_im: &Bound<'_, PyArray3<f64>>,
    q: PyReadonlyArray3<'_, f64>,
    ht: PyReadonlyArray2<'_, f64>,
    xyz: PyReadonlyArray3<'_, f64>,
    img_lo: PyReadonlyArray1<'_, i64>,
    img_hi: PyReadonlyArray1<'_, i64>,
    atoms: PyReadonlyArray1<'_, i64>,
    lo: usize,
    hi: usize,
) -> PyResult<()> {
    let (q, sq) = ro("Q", &q)?;
    let (ht, sht) = ro("HT", &ht)?;
    let (xyz, sx) = ro("xyz", &xyz)?;
    let ((img_lo, _), (img_hi, _), (atoms, _)) =
        (ro("img_lo", &img_lo)?, ro("img_hi", &img_hi)?, ro("atoms", &atoms)?);
    let (n, m, r, s) = orbit_tables(&sq, &sht, &sx, img_lo, img_hi)?;
    for &j in atoms {
        index(j, s, "atom")?;
    }
    range(lo, hi, n, "reflection")?;
    let like = [r, atoms.len(), n];
    let ((a, sa), (b, sb)) = (out("s_re", s_re, &like)?, out("s_im", s_im, &like)?);
    disjoint(&[sa, sb], &[span(q), span(ht), span(xyz), span(img_lo), span(img_hi),
                          span(atoms)])?;
    py.detach(|| unsafe {
        orbit_sums_loop(a.get(), b.get(), q, ht, xyz, img_lo, img_hi, atoms, n, m, r, s, lo, hi)
    });
    Ok(())
}

/// One site per replica, `s_re`/`s_im[r, n]` for site `atom_of_rep[r]`, on
/// reflections `lo..hi`: the batched one-site move.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub(crate) fn solve_orbit_sums_one(
    py: Python<'_>,
    s_re: &Bound<'_, PyArray2<f64>>,
    s_im: &Bound<'_, PyArray2<f64>>,
    q: PyReadonlyArray3<'_, f64>,
    ht: PyReadonlyArray2<'_, f64>,
    xyz: PyReadonlyArray3<'_, f64>,
    img_lo: PyReadonlyArray1<'_, i64>,
    img_hi: PyReadonlyArray1<'_, i64>,
    atom_of_rep: PyReadonlyArray1<'_, i64>,
    lo: usize,
    hi: usize,
) -> PyResult<()> {
    let (q, sq) = ro("Q", &q)?;
    let (ht, sht) = ro("HT", &ht)?;
    let (xyz, sx) = ro("xyz", &xyz)?;
    let ((img_lo, _), (img_hi, _), (atom_of_rep, _)) =
        (ro("img_lo", &img_lo)?, ro("img_hi", &img_hi)?, ro("atom_of_rep", &atom_of_rep)?);
    let (n, m, r, s) = orbit_tables(&sq, &sht, &sx, img_lo, img_hi)?;
    if atom_of_rep.len() != r {
        return err(format!("atom_of_rep has {} entries, xyz has {r} replicas",
                           atom_of_rep.len()));
    }
    for &j in atom_of_rep {
        index(j, s, "atom")?;
    }
    range(lo, hi, n, "reflection")?;
    let like = [r, n];
    let ((a, sa), (b, sb)) = (out("s_re", s_re, &like)?, out("s_im", s_im, &like)?);
    disjoint(&[sa, sb], &[span(q), span(ht), span(xyz), span(img_lo), span(img_hi),
                          span(atom_of_rep)])?;
    py.detach(|| unsafe {
        orbit_sums_one_loop(a.get(), b.get(), q, ht, xyz, img_lo, img_hi, atom_of_rep, n, m, s,
                            lo, hi)
    });
    Ok(())
}

/// The contact energy of site `moved[r]` in replica r, `out[r]`, on replicas
/// `lo..hi`.  `pos` (R, n_atoms, 3) is every atom of the cell, `site_of`
/// its site, `g` the metric tensor and `r0` (n_sites, n_sites) the contact
/// radii.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub(crate) fn solve_clash(
    py: Python<'_>,
    out_e: &Bound<'_, PyArray1<f64>>,
    pos: PyReadonlyArray3<'_, f64>,
    site_of: PyReadonlyArray1<'_, i64>,
    moved: PyReadonlyArray1<'_, i64>,
    g: PyReadonlyArray2<'_, f64>,
    r0: PyReadonlyArray2<'_, f64>,
    sigma: f64,
    w_same: f64,
    lo: usize,
    hi: usize,
) -> PyResult<()> {
    let (pos, sp) = ro("pos", &pos)?;
    let ((site_of, _), (moved, _)) = (ro("site_of", &site_of)?, ro("moved", &moved)?);
    let ((g, sg), (r0, sr)) = (ro("g", &g)?, ro("r0", &r0)?);
    if sp.len() != 3 || sp[2] != 3 {
        return err(format!("pos has shape {sp:?}, the kernel reads (R, n_atoms, 3)"));
    }
    let (r, n_at) = (sp[0], sp[1]);
    shape_is("g", &sg, &[3, 3])?;
    if sr[0] != sr[1] {
        return err(format!("r0 has shape {sr:?}, the kernel reads (n_sites, n_sites)"));
    }
    let n_sites = sr[0];
    check_cells(g, r0)?;
    if site_of.len() != n_at {
        return err(format!("site_of has {} entries, pos has {n_at} atoms", site_of.len()));
    }
    if moved.len() != r {
        return err(format!("moved has {} entries, pos has {r} replicas", moved.len()));
    }
    for &v in site_of {
        index(v, n_sites, "site")?;
    }
    for &v in moved {
        index(v, n_sites, "moved site")?;
    }
    if !(sigma.is_finite() && sigma > 0.0) {
        return err(format!("sigma {sigma} is not a positive number"));
    }
    if !w_same.is_finite() {
        return err(format!("w_same {w_same} is not finite"));
    }
    range(lo, hi, r, "replica")?;
    let (o, so) = out("out", out_e, &[r])?;
    disjoint(&[so], &[span(pos), span(site_of), span(moved), span(g), span(r0)])?;
    py.detach(|| unsafe {
        clash_loop(o.get(), pos, site_of, moved, g, r0, n_sites, sigma, w_same, n_at, lo, hi)
    });
    Ok(())
}
