/**
 * Move an element into another part of the page and keep it there (WP-2213).
 *
 * A graph panel draws its view controls on the shell's title line, as the
 * prototype does (the maintainer's fourth review, 2026-11-07: "the graph title
 * shares a row with the view's controls"). The controls' state stays in the
 * panel that owns it; only the element moves. While `target` is null the
 * element stays where the panel rendered it.
 */
export function portal(node: HTMLElement, target: HTMLElement | null | undefined) {
  const place = (to: HTMLElement | null | undefined) => {
    if (to && node.parentNode !== to) to.appendChild(node);
  };
  place(target);
  return {
    update: place,
    destroy() {
      node.remove();
    },
  };
}
