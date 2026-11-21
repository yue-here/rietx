- `ExtinctionScreen.best_or_none()` names the leading extinction class only when its ΔBIC lead over the runner-up strictly exceeds max(10, 2·ln N + d), with N the fitted points and d the tested positions where the two classes differ (WP-2076).
  A position that shows nothing buys a class ln N and no more, so a lead built from two silent positions no longer decides.
  GSAS-II's PbSO₄ X-ray pattern, which named the wrong `P c - a` at the old margin of 10, now returns `None`, and `EXTINCTION_SYMBOL_AMBIGUOUS` gives the bar and names the two positions.
  Corundum (SRM 676a) and 11-BM NAC keep their classes.
