/** The CodeMirror 6 wiring — the one module that imports the editor.
 *
 * It is imported **dynamically** by `panels/Text.svelte`, which is what keeps
 * CodeMirror out of the boot path: `assets/app.js` stays the size WP-1010
 * measured, and `assets/vendor-cm.js` is fetched the first time someone opens
 * the text pane. Everything the pane actually decides lives in `lib/sync.ts`
 * (the state machine) and `lib/rxt.ts` (the colours); this file is the adapter
 * between them and CM's API, so it holds no rules of its own.
 *
 * `rectangularSelection` is the reason the `.rxt` format aligns its columns at
 * all (WP-1009 sized them per block after a fixed width made the renderer emit
 * `polarization 0.99min 0`), so it, `crosshairCursor` and multi-cursor are the
 * point of the pane rather than trimmings.
 *
 * The highlighter is a `StreamLanguage` over `lib/rxt.ts` with an explicit
 * `tokenTable`: no lezer grammar to build, no second parser to drift, and the
 * token names are this package's own rather than CM's legacy-mode vocabulary.
 */
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { HighlightStyle, StreamLanguage, syntaxHighlighting } from "@codemirror/language";
import { lintGutter, setDiagnostics, type Diagnostic } from "@codemirror/lint";
import { Compartment, EditorState, RangeSetBuilder, StateEffect, StateField,
         type Extension } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  EditorView,
  crosshairCursor,
  drawSelection,
  highlightActiveLine,
  highlightActiveLineGutter,
  highlightSpecialChars,
  keymap,
  lineNumbers,
  rectangularSelection,
} from "@codemirror/view";
import { tags, type Tag } from "@lezer/highlight";

import { spans, type Span, type Token } from "./rxt";
import { minimalChange, type Problem } from "./sync";

/** Our token names → lezer tags. Explicit, so renaming a token here is a
 *  type error rather than a silently uncoloured document. */
const TOKEN_TAGS: Record<Token, Tag> = {
  keyword: tags.keyword,
  vary: tags.atom,
  number: tags.number,
  string: tags.string,
  comment: tags.comment,
  annotation: tags.propertyName,
  flag: tags.modifier,
  operator: tags.operator,
  path: tags.variableName,
};

/** Colours as classes, not literals: `app.css` owns them and follows the theme. */
const HIGHLIGHT = HighlightStyle.define([
  { tag: tags.keyword, class: "tok-keyword" },
  { tag: tags.atom, class: "tok-vary" },
  { tag: tags.number, class: "tok-number" },
  { tag: tags.string, class: "tok-string" },
  { tag: tags.comment, class: "tok-comment" },
  { tag: tags.propertyName, class: "tok-annotation" },
  { tag: tags.modifier, class: "tok-flag" },
  { tag: tags.operator, class: "tok-operator" },
  { tag: tags.variableName, class: "tok-path" },
]);

/**
 * CodeMirror's own chrome, from the app's custom properties (WP-1029).
 *
 * The gutter, the caret, the selection and the active line are CM's, not ours,
 * and they came out **bright white on a dark page**.  Not because nothing
 * styled them — `app.css` has had `.cm-gutters { background: var(--panel) }`
 * since WP-1013 — but because CM's own base theme is injected as `.ͼ1
 * .cm-gutters`, two classes against one, so it wins on specificity every time.
 * A theme extension is generated the same way and so competes on equal terms,
 * which is why these rules live here rather than in the stylesheet with the
 * token colours.
 *
 * `dark` is a real flag rather than a colour: CM branches on it internally (the
 * default selection layer, the drop cursor, `filter: invert` on special
 * characters), so a dark palette without it leaves a page that is *nearly*
 * right and wrong in the details a reader notices last.
 *
 * The values are still `var(--…)`, so the one authority on a colour stays
 * `app.css` and no component learns a hex.
 */
