/** The structure viewer's renderer: ray-cast quadrics in WebGL2 (WP-1462).
 *
 * Every atom is one screen-aligned quad whose fragment shader solves the
 * ellipsoid `|M⁻¹(p − c)| = 1` along the pixel's ray and writes the hit's
 * depth; every bond half is one quad solved as a finite cylinder.  The surface
 * is exact at any zoom and any export size, and a scene costs four vertices a
 * primitive.  This is how Mol\*, NGL and VMD draw atoms (Sigg et al. 2006,
 * Gumhold 2003); the projection is parallel, so every ray has one direction.
 *
 * The module draws a `Scene` from a `View` and knows nothing else:
 * `lib/structure3d.ts` builds both, as pure functions a test can read, and
 * solves the same equations for hover.  jsdom has no WebGL, so the component
 * tests run against `test-gl3d.ts`, which records what it was asked to draw;
 * what a browser paints is `tests/test_structure3d_browser.py`'s.
 *
 * Three facts shape the code:
 *
 * - **An impostor's outline is a `discard`, which MSAA does not smooth.** The
 *   shaders compute their own coverage from the ray's discriminant and hand it
 *   to alpha-to-coverage on a multisampled buffer (D7).
 * - **Alpha-to-coverage writes that coverage into the samples it keeps**, so it
 *   is right only where alpha is thrown away: the canvas is opaque and cleared
 *   to the panel's colour.  A transparent export renders twice, on black and on
 *   white, and takes alpha from the difference.
 * - **A WebGL line is one device pixel** — half a CSS pixel at DPR 2, a
 *   hairline in a 3000 px export — so the cell frame is quads with a width in
 *   CSS pixels that scales with both (D9).
 */

import {
  fogSpan,
  LOOK,
  pixelsPerAngstrom,
  POLY_ALPHA,
  type Scene,
  type View,
} from "./structure3d";

/** A number as a GLSL float literal, which needs its decimal point. */
function f(x: number): string {
  return Number.isInteger(x) ? x.toFixed(1) : String(x);
}

const LIGHT = `const vec3 LIGHT = vec3(${LOOK.light.map(f).join(", ")});`;

const COMMON = `
uniform mat3 uR; uniform vec3 uCenter; uniform vec2 uPan; uniform vec2 uScale;
uniform float uDepth;
vec3 toView(vec3 p) { vec3 v = uR * (p - uCenter); return vec3(v.xy - uPan, v.z); }`;

/** Depth cueing (WP-1548 D1): a colour blended toward the background by its
 *  view-space depth z, linearly from `uFog.x` (nothing) to `uFog.y` (`uFog.z`
 *  of the way), as GLSL's `mix`.  The colour is clamped first, as the Python
 *  raster clamps before it fogs, so a highlight past white fades from white.
 *  `uFog.z` at 0 is off and returns the colour untouched. */
const FOG = `
uniform vec3 uFog; uniform vec3 uFogColor;
vec3 fog(vec3 col, float z) {
  if (uFog.z <= 0.0) return col;
  float f = uFog.z * clamp((uFog.x - z) / (uFog.x - uFog.y), 0.0, 1.0);
  return mix(clamp(col, 0.0, 1.0), uFogColor, f);
}`;

/** Shading shared by every solid: one key light up and to the left of the
 *  screen, fixed to the camera, so the lit side follows every rotation. */
const SHADE = `
${LIGHT}
vec3 shade(vec3 base, vec3 n) {
  vec3 l = normalize(LIGHT);
  float diffuse = max(dot(n, l), 0.0);
  float spec = pow(max(dot(reflect(-l, n), vec3(0.0, 0.0, 1.0)), 0.0), ${f(LOOK.shininess)});
  return base * (${f(LOOK.ambient)} + ${f(LOOK.diffuse)} * diffuse) + ${f(LOOK.specular)} * spec;
}`;

const ATOM_VS = `#version 300 es
in vec2 aCorner;
in vec3 aCenter;
in vec3 aM0; in vec3 aM1; in vec3 aM2;
in vec3 aI0; in vec3 aI1; in vec3 aI2;
in vec4 aColor;
uniform float uPad;
${COMMON}
out vec2 vXY;
flat out vec3 vC; flat out mat3 vMinv; flat out vec4 vColor;
void main() {
  mat3 M = uR * mat3(aM0, aM1, aM2);
  vec3 c = toView(aCenter);
  // the projected ellipsoid's exact half-extents are the norms of M's first
  // two rows; the pad leaves room for the antialiased fringe
  vec2 h = vec2(length(vec3(M[0][0], M[1][0], M[2][0])),
                length(vec3(M[0][1], M[1][1], M[2][1]))) + uPad;
  vXY = c.xy + aCorner * h;
  vC = c;
  vMinv = mat3(aI0, aI1, aI2) * transpose(uR);
  vColor = aColor;
  gl_Position = vec4(vXY * uScale, 0.0, 1.0);
}`;

