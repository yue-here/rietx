from .auto import auto_background
from .diagnostics import (
    ContaminationFlag,
    PatternDiagnostics,
    diagnose,
    identify_anode,
)
from .estimators import arpls, auto_lambda, snip, whittaker_solve
from .models import (
    bspline_design_matrix,
    chebyshev_background,
    chebyshev_design_matrix,
    interpolate_fixed,
    second_difference_matrix,
)
from .select import (
    BackgroundSelection,
    peak_mask,
    select_arpls_lambda,
    select_chebyshev_order,
)

__all__ = [
    "BackgroundSelection",
    "ContaminationFlag",
    "PatternDiagnostics",
    "arpls",
    "auto_background",
    "auto_lambda",
    "bspline_design_matrix",
    "chebyshev_background",
    "chebyshev_design_matrix",
    "diagnose",
    "identify_anode",
    "interpolate_fixed",
    "peak_mask",
    "second_difference_matrix",
    "select_arpls_lambda",
    "select_chebyshev_order",
    "snip",
    "whittaker_solve",
]
