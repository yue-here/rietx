//! The structure figure's rasteriser (WP-1940 § Decisions item 9).  numba
//! compiled it until WP-1940, from `rietx/viz/figure3d/_kernels_numba.py`;
//! these are that file's two kernels, `render_rows` and `id_plane`, and
//! `render_rows_cued` (1.5.0, WP-1548), `render_rows` with depth cueing.
//!
//! **Fog is one function, not a second rasteriser.**  `render_rows` and
//! `render_rows_cued` both check their arguments in [`render`] and draw in
//! [`band`], which takes the fog as an `Option`: `None` is `render_rows`, and
//! every site that fogs passes its colour through [`fogged`], which hands
//! `None` its colour back untouched.  So the unfogged picture runs no
//! arithmetic it did not run in 1.4.0, and the two kernels cannot drift.
//!
//! `rietx/viz/figure3d/raster.py` owns the packing, the banding and every rule
//! about the picture; read its docstring first.  Its `_pack` and `pack_ids`
//! build the arrays these read, and its docstrings say what each holds.
//!
//! **The bar is the bit.**  `raster._band_numpy` and `raster._ids_numpy` are
//! the oracle, and they call no library function: `sqrt` is an IEEE
//! operation, the specular power is repeated squaring, and the box filter adds
//! the samples in one order.  So every expression here mirrors its numpy line
//! operation for operation, and `tests/test_raster_kernels.py` holds both
//! kernels to the oracle bit for bit on every wheel platform.  Two habits keep
//! a comparison in the numpy line's polarity: a test that skips a sample is
//! written as numpy's `hit &= ~(...)`, so a NaN goes the way it goes there;
//! and a minimum, maximum or clamp goes through `npmin`/`npmax`, which pass a
//! NaN on as `np.minimum`/`np.maximum` do, where `f64::min`/`max` drop it.
//!
//! **Threads.**  `raster.draw` hands bands of output rows to the compiled
//! tier's pool, each a `render_rows` call on the same `out` with a disjoint
//! `[r0, r1)`.  So `out` is written through a raw pointer, for the reason
//! `lib.rs`'s header gives, and the band's sample planes are the call's own.
//! `id_plane` is one call a frame and takes ordinary checked borrows.
//!
//! **Every argument is checked before the GIL is released**, as in `lib.rs`:
//! shapes against the leading count of each primitive's group, C order, the
//! output's shape and writeability, a band inside the image, and no output
//! byte shared with an input.  A primitive's box is clipped to the band and
//! the image before any index is formed, so a box value can cost a picture its
//! correctness but never a write outside a plane.

use numpy::ndarray::Dimension;
use numpy::{
    Element, PyArray1, PyArray2, PyArray3, PyArrayMethods, PyReadonlyArray, PyReadonlyArray1,
    PyReadonlyArray2, PyReadonlyArray3, PyUntypedArrayMethods,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::{disjoint, err, span, Span, P};

/// The shader's constants, `raster._pack`'s `look`: light (3), ambient,
/// diffuse, specular, shininess, face diffuse, ring width, ring threshold,
/// ring lighten, ring darken.
const LOOK_LEN: usize = 12;

/// A read-only array as a slice, checked C-contiguous and of shape
/// `(n, *tail)`; returns the slice and `n`.
fn arr<'a, T: Element, D: Dimension>(
    name: &str,
    a: &'a PyReadonlyArray<'_, T, D>,
    tail: &[usize],
) -> PyResult<(&'a [T], usize)> {
    if !a.is_c_contiguous() {
        return err(format!("{name} must be C-contiguous"));
    }
    let s = a.shape();
    if s.len() != tail.len() + 1 || &s[1..] != tail {
        return err(format!("{name} has shape {s:?}, the kernel reads (n, {tail:?})"));
    }
    let v = a.as_slice().map_err(|e| PyValueError::new_err(format!("{name}: {e}")))?;
    Ok((v, s[0]))
}

/// Every array of a group has the group's count of primitives.
fn same_count(group: &str, counts: &[(&str, usize)]) -> PyResult<usize> {
    let n = counts[0].1;
    for (name, c) in &counts[1..] {
        if *c != n {
            return err(format!("{group}: {name} has {c} entries, {} has {n}", counts[0].0));
        }
    }
    Ok(n)
}

/// `[lo, hi)` clipped to `[a, b)`; empty, never reversed, when it misses.
fn clip(lo: i64, hi: i64, a: usize, b: usize) -> (usize, usize) {
    let (a, b) = (a as i64, b as i64);
    let lo = lo.clamp(a, b);
    let hi = hi.clamp(lo, b);
    (lo as usize, hi as usize)
}

fn ipow(x: f64, mut n: i64) -> f64 {
    let mut out = 1.0;
    let mut base = x;
    while n > 0 {
        if n & 1 == 1 {
            out = out * base;
        }
        base = base * base;
        n >>= 1;
    }
    out
}

/// The GUI's `shade`: `base·(ambient + diffuse·d) + specular·s^k`.
fn shade(b: &[f64], n0: f64, n1: f64, n2: f64, look: &[f64]) -> [f64; 3] {
    let ndl = n0 * look[0] + n1 * look[1] + n2 * look[2];
    let d = npmax(ndl, 0.0);
    let rz = -look[2] + 2.0 * ndl * n2;
    let spec = ipow(npmax(rz, 0.0), look[6] as i64);
    let k = look[3] + look[4] * d;
    [b[0] * k + look[5] * spec, b[1] * k + look[5] * spec, b[2] * k + look[5] * spec]
}