const ATOM_FS = `#version 300 es
precision highp float;
in vec2 vXY;
flat in vec3 vC; flat in mat3 vMinv; flat in vec4 vColor;
uniform float uDepth;
${SHADE}
${FOG}
out vec4 frag;
void main() {
  // the ray (x, y, z) with z free is u = q + s·e in the unit-sphere frame
  vec3 q = vMinv * vec3(vXY - vC.xy, 0.0);
  vec3 e = vMinv[2];
  float a = dot(e, e), b = dot(q, e), cc = dot(q, q) - 1.0;
  float disc = b * b - a * cc;
  float w = max(fwidth(disc), 1e-12);
  float coverage = clamp(0.5 + disc / w, 0.0, 1.0);
  if (coverage <= 0.0) discard;
  float s = (-b + sqrt(max(disc, 0.0))) / a;     // the root nearer the viewer
  vec3 u = q + s * e;
  vec3 n = normalize(transpose(vMinv) * u);
  float z = vC.z + s;
  gl_FragDepth = clamp(0.5 - z / (2.0 * uDepth), 0.0, 1.0);
  vec3 col = shade(vColor.rgb, n);
  if (vColor.a > 0.5) {
    // the three principal ellipses: T's columns are the principal axes, so a
    // ring is one unit-frame coordinate near zero; the ink is darker on a
    // light atom and lighter on a dark one, or a violet atom hides its rings
    float m = min(abs(u.x), min(abs(u.y), abs(u.z)));
    float lum = dot(vColor.rgb, vec3(${LOOK.luma.map(f).join(", ")}));
    vec3 ink = lum < ${f(LOOK.ring_dark)} ? mix(col, vec3(1.0), ${f(LOOK.ring_lighten)})
                                          : col * ${f(LOOK.ring_darken)};
    col = mix(ink, col, smoothstep(${f(LOOK.ring_width)}, ${f(LOOK.ring_width)} + fwidth(m), m));
  }
  frag = vec4(fog(col, z), coverage);
}`;

const HALF_VS = `#version 300 es
in vec2 aCorner;              // x in {0, 1} along the bond, y in {-1, 1} across it
in vec3 aA; in vec3 aB; in vec3 aColor; in float aRadius;
uniform float uPad;
${COMMON}
out vec2 vXY;
flat out vec3 vA; flat out vec3 vB; flat out vec3 vColor; flat out float vR;
void main() {
  vec3 A = toView(aA), B = toView(aB);
  vec2 d = B.xy - A.xy;
  float l = length(d);
  vec2 dir = l > 1e-6 ? d / l : vec2(1.0, 0.0);
  vec2 perp = vec2(-dir.y, dir.x);
  float r = aRadius + uPad;
  vXY = mix(A.xy, B.xy, aCorner.x) + dir * (2.0 * aCorner.x - 1.0) * r
      + perp * aCorner.y * r;
  vA = A; vB = B; vColor = aColor; vR = aRadius;
  gl_Position = vec4(vXY * uScale, 0.0, 1.0);
}`;

const HALF_FS = `#version 300 es
precision highp float;
in vec2 vXY;
flat in vec3 vA; flat in vec3 vB; flat in vec3 vColor; flat in float vR;
uniform float uDepth;
${SHADE}
${FOG}
out vec4 frag;
void main() {
  // The ray (x, y, z) with z free, against the finite cylinder A-B, open at
  // both ends: the far end is buried in its own atom (stickRadius' proof) and
  // the near end meets the other half.  Taken apart along the axis w, a point
  // is at radius |q + z·e| from it, with q and e the ray's origin and
  // direction with their parts along w removed — the ellipsoid's equation
  // with a circle for the sphere.
  float len = length(vB - vA);
  if (len < 1e-9) discard;
  vec3 w = (vB - vA) / len;
  vec3 o = vec3(vXY, 0.0) - vA;
  vec3 dz = vec3(0.0, 0.0, 1.0);
  vec3 q = o - dot(o, w) * w, e = dz - dot(dz, w) * w;
  float a = dot(e, e);
  if (a < 1e-9) discard;                     // looking straight down the bond
  float b = dot(q, e), disc = b * b - a * (dot(q, q) - vR * vR);
  float fw = max(fwidth(disc), 1e-12);
  float coverage = clamp(0.5 + disc / fw, 0.0, 1.0);
  if (coverage <= 0.0) discard;
  float z = (-b + sqrt(max(disc, 0.0))) / a;  // the root nearer the viewer
  float along = dot(o, w) + z * dot(dz, w);
  if (along < 0.0 || along > len) discard;
  vec3 n = normalize((q + z * e) / vR);
  gl_FragDepth = clamp(0.5 - z / (2.0 * uDepth), 0.0, 1.0);
  frag = vec4(fog(shade(vColor, n), z), coverage);
}`;

