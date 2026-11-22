/** The event stream's bookkeeping, as pure functions so it can be unit-tested.
 *
 * `/api/events` multiplexes two SSE frame types over one connection:
 *
 *   * `event: event` — an engine event dict (`fit_start`, `stage_start`, `eval`,
 *     `stage_end`, `fit_end`), carrying `seq` and an **open** `data` object;
 *   * `event: state` — the session's run state, which exists because a *failed*
 *     fit emits no `fit_end`: a follower watching engine events alone would hang
 *     on exactly the case it most needs to report.
 *
 * Two rules are encoded here rather than left to each caller.  Event `data` is
 * read field by field with `?.` — the contract says fields are additive, so
 * destructuring a fixed shape is what breaks on the next release.  And the
 * `seq` cursor can genuinely fall behind: the server's ring holds 4096 events
 * and a staged fit emits one per residual evaluation, so `oldest` is compared
 * against the cursor and a real gap is *reported*, never silently renumbered.
 */

export interface EngineEvent {
  seq: number;
  kind: string;
  t: number;
  data: Record<string, any>;
}

export interface RunState {
  state: "idle" | "running" | "cancelling";
  run: {
    kind: string | null;
    status: string | null;
    stage: string | null;
    stage_index: number | null;
    n_stages: number | null;
    rwp: number | null;
    gof: number | null;
    node_id: string | null;
    completed_stages: string[];
    error: { code: string; message: string } | null;
    elapsed?: number | null;
    /** A Le Bail alternation (WP-1323): `pass`/`of` while it runs, `stopped`
     *  (the package's own sentence, which pass was kept) once it has. */
    lebail?: {
      pass?: number; of?: number | null;
      stopped?: string; level?: string; suggestion?: string | null;
    } | null;
  };
  project: string | null;
  head: string | null;
}

/** One console line: what an event says, in the order a reader wants it. */
export function consoleLine(event: EngineEvent): string {
  const data = event.data ?? {};
  const time = new Date((event.t ?? 0) * 1000).toLocaleTimeString();
  const body = Object.entries(data)
    .filter(([key]) => !SERIES_KEYS.has(key))
    .map(([key, value]) => `${key}=${format(value)}`)
    .join(" ");
  return `${time}  ${event.kind.padEnd(11)} ${seriesPrefix(data)}${body}`;
}

/** The series stamp (WP-1016), rendered as a prefix rather than as four fields.
 *
 * The console renders whatever keys arrive — deliberately, since `data` is an
 * open dict and a reader that knew the shape would go stale (`history/events.py`).
 * But a series stamps **five** keys onto every event including every `eval`, and
 * a browser showed what that does: the transcript became
 * `series_index=0 series_label="T300" series_n=3 series_p…` repeated, with the
 * cost and the evaluation counter pushed off the right edge. So these five are
 * folded into one `[T300 ↩]` prefix — the same information, and the line's own
 * fields stay where they were.
 */
const SERIES_KEYS = new Set(["series_index", "series_label", "series_n",
                             "series_pass", "series_cold", "series_rung"]);

/** The escalation ladder's rungs, as one character each (WP-1051).
 *
 * `series_rung` rides only on a **restart**, so an absent key is a pattern's
 * first attempt and gets no glyph — which is also why the cold rung the first
 * pattern of every chain runs is not marked as a rescue. */
const RUNG_GLYPH: Record<string, string> = { warm_staged: " ↑", cold: " ❄" };

function seriesPrefix(data: Record<string, unknown>): string {
  if (data.series_index === undefined) return "";
  const name = data.series_label ?? data.series_index;
  const n = data.series_n ? `/${data.series_n}` : "";
  const back = data.series_pass === "backward" ? " ↩" : "";
  const rung = RUNG_GLYPH[String(data.series_rung ?? "")] ?? "";
  return `[${name} ${Number(data.series_index) + 1}${n}${back}${rung}] `;
}

function format(value: unknown): string {
  if (typeof value === "number") return String(Number(value.toPrecision(6)));
  if (Array.isArray(value)) return `[${value.length}]`;
  return JSON.stringify(value) ?? String(value);
}

/** Progress as a fraction, or `null` when the run has not said enough yet.
 *
 * Derived from `stage_start`'s **1-based** `index`/`n_stages` (WP-1006 put them
 * there precisely so a client needs no bookkeeping), and deliberately coarse: a
 * per-evaluation bar would be a lie, since a stage's evaluation count is not
 * known until it ends. */
