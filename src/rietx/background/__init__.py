from .auto import BackgroundChoice, auto_background
from .diagnostics import (
    ContaminationFlag,
    CoverageRegion,
    DeadChannelRun,
    PatternDiagnostics,
    SignalCutoff,
    background_envelope,
    contamination_flags_from_peaks,
    counting_coverage,
    dead_channels,
    diagnose,
    identify_anode,
    signal_cutoffs,
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
    "BackgroundChoice",
    "BackgroundSelection",
    "ContaminationFlag",
    "CoverageRegion",
    "DeadChannelRun",
    "PatternDiagnostics",
    "SignalCutoff",
    "arpls",
    "auto_background",
    "auto_lambda",
    "background_envelope",
    "bspline_design_matrix",
    "chebyshev_background",
    "chebyshev_design_matrix",
    "contamination_flags_from_peaks",
    "counting_coverage",
    "dead_channels",
    "diagnose",
    "identify_anode",
    "interpolate_fixed",
    "peak_mask",
    "second_difference_matrix",
    "select_arpls_lambda",
    "select_chebyshev_order",
    "signal_cutoffs",
    "snip",
    "whittaker_solve",
]