export function editorTheme(dark: boolean): Extension {
  return EditorView.theme(
    {
      "&": { height: "100%", fontSize: "var(--text-sm)", backgroundColor: "var(--bg)", color: "var(--fg)" },
      ".cm-scroller": { fontFamily: "ui-monospace, 'SF Mono', Menlo, monospace" },
      ".cm-gutters": {
        backgroundColor: "var(--panel)",
        color: "var(--muted)",
        border: "none",
        borderRight: "1px solid var(--line)",
      },
      ".cm-activeLineGutter": {
        backgroundColor: "color-mix(in srgb, var(--accent) 10%, transparent)",
        color: "var(--fg)",
      },
      ".cm-activeLine": { backgroundColor: "color-mix(in srgb, var(--accent) 8%, transparent)" },
      ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--fg)" },
      "&.cm-focused .cm-cursor": { borderLeftColor: "var(--fg)" },
      ".cm-selectionBackground, &.cm-focused .cm-selectionBackground, ::selection": {
        backgroundColor: "color-mix(in srgb, var(--accent) 25%, transparent)",
      },
      ".cm-panels": { backgroundColor: "var(--panel)", color: "var(--fg)" },
      ".cm-tooltip": {
        backgroundColor: "var(--panel)",
        color: "var(--fg)",
        border: "1px solid var(--line)",
      },
      ".cm-lineNumbers .cm-gutterElement": { color: "var(--muted)" },
      // a line the rendering does not have (WP-2231): the prototype's
      // highlighted edit, over the line's text and not the gutter
      ".cm-edited": {
        backgroundColor: "color-mix(in srgb, var(--accent) 16%, transparent)",
        borderRadius: "2px",
      },
    },
    { dark },
  );
}

interface StreamState {
  spans: Span[];
  at: number;
}

/**
 * `lib/rxt.ts`'s per-line spans, walked one token at a time.
 *
 * CM asks for tokens through a `StringStream`, so the whole line is classified
 * once at `sol()` and then handed back span by span. Gaps between spans advance
 * the stream with no style, which is how "the scanner has no opinion about this"
 * is expressed to CM.
 */
const rxtLanguage = StreamLanguage.define<StreamState>({
  name: "rxt",
  startState: () => ({ spans: [], at: 0 }),
  token(stream, state) {
    if (stream.sol()) {
      state.spans = spans(stream.string);
      state.at = 0;
    }
    while (state.at < state.spans.length && state.spans[state.at].to <= stream.pos) {
      state.at += 1;
    }
    const span = state.spans[state.at];
    if (!span) {
      stream.skipToEnd();
      return null;
    }
    if (stream.pos < span.from) {
      stream.pos = span.from;
      return null;
    }
    stream.pos = span.to;
    state.at += 1;
    return span.token;
  },
  tokenTable: TOKEN_TAGS,
});

/** The edited lines as marks over each line's text, set whole by `setEdited`
 *  and carried through the edits typed between two sets. */
const setEditedEffect = StateEffect.define<number[]>();
const EDITED_MARK = Decoration.mark({ class: "cm-edited" });

const editedField = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(marks, tr) {
    let out = marks.map(tr.changes);
    for (const effect of tr.effects) {
      if (!effect.is(setEditedEffect)) continue;
      const doc = tr.state.doc;
      const builder = new RangeSetBuilder<Decoration>();
      for (const n of [...effect.value].sort((x, y) => x - y)) {
        if (n < 1 || n > doc.lines) continue;
        const line = doc.line(n);
        const from = line.from + (line.text.length - line.text.trimStart().length);
        if (from < line.to) builder.add(from, line.to, EDITED_MARK);
      }
      out = builder.finish();
    }
    return out;
  },
  provide: (field) => EditorView.decorations.from(field),
});

