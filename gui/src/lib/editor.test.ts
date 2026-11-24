// @vitest-environment jsdom
/**
 * The CodeMirror adapter — the three things it must not get wrong.
 *
 * It holds no rules (those are in `sync.ts` and `rxt.ts`), so what is left to
 * assert is the wiring, and each of these is a bug that would be invisible until
 * a user hit it:
 *
 *  * **an echo is not an edit** — `setDoc` writes the server's rendering into the
 *    document, and without a guard CM's own change notification would come back
 *    as "the user typed", so every re-read would mark the buffer dirty and the
 *    pane would go stale against itself;
 *  * **a re-render keeps the caret** — the pane re-reads whenever anything else
 *    in the app moves the head, and replacing the whole document would move the
 *    cursor on every stage a fit completes;
 *  * **a diagnostic lands on the line the server named** — 1-based, per
 *    `textdoc.TextError`, and off-by-one here would squiggle the wrong row.
 */
import { diagnosticCount, forEachDiagnostic } from "@codemirror/lint";
import { EditorView } from "@codemirror/view";
import { beforeEach, describe, expect, it } from "vitest";

import { createEditor, type EditorHandle } from "./editor";

const DOC = 'rxt 1\nproject "doc"\nmode rietveld\nlimits 3 60\n';

let host: HTMLDivElement;
let edits: string[];

function open(doc = DOC, onApply = () => {}): EditorHandle {
  edits = [];
  return createEditor({ parent: host, doc, onChange: (text) => edits.push(text), onApply });
}

/** The live view behind the handle — the only way to act as the *user* does. */
function view(): EditorView {
  return EditorView.findFromDOM(host.querySelector(".cm-content") as HTMLElement)!;
}

beforeEach(() => {
  host = document.createElement("div");
  document.body.appendChild(host);
});

describe("the adapter", () => {
  it("renders the document and reports what the user types", () => {
    const editor = open();
    expect(host.textContent).toContain("rietveld");
    view().dispatch({ changes: { from: DOC.indexOf("rietveld"), to: DOC.indexOf("rietveld") + 8,
                                 insert: "lebail" } });
    expect(edits).toHaveLength(1);
    expect(edits[0]).toContain("mode lebail");
    expect(editor.text()).toContain("mode lebail");
    editor.destroy();
  });

  it("does not report `setDoc` as an edit", () => {
    const editor = open();
    editor.setDoc(DOC.replace("rietveld", "pawley"));
    expect(editor.text()).toContain("pawley");
    expect(edits).toEqual([]); // the whole point: a re-read is not a keystroke
    editor.destroy();
  });

  it("keeps the caret where it was when a re-render arrives", () => {
    const editor = open();
    const at = DOC.indexOf("limits");
    view().dispatch({ selection: { anchor: at } });
    // a change *before* the caret: the caret has to move with its text, which is
    // what dispatching a minimal splice buys and replacing the document does not
    editor.setDoc(DOC.replace('project "doc"', 'project "a-much-longer-name"'));
    const moved = view().state.selection.main.head;
    expect(view().state.doc.sliceString(moved, moved + 6)).toBe("limits");
    editor.destroy();
  });

  it("places a diagnostic on the 1-based line the server named", () => {
    const editor = open();
    editor.setProblems([{ line: 3, message: "unknown mode", where: "mode" }]);
    const found: Array<{ line: number; message: string }> = [];
    forEachDiagnostic(view().state, (diagnostic, from) =>
      found.push({ line: view().state.doc.lineAt(from).number, message: diagnostic.message }));
    // the dot-path is prefixed rather than restated: `where` is the server's own
    // answer to "which parameter", so the message reads as one sentence
    expect(found).toEqual([{ line: 3, message: "mode: unknown mode" }]);
    editor.destroy();
  });

  it("replaces the previous diagnostics rather than accumulating them", () => {
    const editor = open();
    editor.setProblems([{ line: 2, message: "one" }, { line: 3, message: "two" }]);
    editor.setProblems([]);
    expect(diagnosticCount(view().state)).toBe(0);
    editor.destroy();
  });

  it("marks an edited line's text, replacing the previous marks (WP-2231)", () => {
    const editor = open('rxt 1\n  project "doc"\nmode rietveld\n');
    const marked = () => [...host.querySelectorAll(".cm-edited")].map((e) => e.textContent).join("");
    editor.setEdited([2]);
    // over the line's text, past its indent
    expect(marked()).toBe('project "doc"');
    editor.setEdited([3, 99]);
    expect(marked()).toBe("mode rietveld");
    editor.setEdited([]);
    expect(marked()).toBe("");
    editor.destroy();
  });

  it("clamps a line number the buffer no longer has, rather than throwing", () => {
    const editor = open("rxt 1\n");
    expect(() => editor.setProblems([{ line: 99, message: "off the end" }])).not.toThrow();
    expect(() => editor.goToLine(99)).not.toThrow();
    editor.destroy();
  });

  it("runs the apply callback on Mod-Enter and not on Enter", () => {
    let applied = 0;
    const editor = open(DOC, () => (applied += 1));
    const target = host.querySelector(".cm-content") as HTMLElement;
    const press = (over: KeyboardEventInit) =>
      target.dispatchEvent(new KeyboardEvent("keydown",
        { key: "Enter", keyCode: 13, bubbles: true, ...over }));

    press({});
    expect(applied).toBe(0);            // a plain Enter is a newline, not an apply
    // `Mod` is CM's platform-agnostic spelling — Cmd on macOS, Ctrl elsewhere —
    // and jsdom's user agent is not a Mac, so Ctrl is what it resolves to here
    press({ ctrlKey: true });
    expect(applied).toBe(1);
    editor.destroy();
  });

  it("colours the document through `lib/rxt.ts` and nothing else", () => {
    const editor = open();
    // the classes are the ones `app.css` styles; their presence is what says the
    // StreamLanguage is wired to our token table rather than to CM's legacy names
    const classes = [...host.querySelectorAll("[class*='tok-']")]
      .map((node) => node.className);
    expect(classes.some((name) => name.includes("tok-keyword"))).toBe(true);
    expect(classes.some((name) => name.includes("tok-string"))).toBe(true);
    expect(classes.some((name) => name.includes("tok-number"))).toBe(true);
    editor.destroy();
  });
});