const LINE_VS = `#version 300 es
in vec2 aCorner;              // x in {0, 1} along the segment, y in {-1, 1} across
in vec3 aA; in vec3 aB; in vec3 aColor; in float aWidth;
uniform vec2 uViewport;       // device pixels
uniform float uPxScale;       // device pixels per CSS pixel
${COMMON}
out float vAcross; out float vZ;
flat out float vHalf; flat out vec3 vColor;
void main() {
  vec3 A = toView(aA), B = toView(aB);
  vec2 a = A.xy * uScale, b = B.xy * uScale;
  vec2 d = (b - a) * uViewport;
  vec2 dir = length(d) > 1e-6 ? normalize(d) : vec2(1.0, 0.0);
  vec2 perp = vec2(-dir.y, dir.x);
  float half_ = 0.5 * aWidth * uPxScale;
  float reach = half_ + 1.0;                 // one device pixel of fringe
  vec2 px = (dir * (2.0 * aCorner.x - 1.0) * half_ + perp * aCorner.y * reach)
          * 2.0 / uViewport;
  float z = mix(A.z, B.z, aCorner.x);
  vAcross = aCorner.y * reach;
  vZ = z;
  vHalf = half_;
  vColor = aColor;
  gl_Position = vec4(mix(a, b, aCorner.x) + px, -z / uDepth, 1.0);
}`;

const LINE_FS = `#version 300 es
precision highp float;
in float vAcross; in float vZ;
flat in float vHalf; flat in vec3 vColor;
${FOG}
out vec4 frag;
void main() {
  float coverage = clamp(vHalf + 0.5 - abs(vAcross), 0.0, 1.0);
  if (coverage <= 0.0) discard;
  frag = vec4(fog(vColor, vZ), coverage);
}`;

/** A polyhedron's faces (WP-1466): flat triangles lit from both sides, so a
 *  back face seen through a front one is shaded as the side it shows. */
const FACE_VS = `#version 300 es
in vec3 aPos; in vec3 aNormal; in vec3 aColor;
${COMMON}
out vec3 vN; out float vZ;
flat out vec3 vColor;
void main() {
  vec3 p = toView(aPos);
  vZ = p.z;
  vN = uR * aNormal;
  vColor = aColor;
  gl_Position = vec4(p.xy * uScale, -p.z / uDepth, 1.0);
}`;

const FACE_FS = `#version 300 es
precision highp float;
in vec3 vN; in float vZ;
flat in vec3 vColor;
uniform float uAlpha;
${LIGHT}
${FOG}
out vec4 frag;
void main() {
  vec3 n = normalize(gl_FrontFacing ? vN : -vN);
  frag = vec4(fog(vColor * (${f(LOOK.ambient)} + ${f(LOOK.face_diffuse)}
                            * max(dot(n, normalize(LIGHT)), 0.0)), vZ), uAlpha);
}`;

/** The long side of an exported PNG, in pixels (D5): a 17 cm figure at
 *  300 dpi is 2008 px, and this leaves room to crop. */
export const EXPORT_LONG_SIDE = 3000;

/** One label as the export draws it, in CSS pixels of the canvas. */
export interface ExportLabel {
  text: string;
  x: number;
  y: number;
  color: string;
  font: string;
}

export interface ExportOptions {
  /** the clear colour, 0..1; `null` for a transparent background */
  background: number[] | null;
  labels: ExportLabel[];
  longSide?: number;
}

export interface ExportedPng {
  blob: Blob;
  width: number;
  height: number;
}

