<script lang="ts">
  /**
   * The padlock, drawn: one stroked SVG for every place the GUI marks a held
   * or locked parameter (the maintainer's look of 2026-11-22, WP-2212). The
   * emoji padlock it replaces drew in colour and at its own size, so the
   * instrument rows and the atom rows wore two different locks.
   * `gui/STYLE.md` § Components carries the rule, and `lib/style.test.ts`
   * fails on an emoji glyph in any source.
   *
   * `on` closes the shackle and fills the body. `label` names the mark where
   * nothing around it does; without one the drawing is hidden from a screen
   * reader, as inside a button that says "hold" itself.
   */
  let { on = true, label = null }: { on?: boolean; label?: string | null } = $props();
</script>

<svg class="padlock" viewBox="0 0 14 14" width="14" height="14"
  role={label ? "img" : undefined} aria-label={label ?? undefined}
  aria-hidden={label ? undefined : "true"}>
  <rect x="2.5" y="6" width="9" height="6.5" rx="1.5"
    fill={on ? "currentColor" : "none"} stroke="currentColor" stroke-width="1.3" />
  <path d={on ? "M4.5 6V4.5a2.5 2.5 0 0 1 5 0V6" : "M4.5 6V4.5a2.5 2.5 0 0 1 5 0"}
    fill="none" stroke="currentColor" stroke-width="1.3" />
</svg>

<style>
  .padlock {
    display: inline-block;
    flex: none;
    vertical-align: -2px;
  }
</style>
