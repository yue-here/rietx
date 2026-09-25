// svgcanvas ships no types. The chart module's SVG export (WP-1461, D6) is its
// one user, and it needs the constructor and nothing else by name.
declare module "svgcanvas" {
  export class Context {
    constructor(options: { width: number; height: number });
    getSvg(): SVGSVGElement;
  }
}
