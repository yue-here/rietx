<script lang="ts">
  /**
   * The one way this app explains a name (WP-1203).
   *
   * `<Help for="stage_fields:max_iter">iterations</Help>` wraps a term in the
   * `.help` register — WP-1201's cursor-only mark, no glyph and no underline —
   * and a click opens the app's single popover on it.  A second click, Esc or
   * a click away closes it, and focus goes back to the term.
   *
   * It sits beside `App.svelte` rather than in `panels/` because it is not a
   * panel: panels use it.  It declares no styles of its own — the trigger is
   * `.help` and the popover is `.popover`, both in `app.css`, which is where a
   * register's geometry is argued about (`lib/style.test.ts`).
   *
   * Two props, and the pair is the WP's measured rule.  `for` is a corpus key
   * and is what almost every use wants: the sentence lives in `rietx.help`, so
   * the GUI, the CLI and the manual read the same one.  `text` is for a
   * sentence the **server** wrote — `held_because`, a refutation, a maturity
   * message — which no corpus can hold because it is about one row rather than
   * one name.  Those were `title=` attributes until this WP, which put them
   * out of reach of the keyboard the moment WP-1201 moved one off a `<button>`.
   * `for` with `title` is a summary about one row that keeps the entry's
   * manual link: the popover shows the title alone, then the link (WP-2240).
   *
   * The trigger is a `<span>` with `role="button"`, not a `<button>`: it wraps
   * running text (a table header, a field's label, a chip's words) and a real
   * button would take the register's fill, weight and padding with it.  What
   * matters is that it is focusable and answers Enter and Space, which it does.
   *
   * **A term is named by its own words, and `label` is the exception.**  It was
   * `aria-label="explain"` by default until a browser pass measured what that
   * does: a name on a term *renames whatever encloses it*.  Accname computes a
   * `<label>`'s or a `<th>`'s name from its contents, and a descendant with an
   * `aria-label` contributes that string instead of its text (accname 1.2 step
   * 2C, and 2E again for the same node read as an embedded control).  So
   * wrapping `zero` in a `<Help>` renamed the instrument editor's input from
   * `zero (°2θ)` to `explain (°2θ)`, the atom table's four column headers to
   * `explain`, and the cell edges to `what a is` — this WP's own subject,
   * inverted, on every labelled field it touched.
   *
   * Hence `label = null`: the term's children are its name, which is what a
   * `<label>` wants anyway, and **`aria-haspopup="dialog"` is what says an
   * explanation opens** — that channel does not take part in a name.  Pass
   * `label` only where the children are a *glyph* (a padlock, `=`, `·`), which names
   * nothing, and only where no `<label>` or `<th>` encloses the term; there is
   * one such site, and `App.test.ts` fails on a second one that is enclosed.
   */
  import { getContext } from "svelte";

  import { HELP_CONTEXT, type HelpOpener } from "./lib/helpContext";

  let {
    for: key = null,
    text = null,
    title = null,
    label = null,
    children,
  }: {
    for?: string | null;
    text?: string | null;
    title?: string | null;
    /** a name for a term whose children are a glyph; see the note above */
    label?: string | null;
    children?: import("svelte").Snippet;
  } = $props();

  const opener = getContext<HelpOpener | undefined>(HELP_CONTEXT);
  let node = $state<HTMLElement | null>(null);
  const open = $derived(!!node && opener?.isOpen(node) === true);

  // a term that leaves the page takes its explanation with it: a layer that
  // closed by a submit left the popover drawn over nothing (WP-2244)
  $effect(() => {
    const term = node;
    return () => {
      if (term && opener?.isOpen(term)) opener.close();
    };
  });

  function toggle(event: Event) {
    if (!node || !opener) return;
    // a term inside a row that is itself clickable must not run the row's verb
    event.stopPropagation();
    event.preventDefault();
    opener.toggle(node, { key, text, title });
  }

  function onkeydown(event: KeyboardEvent) {
    if (event.key === "Enter" || event.key === " ") toggle(event);
  }
</script>

<span
  bind:this={node}
  class="help"
  role="button"
  tabindex="0"
  aria-label={label}
  aria-haspopup="dialog"
  aria-expanded={open}
  onclick={toggle}
  {onkeydown}
>{@render children?.()}</span>