export function stageProgress(state: RunState): number | null {
  const { stage_index, n_stages } = state.run;
  if (!stage_index || !n_stages) return null;
  return Math.min(1, (stage_index - 1) / n_stages);
}

export interface Cursor {
  seq: number;
  dropped: number;
}

/** Advance a cursor over a batch, counting frames the ring dropped.
 *
 * `oldest` is the lowest seq the server still holds.  If it is more than one
 * past our cursor, events vanished between polls and the count is surfaced —
 * a console that silently skips 300 evaluations looks like a stalled fit. */
export function advance(cursor: Cursor, batch: { events: EngineEvent[]; oldest?: number; next?: number }): Cursor {
  const oldest = batch.oldest ?? cursor.seq + 1;
  const gap = Math.max(0, oldest - (cursor.seq + 1));
  const last = batch.events.length ? batch.events[batch.events.length - 1].seq : batch.next ?? cursor.seq;
  return { seq: Math.max(cursor.seq, last), dropped: cursor.dropped + gap };
}

/** Follow the stream: SSE when it works, `?poll=1` when it does not.
 *
 * EventSource cannot be told "resume at seq N" once it reconnects on its own,
 * so the query carries the cursor and a reconnect re-opens with the cursor we
 * hold — which is why the server accepts `?since=` on the SSE route too.
 *
 * `onDropped` hears the running count of frames the server's ring lost while
 * this page followed (#1656 item 1): the polling path reads it off each
 * batch's `oldest` (`advance`), and the SSE path off a jump in `seq`, which
 * the server numbers one by one. What the ring had lost before the first
 * answer (a poll's, or the first SSE event) is history this page never
 * followed, so it is not counted, unless
 * the caller gave a `since` and so claimed the frames after it. */
export function follow(
  onEvent: (event: EngineEvent) => void,
  onState: (state: RunState) => void,
  options: { since?: number; poll?: (since: number) => Promise<any>;
             onDropped?: (dropped: number) => void } = {},
): () => void {
  let cursor: Cursor = { seq: options.since ?? 0, dropped: 0 };
  let primed = options.since !== undefined;
  const moved = (next: Cursor) => {
    const lost = next.dropped !== cursor.dropped;
    cursor = next;
    if (lost) options.onDropped?.(cursor.dropped);
  };
  let stopped = false;
  let source: EventSource | null = null;
  let timer: number | null = null;

  const openSse = () => {
    if (stopped) return;
    source = new EventSource(`/api/events?since=${cursor.seq}`);
    source.addEventListener("event", (message) => {
      const event = JSON.parse((message as MessageEvent).data) as EngineEvent;
      const gap = primed ? Math.max(0, event.seq - (cursor.seq + 1)) : 0;
      primed = true;
      moved({ seq: Math.max(cursor.seq, event.seq), dropped: cursor.dropped + gap });
      onEvent(event);
    });
    source.addEventListener("state", (message) => {
      onState(JSON.parse((message as MessageEvent).data) as RunState);
    });
    source.onerror = () => {
      // The server closes the connection per response (HTTP/1.0 semantics), so
      // an error here is ordinary. EventSource reconnects by itself; we only
      // fall back to polling if it is unavailable at all.
      if (!source || source.readyState === EventSource.CLOSED) startPolling();
    };
  };

  const startPolling = () => {
    if (stopped || timer !== null || !options.poll) return;
    const tick = async () => {
      if (stopped) return;
      try {
        const batch = await options.poll!(cursor.seq);
        for (const event of batch.events ?? []) onEvent(event);
        const next = advance(cursor, batch);
        moved(primed ? next : { ...next, dropped: cursor.dropped });
        // the first answer, empty or not, is where this page began following:
        // a frame the ring loses after it was lost while followed
        primed = true;
        if (batch.state) onState(batch as RunState);
      } catch {
        /* the server is gone; the next tick will find out */
      }
      timer = window.setTimeout(tick, 700);
    };
    timer = window.setTimeout(tick, 0);
  };

  if (typeof EventSource === "undefined") startPolling();
  else openSse();

  return () => {
    stopped = true;
    source?.close();
    if (timer !== null) window.clearTimeout(timer);
  };
}
