<script lang="ts">
  /**
   * The FitReport, rendered — and, where the package has a verb for it, applied.
   *
   * The report's founding rule is that it must never hand back a confident wrong
   * singleton, and a renderer can break that without touching a number. So four
   * things here are deliberate rather than incidental. An **abstention renders as
   * an abstention** (Layer 1 refusing is a finding, not an empty panel). A
   * **vetoed suggestion is greyed with the veto as its reason, never hidden** —
   * the veto is the reasoning. A **non-separable attribution is labelled**, since
   * its confidence has already been capped and the alternatives it could not rule
   * out travel with it. And the **predicted Δχ² is shown once**, at the top: it is
   * one estimate for the whole report (`build_report` stamps the same figure on
   * every action) and it bounds only the misfit attributed inside the gated
   * regions, so a per-row column would invent a per-action prediction — measured
   * 16.19 predicted against 16.33 observed (`tests/test_report_apply.py`).
   *
   * Which suggestions have buttons is **not decided here**: `GET /api/report`
   * carries an `apply` arm per action, so the enabled-ness of a button is the
   * route's own willingness to act rather than a rule this file re-derives.
   */
  import { ApiError, api } from "../api";
  import Help from "../Help.svelte";
  import {
    actionRows, diagnosticTone, headline, orderDiagnostics, predictionNote,
    underNote, worstRegions, zoomWindow, type FitDiagnostic,
  } from "../lib/report";
  import { num } from "../lib/table";

  let {
    head = null,
    busy = false,
    simple = true,
    chi2 = null,
    diagnostics = [],
    applied = null,
    say = (_line: string) => {},
    onzoom = (_lo: number, _hi: number) => {},
    onapplied = (_payload: any) => {},
    onmoved = () => {},
  }: {
    head?: string | null;
    busy?: boolean;
    simple?: boolean;
    chi2?: number | null;
    /** the result's own diagnostics (`/api/result`), which App already holds */
    diagnostics?: FitDiagnostic[];
    applied?: { kind: string; chi2_before: number; predicted: number | null; undo: string } | null;
    say?: (line: string) => void;
    onzoom?: (lo: number, hi: number) => void;
    onapplied?: (payload: any) => void;
    onmoved?: () => void;
  } = $props();

  let report = $state<any>(null);
  let arms = $state<any[]>([]);
  let empty = $state("");
  let error = $state("");

  const head_ = $derived(report ? headline(report) : null);
  const rows = $derived(report ? actionRows(report.suggested_actions ?? [], arms) : []);
  const fitDiagnostics = $derived(orderDiagnostics(diagnostics));
  const regions = $derived(report ? worstRegions(report.regions ?? []) : []);
  // `null` while the stage is still running, not 0: `chi2` is the *last* result's,
  // which is the one the action was applied at, so subtracting mid-run would print
  // a confident "observed 0.000" for a measurement that has not been made yet
  const observed = $derived(
    !busy && applied && chi2 !== null && chi2 !== undefined
      ? applied.chi2_before - chi2
      : null,
  );

  async function load() {
    // idle-only: Layers 1-2 read the compiled model a stage would be rewriting,
    // so mid-run the route 409s and the panel keeps the last report it had
    if (busy) return;
    try {
      const payload = await api.report();
      report = payload.report;
      arms = payload.apply ?? [];
      empty = "";
      error = "";
    } catch (exc) {
      if (exc instanceof ApiError && exc.empty) {
        report = null;
        empty = "No fit to report on yet. Run the plan — or, if you just moved the "
              + "history, run again: a checkout restores values, not a fit.";
      } else if (!(exc instanceof ApiError && exc.busy)) {
        error = (exc as Error).message;
      }
    }
  }

  $effect(() => {
    void head;
    void busy;
    load();
  });

  async function apply(kind: string, paths: string[]) {
    try {
      // no echo here: the shell prints the `api_call` the *server* said it would
      // run, once, on the way back — echoing the arm's copy first would print the
      // same line twice, and looking the arm up by kind would be wrong anyway
      // (two textured phases share a kind)
      const payload = await api.applyAction(kind, paths);
      onapplied(payload);
      error = "";
    } catch (exc) {
      // ACTION_NOT_APPLICABLE carries the veto or the held reason verbatim; a
      // 409 while running is the ordinary "wait" case
      error = exc instanceof ApiError && exc.busy
        ? "a run is in flight — nothing can be applied until it ends"
        : (exc as Error).message;
    }
  }

  async function undo(nodeId: string) {
    try {
      say(`ref.checkout(${JSON.stringify(nodeId)})  # undo the applied action`);
      await api.checkout(nodeId);
      onapplied(null);
      onmoved();
    } catch (exc) {
      error = (exc as Error).message;
    }
  }

  function zoom(lo: number, hi: number) {
    const [a, b] = zoomWindow(lo, hi);
    onzoom(a, b);
  }
