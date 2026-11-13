/** The rebuilt page's tab strips (WP-2215), from the prototype and `gui/STYLE.md`
 * § Layout and panels: graphs on the left, the model's modes on the right, Console
 * and History along the foot.
 *
 * They live here, apart from `lib/tabs.ts`, because `lib/tabs.test.ts` writes that
 * file's strips into `tests/data/gui/panels.json`, which holds the manual to the
 * page a person gets by default. The new page's names join it at the swap
 * (WP-2214 § Tests and the manual, piece by piece).
 */
export const GRAPH_TABS = [
  { id: "pattern", label: "Pattern" },
  { id: "peaks", label: "Peaks" },
  { id: "background", label: "Background" },
  { id: "structure", label: "Structure" },
] as const;

export const MODEL_TABS = [
  { id: "params", label: "Parameters" },
  { id: "interactive", label: "Interactive" },
  { id: "plan", label: "Plan" },
  { id: "text", label: "Text" },
] as const;

export const BOTTOM_TABS = [
  { id: "console", label: "Console" },
  { id: "history", label: "History" },
] as const;

export type GraphTab = (typeof GRAPH_TABS)[number]["id"];
export type ModelTab = (typeof MODEL_TABS)[number]["id"];
export type BottomTab = (typeof BOTTOM_TABS)[number]["id"];