/// `np.maximum`: a NaN on either side is the answer, where `f64::max` drops it.
fn npmax(a: f64, b: f64) -> f64 {
    if a.is_nan() || a >= b { a } else { b }
}

/// `np.minimum`, NaN passed on as in [`npmax`].
fn npmin(a: f64, b: f64) -> f64 {
    if a.is_nan() || a <= b { a } else { b }
}

/// `np.minimum(np.maximum(v, 0.0), 1.0)`, a NaN kept.
fn clamp01(v: f64) -> f64 {
    npmin(npmax(v, 0.0), 1.0)
}

/// Depth cueing (WP-1548 D1), `raster._fogged`'s `fog`: the factor is 0 in
/// front of `z_start`, rises linearly to `f_max` at `z_end`, and stays there
/// behind it.  View coordinates, z toward the viewer.
#[derive(Clone, Copy)]
struct Fog {
    z_start: f64,
    z_end: f64,
    f_max: f64,
    colour: [f64; 3],
}

/// `raster._fogged` for one sample: `col` blended toward the fog colour by
/// its depth `z`, `col·(1 − f) + colour·f` in that association.  `None`
/// returns `col` itself, so a picture without fog runs no arithmetic it did
/// not run before.
fn fogged(col: [f64; 3], z: f64, fog: Option<Fog>) -> [f64; 3] {
    let Some(Fog { z_start, z_end, f_max, colour }) = fog else {
        return col;
    };
    let f = f_max * clamp01((z_start - z) / (z_start - z_end));
    [col[0] * (1.0 - f) + colour[0] * f, col[1] * (1.0 - f) + colour[1] * f,
     col[2] * (1.0 - f) + colour[2] * f]
}

// --- the primitives ----------------------------------------------------

type AtomArgs<'py> = (
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray3<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray1<'py, bool>,
    PyReadonlyArray2<'py, i64>,
);
type HalfArgs<'py> = (
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray2<'py, i64>,
);
type SegArgs<'py> = (
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray2<'py, i64>,
);
type TriArgs<'py> = (
    PyReadonlyArray3<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray2<'py, bool>,
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray2<'py, i64>,
);
type IdAtomArgs<'py> = (
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray3<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray2<'py, i64>,
);
type IdHalfArgs<'py> = (
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray2<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray2<'py, i64>,
);

/// `raster._pack`'s `atom`: centre, `M⁻¹` in the view frame, `a = |M⁻¹ẑ|²`,
/// colour, luminance, ring flag, box.
#[derive(Clone, Copy)]
struct Atoms<'a> {
    n: usize,
    c: &'a [f64],
    m: &'a [f64],
    a: &'a [f64],
    col: &'a [f64],
    lum: &'a [f64],
    ring: &'a [bool],
    bx: &'a [i64],
}

/// `raster._pack`'s `half`: start, unit axis, length, the ray direction less
/// its part along the axis, that vector's square, radius, colour, box.
#[derive(Clone, Copy)]
struct Halves<'a> {
    n: usize,
    a: &'a [f64],
    w: &'a [f64],
    len: &'a [f64],
    e: &'a [f64],
    ea: &'a [f64],
    r: &'a [f64],
    col: &'a [f64],
    bx: &'a [i64],
}

/// `raster._segments`: ends in samples, half-width, unit direction, length,
/// the two depths, colour, box.
#[derive(Clone, Copy)]
struct Segs<'a> {
    n: usize,
    p: &'a [f64],
    half: &'a [f64],
    dir: &'a [f64],
    len: &'a [f64],
    z: &'a [f64],
    col: &'a [f64],
    bx: &'a [i64],
}

/// `raster._pack`'s `tri`: corners, twice the area, which edges own their
/// on-edge samples, colour, box.
#[derive(Clone, Copy)]
struct Tris<'a> {
    n: usize,
    v: &'a [f64],
    area: &'a [f64],
    tie: &'a [bool],
    col: &'a [f64],
    bx: &'a [i64],
}

fn atoms<'a>(t: &'a AtomArgs<'_>, ins: &mut Vec<Span>) -> PyResult<Atoms<'a>> {
    let (c, nc) = arr("atom_c", &t.0, &[3])?;
    let (m, nm) = arr("atom_m", &t.1, &[3, 3])?;
    let (a, na) = arr("atom_a", &t.2, &[])?;
    let (col, ncol) = arr("atom_col", &t.3, &[3])?;
    let (lum, nl) = arr("atom_lum", &t.4, &[])?;
    let (ring, nr) = arr("atom_ring", &t.5, &[])?;
    let (bx, nb) = arr("atom_box", &t.6, &[4])?;
    let n = same_count("atom", &[("atom_c", nc), ("atom_m", nm), ("atom_a", na),
                                 ("atom_col", ncol), ("atom_lum", nl), ("atom_ring", nr),
                                 ("atom_box", nb)])?;
    ins.extend([span(c), span(m), span(a), span(col), span(lum), span(ring), span(bx)]);
    Ok(Atoms { n, c, m, a, col, lum, ring, bx })
}

fn halves<'a>(t: &'a HalfArgs<'_>, ins: &mut Vec<Span>) -> PyResult<Halves<'a>> {
    let (a, n0) = arr("half_a", &t.0, &[3])?;
    let (w, n1) = arr("half_w", &t.1, &[3])?;
    let (len, n2) = arr("half_len", &t.2, &[])?;
    let (e, n3) = arr("half_e", &t.3, &[3])?;
    let (ea, n4) = arr("half_ea", &t.4, &[])?;
    let (r, n5) = arr("half_r", &t.5, &[])?;
    let (col, n6) = arr("half_col", &t.6, &[3])?;
    let (bx, n7) = arr("half_box", &t.7, &[4])?;
    let n = same_count("half", &[("half_a", n0), ("half_w", n1), ("half_len", n2),
                                 ("half_e", n3), ("half_ea", n4), ("half_r", n5),
                                 ("half_col", n6), ("half_box", n7)])?;
    ins.extend([span(a), span(w), span(len), span(e), span(ea), span(r), span(col),
                span(bx)]);
    Ok(Halves { n, a, w, len, e, ea, r, col, bx })
}