export interface EditorHandle {
  /** Replace the document with a server rendering, keeping cursor and scroll. */
  setDoc(text: string): void;
  /** Paint the server's problems as lint diagnostics. */
  setProblems(problems: Problem[]): void;
  /** Mark these lines (1-based) as edited, replacing the previous marks. */
  setEdited(lines: number[]): void;
  /** Put the caret on a line (1-based) and scroll it into view. */
  goToLine(line: number): void;
  /** Re-measure after the container was hidden and shown again. */
  refresh(): void;
  /** Repaint the chrome for a theme change, keeping the document and its undo
   *  history — a rebuilt editor would lose both to a click on a toggle. */
  setTheme(dark: boolean): void;
  text(): string;
  focus(): void;
  destroy(): void;
}

export interface EditorOptions {
  parent: HTMLElement;
  doc: string;
  /** every user edit, already debounced by nobody — the pane owns the timer */
  onChange: (text: string) => void;
  /** Cmd/Ctrl-Enter */
  onApply: () => void;
  readOnly?: boolean;
  dark?: boolean;
}

export function createEditor(options: EditorOptions): EditorHandle {
  /** true while `setDoc` is writing, so its own transaction is not an edit */
  let echoing = false;
  const theme = new Compartment();
  const extensions: Extension[] = [
    lineNumbers(),
    highlightActiveLineGutter(),
    highlightActiveLine(),
    highlightSpecialChars(),
    history(),
    drawSelection(),
    // the jEdit-style column edit the format's aligned columns exist for
    rectangularSelection(),
    crosshairCursor(),
    lintGutter(),
    editedField,
    EditorState.allowMultipleSelections.of(true),
    rxtLanguage,
    syntaxHighlighting(HIGHLIGHT),
    keymap.of([
      { key: "Mod-Enter", preventDefault: true, run: () => (options.onApply(), true) },
      ...defaultKeymap,
      ...historyKeymap,
      indentWithTab,
    ]),
    EditorView.updateListener.of((update) => {
      // `setDoc` is the server's rendering arriving, not the user typing: without
      // this guard adopting a render would report itself back as an edit and the
      // pane would call every re-read a dirty buffer
      if (update.docChanged && !echoing) options.onChange(update.state.doc.toString());
    }),
    EditorState.readOnly.of(options.readOnly ?? false),
    theme.of(editorTheme(options.dark ?? false)),
  ];

  const view = new EditorView({
    state: EditorState.create({ doc: options.doc, extensions }),
    parent: options.parent,
  });

  return {
    setDoc(text: string) {
      const change = minimalChange(view.state.doc.toString(), text);
      if (!change) return;
      echoing = true;
      try {
        view.dispatch({ changes: change });
      } finally {
        echoing = false;
      }
    },
    setProblems(problems: Problem[]) {
      const doc = view.state.doc;
      const diagnostics: Diagnostic[] = problems.map((problem) => {
        // clamp: a server line number outside the buffer means the buffer moved
        // on, and a diagnostic that throws is worse than one on the wrong line
        const line = doc.line(Math.min(Math.max(problem.line, 1), doc.lines));
        return {
          from: line.from,
          to: line.to,
          severity: "error",
          message: problem.where ? `${problem.where}: ${problem.message}` : problem.message,
        };
      });
      view.dispatch(setDiagnostics(view.state, diagnostics));
    },
    setEdited(lines: number[]) {
      view.dispatch({ effects: setEditedEffect.of(lines) });
    },
    goToLine(line: number) {
      const at = view.state.doc.line(Math.min(Math.max(line, 1), view.state.doc.lines));
      view.dispatch({ selection: { anchor: at.from }, scrollIntoView: true });
      view.focus();
    },
    refresh() {
      view.requestMeasure();
    },
    setTheme(dark: boolean) {
      view.dispatch({ effects: theme.reconfigure(editorTheme(dark)) });
    },
    text: () => view.state.doc.toString(),
    focus: () => view.focus(),
    destroy: () => view.destroy(),
  };
}
