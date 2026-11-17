/**
 * Unapplied edits kept across a close or a crash (WP-2209).
 *
 * The maintainer's ruling of 2026-11-09: pending edits follow the software
 * field's practice, a recovery copy kept apart from the project in rietx's
 * state directory (VS Code's hot exit, Blender, Office AutoRecover).  The
 * server keeps one copy per project (`src/rietx/gui/recovery.py`); this module
 * holds the client's half: the draft's shape, and the writer that sends it.
 *
 * The draft holds *proposed* edits only, one arm per panel, and never a value
 * the project stores.  Three arms are the panels the action bar counts; the
 * Text document and the Model forms keep their own Apply and join the copy
 * uncounted (WP-2213, the maintainer's ruling of 2026-11-10).  An empty draft
 * is `null`, and writing `null` deletes the copy, which is how an Apply, a
 * Revert or a Discard removes it.
 */

/** The Parameters panel's six pending maps, as plain objects. */
export interface ParamsDraft {
  edits: Record<string, string>;
  vary: Record<string, boolean>;
  hold: Record<string, boolean>;
  limits: Record<string, unknown>;
  restraints: Record<string, unknown>;
  positions: Record<string, Record<string, string>>;
}

/** The Interactive panel's slider values. */
export interface InteractiveDraft {
  values: Record<string, number>;
}

/** The Plan tab's edited plan. */
export interface PlanDraft {
  stages: unknown[];
  guard: number;
}

/** The Text panel's buffer as typed, comments included, and the revision of
 *  the rendering it was typed against: restored at another revision it comes
 *  back stale, since the document has no merge (`lib/sync.ts`). */
export interface TextDraft {
  buffer: string;
  revision: string;
}

/** The Model panel's typed fields, by the form each belongs to, and the
 *  new-atom row.  `count` is what the panel itself shows as its edits. */
export interface ModelDraft {
  count: number;
  /** model fields, keyed by the field's path in the model */
  edits: Record<string, string>;
  /** raw parameter rows (the ADP patterns) */
  params: Record<string, string>;
  /** typed coordinates, keyed by the model path `phases.i.atoms.j.x|y|z` */
  positions: Record<string, string>;
  /** refine flags, keyed by parameter path */
  vary: Record<string, boolean>;
  atom: { label: string; species: string; x: string; y: string; z: string } | null;
}

export interface Draft {
  /** what the action bar counted, for the offer's wording */
  count: number;
  params: ParamsDraft | null;
  interactive: InteractiveDraft | null;
  plan: PlanDraft | null;
  text: TextDraft | null;
  model: ModelDraft | null;
}

export type Arms = Partial<Omit<Draft, "count">>;

/** The panels' arms combined, or `null` when none holds an edit. */
export function combine(count: number, arms: Arms): Draft | null {
  const out: Draft = { count, params: arms.params ?? null,
                       interactive: arms.interactive ?? null, plan: arms.plan ?? null,
                       text: arms.text ?? null, model: arms.model ?? null };
  if (!out.params && !out.interactive && !out.plan && !out.text && !out.model) return null;
  return out;
}

/** A copy read back, checked for the shape this module writes.  Anything
 *  else is no copy: a hand-edited file must not break the open. */
export function readDraft(value: unknown): Draft | null {
  if (!value || typeof value !== "object") return null;
  const d = value as Record<string, unknown>;
  const arm = (x: unknown) => (x && typeof x === "object" ? x : null);
  const t = arm(d.text) as Record<string, unknown> | null;
  // a Text arm restores a buffer into an editor, so only the shape written
  const text = t && typeof t.buffer === "string" && typeof t.revision === "string"
    ? { buffer: t.buffer, revision: t.revision } : null;
  // a Model arm restores four maps into the forms, so each must be one
  const m = arm(d.model) as Record<string, unknown> | null;
  const model = m && ["edits", "params", "positions", "vary"].every((k) => arm(m[k]))
    ? m as unknown as ModelDraft : null;
  return combine(typeof d.count === "number" ? d.count : 0, {
    params: arm(d.params) as ParamsDraft | null,
    interactive: arm(d.interactive) as InteractiveDraft | null,
    plan: arm(d.plan) as PlanDraft | null,
    text,
    model,
  });
}

const plural = (n: number, noun: string) => (n === 1 ? `1 ${noun}` : `${n} ${noun}s`);

/** What a copy holds, in words: the action bar's count (`noun` names it),
 *  then the Model forms' edits, then the Text document. */