fn segs<'a>(group: &str, t: &'a SegArgs<'_>, ins: &mut Vec<Span>) -> PyResult<Segs<'a>> {
    let (p, n0) = arr(&format!("{group}_p"), &t.0, &[4])?;
    let (half, n1) = arr(&format!("{group}_half"), &t.1, &[])?;
    let (dir, n2) = arr(&format!("{group}_dir"), &t.2, &[2])?;
    let (len, n3) = arr(&format!("{group}_len"), &t.3, &[])?;
    let (z, n4) = arr(&format!("{group}_z"), &t.4, &[2])?;
    let (col, n5) = arr(&format!("{group}_col"), &t.5, &[3])?;
    let (bx, n6) = arr(&format!("{group}_box"), &t.6, &[4])?;
    let n = same_count(group, &[("p", n0), ("half", n1), ("dir", n2), ("len", n3), ("z", n4),
                                ("col", n5), ("box", n6)])?;
    ins.extend([span(p), span(half), span(dir), span(len), span(z), span(col), span(bx)]);
    Ok(Segs { n, p, half, dir, len, z, col, bx })
}

fn tris<'a>(t: &'a TriArgs<'_>, ins: &mut Vec<Span>) -> PyResult<Tris<'a>> {
    let (v, n0) = arr("tri_v", &t.0, &[3, 3])?;
    let (area, n1) = arr("tri_area", &t.1, &[])?;
    let (tie, n2) = arr("tri_tie", &t.2, &[3])?;
    let (col, n3) = arr("tri_col", &t.3, &[3])?;
    let (bx, n4) = arr("tri_box", &t.4, &[4])?;
    let n = same_count("tri", &[("tri_v", n0), ("tri_area", n1), ("tri_tie", n2),
                                ("tri_col", n3), ("tri_box", n4)])?;
    ins.extend([span(v), span(area), span(tie), span(col), span(bx)]);
    Ok(Tris { n, v, area, tie, col, bx })
}

// --- the band ----------------------------------------------------------

/// What a band draws into: depth, premultiplied colour and coverage, `he`
/// sample rows of `ws`, starting at sample row `ext0`.
struct Planes {
    ext0: usize,
    he: usize,
    ws: usize,
    zb: Vec<f64>,
    pm: Vec<f64>,
    al: Vec<f64>,
}

/// The band's geometry and the shader's constants.
#[derive(Clone, Copy)]
struct View<'a> {
    x0: f64,
    y0: f64,
    pxs: f64,
    look: &'a [f64],
}

/// Atoms: |M⁻¹(p − c)| = 1 along the view's z, the GUI's atom shader.
fn draw_atoms(g: &mut Planes, v: View<'_>, at: Atoms<'_>, fog: Option<Fog>) {
    let Atoms { n, c, m, a: aa, col: acol, lum, ring, bx } = at;
    let View { x0, y0, pxs, look } = v;
    let (ext0, ext1, ws) = (g.ext0, g.ext0 + g.he, g.ws);
    for i in 0..n {
        let (iy0, iy1) = clip(bx[4 * i], bx[4 * i + 1], ext0, ext1);
        let (ix0, ix1) = clip(bx[4 * i + 2], bx[4 * i + 3], 0, ws);
        if iy0 >= iy1 {
            continue;
        }
        let (cx, cy, cz) = (c[3 * i], c[3 * i + 1], c[3 * i + 2]);
        let mi = &m[9 * i..9 * i + 9];
        let (m00, m01, e0) = (mi[0], mi[1], mi[2]);
        let (m10, m11, e1) = (mi[3], mi[4], mi[5]);
        let (m20, m21, e2) = (mi[6], mi[7], mi[8]);
        let a = aa[i];
        let base = &acol[3 * i..3 * i + 3];
        for iy in iy0..iy1 {
            let y = y0 - (iy as f64 + 0.5) / pxs - cy;
            let row = (iy - ext0) * ws;
            for ix in ix0..ix1 {
                let x = x0 + (ix as f64 + 0.5) / pxs - cx;
                let q0 = m00 * x + m01 * y;
                let q1 = m10 * x + m11 * y;
                let q2 = m20 * x + m21 * y;
                let b = q0 * e0 + q1 * e1 + q2 * e2;
                let cc = q0 * q0 + q1 * q1 + q2 * q2 - 1.0;
                let disc = b * b - a * cc;
                if disc < 0.0 {
                    continue;
                }
                let t = (-b + disc.sqrt()) / a;
                let z = cz + t;
                let k = row + ix;
                if z < g.zb[k] {
                    continue;
                }
                g.zb[k] = z;
                let u0 = q0 + t * e0;
                let u1 = q1 + t * e1;
                let u2 = q2 + t * e2;
                let n0 = m00 * u0 + m10 * u1 + m20 * u2;
                let n1 = m01 * u0 + m11 * u1 + m21 * u2;
                let n2 = e0 * u0 + e1 * u1 + e2 * u2;
                let nn = (n0 * n0 + n1 * n1 + n2 * n2).sqrt();
                let mut col = shade(base, n0 / nn, n1 / nn, n2 / nn, look);
                if ring[i] && npmin(u0.abs(), npmin(u1.abs(), u2.abs())) < look[8] {
                    if lum[i] < look[9] {
                        for ch in &mut col {
                            *ch = *ch + look[10] * (1.0 - *ch);
                        }
                    } else {
                        for ch in &mut col {
                            *ch = *ch * look[11];
                        }
                    }
                }
                // clamped, then fogged at the sample's own depth
                let col = fogged([clamp01(col[0]), clamp01(col[1]), clamp01(col[2])], z, fog);
                g.pm[3 * k..3 * k + 3].copy_from_slice(&col);
                g.al[k] = 1.0;
            }
        }
    }
}

