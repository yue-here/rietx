/**
 * A Hermann-Mauguin symbol typeset as crystallographers print it (WP-2126).
 *
 * Ruled 2026-11-06 and 2026-11-07: space groups are typeset, in a serif face,
 * with no comma and no spaces — `P6₃/m`, `Fm3̄m`, `I2₁3`. A letter is italic, a
 * `-d` rotoinversion is the digit under an overbar, and a two-digit token is a
 * screw axis, the second digit a subscript. An origin or axes choice after `:`
 * (`R -3 c:H`) is kept, small, after the symbol.
 *
 * The output is tokens, so the panel renders them with elements and the
 * function stays testable without a DOM.
 */
export type SgToken =
  | { kind: "italic"; text: string }
  | { kind: "digit"; text: string }
  | { kind: "bar"; text: string }
  | { kind: "screw"; text: string; sub: string }
  | { kind: "slash" }
  | { kind: "ext"; text: string };

function piece(token: string): SgToken[] {
  if (/^-\d$/.test(token)) return [{ kind: "bar", text: token[1] }];
  if (/^\d\d$/.test(token)) return [{ kind: "screw", text: token[0], sub: token[1] }];
  if (/^\d$/.test(token)) return [{ kind: "digit", text: token }];
  // anything else is letters (and the odd digit run a setting symbol carries),
  // italic as a whole so adjacent letters of one word stay one run
  return [{ kind: "italic", text: token }];
}

export function typesetSpaceGroup(symbol: string): SgToken[] {
  const [main, ext] = symbol.trim().split(":", 2);
  const out: SgToken[] = [];
  for (const word of main.split(/\s+/).filter(Boolean)) {
    word.split("/").forEach((part, index) => {
      if (index > 0) out.push({ kind: "slash" });
      if (part) out.push(...piece(part));
    });
  }
  // merge adjacent italics, as `</i><i>` would be in print
  const merged: SgToken[] = [];
  for (const token of out) {
    const last = merged.at(-1);
    if (token.kind === "italic" && last?.kind === "italic") last.text += token.text;
    else merged.push({ ...token });
  }
  if (ext) merged.push({ kind: "ext", text: `:${ext}` });
  return merged;
}

/** The plain-text reading of the typeset symbol, for an accessible name and a
 *  copy: `P6_3/m`, `Fm-3m`. */
export function spaceGroupText(symbol: string): string {
  return typesetSpaceGroup(symbol).map((t) => {
    if (t.kind === "slash") return "/";
    if (t.kind === "bar") return `-${t.text}`;
    if (t.kind === "screw") return `${t.text}_${t.sub}`;
    return t.text;
  }).join("");
}
