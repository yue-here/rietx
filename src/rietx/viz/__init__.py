from .indexing import (
    plot_candidates,
    plot_indexing,
    plot_peak_list,
    plot_validation,
)
from .plots import plot_for_vlm, plot_pattern, plot_result, plot_trajectory

__all__ = ["LiveSession", "component", "keep", "periodicity", "plane", "plot_candidates",
           "plot_for_vlm", "plot_indexing", "plot_pattern", "plot_peak_list",
           "plot_result", "plot_strain_surface", "plot_trajectory", "plot_validation", "recolour",
           "render_structure", "select", "sphere", "write_html"]

_FIGURE3D = ("component", "keep", "periodicity", "plane", "recolour", "render_structure",
             "select", "sphere")


def __getattr__(name: str):
    # none imports a plotting library (WP-1402, WP-1461, WP-1470); all stay
    # out of the base import, which a plot does not need
    if name in _FIGURE3D:
        from . import figure3d

        return getattr(figure3d, name)
    if name == "plot_strain_surface":
        from .strain import plot_strain_surface

        return plot_strain_surface
    if name == "write_html":
        from .html import write_html

        return write_html
    if name == "LiveSession":
        from .live import LiveSession

        return LiveSession
    raise AttributeError(name)