/// Bond halves: open finite cylinders, the GUI's half shader.
fn draw_halves(g: &mut Planes, v: View<'_>, hv: Halves<'_>, fog: Option<Fog>) {
    let Halves { n, a: ha, w, len, e, ea, r: hr, col: hcol, bx } = hv;
    let View { x0, y0, pxs, look } = v;
    let (ext0, ext1, ws) = (g.ext0, g.ext0 + g.he, g.ws);
    for i in 0..n {
        let (iy0, iy1) = clip(bx[4 * i], bx[4 * i + 1], ext0, ext1);
        let (ix0, ix1) = clip(bx[4 * i + 2], bx[4 * i + 3], 0, ws);
        if iy0 >= iy1 {
            continue;
        }
        let (ax, ay, az) = (ha[3 * i], ha[3 * i + 1], ha[3 * i + 2]);
        let (w0, w1, w2) = (w[3 * i], w[3 * i + 1], w[3 * i + 2]);
        let (f0, f1, f2) = (e[3 * i], e[3 * i + 1], e[3 * i + 2]);
        let (a, r, length) = (ea[i], hr[i], len[i]);
        let base = &hcol[3 * i..3 * i + 3];
        for iy in iy0..iy1 {
            let o1 = y0 - (iy as f64 + 0.5) / pxs - ay;
            let row = (iy - ext0) * ws;
            for ix in ix0..ix1 {
                let o0 = x0 + (ix as f64 + 0.5) / pxs - ax;
                let o2 = -az;
                let oa = o0 * w0 + o1 * w1 + o2 * w2;
                let q0 = o0 - oa * w0;
                let q1 = o1 - oa * w1;
                let q2 = o2 - oa * w2;
                let b = q0 * f0 + q1 * f1 + q2 * f2;
                let disc = b * b - a * (q0 * q0 + q1 * q1 + q2 * q2 - r * r);
                if disc < 0.0 {
                    continue;
                }
                let z = (-b + disc.sqrt()) / a;
                let along = oa + z * w2;
                if along < 0.0 || along > length {
                    continue;
                }
                let k = row + ix;
                if z < g.zb[k] {
                    continue;
                }
                g.zb[k] = z;
                let n0 = q0 + z * f0;
                let n1 = q1 + z * f1;
                let n2 = q2 + z * f2;
                let nn = (n0 * n0 + n1 * n1 + n2 * n2).sqrt();
                let col = shade(base, n0 / nn, n1 / nn, n2 / nn, look);
                let col = fogged([clamp01(col[0]), clamp01(col[1]), clamp01(col[2])], z, fog);
                g.pm[3 * k..3 * k + 3].copy_from_slice(&col);
                g.al[k] = 1.0;
            }
        }
    }
}

/// Ink a covered sample whose depth stands more than `otau` in front of any
/// sample within `ow` samples of it: the silhouette from the depth buffer's
/// discontinuities, read after the atoms and bond halves and before anything
/// else.  The band carries `ow` rows of halo, so a silhouette crossing a band
/// boundary is found from both sides.  The ink fades with the surface it is
/// drawn over: it is fogged at the sample's own depth.
#[allow(clippy::too_many_arguments)]
fn draw_outline(g: &mut Planes, sr0: usize, hs: usize, total: usize, ow: usize, otau: f64,
                ocol: &[f64], fog: Option<Fog>) {
    let ink = [ocol[0], ocol[1], ocol[2]];
    let (ext0, ws) = (g.ext0, g.ws);
    let o = ow as i64;
    for iy in sr0..sr0 + hs {
        let row = (iy - ext0) * ws;
        for ix in 0..ws {
            let z = g.zb[row + ix];
            if z == f64::NEG_INFINITY {
                continue;
            }
            let mut edge = false;
            'disc: for dy in -o..=o {
                let qy = iy as i64 + dy;
                if qy < 0 || qy >= total as i64 {
                    continue;
                }
                let qrow = (qy as usize - ext0) * ws;
                for dx in -o..=o {
                    if dx * dx + dy * dy > o * o {
                        continue;
                    }
                    let qx = ix as i64 + dx;
                    if qx < 0 || qx >= ws as i64 {
                        continue;
                    }
                    if g.zb[qrow + qx as usize] < z - otau {
                        edge = true;
                        break 'disc;
                    }
                }
            }
            if edge {
                let k = 3 * (row + ix);
                g.pm[k..k + 3].copy_from_slice(&fogged(ink, z, fog));
            }
        }
    }
}

