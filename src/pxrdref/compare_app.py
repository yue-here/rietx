"""``pxrdref compare`` — a browser UI for comparing refinement settings.

    pxrdref compare              # → http://127.0.0.1:8730
    pxrdref compare --open --port 9000 --data /path/to/tests/data

Pick a standard, tick the variants to compare, press Run. The server refines
each (standard, variant) pair in a worker thread, caches the reduced result,
and the page draws three linked panels — see :mod:`pxrdref.viz.compare` for
what each one answers and why the third one is the load-bearing view.

Same architecture as ``pxrdref watch``: stdlib ``http.server``, plain fetch
polling, no FastAPI, no websockets, no javascript build step. plotly.js is
served from the installed ``plotly`` package, so the page is fully offline —
a strict-CSP or air-gapped machine needs no exception.

Runs are cached in memory keyed by ``(standard, variant)``. Re-ticking a
variant you already ran is instant, which is the point: the loop this supports
is *change one thing, look, change it back*.
"""

from __future__ import annotations

import http.server
import json
import threading
import webbrowser
from dataclasses import asdict
from pathlib import Path

from .viz import compare as cmp

DEFAULT_PORT = 8730


class _State:
    """Run cache + one background worker, shared by every request thread."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.lock = threading.Lock()
        self.records: dict[tuple[str, str], dict] = {}
        self.pending: set[tuple[str, str]] = set()
        self.log: list[str] = []
        self.worker: threading.Thread | None = None

    # -- worker ------------------------------------------------------
    def request(self, standard: str, variants: list[str]) -> None:
        """Queue the (standard, variant) pairs that are not already cached."""
        with self.lock:
            wanted = [(standard, v) for v in variants
                      if (standard, v) not in self.records]
            self.pending.update(wanted)
            busy = self.worker is not None and self.worker.is_alive()
        if wanted and not busy:
            self.worker = threading.Thread(target=self._drain, daemon=True)
            self.worker.start()

    def _drain(self) -> None:
        while True:
            with self.lock:
                if not self.pending:
                    return
                key = sorted(self.pending)[0]
                self.pending.discard(key)
            standard, variant = key
            self._note(f"running {standard} / {variant} …")
            try:
                record = asdict(cmp.run(standard, variant, data_dir=self.data_dir))
            except Exception as exc:  # registry/dataset problem, not a fit failure
                record = {"standard": standard, "variant": variant,
                          "status": "error", "error": f"{type(exc).__name__}: {exc}",
                          "seconds": 0.0, "rwp": None, "gof": None, "chi2": None,
                          "rp": None, "n_free": 0, "n_points": 0,
                          "durbin_watson": None, "esd_inflation": None,
                          "two_theta": [], "y_obs": [], "y_calc": [],
                          "y_background": [], "delta": [], "cumulative_chi2": [],
                          "ticks": {}, "diagnostics": [], "parameters": []}
            with self.lock:
                self.records[key] = record
            done = record.get("error") or (
                f"Rwp {record['rwp']:.4f}  GoF {record['gof']:.3f}"
                if record.get("rwp") is not None else record.get("status"))
            self._note(f"  {standard} / {variant}: {done} "
                       f"({record['seconds']:.1f} s)")

    def _note(self, line: str) -> None:
        with self.lock:
            self.log.append(line)
            del self.log[:-200]

    # -- reads -------------------------------------------------------
    def snapshot(self, standard: str, variants: list[str]) -> dict:
        with self.lock:
            ready = {v: self.records[(standard, v)] for v in variants
                     if (standard, v) in self.records}
            running = sorted(v for s, v in self.pending if s == standard)
            busy = self.worker is not None and self.worker.is_alive()
            return {"records": ready, "queued": running, "busy": busy,
                    "log": list(self.log[-40:])}


def _plotly_js() -> str:
    try:
        from plotly.offline import get_plotlyjs
    except ImportError:  # pragma: no cover - exercised by the missing-dep path
        return ("document.body.innerHTML = '<p style=\"font:14px sans-serif;"
                "padding:2rem\">This page needs plotly: "
                "<code>pip install \\'pxrd-refine[viz]\\'</code></p>';")
    return get_plotlyjs()


def _handler(state: _State):
    page = _PAGE

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "pxrdref-compare"

        def log_message(self, *args) -> None:  # quiet by default
            pass

        def _send(self, body: bytes, content_type: str, code: int = 200) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload: dict, code: int = 200) -> None:
            self._send(json.dumps(payload).encode("utf-8"),
                       "application/json; charset=utf-8", code)

        def do_GET(self) -> None:  # noqa: N802 - stdlib API
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                self._send(page.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/plotly.js":
                self._send(_plotly_js().encode("utf-8"),
                           "application/javascript; charset=utf-8")
            elif path == "/api/catalog":
                self._json(cmp.catalog(state.data_dir))
            elif path.startswith("/api/state"):
                query = dict(p.split("=", 1) for p in
                             self.path.partition("?")[2].split("&") if "=" in p)
                standard = query.get("standard", "")
                variants = [v for v in query.get("variants", "").split(",") if v]
                self._json(state.snapshot(standard, variants))
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:  # noqa: N802 - stdlib API
            if self.path != "/api/run":
                self._json({"error": "not found"}, 404)
                return
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            standard = body.get("standard", "")
            variants = list(body.get("variants", []))
            if standard not in cmp.STANDARD_BY_KEY:
                self._json({"error": f"unknown standard {standard!r}"}, 400)
                return
            state.request(standard, variants)
            self._json({"queued": variants})

    return Handler


def serve(data_dir: Path | None = None, *, port: int = DEFAULT_PORT,
          open_browser: bool = False) -> None:
    data_dir = Path(data_dir) if data_dir is not None else cmp.default_data_dir()
    state = _State(data_dir)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), _handler(state))
    url = f"http://127.0.0.1:{port}"
    available = [s.key for s in cmp.STANDARDS if s.available(data_dir)]
    print(f"pxrdref compare — {url}")
    print(f"  data: {data_dir}")
    print(f"  standards available: {', '.join(available) or '(none found)'}")
    if not available:
        print("  hint: pass --data <dir> pointing at a checkout's tests/data")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="pxrdref compare",
        description="Compare refinement settings on the bundled standards.")
    parser.add_argument("--data", type=Path, default=None,
                        help="directory holding the standards (default: the "
                             "checkout's tests/data)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--open", action="store_true", dest="open_browser",
                        help="open a browser window")
    args = parser.parse_args(argv)
    serve(args.data, port=args.port, open_browser=args.open_browser)
    return 0


# ----------------------------------------------------------------------
# the page
# ----------------------------------------------------------------------
_PAGE = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>pxrdref — compare settings</title>
<script src="/plotly.js"></script>
<style>
  :root { color-scheme: light dark; --fg:#1b1b1b; --bg:#fbfbfa; --panel:#fff;
          --line:#dcdcd6; --muted:#6b6b66; --accent:#1f5fa8; }
  @media (prefers-color-scheme: dark) {
    :root { --fg:#e6e6e2; --bg:#151515; --panel:#1e1e1e; --line:#333;
            --muted:#9a9a94; --accent:#7fb2ea; }
  }
  * { box-sizing: border-box; }
  body { margin:0; display:flex; height:100vh; color:var(--fg);
         background:var(--bg); font:13px/1.45 ui-sans-serif, system-ui, sans-serif; }
  #side { flex:0 0 320px; overflow-y:auto; padding:14px; border-right:1px solid var(--line);
          background:var(--panel); }
  #main { flex:1 1 auto; overflow-y:auto; padding:14px 18px; }
  h1 { font-size:15px; margin:0 0 2px; letter-spacing:.02em; }
  h2 { font-size:12px; text-transform:uppercase; letter-spacing:.08em;
       color:var(--muted); margin:18px 0 6px; font-weight:600; }
  .sub { color:var(--muted); font-size:11px; margin:0 0 14px; }
  label { display:block; padding:4px 0; cursor:pointer; }
  label.row { display:flex; gap:7px; align-items:flex-start; }
  label input { margin-top:2px; flex:0 0 auto; }
  .desc { color:var(--muted); font-size:11px; margin:1px 0 0 22px; }
  select, button { font:inherit; }
  select { width:100%; padding:6px; background:var(--bg); color:var(--fg);
           border:1px solid var(--line); border-radius:5px; }
  button { padding:7px 14px; border-radius:5px; border:1px solid var(--accent);
           background:var(--accent); color:#fff; cursor:pointer; font-weight:600; }
  button:disabled { opacity:.5; cursor:default; }
  button.ghost { background:transparent; color:var(--accent); font-weight:400; }
  table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }
  th, td { text-align:right; padding:4px 8px; border-bottom:1px solid var(--line);
           white-space:nowrap; }
  th:first-child, td:first-child { text-align:left; }
  th { color:var(--muted); font-weight:600; font-size:11px; text-transform:uppercase;
       letter-spacing:.05em; }
  .best { font-weight:700; }
  .plot { height:300px; margin-bottom:6px; }
  .note { color:var(--muted); font-size:11px; margin:0 0 12px; max-width:70ch; }
  .diag { margin:2px 0; padding:5px 8px; border-left:3px solid #c93; border-radius:3px;
          background:rgba(200,150,50,.10); font-size:11.5px; }
  .diag.info { border-left-color:#59a; background:rgba(80,150,190,.10); }
  .diag code { font-weight:700; }
  #log { font:11px ui-monospace, Menlo, monospace; color:var(--muted);
         white-space:pre-wrap; margin-top:10px; max-height:150px; overflow-y:auto; }
  .swatch { display:inline-block; width:9px; height:9px; border-radius:2px;
            margin-right:5px; vertical-align:baseline; }
  .warn { color:#b3541e; }
</style></head><body>
<div id="side">
  <h1>pxrdref · compare settings</h1>
  <p class="sub">Does this correction actually make the fit better — and where?</p>

  <h2>Standard</h2>
  <select id="standard"></select>
  <p class="desc" id="standard-desc" style="margin-left:0"></p>

  <h2>Variants</h2>
  <div id="variants"></div>

  <h2>Reference for &Delta;&chi;&sup2;</h2>
  <select id="reference"></select>

  <div style="margin-top:14px; display:flex; gap:8px;">
    <button id="run">Run</button>
    <button id="clear" class="ghost">Clear plots</button>
  </div>
  <div id="log"></div>
</div>

<div id="main">
  <h2>Cumulative &Delta;&chi;&sup2; vs the reference</h2>
  <p class="note">&Sigma;<sub>2&theta;'&le;2&theta;</sub>(&delta;&sup2;<sub>variant</sub> &minus;
    &delta;&sup2;<sub>ref</sub>). <b>Falling = winning</b>, rising = losing, flat = doing
    nothing. The slope says <i>where</i> the change acted, which is what separates a
    correction that models physics from one that absorbs it. The endpoint is the whole
    &chi;&sup2; difference.</p>
  <div id="plot-cum" class="plot"></div>

  <h2>Weighted residual (y<sub>obs</sub> &minus; y<sub>calc</sub>)/&sigma;</h2>
  <p class="note">Same vertical scale for every variant, so smaller is literally better.</p>
  <div id="plot-diff" class="plot"></div>

  <h2>Observed and calculated</h2>
  <div id="plot-fit" class="plot"></div>

  <h2>Statistics</h2>
  <p class="note">Read the diagnostics below before believing a Rwp improvement.
    Some variants here <i>cannot</i> change Rwp by construction — capillary
    absorption is an exact reparameterisation of the scale and B<sub>iso</sub> —
    so the parameter columns are where their effect shows up.</p>
  <div id="stats"></div>

  <h2>Diagnostics</h2>
  <div id="diagnostics"></div>

  <h2>Refined parameters</h2>
  <div id="params"></div>
</div>

<script>
const COLORS = ["#1f5fa8","#c23b22","#2e8b57","#8a5cc4","#c98a17","#0f8f9c",
                "#b3487e","#6b7280","#4b7f1f","#a1421f"];
let CATALOG = null, RECORDS = {}, POLL = null;

const $ = (id) => document.getElementById(id);
const chosenVariants = () =>
  [...document.querySelectorAll('#variants input:checked')].map(el => el.value);

async function boot() {
  CATALOG = await (await fetch('/api/catalog')).json();
  const sel = $('standard');
  for (const s of CATALOG.standards) {
    const opt = document.createElement('option');
    opt.value = s.key;
    opt.textContent = s.available ? s.title : s.title + '  (data missing)';
    opt.disabled = !s.available;
    sel.appendChild(opt);
  }
  const first = CATALOG.standards.find(s => s.available);
  if (first) sel.value = first.key;
  sel.onchange = () => { RECORDS = {}; renderVariants(); draw(); };
  $('run').onclick = run;
  $('clear').onclick = () => { RECORDS = {}; draw(); };
  renderVariants();
}

function currentStandard() {
  return CATALOG.standards.find(s => s.key === $('standard').value);
}

function renderVariants() {
  const std = currentStandard();
  $('standard-desc').innerHTML = std ? std.description : '';
  const box = $('variants');
  box.innerHTML = '';
  for (const v of CATALOG.variants) {
    if (std && !std.variants.includes(v.key)) continue;
    const lab = document.createElement('label');
    lab.className = 'row';
    lab.innerHTML =
      `<input type="checkbox" value="${v.key}" ${v.key === 'baseline' ? 'checked' : ''}>` +
      `<span><b>${v.title}</b><span class="desc" style="margin-left:0;display:block">` +
      `${v.description}</span></span>`;
    lab.querySelector('input').onchange = syncReference;
    box.appendChild(lab);
  }
  syncReference();
}

function syncReference() {
  const ref = $('reference'), previous = ref.value;
  ref.innerHTML = '';
  for (const key of chosenVariants()) {
    const v = CATALOG.variants.find(x => x.key === key);
    const opt = document.createElement('option');
    opt.value = key; opt.textContent = v.title;
    ref.appendChild(opt);
  }
  ref.value = [...ref.options].some(o => o.value === previous)
    ? previous : (ref.options[0] ? ref.options[0].value : '');
  ref.onchange = draw;
}

async function run() {
  const standard = $('standard').value, variants = chosenVariants();
  if (!variants.length) return;
  $('run').disabled = true;
  await fetch('/api/run', {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({standard, variants})});
  if (POLL) clearInterval(POLL);
  POLL = setInterval(poll, 700);
  poll();
}

async function poll() {
  const standard = $('standard').value, variants = chosenVariants();
  const q = `standard=${standard}&variants=${variants.join(',')}`;
  const s = await (await fetch('/api/state?' + q)).json();
  RECORDS = s.records;
  $('log').textContent = s.log.join('\n');
  $('log').scrollTop = $('log').scrollHeight;
  draw();
  const outstanding = variants.some(v => !(v in RECORDS));
  if (!outstanding && !s.busy) {
    clearInterval(POLL); POLL = null; $('run').disabled = false;
  }
}

const LAYOUT = (title, ytitle) => ({
  margin: {l: 62, r: 12, t: 6, b: 38}, showlegend: true,
  legend: {orientation: 'h', y: 1.14, x: 0},
  xaxis: {title: {text: '2θ (°)'}, zeroline: false},
  yaxis: {title: {text: ytitle}, zeroline: true, zerolinecolor: '#9995'},
  paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
  font: {color: getComputedStyle(document.body).color, size: 11},
});

function ok(r) { return r && !r.error && r.two_theta && r.two_theta.length; }

// Linear resample of (xs, ys) onto `at`; both are ascending, so one merged walk.
function resample(xs, ys, at) {
  const out = new Array(at.length);
  let j = 0;
  for (let i = 0; i < at.length; i++) {
    const x = at[i];
    while (j < xs.length - 2 && xs[j + 1] < x) j++;
    const x0 = xs[j], x1 = xs[j + 1], y0 = ys[j], y1 = ys[j + 1];
    const t = (x1 === x0) ? 0 : (x - x0) / (x1 - x0);
    out[i] = y0 + t * (y1 - y0);
  }
  return out;
}

function draw() {
  const variants = chosenVariants();
  const refKey = $('reference').value;
  const ref = RECORDS[refKey];
  const color = (k) => COLORS[CATALOG.variants.findIndex(v => v.key === k) % COLORS.length];
  const title = (k) => (CATALOG.variants.find(v => v.key === k) || {}).title || k;

  // -- cumulative Δχ² against the reference.
  // Each variant is decimated on its OWN min/max index set, so the arrays are
  // not aligned point-for-point (measured: 5873 vs 5875 on the same pattern).
  // Interpolating the reference onto the variant's 2θ is exact enough — the
  // cumulative curve is monotone, and both are sampled from the same underlying
  // grid — and it is what keeps this panel from silently rendering empty.
  const cum = [];
  if (ok(ref)) {
    for (const k of variants) {
      const r = RECORDS[k];
      if (!ok(r) || k === refKey) continue;
      const base = resample(ref.two_theta, ref.cumulative_chi2, r.two_theta);
      cum.push({x: r.two_theta, type: 'scattergl', mode: 'lines', name: title(k),
                line: {width: 1.6, color: color(k)},
                y: r.cumulative_chi2.map((c, i) => c - base[i])});
    }
  }
  Plotly.react('plot-cum', cum,
    Object.assign(LAYOUT('', 'Δχ² vs ' + title(refKey)), {}), {responsive: true});

  // -- weighted residuals
  const diff = variants.filter(k => ok(RECORDS[k])).map(k => ({
    x: RECORDS[k].two_theta, y: RECORDS[k].delta, type: 'scattergl', mode: 'lines',
    name: title(k), line: {width: 1, color: color(k)}}));
  Plotly.react('plot-diff', diff, LAYOUT('', '(obs − calc)/σ'), {responsive: true});

  // -- obs + calc, with a reflection tick row per phase.  The ticks are what
  // make the Δχ² panel readable: a step there belongs to a reflection, and
  // knowing which one is the difference between "this correction helped" and
  // "this correction helped at the low-angle reflections, as its physics says".
  const fit = [];
  const anyRec = variants.map(k => RECORDS[k]).find(ok);
  if (anyRec) {
    const lo = Math.min(...anyRec.y_obs), hi = Math.max(...anyRec.y_obs);
    const span = (hi - lo) || 1;
    fit.push({x: anyRec.two_theta, y: anyRec.y_obs, type: 'scattergl', mode: 'markers',
              name: 'observed', marker: {size: 2.5, color: '#8888'}});
    for (const k of variants) {
      if (!ok(RECORDS[k])) continue;
      fit.push({x: RECORDS[k].two_theta, y: RECORDS[k].y_calc, type: 'scattergl',
                mode: 'lines', name: title(k), line: {width: 1.1, color: color(k)}});
    }
    const phases = Object.keys(anyRec.ticks || {});
    phases.forEach((phase, i) => {
      const y = lo - span * (0.06 + 0.045 * i);
      fit.push({x: anyRec.ticks[phase], y: anyRec.ticks[phase].map(() => y),
                type: 'scattergl', mode: 'markers', name: phase,
                marker: {symbol: 'line-ns-open', size: 7, line: {width: 1},
                         color: COLORS[(i + 4) % COLORS.length]},
                hovertemplate: phase + ' %{x:.3f}°<extra></extra>'});
    });
  }
  Plotly.react('plot-fit', fit, LAYOUT('', 'intensity'), {responsive: true});

  drawStats(variants, title, color);
  drawDiagnostics(variants, title);
  drawParams(variants, title);
}

function drawStats(variants, title, color) {
  const rows = variants.filter(k => RECORDS[k]);
  if (!rows.length) { $('stats').innerHTML = '<p class="note">Nothing run yet.</p>'; return; }
  const num = (v, d) => (v === null || v === undefined || Number.isNaN(v))
    ? '—' : Number(v).toFixed(d);
  const bestRwp = Math.min(...rows.filter(k => ok(RECORDS[k])).map(k => RECORDS[k].rwp));
  let html = '<table><tr><th>variant</th><th>Rwp</th><th>Rp</th><th>GoF</th>' +
             '<th>χ²</th><th>DW</th><th>esd×</th><th>free</th><th>status</th>' +
             '<th>time</th></tr>';
  for (const k of rows) {
    const r = RECORDS[k];
    if (r.error) {
      html += `<tr><td><span class="swatch" style="background:${color(k)}"></span>` +
              `${title(k)}</td><td colspan="9" class="warn">${r.error}</td></tr>`;
      continue;
    }
    const cls = Math.abs(r.rwp - bestRwp) < 1e-12 ? ' class="best"' : '';
    html += `<tr><td><span class="swatch" style="background:${color(k)}"></span>` +
      `${title(k)}</td><td${cls}>${num(r.rwp, 5)}</td><td>${num(r.rp, 5)}</td>` +
      `<td>${num(r.gof, 3)}</td><td>${num(r.chi2, 3)}</td>` +
      `<td>${num(r.durbin_watson, 3)}</td><td>${num(r.esd_inflation, 2)}</td>` +
      `<td>${r.n_free}</td><td>${r.status}</td><td>${num(r.seconds, 1)} s</td></tr>`;
  }
  $('stats').innerHTML = html + '</table>';
}

function drawDiagnostics(variants, title) {
  let html = '';
  for (const k of variants) {
    const r = RECORDS[k];
    if (!r || !r.diagnostics || !r.diagnostics.length) continue;
    html += `<p class="note" style="margin:12px 0 3px"><b>${title(k)}</b></p>`;
    for (const d of r.diagnostics) {
      html += `<div class="diag ${d.level}"><code>${d.code}</code> ` +
              `${d.where.length ? '<i>' + d.where.join(', ') + '</i> — ' : ''}` +
              `${d.message}</div>`;
    }
  }
  $('diagnostics').innerHTML = html ||
    '<p class="note">No diagnostics raised (or nothing run yet).</p>';
}

function drawParams(variants, title) {
  const rows = variants.filter(k => ok(RECORDS[k]));
  if (!rows.length) { $('params').innerHTML = ''; return; }
  const paths = [];
  for (const k of rows) for (const p of RECORDS[k].parameters)
    if (!paths.includes(p.path)) paths.push(p.path);
  paths.sort();
  let html = '<table><tr><th>parameter</th>' +
    rows.map(k => `<th>${title(k)}</th>`).join('') + '</tr>';
  for (const path of paths) {
    html += `<tr><td>${path}</td>`;
    for (const k of rows) {
      const p = RECORDS[k].parameters.find(x => x.path === path);
      html += '<td>' + (p ? fmt(p.value, p.stderr) : '—') + '</td>';
    }
    html += '</tr>';
  }
  $('params').innerHTML = html + '</table>';
}

function fmt(value, stderr) {
  const mag = Math.abs(value);
  const digits = mag >= 100 ? 3 : mag >= 1 ? 5 : 6;
  const v = Number(value).toFixed(digits);
  return stderr ? `${v} <span style="opacity:.6">±${Number(stderr).toPrecision(2)}</span>` : v;
}

boot();
</script>
</body></html>
"""
