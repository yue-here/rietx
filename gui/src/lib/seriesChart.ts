/**
 * The Series panel's figures (WP-1461).
 *
 * `Series.svelte` imports this module on its first draw, so uPlot is fetched
 * then and never at boot, as `lib/pattern.ts` does for the pattern panel. It
 * binds the vendored uPlot to the chart module's three figures the panel shows:
 * a parameter's trajectory across the series, one member's pattern, and the
 * trace the reader scrubs along (WP-1317).
 */

import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { pattern, trace, trajectory, unpack, type Curves, type Pattern, type PatternSpec,
         type TraceData, type TraceFigure, type TraceSpec,
         type TrajectoryData, type TrajectoryFigure, type TrajectorySpec } from "rxplot";

export { unpack };

export function mountTrajectory(host: HTMLElement, traj: TrajectoryData,
                                spec: TrajectorySpec): TrajectoryFigure {
  return trajectory(uPlot, host, traj, spec);
}

export function mountMember(host: HTMLElement, curves: Curves, spec: PatternSpec): Pattern {
  return pattern(uPlot, host, curves, spec);
}

export function mountTrace(host: HTMLElement, data: TraceData, spec: TraceSpec): TraceFigure {
  return trace(uPlot, host, data, spec);
}