/// Segments with a width in samples: the cell frame and polyhedron edges
/// (`depth` true, tested and written like the GUI's line quads), or the
/// letters (`depth` false, drawn over everything).  Only a depth-tested
/// segment is fogged, at its own depth; the letters never are.
fn draw_flat(g: &mut Planes, sg: Segs<'_>, depth: bool, fog: Option<Fog>) {
    let Segs { n, p, half, dir, len, z, col, bx } = sg;
    let (ext0, ext1, ws) = (g.ext0, g.ext0 + g.he, g.ws);
    for i in 0..n {
        let (iy0, iy1) = clip(bx[4 * i], bx[4 * i + 1], ext0, ext1);
        let (ix0, ix1) = clip(bx[4 * i + 2], bx[4 * i + 3], 0, ws);
        if iy0 >= iy1 {
            continue;
        }
        let (ax, ay) = (p[4 * i], p[4 * i + 1]);
        let (dx, dy) = (dir[2 * i], dir[2 * i + 1]);
        let h = half[i];
        let length = len[i];
        let za = z[2 * i];
        let dz = z[2 * i + 1] - z[2 * i];
        let span = length + 2.0 * h;
        for iy in iy0..iy1 {
            let v = iy as f64 + 0.5 - ay;
            let row = (iy - ext0) * ws;
            for ix in ix0..ix1 {
                let u = ix as f64 + 0.5 - ax;
                let along = u * dx + v * dy;
                let across = v * dx - u * dy;
                if across.abs() > h || along < -h || along > length + h {
                    continue;
                }
                let k = row + ix;
                let ink = [col[3 * i], col[3 * i + 1], col[3 * i + 2]];
                let ink = if depth {
                    let zz = za + dz * ((along + h) / span);
                    if zz < g.zb[k] {
                        continue;
                    }
                    g.zb[k] = zz;
                    fogged(ink, zz, fog)
                } else {
                    ink
                };
                g.pm[3 * k..3 * k + 3].copy_from_slice(&ink);
                g.al[k] = 1.0;
            }
        }
    }
}

/// Polyhedron faces, already in drawing order: blended, depth-tested, and
/// writing no depth.  A face's colour is fogged at the sample's depth before
/// it is blended.
fn draw_tris(g: &mut Planes, v: View<'_>, tr: Tris<'_>, alpha: f64, fog: Option<Fog>) {
    let Tris { n, v: tv, area, tie, col, bx } = tr;
    let View { x0, y0, pxs, .. } = v;
    let (ext0, ext1, ws) = (g.ext0, g.ext0 + g.he, g.ws);
    for i in 0..n {
        let (iy0, iy1) = clip(bx[4 * i], bx[4 * i + 1], ext0, ext1);
        let (ix0, ix1) = clip(bx[4 * i + 2], bx[4 * i + 3], 0, ws);
        if iy0 >= iy1 {
            continue;
        }
        let t = &tv[9 * i..9 * i + 9];
        let (ax, ay, az) = (t[0], t[1], t[2]);
        let (bx_, by, bz) = (t[3], t[4], t[5]);
        let (qx, qy, qz) = (t[6], t[7], t[8]);
        let (t0, t1, t2) = (tie[3 * i], tie[3 * i + 1], tie[3 * i + 2]);
        let ar = area[i];
        let base = [col[3 * i], col[3 * i + 1], col[3 * i + 2]];
        for iy in iy0..iy1 {
            let y = y0 - (iy as f64 + 0.5) / pxs;
            let row = (iy - ext0) * ws;
            for ix in ix0..ix1 {
                let x = x0 + (ix as f64 + 0.5) / pxs;
                let ea = (qx - bx_) * (y - by) - (qy - by) * (x - bx_);
                let eb = (ax - qx) * (y - qy) - (ay - qy) * (x - qx);
                let ec = (bx_ - ax) * (y - ay) - (by - ay) * (x - ax);
                if ea < 0.0 || (ea == 0.0 && !t0) {
                    continue;
                }
                if eb < 0.0 || (eb == 0.0 && !t1) {
                    continue;
                }
                if ec < 0.0 || (ec == 0.0 && !t2) {
                    continue;
                }
                let z = (ea * az + eb * bz + ec * qz) / ar;
                let k = row + ix;
                if z < g.zb[k] {
                    continue;
                }
                let c = fogged(base, z, fog);
                for ch in 0..3 {
                    g.pm[3 * k + ch] = alpha * c[ch] + (1.0 - alpha) * g.pm[3 * k + ch];
                }
                g.al[k] = alpha + (1.0 - alpha) * g.al[k];
            }
        }
    }
}

/// The box filter, and the background or straight alpha, into rows
/// `[r0, r0 + rows)` of `out`.
///
/// # Safety
/// `out` is a C-contiguous `height × width × 4` plane covering those rows, and
/// no other thread writes them.
#[allow(clippy::too_many_arguments)]
unsafe fn resolve(g: &Planes, out: *mut u8, r0: usize, rows: usize, width: usize, s: usize,
                  sr0: usize, bg: Option<&[f64]>) {
    let n = (s * s) as f64;
    let ws = g.ws;
    for oy in 0..rows {
        for ox in 0..width {
            let (mut p0, mut p1, mut p2, mut pa) = (0.0, 0.0, 0.0, 0.0);
            for dy in 0..s {
                let srow = (sr0 - g.ext0 + oy * s + dy) * ws;
                for dx in 0..s {
                    let k = srow + ox * s + dx;
                    p0 += g.pm[3 * k];
                    p1 += g.pm[3 * k + 1];
                    p2 += g.pm[3 * k + 2];
                    pa += g.al[k];
                }
            }
            p0 = p0 / n;
            p1 = p1 / n;
            p2 = p2 / n;
            pa = pa / n;
            let rgba = match bg {
                Some(bg) => [p0 + (1.0 - pa) * bg[0], p1 + (1.0 - pa) * bg[1],
                             p2 + (1.0 - pa) * bg[2], 1.0],
                None if pa > 0.0 => [p0 / pa, p1 / pa, p2 / pa, pa],
                None => [0.0, 0.0, 0.0, pa],
            };
            let o = unsafe { out.add(((r0 + oy) * width + ox) * 4) };
            for (ch, v) in rgba.iter().enumerate() {
                unsafe { *o.add(ch) = (clamp01(*v) * 255.0 + 0.5).floor() as u8 };
            }
        }
    }
}

