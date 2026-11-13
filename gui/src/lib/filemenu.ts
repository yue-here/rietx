/**
 * The File menu's items, as data (WP-2133).
 *
 * The maintainer's save model A (2026-11-07): work saves itself, so the menu
 * has no Save, and ⌘S only says "Saved". The items are the round-6 design's,
 * less what a browser cannot do (Show in Finder, ⌘N and ⌘W, which the browser
 * keeps) and the two exports with no server writer (the plot's own PNG/SVG
 * buttons hold the picture). Kept pure so the enabled states are asserted
 * without a DOM.
 */
import { lastSeparator } from "./wizard";

export type MenuItem = {
  id: string;
  label: string;
  /** the shortcut, as the platform spells it */
  key?: string;
  disabled?: boolean;
  /** why it is disabled, or what a recent row points at */
  title?: string;
  sub?: Entry[];
};
export type Entry = MenuItem | "-";

/**
 * The server's export kinds (`session.EXPORT_DEFAULTS`), each with the file
 * name the dialog starts from. `tests/test_gui_file_menu.py` holds the kinds
 * and the names equal to the server's, since this file cannot import Python.
 * `modelOnly` is `_EXPORT_MODEL_ONLY`: answered from the project, no fit needed.
 */
export const EXPORT_KINDS = [
  { kind: "cif", label: "Refined structure (CIF)", file: "refinement.cif", modelOnly: false },
  { kind: "reflections", label: "Reflections (CSV)", file: "reflections.csv", modelOnly: false },
  { kind: "qpa", label: "Phase fractions (CSV)", file: "qpa.csv", modelOnly: false },
  { kind: "html", label: "Fit report (HTML)", file: "fit.html", modelOnly: false },
  { kind: "result_json", label: "Result (JSON)", file: "result.json", modelOnly: false },
  { kind: "instrument_profile", label: "Instrument profile (JSON)", file: "instrument_profile.json",
    modelOnly: true },
] as const;

export type ExportKind = (typeof EXPORT_KINDS)[number];

export type MenuState = {
  hasProject: boolean;
  busy: boolean;
  hasResult: boolean;
  nPhases: number;
  mode: string;
  /** `GET /api/recent`, newest first */
  recent: { path: string; name: string; missing?: boolean }[];
  /** the open project's folder, left off Open recent */
  current: string | null;
  mac: boolean;
};

const BUSY = "A run is in flight";

/** A shortcut as the platform spells it. */
export function keyLabel(mac: boolean, shift: boolean, letter: string): string {
  return mac ? `${shift ? "⇧" : ""}⌘${letter}` : `Ctrl+${shift ? "Shift+" : ""}${letter}`;
}

/** The File menu, in the round-6 order. */
export function fileMenu(s: MenuState): Entry[] {
  const none = !s.hasProject;
  const held = none || s.busy;
  const why = none ? "No project is open" : s.busy ? BUSY : undefined;
  const others = s.recent.filter((r) => r.path !== s.current);
  return [
    { id: "new", label: "New project…", disabled: s.busy, title: s.busy ? BUSY : undefined },
    { id: "open", label: "Open…", key: keyLabel(s.mac, false, "O"), disabled: s.busy,
      title: s.busy ? BUSY : undefined },
    { id: "recent", label: "Open recent", disabled: !others.length,
      sub: [
        ...others.map((r) => ({
          id: `recent:${r.path}`, label: r.name.replace(/\.rex$/, ""),
          disabled: s.busy || !!r.missing, title: r.missing ? `Not found: ${r.path}` : r.path,
        })),
        "-",
        { id: "recent-clear", label: "Clear the list", disabled: !s.recent.length },
      ] },
    "-",
    { id: "copy", label: "Save a copy…", key: keyLabel(s.mac, true, "S"), disabled: held, title: why },
    { id: "rename", label: "Rename…", disabled: held, title: why },
    { id: "move", label: "Move to…", disabled: held, title: why },
    "-",
    { id: "export", label: "Export", disabled: none, title: none ? why : undefined,
      sub: EXPORT_KINDS.map((k) => {
        const reason = exportBlocked(k, s);
        return { id: `export:${k.kind}`, label: `${k.label}…`, disabled: !!reason, title: reason };
      }) },
    "-",
    { id: "close", label: "Close project", disabled: held, title: why },
  ];
}

/** Why an export kind cannot be written now, or `undefined` when it can. */
export function exportBlocked(k: ExportKind, s: MenuState): string | undefined {
  if (!s.hasProject) return "No project is open";
  if (s.busy) return BUSY;
  if (!k.modelOnly && !s.hasResult) return "Run a fit first";
  if (k.kind === "qpa" && s.mode !== "rietveld") return "Phase fractions need a Rietveld fit";
  if (k.kind === "qpa" && s.nPhases < 2) return "One phase: nothing to quantify";
  return undefined;
}

/** Which File menu shortcut a key press is, if any. ⌘N and ⌘W stay the browser's. */
export function shortcut(event: { key: string; metaKey: boolean; ctrlKey: boolean; shiftKey: boolean; altKey: boolean }):
    "open" | "copy" | "saved" | null {
  if (!(event.metaKey || event.ctrlKey) || event.altKey) return null;
  const k = event.key.toLowerCase();
  if (k === "o" && !event.shiftKey) return "open";
  if (k === "s") return event.shiftKey ? "copy" : "saved";
  return null;
}

/** A project's name without its suffix: `/a/b/sample.rex` → `sample`. */
export function projectStem(path: string): string {
  return path.slice(lastSeparator(path) + 1).replace(/\.rex$/, "");
}

/** The folder a project sits in: `/sample.rex` sits in `/`. */
export function folderOf(path: string): string {
  const cut = lastSeparator(path);
  return cut > 0 ? path.slice(0, cut) : cut === 0 ? path.slice(0, 1) : path;
}