export interface Renderer {
  /** upload a scene; the next `draw` shows it */
  setScene(scene: Scene): void;
  /** fade each surface toward the background with its depth (WP-1548); off
   *  by default, and an export on a transparent background draws without it */
  setDepthCue(on: boolean): void;
  /** draw one frame at the canvas's size, on `background` (0..1 RGB) */
  draw(view: View, background: number[]): void;
  /** render once more, offscreen and larger, to a PNG, with the size it came
   *  out at: smaller than asked where the GPU could not allocate that */
  exportPng(view: View, options: ExportOptions): Promise<ExportedPng | null>;
  dispose(): void;
}

interface Program {
  program: WebGLProgram;
  uniforms: Record<string, WebGLUniformLocation | null>;
}

interface Batch {
  vao: WebGLVertexArrayObject;
  buffers: WebGLBuffer[];
  count: number;
}

const ATOM_LAYOUT: Array<[string, number]> = [
  ["aCenter", 3], ["aM0", 3], ["aM1", 3], ["aM2", 3],
  ["aI0", 3], ["aI1", 3], ["aI2", 3], ["aColor", 4],
];
const HALF_LAYOUT: Array<[string, number]> = [["aA", 3], ["aB", 3], ["aColor", 3], ["aRadius", 1]];
const LINE_LAYOUT: Array<[string, number]> = [["aA", 3], ["aB", 3], ["aColor", 3], ["aWidth", 1]];

/** A row-major 3×3 as the three columns GLSL's `mat3(c0, c1, c2)` wants. */
function columns(m: number[]): number[] {
  return [m[0], m[3], m[6], m[1], m[4], m[7], m[2], m[5], m[8]];
}

/** The polyhedra as one vertex array, nine numbers a vertex (position,
 *  normal, colour), and each polyhedron's range of it — pure, so a test can
 *  read them. */
export function faceData(scene: Scene): { vertices: Float32Array;
                                          ranges: Array<{ first: number; count: number;
                                                          centroid: number[] }> } {
  const total = scene.faces.reduce((n, f) => n + f.triangles.length / 3, 0);
  const vertices = new Float32Array(total * 9);
  const ranges: Array<{ first: number; count: number; centroid: number[] }> = [];
  let at = 0;
  for (const polyhedron of scene.faces) {
    const first = at;
    const t = polyhedron.triangles;
    for (let k = 0; k < t.length / 3; k += 1) {
      const n = polyhedron.normals.slice(3 * Math.floor(k / 3), 3 * Math.floor(k / 3) + 3);
      vertices.set([t[3 * k], t[3 * k + 1], t[3 * k + 2], ...n, ...polyhedron.color], 9 * at);
      at += 1;
    }
    ranges.push({ first, count: at - first, centroid: polyhedron.centroid });
  }
  return { vertices, ranges };
}

/** The scene's per-instance arrays — pure, so a test can read them. */
export function instanceData(scene: Scene): { atoms: Float32Array; halves: Float32Array;
                                              lines: Float32Array } {
  const atoms = new Float32Array(scene.atoms.length * 25);
  scene.atoms.forEach((atom, i) => {
    atoms.set([...atom.pos, ...columns(atom.shape), ...columns(atom.inverse),
               ...atom.color, atom.rings ? 1 : 0], 25 * i);
  });
  const halves = new Float32Array(scene.halves.length * 10);
  scene.halves.forEach((half, i) => {
    halves.set([...half.from, ...half.to, ...half.color, half.radius], 10 * i);
  });
  const lines = new Float32Array(scene.lines.length * 10);
  scene.lines.forEach((line, i) => {
    lines.set([...line.a, ...line.b, ...line.color, line.width], 10 * i);
  });
  return { atoms, halves, lines };
}

/**
 * A renderer on `canvas`, or `null` where the browser has no WebGL2 or cannot
 * build these shaders with it (a context lost at birth, a driver's refusal).
 *
 * One context for the viewer's life: browsers keep about sixteen a page and
 * drop the oldest past that without a word, so `dispose` gives it back at once
 * rather than waiting for a collection.
 */
