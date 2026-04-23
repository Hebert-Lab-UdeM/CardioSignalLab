"""Bad segment overlay for PyQtGraph plots.

Renders bad segments as semi-transparent shaded regions (BadSegmentOverlay)
or as colored trace lines at gap locations (GapSegmentOverlay).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from loguru import logger
from PySide6.QtGui import QColor

if TYPE_CHECKING:
    from cardio_signal_lab.core import BadSegment, SignalData


# Orange shading for detected bad segments — clearly distinct from the red event lines
_FILL_COLOR = QColor(255, 140, 0, 55)   # RGBA: semi-transparent amber
_BORDER_COLOR = QColor(200, 100, 0, 130)

# Blue/purple shading for interpolated segments — visually distinct from detected
_INTERP_FILL_COLOR = QColor(80, 120, 220, 50)
_INTERP_BORDER_COLOR = QColor(60, 90, 200, 120)

# Red for timestamp gap segments — drawn as colored trace lines, not shaded regions
_GAP_PEN_COLOR = QColor(220, 50, 50)


class BadSegmentOverlay:
    """Overlay that renders bad segments as shaded regions on a plot.

    Usage:
        overlay = BadSegmentOverlay(plot_widget)
        overlay.set_bad_segments(signal.bad_segments, signal)
        overlay.clear()
    """

    def __init__(self, plot_widget, fill_color=None, border_color=None):
        """Initialize overlay.

        Args:
            plot_widget: SignalPlotWidget (or any pg.PlotWidget) to attach to
            fill_color: QColor for region fill (defaults to amber for detected segments)
            border_color: QColor for region border (defaults to dark amber)
        """
        self.plot_widget = plot_widget
        self._fill_color = fill_color or _FILL_COLOR
        self._border_color = border_color or _BORDER_COLOR
        self._visible = True
        self._regions: list[pg.LinearRegionItem] = []

        if hasattr(plot_widget, "plotItem"):
            self.plot_item = plot_widget.plotItem
        else:
            self.plot_item = plot_widget

        logger.debug("BadSegmentOverlay initialized")

    def set_bad_segments(self, bad_segments: list[BadSegment], signal: SignalData):
        """Render bad segments as shaded red regions.

        Converts sample indices to time coordinates using signal.timestamps,
        then places a LinearRegionItem for each segment.

        Args:
            bad_segments: List of BadSegment objects
            signal: SignalData used to map indices to timestamps
        """
        self.clear()

        if not bad_segments:
            return

        timestamps = signal.timestamps

        for seg in bad_segments:
            start_idx = max(0, seg.start_idx)
            end_idx = min(len(timestamps) - 1, seg.end_idx)

            t_start = float(timestamps[start_idx])
            t_end = float(timestamps[end_idx])

            region = pg.LinearRegionItem(
                values=(t_start, t_end),
                orientation="vertical",
                brush=self._fill_color,
                pen=pg.mkPen(color=self._border_color, width=1),
                movable=False,
            )
            region.setVisible(self._visible)
            # Disable z-ordering interference with signal line
            region.setZValue(-10)

            self.plot_item.addItem(region)
            self._regions.append(region)

        logger.info(
            f"BadSegmentOverlay: rendered {len(bad_segments)} segment(s) "
            f"(visible={self._visible})"
        )

    def clear(self):
        """Remove all region items from the plot."""
        for region in self._regions:
            self.plot_item.removeItem(region)
        self._regions.clear()
        logger.debug("BadSegmentOverlay cleared")

    def set_visible(self, visible: bool):
        """Show or hide all shaded regions.

        Args:
            visible: True to show, False to hide
        """
        self._visible = visible
        for region in self._regions:
            region.setVisible(visible)
        logger.debug(f"BadSegmentOverlay visibility: {visible}")

    def toggle_visibility(self):
        """Toggle between visible and hidden."""
        self.set_visible(not self._visible)

    def is_visible(self) -> bool:
        """Return current visibility state."""
        return self._visible

    def num_segments(self) -> int:
        """Return number of segments currently displayed."""
        return len(self._regions)


class GapSegmentOverlay:
    """Overlay that colors signal trace at timestamp-gap locations.

    Each gap (start_idx, end_idx) is drawn as a 2-point PlotCurveItem
    connecting the last sample before the gap to the first sample after it,
    using the current signal's y-values. This colors the connecting line red
    without obscuring surrounding signal — a shaded region would be invisible
    at the typical 1-2 sample gap width.

    Call set_gap_segments() again after any processing step that changes sample
    values, so y-positions stay accurate.
    """

    def __init__(self, plot_widget):
        """Initialize overlay.

        Args:
            plot_widget: SignalPlotWidget (or any pg.PlotWidget) to attach to
        """
        self.plot_widget = plot_widget
        if hasattr(plot_widget, "plotItem"):
            self.plot_item = plot_widget.plotItem
        else:
            self.plot_item = plot_widget
        self._curves: list[pg.PlotCurveItem] = []
        self._visible = True

    def set_gap_segments(self, gap_segments: list, signal: SignalData):
        """Draw colored line segments at gap locations using current signal samples.

        Args:
            gap_segments: List of BadSegment objects (source="gap")
            signal: SignalData providing current timestamps and samples for y-values
        """
        self.clear()
        if not gap_segments:
            return

        pen = pg.mkPen(color=_GAP_PEN_COLOR, width=2)
        n = len(signal.timestamps)

        for seg in gap_segments:
            i0 = max(0, seg.start_idx)
            i1 = min(n - 1, seg.end_idx)
            if i0 >= n or i1 >= n or i0 >= i1:
                continue
            t = np.array([signal.timestamps[i0], signal.timestamps[i1]])
            s = np.array([signal.samples[i0], signal.samples[i1]])
            curve = pg.PlotCurveItem(t, s, pen=pen)
            curve.setZValue(5)  # Draw above signal line
            curve.setVisible(self._visible)
            self.plot_item.addItem(curve)
            self._curves.append(curve)

        logger.info(
            f"GapSegmentOverlay: rendered {len(self._curves)} gap segment(s) "
            f"(visible={self._visible})"
        )

    def clear(self):
        """Remove all gap curve items from the plot."""
        for curve in self._curves:
            self.plot_item.removeItem(curve)
        self._curves.clear()

    def set_visible(self, visible: bool):
        """Show or hide all gap curves."""
        self._visible = visible
        for curve in self._curves:
            curve.setVisible(visible)

    def num_segments(self) -> int:
        """Return number of gap segments currently displayed."""
        return len(self._curves)
