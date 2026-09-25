// The types of `src/rietx/viz/static/rxplot.mjs`, which is javascript because
// `rietx watch` and `rietx compare` serve it to a page as it is (WP-1461, D3).
// `vite.config.ts` aliases the name to the file. What is declared here is what
// the GUI calls, so a new use of the module declares its part here first.

declare module "rxplot" {
  /** An unpacked curves payload (D4): the header, and a view per array. */
  export interface Curves {
    header: Record<string, any>;
    arrays: Record<string, Float64Array | Int32Array>;
  }

  export function unpack(buffer: ArrayBuffer): Curves;
  export function lower(xs: ArrayLike<number>, v: number): number;
  export function chi2Base(cum: ArrayLike<number>, xs: ArrayLike<number>, lo: number): number;
  export function token(name: string, el?: Element): string;
  export function hklLabel(hkl: unknown): string;
  export function vlines(u: any, xs: ArrayLike<number>, top: number, height: number,
                         color: string): void;
  export function tsv(names: readonly string[], rows: readonly (readonly unknown[])[]): string;
  export function download(blob: Blob, name: string): void;

  export interface Hit { key: string; idx: number; x: number; left: number; top: number }

  export interface Group {
    panes: Record<string, any>;
    mode: "zoom" | "select";
    onSelect: ((lo: number, hi: number, key: string) => void) | null;
    onCursor: ((hit: Hit | null) => void) | null;
    setX(lo: number, hi: number): void;
    setMode(mode: "zoom" | "select"): void;
    reset(): void;
    unpin(key?: string): void;
    redraw(): void;
    destroy(): void;
    /** The exports (D6), each on the figure as drawn now, at the reader's zoom. */
    inView(): [number, number];
    image(): HTMLCanvasElement;
    png(): Promise<Blob>;
    copyImage(): Promise<Blob>;
    svg(load: () => Promise<{ Context: any }>): Promise<string>;
    tsv(): string;
    table: (() => { names: string[]; rows: unknown[][] }) | null | undefined;
  }

  export interface PatternColors {
    obs: string; masked: string; calc: string; bkg: string; diff: string; zero: string;
    phase: string[];
  }

  export type Layer = (u: any) => void;

  export interface PatternSpec {
    colors: () => PatternColors;
    y?: "lin" | "sqrt" | "log";
    residual?: "weighted" | "delta" | "cumulative";
    hidden?: readonly string[];
    labels?: { y?: () => string; resid?: () => string };
    layers?: Record<string, { under?: Layer[]; over?: Layer[] }>;
    rawResidual?: () => ArrayLike<number | null> | null;
  }

  export interface Pattern extends Group {
    setCurves(curves: Curves, keep?: boolean): void;
    setY(kind: "lin" | "sqrt" | "log"): void;
    setResidual(kind: "weighted" | "delta" | "cumulative"): void;
    setHidden(ids: readonly string[]): void;
    refreshResidual(): void;
    chi2Base(): number;
  }

  export function pattern(uPlot: any, host: HTMLElement, curves: Curves,
                          spec: PatternSpec): Pattern;

  /** A parameter across a series, in chain order. A null is a point with no value. */
  export interface TrajectoryData {
    x: readonly number[];
    value: readonly (number | null)[];
    stderr?: readonly (number | null)[];
    backward?: readonly (number | null)[] | null;
  }

  export type TrajectoryMark = "forward" | "esd" | "backward" | "rings" | "crosses";

  export interface TrajectorySpec {
    colors: () => { tone: string; warn: string; muted: string };
    dashed?: boolean;
    rings?: readonly boolean[];
    crosses?: readonly boolean[];
    hidden?: readonly TrajectoryMark[];
    xLabel?: string;
    yLabel?: string;
  }

  export interface PointHit { i: number; chain: "forward" | "backward"; left: number; top: number }

  export interface TrajectoryFigure extends Group {
    onPoint: ((hit: PointHit | null) => void) | null;
    setHidden(ids: readonly TrajectoryMark[]): void;
  }

  export function trajectory(uPlot: any, host: HTMLElement, traj: TrajectoryData,
                             spec: TrajectorySpec): TrajectoryFigure;
}