/// Draw output rows `[r0, r1)` into `out` (`height × width × 4`, `uint8`).
///
/// The band's sample rows are `[sr0, sr0 + hs)`; it draws `ow` rows more on
/// each side, `[ext0, ext1)`, for the outline to read.  `raster._band_numpy`
/// is the oracle, and its order of drawing is this one.
///
/// # Safety
/// As [`resolve`].
#[allow(clippy::too_many_arguments)]
unsafe fn band(out: *mut u8, r0: usize, r1: usize, s: usize, height: usize, width: usize,
               v: View<'_>, alpha: f64, bg: Option<&[f64]>, ow: usize, otau: f64, ocol: &[f64],
               at: Atoms<'_>, hv: Halves<'_>, line: Segs<'_>, tri: Tris<'_>, text: Segs<'_>,
               fog: Option<Fog>) {
    let (hs, ws, sr0, total) = ((r1 - r0) * s, width * s, r0 * s, height * s);
    let ext0 = sr0.saturating_sub(ow);
    let ext1 = (sr0 + hs).saturating_add(ow).min(total);
    let he = ext1 - ext0;
    let mut g = Planes {
        ext0, he, ws,
        zb: vec![f64::NEG_INFINITY; he * ws],
        pm: vec![0.0; he * ws * 3],
        al: vec![0.0; he * ws],
    };
    draw_atoms(&mut g, v, at, fog);
    draw_halves(&mut g, v, hv, fog);
    // the outline reads the surfaces alone, so a line is never inked as one
    if ow > 0 {
        draw_outline(&mut g, sr0, hs, total, ow, otau, ocol, fog);
    }
    draw_flat(&mut g, line, true, fog);
    draw_tris(&mut g, v, tri, alpha, fog);
    draw_flat(&mut g, text, false, None);
    unsafe { resolve(&g, out, r0, r1 - r0, width, s, sr0, bg) };
}

// --- the bindings ------------------------------------------------------

/// `render_rows_cued`'s fog as it arrives, before [`render`] checks it.
struct FogArgs<'py> {
    z_start: f64,
    z_end: f64,
    f_max: f64,
    colour: PyReadonlyArray1<'py, f64>,
}

/// Both bindings' checks and their one call of [`band`]; `fog` is `None` for
/// `render_rows`.
#[allow(clippy::too_many_arguments)]
fn render<'py>(
    py: Python<'py>,
    r0: usize,
    r1: usize,
    s: usize,
    height: usize,
    x0: f64,
    y0: f64,
    pxs: f64,
    width: usize,
    look: PyReadonlyArray1<'py, f64>,
    alpha: f64,
    bg: Option<PyReadonlyArray1<'py, f64>>,
    ow: usize,
    otau: f64,
    ocol: PyReadonlyArray1<'py, f64>,
    atom: AtomArgs<'py>,
    half: HalfArgs<'py>,
    line: SegArgs<'py>,
    tri: TriArgs<'py>,
    text: SegArgs<'py>,
    fog: Option<FogArgs<'py>>,
    out: &Bound<'py, PyArray3<u8>>,
) -> PyResult<()> {
    if s == 0 {
        return err("s must be at least 1");
    }
    if r0 > r1 || r1 > height {
        return err(format!("rows {r0}..{r1} outside 0..{height}"));
    }
    // the band's planes are at most the whole picture's samples, three f64
    // channels deep; refused here, a wrapped product would size them in release
    let planes = height.checked_mul(s).zip(width.checked_mul(s))
        .and_then(|(h, w)| h.checked_mul(w)?.checked_mul(3 * size_of::<f64>()));
    if planes.is_none_or(|b| b > isize::MAX as usize) {
        return err(format!("a {height} × {width} picture at {s} samples a side overflows \
                            its sample planes"));
    }
    // the outline's disc test squares offsets up to ow in an i64
    if ow >= 1 << 30 {
        return err(format!("ow {ow} is past 2^30 samples"));
    }
    if !out.is_c_contiguous() {
        return err("out must be C-contiguous");
    }
    if unsafe { (*out.as_array_ptr()).flags } & numpy::npyffi::NPY_ARRAY_WRITEABLE == 0 {
        return err("out must be writeable");
    }
    if out.shape() != [height, width, 4] {
        return err(format!("out has shape {:?}, the picture is [{height}, {width}, 4]",
                           out.shape()));
    }
    let mut ins = Vec::new();
    let (look, _) = arr("look", &look, &[])?;
    if look.len() != LOOK_LEN {
        return err(format!("look has {} entries, the shader reads {LOOK_LEN}", look.len()));
    }
    let (ocol, _) = arr("ocol", &ocol, &[])?;
    if ocol.len() != 3 {
        return err(format!("ocol has {} entries, not 3", ocol.len()));
    }
    let bg = match &bg {
        Some(b) => {
            let (b, nb) = arr("bg", b, &[])?;
            if nb != 3 {
                return err(format!("bg has {nb} entries, not 3"));
            }
            ins.push(span(b));
            Some(b)
        }
        None => None,
    };
    ins.extend([span(look), span(ocol)]);
    let fog = match &fog {
        Some(f) => {
            // the numpy path's refusal, `raster.draw`'s: a NaN end is refused too
            if f.z_start.is_nan() || f.z_end.is_nan() || f.z_start <= f.z_end {
                return err(format!("fog starts at z_start = {}, which is not in front of \
                                    where it ends, z_end = {}", f.z_start, f.z_end));
            }
            let (c, nc) = arr("fog_colour", &f.colour, &[])?;
            if nc != 3 {
                return err(format!("fog_colour has {nc} entries, not 3"));
            }
            ins.push(span(c));
            Some(Fog { z_start: f.z_start, z_end: f.z_end, f_max: f.f_max,
                       colour: [c[0], c[1], c[2]] })
        }
        None => None,
    };
    let at = atoms(&atom, &mut ins)?;
    let hv = halves(&half, &mut ins)?;
    let ln = segs("line", &line, &mut ins)?;
    let tr = tris(&tri, &mut ins)?;
    let tx = segs("text", &text, &mut ins)?;
    let o = out.data();
    disjoint(&[(o as usize, o as usize + out.len())], &ins)?;
    let o = P(o);
    let v = View { x0, y0, pxs, look };
    py.detach(|| unsafe {
        band(o.get(), r0, r1, s, height, width, v, alpha, bg, ow, otau, ocol, at, hv, ln, tr, tx,
             fog)
    });
    Ok(())
}

