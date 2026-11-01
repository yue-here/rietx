// The theme control (`_templates/rietx-theme.html`): the landing page's two states, on
// pydata-sphinx-theme's engine (WP-2021).
//
// pydata keeps the choice in localStorage `mode` (auto, light or dark) and `theme` (the one
// in force), mirrors both to `html[data-mode]` and `html[data-theme]`, and resolves `auto`
// against the system.  Until a reader pins a theme the mode is `auto` (pydata writes it on
// every load), so the page follows the system as the landing page does.  A click pins the
// other theme by writing all four, the same keys the landing page writes, so one choice
// holds across the site.  pydata exposes no setter, so this writes them itself.  The header
// and the narrow-screen drawer each draw a button, so every one is labelled, and the label
// follows `data-theme` whoever changed it.
//
// Two things pydata's own setter does that writing the keys does not, so they are done here
// on every change of `data-theme`.  pydata's load left a system listener behind while the
// mode was `auto`, which would follow the system again over a pin made since; a pinned mode
// therefore puts the theme back.  And pydata recolours its dropdowns (the version switcher)
// by a class, which follows the theme here too.
(() => {
  "use strict";
  const root = document.documentElement;
  const dark = () => root.dataset.theme === "dark";
  const pinned = () => root.dataset.mode === "light" || root.dataset.mode === "dark";

  function follow() {
    if (pinned() && root.dataset.theme !== root.dataset.mode) {
      root.dataset.theme = root.dataset.mode;   // observed again, and then in agreement
      return;
    }
    const to = `Switch to the ${dark() ? "light" : "dark"} theme`;
    for (const button of document.querySelectorAll(".rietx-theme")) {
      button.setAttribute("aria-label", to);
      button.setAttribute("title", to);
    }
    for (const menu of document.querySelectorAll(".dropdown-menu")) {
      menu.classList.toggle("dropdown-menu-dark", dark());
    }
  }

  function pin(theme) {
    root.dataset.mode = theme;
    root.dataset.theme = theme;
    try {
      localStorage.setItem("mode", theme);
      localStorage.setItem("theme", theme);
    } catch (e) {}
  }

  document.addEventListener("click", (event) => {
    if (event.target.closest(".rietx-theme")) pin(dark() ? "light" : "dark");
  });
  new MutationObserver(follow).observe(root, { attributes: true, attributeFilter: ["data-theme"] });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", follow);
  else follow();
})();