</script>

<section>
  {#if error}<p class="bad">{error}</p>{/if}

  {#if !report}
    <p class="muted pad">{empty || "loading the report…"}</p>
  {:else}
    {@const h = head_!}
    <div class="scroller">
      <div class="head">
        <span class="mono tabular">Rwp <strong>{(h.rwp * 100).toFixed(3)}%</strong></span>
        <span class="mono tabular muted">GoF {h.gof.toFixed(3)}</span>
        <span class="muted">Layer 1 on {h.gated} regions</span>
        <!-- two counts, not one: an observed peak with no tick is an impurity or a
             wrong cell, while a calculated peak with no intensity is what a
             *mispositioned* model produces at every peak. One badge for both read
             "15 unindexed" beside a summary saying "0 unmatched observed peak(s)" -->
        {#if h.unindexed}
          <span class="chip warn" title="observed peaks with no calculated reflection nearby">
            {h.unindexed} unindexed</span>
        {/if}
        {#if h.unobserved}
          <span class="chip" title="calculated peaks with no observed intensity — a
mispositioned or absent phase, not an impurity">
            {h.unobserved} unobserved</span>
        {/if}
        <span class="muted mono">v{report.thresholds_version}</span>
      </div>

      <p class="summary">{report.summary}</p>

      {#if h.abstained}
        <!-- an abstention is a finding: Layer 1 refused, and the reason is the
             information. Rendering it as an empty panel would be the one thing
             the report's design exists to prevent -->
        <p class="abstain">Layer 1 abstained — {h.abstained}</p>
      {/if}

      {#if h.refusedBy.length}
        <p class="muted">
          gates refused:
          {#each h.refusedBy as entry (entry)}<span class="chip">{entry}</span>{/each}
        </p>
      {/if}

      {#if applied}
        <div class="applied">
          <strong>applied {applied.kind}</strong>
          <span class="mono tabular">
            predicted Δχ² {applied.predicted === null ? "—" : applied.predicted.toPrecision(4)}
            · observed {observed === null ? "running…" : observed.toPrecision(4)}
          </span>
          <span class="spacer"></span>
          <button class="ghost" disabled={busy} onclick={() => undo(applied!.undo)}
            title="check out the node this project stood at before the action">
            Undo</button>
        </div>
      {/if}

      <!-- the answer's own diagnostics: produced by the package, shown by no
           other panel (a node holds only those committed with it).  All of
           them, errors first; a level is a chip tone, never a filter.  Which
           rows open is the server's (`full`, WP-2037): the errors, as
           `str(result)` prints them in full.  Every other row is folded to
           its code, its paths and what it is a warning under, the code's
           explanation one click away beside it -->
      {#if fitDiagnostics.length}
        <h3>Fit diagnostics</h3>
        {#each fitDiagnostics as d (d.code + d.message)}
          {@const under = underNote(d)}
          <details class="fitdiag" data-level={d.level} open={d.full === true}>
            <summary>
              <span class="line">
                <span class="chip {diagnosticTone(d.level)}">{d.level}</span>
                <strong class="kind mono"
                  ><Help for="diagnostics:{d.code}">{d.code}</Help></strong>
              </span>
              {#if under}<span class="under muted">{under}</span>{/if}
              {#if d.where?.length}<span class="paths mono muted">{d.where.join("  ")}</span>{/if}
            </summary>
            <p class="why">{d.message}</p>
            {#if d.suggestion}<p class="muted">{d.suggestion}</p>{/if}
          </details>
        {/each}
      {/if}

      <!-- Layer 2 -->
      <h3>Suggestions</h3>
      {#if h.predicted !== null}
        <p class="muted">{predictionNote(h)}</p>
      {/if}
      {#if !rows.length}
        <p class="muted">Nothing suggested — on a converged fit that is the
          right answer, not a missing panel.</p>
      {/if}
      {#each rows as row (row.action.kind + row.action.parameter_paths.join(","))}
        {@const arm = row.arm}
        <div class="action" data-tone={row.tone} class:off={!arm?.can_apply}>
          <div class="line">
            <span class="conf mono tabular" title="confidence: importance × quality, capped on ambiguity">
              {num(row.action.confidence).toFixed(2)}
            </span>
            <strong class="kind mono">{row.action.kind}</strong>
            {#if arm && arm.how !== "stage"}<span class="chip">{arm.how}</span>{/if}
            <span class="spacer"></span>
            {#if row.action.two_theta_range}
              <button class="ghost" onclick={() =>
                zoom(row.action.two_theta_range![0], row.action.two_theta_range![1])}
                title="zoom the plot to where this was measured">
                {row.action.two_theta_range[0].toFixed(2)}°</button>
            {/if}
            {#if arm?.can_apply}
              <button disabled={busy}
                title={arm.api_call ?? ""}
                onclick={() => apply(row.action.kind, row.action.parameter_paths)}>
                Apply</button>
            {/if}
          </div>
          <p class="why">{row.action.rationale}</p>
          <p class="paths mono muted">{row.action.parameter_paths.join("  ")}</p>
          {#if row.action.alternatives.length}
            <p class="muted">could not rule out: {row.action.alternatives.join(", ")}</p>
          {/if}
          {#if arm && !arm.can_apply}
            <!-- greyed with the reason, never hidden: the veto *is* the reasoning,
                 and an advice note is the action's whole deliverable -->
            <p class="refusal">{arm.refusal}</p>
          {/if}
        </div>
      {/each}

      <!-- Layer 0 -->
      <h3>Worst regions</h3>
      <div class="table">
        {#each regions as region (region.two_theta_lo)}
          <button class="trow pick" onclick={() => zoom(region.two_theta_lo, region.two_theta_hi)}
            title="zoom the plot to this window">
            <span class="mono tabular">{region.two_theta_lo.toFixed(2)}–{region.two_theta_hi.toFixed(2)}°</span>
            <span class="mono tabular">{(num(region.chi2_share) * 100).toFixed(1)}% χ²</span>
            <span class="mono tabular muted">Rwp {(num(region.local_rwp) * 100).toFixed(1)}%</span>
            <span class="mono tabular muted">|Δ|/σ {num(region.max_abs_delta_over_sigma).toFixed(0)}</span>
            <span class="mono tabular muted">{region.n_reflections} hkl</span>
          </button>
        {/each}
      </div>

      {#if report.unmatched?.length}
        <h3>Peaks with no partner</h3>
        <div class="table">
          {#each report.unmatched.slice(0, 10) as peak (peak.two_theta + peak.kind)}
            <button class="trow pick" onclick={() => zoom(peak.two_theta - 0.3, peak.two_theta + 0.3)}>
              <span class="mono tabular">{peak.two_theta.toFixed(3)}°</span>
              <span class="mono tabular">{num(peak.height_over_sigma).toFixed(0)}σ</span>
              <span class="muted">{peak.kind === "unmatched_obs"
                ? "observed, no reflection" : "calculated, no intensity"}</span>
            </button>
          {/each}
        </div>
      {/if}

      <!-- Layer 1, behind the disclosure: these are the per-region coefficients,
           and reading them at all requires knowing what a gate is -->
      {#if !simple}
        <h3>Trends</h3>
        {#each report.trends ?? [] as trend (trend.observable)}
          <div class="trend">
            <strong>{trend.observable}</strong>
            <span class="muted">{(num(trend.misfit_share) * 100).toFixed(0)}% of χ²,
              {trend.n_regions_used} regions</span>
            {#if !trend.separable}
              <span class="chip warn" title="|r|={num(trend.max_template_collinearity).toFixed(3)}">
                not separable</span>
            {/if}
            <div class="templates mono">
              {#each trend.templates as t (t.name)}
                <span class:best={t.r2 === Math.max(...trend.templates.map((x: any) => num(x.r2)))}>
                  {t.name} {num(t.coefficient).toPrecision(3)}±{num(t.stderr).toPrecision(2)}
                  (R²{num(t.r2).toFixed(2)})
                </span>
              {/each}
            </div>
          </div>
        {/each}

        <h3>Attribution</h3>
        <div class="table">
          {#each report.attribution ?? [] as region (region.two_theta_lo)}
            <div class="trow flat" class:gated={region.gates_passed}>
              <span class="mono tabular">{region.two_theta_lo.toFixed(2)}–{region.two_theta_hi.toFixed(2)}°</span>
              <span class="mono tabular muted">R²{num(region.r2).toFixed(2)}</span>
              <span class="mono tabular muted">κ{num(region.gram_condition).toPrecision(2)}</span>
              <span class="coefs mono">
                {#each region.coefficients.filter((c: any) => c.significant) as c (c.kind)}
                  {c.kind[0]}{num(c.value) > 0 ? "+" : ""}{num(c.value).toPrecision(2)}
                {/each}
              </span>
              {#if !region.gates_passed}
                <span class="muted"
                      title={region.gate_failures.map((f: any) => f.message).join("; ")}>
                  {region.gate_failures.map((f: any) => f.code).join(" ")}</span>
              {/if}
            </div>
          {/each}
        </div>

        {#each (report.texture ?? []).filter((t: any) => t.detected) as t (t.phase_index)}
          <p>texture: phase {t.phase_index} along {t.best_axis?.join("")},
            r={num(t.march_coefficient).toFixed(3)}, R²{num(t.r2).toFixed(2)}</p>
        {/each}
        {#each (report.strain ?? []).filter((s: any) => s.detected) as s (s.phase_index)}
          <p>strain: phase {s.phase_index} directional by
            {num(s.anisotropy).toFixed(1)}×{s.separable ? "" : " (patterns unresolved)"}</p>
        {/each}
      {/if}
    </div>
  {/if}
</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    min-height: 0;
    flex: 1 1 auto;
  }

  .scroller {
    overflow: auto;
    padding: 6px 9px 12px;
    flex: 1 1 auto;
  }

  .pad {
    padding: 10px;
  }

  h3 {
    margin: 10px 0 3px;
  }

  p {
    margin: var(--s1) 0;
  }

  .head {
    display: flex;
    align-items: baseline;
    gap: 8px;
    flex-wrap: wrap;
  }

  .summary {
    margin: 3px 0;
    color: var(--muted);
    /* one sentence a line (WP-1985) */
    white-space: pre-line;
  }

  .abstain {
    border-left: 2px solid var(--warn);
    padding-left: 6px;
    margin: 4px 0;
    color: var(--warn);
  }

  .applied {
    display: flex;
    align-items: center;
    gap: 7px;
    border: 1px solid var(--accent);
    border-radius: 4px;
    padding: 3px 6px;
    margin: 5px 0;
    flex-wrap: wrap;
  }

  .spacer {
    flex: 1 1 auto;
  }

  .chip {
    margin-left: 3px;
  }

  .action {
    border: 1px solid var(--line);
    border-left-width: 3px;
    border-radius: 4px;
    padding: 3px 6px;
    margin-bottom: 4px;
  }

  .action[data-tone="high"] {
    border-left-color: var(--ok);
  }

  .action[data-tone="medium"] {
    border-left-color: var(--warn);
  }

  .action[data-tone="low"] {
    border-left-color: var(--line);
  }

  .fitdiag {
    border-left: 3px solid var(--line);
    padding: 1px 6px;
    margin-bottom: 4px;
  }

  .fitdiag[data-level="error"] {
    border-left-color: var(--bad);
  }

  .fitdiag[data-level="warning"] {
    border-left-color: var(--warn);
  }

  .fitdiag > summary {
    cursor: pointer;
  }

  .fitdiag > summary > .line {
    display: inline-flex;
  }

  .fitdiag .under,
  .fitdiag .paths {
    display: block;
  }

  .action.off {
    opacity: 0.66;
  }

  .line {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .conf {
    flex: 0 0 auto;
    font-size: var(--text-sm);
  }

  .kind {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .why {
    margin: 2px 0;
  }

  .paths,
  .refusal {
    margin: 1px 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .refusal {
    color: var(--muted);
  }

  .table {
    display: flex;
    flex-direction: column;
  }

  /* a table row, whether or not it acts — the `.pick` register (app.css) is
     what takes the box off the ones that do */
  .trow {
    display: flex;
    gap: 7px;
    align-items: center;
    border-bottom: 1px solid var(--line);
    padding: 1px 2px;
    font-size: var(--text-sm);
    line-height: 18px;
  }

  .trow.flat {
    opacity: 0.6;
  }

  .trow.gated {
    opacity: 1;
  }

  .coefs {
    flex: 1 1 auto;
    overflow: hidden;
    white-space: nowrap;
  }

  .trend {
    margin: 3px 0;
  }

  .templates {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    color: var(--muted);
  }

  .templates .best {
    color: var(--fg);
  }

  .bad {
    padding: 0 9px;
    margin: 3px 0;
  }
</style>