/// Draw output rows `[r0, r1)` of the picture into `out`, as
/// `raster._band_numpy` does.  `atom`, `half`, `line`, `tri` and `text` are
/// `raster._pack`'s tuples of the same names, `look` its shader constants,
/// `pxs` the samples per Å, and `bg` three channels in 0..1 or `None` for
/// straight alpha.  `ow` is the outline's radius in samples (0 for none),
/// `otau` its depth step and `ocol` its colour.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub(crate) fn render_rows<'py>(
    py: Python<'py>,
    r0: usize,
    r1: usize,
    s: usize,
    height: usize,
    x0: f64,
    y0: f64,
    pxs: f64,
    width: usize,
    look: PyReadonlyArray1<'py, f64>,
    alpha: f64,
    bg: Option<PyReadonlyArray1<'py, f64>>,
    ow: usize,
    otau: f64,
    ocol: PyReadonlyArray1<'py, f64>,
    atom: AtomArgs<'py>,
    half: HalfArgs<'py>,
    line: SegArgs<'py>,
    tri: TriArgs<'py>,
    text: SegArgs<'py>,
    out: &Bound<'py, PyArray3<u8>>,
) -> PyResult<()> {
    render(py, r0, r1, s, height, x0, y0, pxs, width, look, alpha, bg, ow, otau, ocol, atom, half,
           line, tri, text, None, out)
}

/// [`render_rows`] with depth cueing (WP-1548 D1, 1.5.0), as
/// `raster._band_numpy` draws with its `fog`: the atoms, bond halves, lines,
/// outline and faces blend toward `fog_colour` by their own depth, the factor
/// 0 in front of `z_start`, rising linearly to `f_max` at `z_end` and held
/// behind it.  The letters are not fogged.  `z_start` must lie in front of
/// `z_end`, in view coordinates with z toward the viewer.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub(crate) fn render_rows_cued<'py>(
    py: Python<'py>,
    r0: usize,
    r1: usize,
    s: usize,
    height: usize,
    x0: f64,
    y0: f64,
    pxs: f64,
    width: usize,
    look: PyReadonlyArray1<'py, f64>,
    alpha: f64,
    bg: Option<PyReadonlyArray1<'py, f64>>,
    ow: usize,
    otau: f64,
    ocol: PyReadonlyArray1<'py, f64>,
    atom: AtomArgs<'py>,
    half: HalfArgs<'py>,
    line: SegArgs<'py>,
    tri: TriArgs<'py>,
    text: SegArgs<'py>,
    z_start: f64,
    z_end: f64,
    f_max: f64,
    fog_colour: PyReadonlyArray1<'py, f64>,
    out: &Bound<'py, PyArray3<u8>>,
) -> PyResult<()> {
    let fog = FogArgs { z_start, z_end, f_max, colour: fog_colour };
    render(py, r0, r1, s, height, x0, y0, pxs, width, look, alpha, bg, ow, otau, ocol, atom, half,
           line, tri, text, Some(fog), out)
}