export function keptParts(draft: Draft, noun = "edit"): string {
  const counted = draft.params || draft.interactive || draft.plan;
  const parts: string[] = [];
  if (counted || (!draft.text && !draft.model)) parts.push(plural(Math.max(1, draft.count), noun));
  if (draft.model) parts.push(`${plural(Math.max(1, draft.model.count), "edit")} in the Model forms`);
  if (draft.text) parts.push("an edited Text document");
  return parts.length > 1
    ? `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}` : parts[0];
}

/** The offer's sentence: what was kept, and when. */
export function offerText(draft: Draft, savedUtc: string | null | undefined,
                          locale?: string): string {
  const what = keptParts(draft);
  const lead = what.charAt(0).toUpperCase() + what.slice(1);
  const when = savedUtc ? new Date(savedUtc) : null;
  if (!when || Number.isNaN(when.getTime())) return `${lead} not applied when the project closed.`;
  const stamp = when.toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" });
  return `${lead} from ${stamp}, not applied when the project closed.`;
}

type Put = (project: string, head: string | null, draft: Draft | null) => Promise<unknown>;

interface Timers {
  set: (fn: () => void, ms: number) => unknown;
  clear: (handle: unknown) => void;
}

const REAL_TIMERS: Timers = {
  set: (fn, ms) => setTimeout(fn, ms),
  clear: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
};

/**
 * Sends the draft half a second after the last change, to one project.
 *
 * The writer is **armed** for one project at a time.  While it is disarmed,
 * or asked to write for another project, it drops the request: that is what
 * keeps an unanswered offer from being overwritten, and a project switch from
 * writing the panels' emptied maps over the copy of the project just left.
 * A write that matches the last one sent is not sent again.
 */
export class RecoveryWriter {
  private project: string | null = null;
  private sent = "null";
  private next: { head: string | null; draft: Draft | null } | null = null;
  private handle: unknown = null;
  private flight: Promise<unknown> = Promise.resolve();

  constructor(private put: Put, private delayMs = 500, private timers: Timers = REAL_TIMERS) {}

  /** Write for `project` from now on.  `stored` is the copy the server holds
   *  for it, so a draft equal to it is not sent again. */
  arm(project: string, stored: Draft | null = null) {
    this.drop();
    this.project = project;
    this.sent = JSON.stringify(stored);
  }

  /** Stop writing, dropping any write not yet sent. */
  disarm() {
    this.drop();
    this.project = null;
  }

  /** The project now has another path (a rename or a move made in the app,
   *  which the server re-keyed): keep the scheduled write, aimed there. */
  follow(project: string) {
    if (this.project !== null) this.project = project;
  }

  get armedFor(): string | null {
    return this.project;
  }

  /** Ask for `draft` to be kept for `project`, after the delay. */
  schedule(project: string | null, head: string | null, draft: Draft | null) {
    if (!project || project !== this.project) return;
    this.next = { head, draft };
    if (this.handle !== null) this.timers.clear(this.handle);
    this.handle = this.timers.set(() => {
      this.handle = null;
      void this.send();
    }, this.delayMs);
  }

  /** Send a scheduled write now, and wait for every write in flight. */
  async flush(): Promise<void> {
    if (this.handle !== null) {
      this.timers.clear(this.handle);
      this.handle = null;
      void this.send();
    }
    try {
      await this.flight;
    } catch {
      // a refused write is the writer's to drop; the edits are still on screen
    }
  }

  /** The write not yet sent, for a page about to go: `pagehide` sends it
   *  with `keepalive`, since a timer does not outlive the page. */
  unsent(): { project: string; head: string | null; draft: Draft | null } | null {
    if (this.handle === null || !this.next || !this.project) return null;
    return { project: this.project, ...this.next };
  }

  /** {@link unsent}, handed over: the timer is cleared and the draft counted
   *  as sent, so a page that comes back from the back-forward cache does not
   *  send it a second time behind the `keepalive` one. */
  takeUnsent(): { project: string; head: string | null; draft: Draft | null } | null {
    const out = this.unsent();
    if (!out) return null;
    this.drop();
    this.sent = JSON.stringify(out.draft);
    return out;
  }

  private drop() {
    if (this.handle !== null) this.timers.clear(this.handle);
    this.handle = null;
    this.next = null;
  }

  private send(): Promise<unknown> {
    const project = this.project;
    const next = this.next;
    this.next = null;
    if (!project || !next) return this.flight;
    const text = JSON.stringify(next.draft);
    if (text === this.sent) return this.flight;
    this.sent = text;
    // one write at a time, in order, so an older draft never lands last
    this.flight = this.flight.catch(() => {}).then(() => this.put(project, next.head, next.draft));
    this.flight.catch(() => {
      // refused: forget what was sent, so the next change tries again
      this.sent = "\u0000";
    });
    return this.flight;
  }
}