export function createRenderer(canvas: HTMLCanvasElement): Renderer | null {
  const gl = canvas.getContext("webgl2", {
    antialias: true, alpha: false, premultipliedAlpha: false,
    preserveDrawingBuffer: false,
  }) as WebGL2RenderingContext | null;
  if (!gl || gl.isContextLost()) return null;
  const context: WebGL2RenderingContext = gl;

  let programs: { atom: Program; half: Program; line: Program; face: Program } | null = null;
  let batches: { atoms: Batch; halves: Batch; lines: Batch; faces: Batch } | null = null;
  let faceRanges: Array<{ first: number; count: number; centroid: number[] }> = [];
  let corner: { atom: WebGLBuffer; strip: WebGLBuffer } | null = null;
  let scene: Scene | null = null;
  let last: { view: View; background: number[] } | null = null;
  let depthCue = false;
  let lost = false;

  function compile(vs: string, fs: string): Program {
    const program = context.createProgram()!;
    for (const [type, source] of [[context.VERTEX_SHADER, vs], [context.FRAGMENT_SHADER, fs]] as const) {
      const shader = context.createShader(type)!;
      context.shaderSource(shader, source);
      context.compileShader(shader);
      if (!context.getShaderParameter(shader, context.COMPILE_STATUS)) {
        throw new Error(`structure viewer shader: ${context.getShaderInfoLog(shader)}`);
      }
      context.attachShader(program, shader);
      context.deleteShader(shader);
    }
    context.linkProgram(program);
    if (!context.getProgramParameter(program, context.LINK_STATUS)) {
      throw new Error(`structure viewer program: ${context.getProgramInfoLog(program)}`);
    }
    const uniforms: Record<string, WebGLUniformLocation | null> = {};
    const n = context.getProgramParameter(program, context.ACTIVE_UNIFORMS);
    for (let i = 0; i < n; i += 1) {
      const name = context.getActiveUniform(program, i)!.name;
      uniforms[name] = context.getUniformLocation(program, name);
    }
    return { program, uniforms };
  }

  function init() {
    programs = {
      atom: compile(ATOM_VS, ATOM_FS),
      half: compile(HALF_VS, HALF_FS),
      line: compile(LINE_VS, LINE_FS),
      face: compile(FACE_VS, FACE_FS),
    };
    const buffer = (data: number[]) => {
      const b = context.createBuffer()!;
      context.bindBuffer(context.ARRAY_BUFFER, b);
      context.bufferData(context.ARRAY_BUFFER, new Float32Array(data), context.STATIC_DRAW);
      return b;
    };
    corner = { atom: buffer([-1, -1, 1, -1, -1, 1, 1, 1]), strip: buffer([0, -1, 1, -1, 0, 1, 1, 1]) };
  }

  function batch(program: Program, cornerBuffer: WebGLBuffer,
                 layout: Array<[string, number]>, data: Float32Array, width: number): Batch {
    const vao = context.createVertexArray()!;
    context.bindVertexArray(vao);
    context.bindBuffer(context.ARRAY_BUFFER, cornerBuffer);
    const at = context.getAttribLocation(program.program, "aCorner");
    context.enableVertexAttribArray(at);
    context.vertexAttribPointer(at, 2, context.FLOAT, false, 0, 0);
    const instances = context.createBuffer()!;
    context.bindBuffer(context.ARRAY_BUFFER, instances);
    context.bufferData(context.ARRAY_BUFFER, data, context.STATIC_DRAW);
    let offset = 0;
    for (const [name, size] of layout) {
      const location = context.getAttribLocation(program.program, name);
      if (location >= 0) {
        context.enableVertexAttribArray(location);
        context.vertexAttribPointer(location, size, context.FLOAT, false, width * 4, offset);
        context.vertexAttribDivisor(location, 1);
      }
      offset += size * 4;
    }
    context.bindVertexArray(null);
    return { vao, buffers: [instances], count: data.length / width };
  }

  /** The polyhedra's triangles, one vertex each, drawn without instancing. */
  function faceBatch(program: Program, data: Float32Array): Batch {
    const vao = context.createVertexArray()!;
    context.bindVertexArray(vao);
    const buffer = context.createBuffer()!;
    context.bindBuffer(context.ARRAY_BUFFER, buffer);
    context.bufferData(context.ARRAY_BUFFER, data, context.STATIC_DRAW);
    let offset = 0;
    for (const [name, size] of [["aPos", 3], ["aNormal", 3], ["aColor", 3]] as const) {
      const location = context.getAttribLocation(program.program, name);
      if (location >= 0) {
        context.enableVertexAttribArray(location);
        context.vertexAttribPointer(location, size, context.FLOAT, false, 9 * 4, offset);
      }
      offset += size * 4;
    }
    context.bindVertexArray(null);
    return { vao, buffers: [buffer], count: data.length / 9 };
  }

  function release() {
    if (!batches) return;
    for (const b of Object.values(batches)) {
      context.deleteVertexArray(b.vao);
      for (const buffer of b.buffers) context.deleteBuffer(buffer);
    }
    batches = null;
  }

  function upload() {
    release();
    if (!scene || !programs || !corner) return;
    const data = instanceData(scene);
    const faces = faceData(scene);
    faceRanges = faces.ranges;
    batches = {
      atoms: batch(programs.atom, corner.atom, ATOM_LAYOUT, data.atoms, 25),
      halves: batch(programs.half, corner.strip, HALF_LAYOUT, data.halves, 10),
      lines: batch(programs.line, corner.strip, LINE_LAYOUT, data.lines, 10),
      faces: faceBatch(programs.face, faces.vertices),
    };
  }

  /**
   * One frame into whatever framebuffer is bound, `width` × `height` device
   * pixels for a canvas of `cssWidth` × `cssHeight`.
   */
  function render(view: View, background: number[], width: number, height: number,
                  cssWidth: number, cssHeight: number, cue = depthCue) {
    if (!scene || !programs || !batches) return;
    const span = cue ? fogSpan(scene, view.rotation) : null;
    const fogUniform = span ? [span[0], span[1], LOOK.fog_max] : [0, -1, 0];
    const s = pixelsPerAngstrom(scene, view, cssWidth, cssHeight);
    const pxScale = width / cssWidth;
    context.viewport(0, 0, width, height);
    context.clearColor(background[0], background[1], background[2], 1);
    context.clearDepth(1);
    context.enable(context.DEPTH_TEST);
    context.depthFunc(context.LEQUAL);
    context.depthMask(true);
    context.disable(context.BLEND);
    context.enable(context.SAMPLE_ALPHA_TO_COVERAGE);
    context.clear(context.COLOR_BUFFER_BIT | context.DEPTH_BUFFER_BIT);
    const common = (p: Program) => {
      context.useProgram(p.program);
      context.uniformMatrix3fv(p.uniforms.uR, false, columns(view.rotation));
      context.uniform3fv(p.uniforms.uCenter, scene!.center);
      context.uniform2fv(p.uniforms.uPan, view.pan);
      context.uniform2f(p.uniforms.uScale, 2 * s / cssWidth, 2 * s / cssHeight);
      context.uniform1f(p.uniforms.uDepth, scene!.depth);
      // one and a half device pixels, in Å, for the antialiased fringe
      if (p.uniforms.uPad) context.uniform1f(p.uniforms.uPad, 1.5 / (s * pxScale));
      context.uniform3fv(p.uniforms.uFog, fogUniform);
      context.uniform3fv(p.uniforms.uFogColor, background.slice(0, 3));
    };
    common(programs.atom);
    context.bindVertexArray(batches.atoms.vao);
    context.drawArraysInstanced(context.TRIANGLE_STRIP, 0, 4, batches.atoms.count);
    common(programs.half);
    context.bindVertexArray(batches.halves.vao);
    context.drawArraysInstanced(context.TRIANGLE_STRIP, 0, 4, batches.halves.count);
    common(programs.line);
    context.uniform2f(programs.line.uniforms.uViewport, width, height);
    context.uniform1f(programs.line.uniforms.uPxScale, pxScale);
    context.bindVertexArray(batches.lines.vao);
    context.drawArraysInstanced(context.TRIANGLE_STRIP, 0, 4, batches.lines.count);
    context.disable(context.SAMPLE_ALPHA_TO_COVERAGE);
    if (faceRanges.length) {
      // Translucent faces last, blended rather than through coverage: tested
      // against the depth of everything opaque and writing none, the farthest
      // polyhedron first and each one's back faces before its front.  Whole
      // polyhedra can be ordered because coordination polyhedra share
      // corners, edges or faces and never overlap in volume (WP-1462
      // § Polyhedra).
      common(programs.face);
      context.uniform1f(programs.face.uniforms.uAlpha, POLY_ALPHA);
      context.enable(context.BLEND);
      context.blendFunc(context.SRC_ALPHA, context.ONE_MINUS_SRC_ALPHA);
      context.depthMask(false);
      context.enable(context.CULL_FACE);
      context.bindVertexArray(batches.faces.vao);
      const r = view.rotation, c = scene.center;
      const depth = (p: number[]) => r[6] * (p[0] - c[0]) + r[7] * (p[1] - c[1]) + r[8] * (p[2] - c[2]);
      for (const range of [...faceRanges].sort((p, q) => depth(p.centroid) - depth(q.centroid))) {
        context.cullFace(context.FRONT);
        context.drawArrays(context.TRIANGLES, range.first, range.count);
        context.cullFace(context.BACK);
        context.drawArrays(context.TRIANGLES, range.first, range.count);
      }
      context.disable(context.CULL_FACE);
      context.depthMask(true);
      context.disable(context.BLEND);
    }
    context.bindVertexArray(null);
  }

  function draw(view: View, background: number[]) {
    last = { view, background };
    if (lost) return;
    const dpr = window.devicePixelRatio || 1;
    const cssWidth = canvas.clientWidth, cssHeight = canvas.clientHeight;
    if (!cssWidth || !cssHeight) return;
    const width = Math.round(cssWidth * dpr), height = Math.round(cssHeight * dpr);
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    context.bindFramebuffer(context.FRAMEBUFFER, null);
    render(view, background, width, height, cssWidth, cssHeight);
  }

  function exportSize(longSide = EXPORT_LONG_SIDE): { width: number; height: number } {
    const cssWidth = canvas.clientWidth || 1, cssHeight = canvas.clientHeight || 1;
    const limit = Math.min(context.getParameter(context.MAX_RENDERBUFFER_SIZE) as number,
                           ...(context.getParameter(context.MAX_VIEWPORT_DIMS) as Int32Array));
    const factor = Math.min(longSide, limit) / Math.max(cssWidth, cssHeight);
    return { width: Math.round(cssWidth * factor), height: Math.round(cssHeight * factor) };
  }

  /**
   * Render into a multisampled offscreen buffer and read the resolved pixels.
   * Falls back to fewer samples, then to half the size, when the buffers
   * cannot be allocated — an export is 240 MB at 3000 px and 4 samples.
   */
  function offscreen(view: View, background: number[], width: number,
                     height: number, cue = depthCue): Uint8Array | null {
    const cssWidth = canvas.clientWidth || 1, cssHeight = canvas.clientHeight || 1;
    const maxSamples = context.getParameter(context.MAX_SAMPLES) as number;
    for (const samples of [Math.min(4, maxSamples), 0]) {
      const msaa = context.createFramebuffer()!;
      const color = context.createRenderbuffer()!;
      const depth = context.createRenderbuffer()!;
      const resolved = context.createFramebuffer()!;
      const target = context.createRenderbuffer()!;
      const cleanup = () => {
        context.bindFramebuffer(context.FRAMEBUFFER, null);
        for (const f of [msaa, resolved]) context.deleteFramebuffer(f);
        for (const r of [color, depth, target]) context.deleteRenderbuffer(r);
      };
      context.bindRenderbuffer(context.RENDERBUFFER, color);
      context.renderbufferStorageMultisample(context.RENDERBUFFER, samples, context.RGBA8, width, height);
      context.bindRenderbuffer(context.RENDERBUFFER, depth);
      context.renderbufferStorageMultisample(context.RENDERBUFFER, samples, context.DEPTH_COMPONENT24, width, height);
      context.bindFramebuffer(context.FRAMEBUFFER, msaa);
      context.framebufferRenderbuffer(context.FRAMEBUFFER, context.COLOR_ATTACHMENT0, context.RENDERBUFFER, color);
      context.framebufferRenderbuffer(context.FRAMEBUFFER, context.DEPTH_ATTACHMENT, context.RENDERBUFFER, depth);
      if (context.checkFramebufferStatus(context.FRAMEBUFFER) !== context.FRAMEBUFFER_COMPLETE
          || context.getError() !== context.NO_ERROR) {
        cleanup();
        continue;
      }
      render(view, background, width, height, cssWidth, cssHeight, cue);
      context.bindRenderbuffer(context.RENDERBUFFER, target);
      context.renderbufferStorage(context.RENDERBUFFER, context.RGBA8, width, height);
      context.bindFramebuffer(context.FRAMEBUFFER, resolved);
      context.framebufferRenderbuffer(context.FRAMEBUFFER, context.COLOR_ATTACHMENT0, context.RENDERBUFFER, target);
      context.bindFramebuffer(context.READ_FRAMEBUFFER, msaa);
      context.bindFramebuffer(context.DRAW_FRAMEBUFFER, resolved);
      context.blitFramebuffer(0, 0, width, height, 0, 0, width, height,
                              context.COLOR_BUFFER_BIT, context.NEAREST);
      context.bindFramebuffer(context.FRAMEBUFFER, resolved);
      const pixels = new Uint8Array(width * height * 4);
      context.readPixels(0, 0, width, height, context.RGBA, context.UNSIGNED_BYTE, pixels);
      const ok = context.getError() === context.NO_ERROR;
      cleanup();
      if (ok) return pixels;
    }
    return null;
  }

  async function exportPng(view: View, options: ExportOptions): Promise<ExportedPng | null> {
    if (lost || !scene) return null;
    let { width, height } = exportSize(options.longSide);
    let pixels: Uint8Array | null = null;
    let alpha: Uint8Array | null = null;
    for (let attempt = 0; attempt < 3 && !pixels; attempt += 1) {
      if (options.background) {
        pixels = offscreen(view, options.background, width, height);
      } else {
        // difference matting: on black a pixel is a·C, on white a·C + (1 − a)
        // without fog: fogged toward black and toward white, the two renders
        // would differ by more than coverage, and there is no ground to fade
        // toward (WP-1548 D3, Python's background=None refusal)
        const black = offscreen(view, [0, 0, 0], width, height, false);
        const white = black && offscreen(view, [1, 1, 1], width, height, false);
        if (black && white) {
          pixels = black;
          alpha = white;
        }
      }
      if (!pixels) {
        width = Math.round(width / 2);
        height = Math.round(height / 2);
      }
    }
    if (last) draw(last.view, last.background);
    if (!pixels) return null;
    const out = document.createElement("canvas");
    out.width = width;
    out.height = height;
    const ctx = out.getContext("2d");
    if (!ctx) return null;
    const image = ctx.createImageData(width, height);
    for (let y = 0; y < height; y += 1) {
      // GL's rows run bottom-up
      const from = (height - 1 - y) * width * 4, to = y * width * 4;
      for (let x = 0; x < width * 4; x += 4) {
        const r = pixels[from + x], g = pixels[from + x + 1], b = pixels[from + x + 2];
        if (alpha) {
          const onWhite = (alpha[from + x] + alpha[from + x + 1] + alpha[from + x + 2]) / 3;
          const a = 255 - (onWhite - (r + g + b) / 3);
          const k = a > 0 ? 255 / a : 0;
          image.data[to + x] = Math.min(255, Math.round(r * k));
          image.data[to + x + 1] = Math.min(255, Math.round(g * k));
          image.data[to + x + 2] = Math.min(255, Math.round(b * k));
          image.data[to + x + 3] = Math.max(0, Math.min(255, Math.round(a)));
        } else {
          image.data[to + x] = r;
          image.data[to + x + 1] = g;
          image.data[to + x + 2] = b;
          image.data[to + x + 3] = 255;
        }
      }
    }
    ctx.putImageData(image, 0, 0);
    // the a, b, c labels are DOM over the canvas on screen (D3), so the export
    // draws them itself, at the size they would have at this scale
    const scale = width / (canvas.clientWidth || 1);
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const label of options.labels) {
      ctx.font = label.font.replace(/(\d+(?:\.\d+)?)px/, (_m, px) => `${Number(px) * scale}px`);
      ctx.fillStyle = label.color;
      ctx.fillText(label.text, label.x * scale, label.y * scale);
    }
    return new Promise((resolve) => out.toBlob(
      (blob) => resolve(blob && { blob, width, height }), "image/png"));
  }

  function onLost(event: Event) {
    event.preventDefault();
    lost = true;
  }

  function onRestored() {
    lost = false;
    batches = null;
    init();
    upload();
    if (last) draw(last.view, last.background);
  }

  try {
    init();
  } catch (exc) {
    // thrown out of a mount effect this would take the panel with it; the
    // viewer says it cannot draw instead, and the reason stays in the console
    console.error(exc);
    return null;
  }
  canvas.addEventListener("webglcontextlost", onLost);
  canvas.addEventListener("webglcontextrestored", onRestored);

  return {
    setScene(next: Scene) {
      scene = next;
      if (!lost) upload();
    },
    setDepthCue(on: boolean) {
      depthCue = on;
    },
    draw,
    exportPng,
    dispose() {
      canvas.removeEventListener("webglcontextlost", onLost);
      canvas.removeEventListener("webglcontextrestored", onRestored);
      if (!lost) {
        release();
        if (programs) for (const p of Object.values(programs)) context.deleteProgram(p.program);
        if (corner) for (const b of Object.values(corner)) context.deleteBuffer(b);
      }
      context.getExtension("WEBGL_lose_context")?.loseContext();
    },
  };
}