/// Which atom or bond half is in front at each pixel, as `raster._ids_numpy`
/// writes it (WP-1503): `render_rows`' atom and half tests without the
/// shading, one sample a pixel, the whole frame in one call.  `atom` is
/// `(atom_c, atom_m, atom_a, atom_box)` and `half` `(half_a, half_w,
/// half_len, half_e, half_ea, half_r, half_box)` from `raster.pack_ids` and
/// `raster._boxes`.  `ids` (`height × width`, `int32`) takes `k` for the
/// `k`-th atom and `n_atoms + k` for the `k`-th half where one wins and is
/// left alone elsewhere; `seen[k]` takes the samples atom `k` would cover were
/// nothing in front of it, for every atom whose box meets the frame.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub(crate) fn id_plane<'py>(
    py: Python<'py>,
    y0: f64,
    x0: f64,
    pxs: f64,
    atom: IdAtomArgs<'py>,
    half: IdHalfArgs<'py>,
    ids: &Bound<'py, PyArray2<i32>>,
    seen: &Bound<'py, PyArray1<i64>>,
) -> PyResult<()> {
    let mut ins = Vec::new();
    let (c, nc) = arr("atom_c", &atom.0, &[3])?;
    let (m, nm) = arr("atom_m", &atom.1, &[3, 3])?;
    let (aa, na) = arr("atom_a", &atom.2, &[])?;
    let (abx, nab) = arr("atom_box", &atom.3, &[4])?;
    let n_at = same_count("atom", &[("atom_c", nc), ("atom_m", nm), ("atom_a", na),
                                    ("atom_box", nab)])?;
    let (ha, n0) = arr("half_a", &half.0, &[3])?;
    let (hw, n1) = arr("half_w", &half.1, &[3])?;
    let (hlen, n2) = arr("half_len", &half.2, &[])?;
    let (he, n3) = arr("half_e", &half.3, &[3])?;
    let (hea, n4) = arr("half_ea", &half.4, &[])?;
    let (hr, n5) = arr("half_r", &half.5, &[])?;
    let (hbx, n6) = arr("half_box", &half.6, &[4])?;
    let n_h = same_count("half", &[("half_a", n0), ("half_w", n1), ("half_len", n2),
                                   ("half_e", n3), ("half_ea", n4), ("half_r", n5),
                                   ("half_box", n6)])?;
    if i32::try_from(n_at + n_h).is_err() {
        return err(format!("{n_at} atoms and {n_h} halves do not fit an int32 id"));
    }
    ins.extend([span(c), span(m), span(aa), span(abx), span(ha), span(hw), span(hlen),
                span(he), span(hea), span(hr), span(hbx)]);
    if !ids.is_c_contiguous() {
        return err("ids must be C-contiguous");
    }
    let (height, width) = (ids.shape()[0], ids.shape()[1]);
    let mut ids = ids.try_readwrite().map_err(|e| PyValueError::new_err(format!("ids: {e}")))?;
    let mut seen = seen.try_readwrite()
        .map_err(|e| PyValueError::new_err(format!("seen: {e}")))?;
    let ids = ids.as_slice_mut().map_err(|e| PyValueError::new_err(format!("ids: {e}")))?;
    let seen = seen.as_slice_mut().map_err(|e| PyValueError::new_err(format!("seen: {e}")))?;
    if seen.len() != n_at {
        return err(format!("seen has {} entries, atom_c has {n_at}", seen.len()));
    }
    disjoint(&[span(ids), span(seen)], &ins)?;
    py.detach(|| {
        let mut zb = vec![f64::NEG_INFINITY; height * width];
        for i in 0..n_at {
            let (iy0, iy1) = clip(abx[4 * i], abx[4 * i + 1], 0, height);
            let (ix0, ix1) = clip(abx[4 * i + 2], abx[4 * i + 3], 0, width);
            if iy0 >= iy1 || ix0 >= ix1 {
                continue;
            }
            let (cx, cy, cz) = (c[3 * i], c[3 * i + 1], c[3 * i + 2]);
            let mi = &m[9 * i..9 * i + 9];
            let (m00, m01, e0) = (mi[0], mi[1], mi[2]);
            let (m10, m11, e1) = (mi[3], mi[4], mi[5]);
            let (m20, m21, e2) = (mi[6], mi[7], mi[8]);
            let a = aa[i];
            let mut count = 0i64;
            for iy in iy0..iy1 {
                let y = y0 - (iy as f64 + 0.5) / pxs - cy;
                for ix in ix0..ix1 {
                    let x = x0 + (ix as f64 + 0.5) / pxs - cx;
                    let q0 = m00 * x + m01 * y;
                    let q1 = m10 * x + m11 * y;
                    let q2 = m20 * x + m21 * y;
                    let b = q0 * e0 + q1 * e1 + q2 * e2;
                    let cc = q0 * q0 + q1 * q1 + q2 * q2 - 1.0;
                    let disc = b * b - a * cc;
                    if disc < 0.0 {
                        continue;
                    }
                    count += 1;
                    let z = cz + (-b + disc.sqrt()) / a;
                    let k = iy * width + ix;
                    if z < zb[k] {
                        continue;
                    }
                    zb[k] = z;
                    ids[k] = i as i32;
                }
            }
            seen[i] = count;
        }
        for i in 0..n_h {
            let (iy0, iy1) = clip(hbx[4 * i], hbx[4 * i + 1], 0, height);
            let (ix0, ix1) = clip(hbx[4 * i + 2], hbx[4 * i + 3], 0, width);
            if iy0 >= iy1 || ix0 >= ix1 {
                continue;
            }
            let (ax, ay, az) = (ha[3 * i], ha[3 * i + 1], ha[3 * i + 2]);
            let (w0, w1, w2) = (hw[3 * i], hw[3 * i + 1], hw[3 * i + 2]);
            let (f0, f1, f2) = (he[3 * i], he[3 * i + 1], he[3 * i + 2]);
            let (a, r, length) = (hea[i], hr[i], hlen[i]);
            for iy in iy0..iy1 {
                let o1 = y0 - (iy as f64 + 0.5) / pxs - ay;
                for ix in ix0..ix1 {
                    let o0 = x0 + (ix as f64 + 0.5) / pxs - ax;
                    let o2 = -az;
                    let oa = o0 * w0 + o1 * w1 + o2 * w2;
                    let q0 = o0 - oa * w0;
                    let q1 = o1 - oa * w1;
                    let q2 = o2 - oa * w2;
                    let b = q0 * f0 + q1 * f1 + q2 * f2;
                    let disc = b * b - a * (q0 * q0 + q1 * q1 + q2 * q2 - r * r);
                    if disc < 0.0 {
                        continue;
                    }
                    let z = (-b + disc.sqrt()) / a;
                    let along = oa + z * w2;
                    if along < 0.0 || along > length {
                        continue;
                    }
                    let k = iy * width + ix;
                    if z < zb[k] {
                        continue;
                    }
                    zb[k] = z;
                    ids[k] = (n_at + i) as i32;
                }
            }
        }
    });
    Ok(())
}
