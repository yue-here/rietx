- **A plan that frees a magnetic width ends with the closing stage again** (#1850, the ruling on #1708).
  `RefinementPlan.magnetic_width()`, and any plan whose stages free `magnetic_lor_size` or `magnetic_lor_strain`, now defaults to `closing_window_tol=CLOSING_WINDOW_TOL` (1e-3); every other plan keeps `None`.
  The default is read off the stages when the plan is asked, so a stage appended in place counts, and an explicit `closing_window_tol=None` still turns the closing stage off.
  Without it, a width freed from zero was drawn on windows sized at `MAGNETIC_SIZING_FLOOR`, and the moment depended on how the plan was staged: on a simulated MnF₂ pattern it landed 0.12 plain esd from the closing-stage answer under the preset and 0.25 under one stage freeing the same parameters. With it both land on one answer.
  The moment and widths of such fits move by up to those amounts, and each fit runs one more stage.
  `PlanSpec` and the GUI's text document follow the same default when `closing_window_tol` or the `closing` line is absent; a project or history file that recorded `null` keeps it.
