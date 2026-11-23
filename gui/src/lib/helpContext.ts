/** The one channel between a `<Help>` term and the page's single popover.
 *
 * Context rather than a store module, for the reason `App.svelte`'s own
 * docstring gives: there is one session and one popover, state lives in runes
 * in the page and is passed down, and a second source of truth for "what is
 * open" is the bug a single instance exists to prevent.  The provider is
 * `HelpPopover.svelte`'s `provideHelp()`, which each page calls (WP-2244).  A `<Help>` mounted
 * with no provider degrades to a term that does nothing rather than throwing,
 * which is what keeps it usable in a component test that mounts one panel.
 */

/** What a `<Help>` term asks the shell to show. */
export interface HelpRequest {
  /** an `arm:name` corpus key, or null when the sentence is supplied */
  key: string | null;
  /** a sentence the server wrote, for a fact no corpus can hold */
  text: string | null;
  /** an optional heading for a `text` request; beside a `key`, a summary
   *  about one row that stands in for the entry's words (WP-2240) */
  title: string | null;
}

export interface HelpOpener {
  /** open on this term, or close if it is already the open one */
  toggle(node: HTMLElement, request: HelpRequest): void;
  /** whether the popover is currently anchored to this term */
  isOpen(node: HTMLElement): boolean;
  /** close whatever is open; a term that leaves the page calls it, so the
   *  popover is never left anchored to nothing (WP-2244) */
  close(): void;
}

export const HELP_CONTEXT = Symbol("rietx.help");
