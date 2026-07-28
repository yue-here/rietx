from .plots import plot_for_vlm, plot_result, plot_trajectory

__all__ = ["LiveSession", "plot_for_vlm", "plot_result",
           "plot_trajectory", "write_html"]


def __getattr__(name: str):
    # write_html/LiveSession import plotly lazily — keep base import light
    if name == "write_html":
        from .html import write_html

        return write_html
    if name == "LiveSession":
        from .live import LiveSession

        return LiveSession
    raise AttributeError(name)
