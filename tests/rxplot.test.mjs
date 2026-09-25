// WP-1461: the pure half of `src/rietx/viz/static/rxplot.mjs`, under `node --test`.
//
// Run by `tests/test_rxplot.py::test_the_pure_half_is_unit_tested`, which is what
// keeps it from going quiet. `node --test tests/rxplot.test.mjs` from the
// repository root runs it by hand. The drawing half needs a canvas, so
// `tests/test_rxplot_browser.py` covers it in chromium.

import assert from 'node:assert/strict';
import {test} from 'node:test';

import {
  chi2Base, difference, hklLabel, lower, nearest, nearestXY, partition, phaseInk, positive, scatter, sqrtSplits,
  tickDecimals, tickHeight,
  tickLabels, tsv, unpack, upper,
} from '../src/rietx/viz/static/rxplot.mjs';

// ------------------------------------------------------------------ lookups
test('lower is the first index at or above the value', () => {
  const xs = [1, 2, 2, 3];
  assert.equal(lower(xs, 0), 0);
  assert.equal(lower(xs, 2), 1);
  assert.equal(lower(xs, 2.5), 3);
  assert.equal(lower(xs, 9), 4);
});

test('nearest picks the closer neighbour and refuses one out of reach', () => {
  const xs = [10, 20, 30], px = (v) => v;   // one unit, one pixel
  assert.equal(nearest(xs, 14, px, 5), 0);
  assert.equal(nearest(xs, 16, px, 5), 1);
  assert.equal(nearest(xs, 25, px, 4), -1);
  assert.equal(nearest(xs, 99, px, 100), 2);
});

test('nearestXY is by distance in the plane, for points that share an x', () => {
  // a heat-then-cool series passes one x twice, once per leg (D8)
  const xs = [100, 100, 140], ys = [50, 10, 30];
  assert.equal(nearestXY(xs, ys, 101, 12, 8), 1);
  assert.equal(nearestXY(xs, ys, 101, 48, 8), 0);
  // a point with no value is never picked, and nothing out of reach is
  assert.equal(nearestXY(xs, [null, 10, 30], 100, 50, 8), -1);
  assert.equal(nearestXY(xs, ys, 120, 30, 8), -1);
});

// ------------------------------------------------------------------ finding 2
test('a √ axis gets several ticks, not one', () => {
  const ticks = sqrtSplits(0, 12000);
  assert.ok(ticks.length >= 4, `${ticks}`);
  for (let i = 1; i < ticks.length; i++) assert.ok(ticks[i] > ticks[i - 1], `${ticks}`);
  assert.ok(ticks.every((t) => t >= 0 && t <= 12000), `${ticks}`);
  // evenly spaced in √ space means the low end is crowded in value space
  assert.ok(ticks[1] - ticks[0] < ticks.at(-1) - ticks.at(-2), `${ticks}`);
});

test('a √ axis zoomed to a narrow window keeps several ticks', () => {
  // rounded to the value's own decade, every tick from 1000 to 1010 was 1000
  for (const [lo, hi] of [[1000, 1010], [0, 0.04], [5e5, 5.0002e5]]) {
    const ticks = sqrtSplits(lo, hi);
    assert.ok(ticks.length >= 4, `${lo}-${hi}: ${ticks}`);
    // and each label prints its own tick, which is not a multiple of the smallest gap
    assert.deepEqual(tickLabels(ticks).map(Number), ticks.map((t) => +t.toPrecision(12)),
                     `${lo}-${hi}: ${tickLabels(ticks)}`);
  }
});

// ------------------------------------------------------------------ finding 3
test('ticks over a narrow range read differently from each other', () => {
  // a trajectory spanning 1e-4 Å printed `10.251` five times under uPlot's default
  const splits = [10.2510, 10.2512, 10.2514, 10.2516, 10.2518];
  assert.deepEqual(tickLabels(splits), ['10.2510', '10.2512', '10.2514', '10.2516', '10.2518']);
});

test('the precision follows the step, not the magnitude', () => {
  assert.equal(tickDecimals([0, 0.25, 0.5]), 2);
  assert.equal(tickDecimals([0, 5, 10]), 0);
  assert.equal(tickDecimals([1000, 1200, 1400]), 0);
  // float noise in uPlot's splits does not add digits
  assert.equal(tickDecimals([10.251000000000001, 10.2512, 10.2514]), 4);
});

test('a zero tick prints as zero and a filtered tick as nothing', () => {
  assert.deepEqual(tickLabels([-0.5, -1e-17, 0.5]), ['-0.5', '0.0', '0.5']);
  assert.deepEqual(tickLabels([1, null, 3]), ['1', '', '3']);
});

// ------------------------------------------------------------------ finding 10
test('a fitted array lands on the pattern grid by index, null elsewhere', () => {
  assert.deepEqual(scatter(6, [1, 3, 4], ['a', 'b', 'c']), [null, 'a', null, 'b', 'c', null]);
  assert.deepEqual(scatter(3, Int32Array.from([0]), Float64Array.from([7])), [7, null, null]);
});

test('the observed pattern splits into fitted and masked over one grid', () => {
  const [inside, outside] = partition([1, 2, 3, 4, 5, 6], Int32Array.from([1, 3]));
  assert.deepEqual(inside, [null, 2, null, 4, null, null]);
  assert.deepEqual(outside, [1, null, 3, null, 5, 6]);
});

test('a zoomed Σχ² starts from what the channels before the view summed', () => {
  // the window route accumulated over its window; the client re-bases the
  // pattern's one sum as cum[j] - cum[i0 - 1], i0 the first channel in view
  const cum = [1, 3, 6, 10], xs = [10, 11, 12, 13];
  assert.equal(chi2Base(cum, xs, 9), 0);
  assert.equal(chi2Base(cum, xs, 10), 0);
  assert.equal(chi2Base(cum, xs, 11.5), 3);
  assert.equal(chi2Base(cum, xs, 99), 10);
  // so the view 11.5-13 draws 3 and 7, and ends at its own χ², 7
  assert.deepEqual(cum.slice(2).map((v) => v - chi2Base(cum, xs, 11.5)), [3, 7]);
});

// ------------------------------------------------------------------ the pattern
test('a log scale gets a gap wherever a value is at or under zero', () => {
  assert.deepEqual(positive(Float64Array.from([2, 0, -1, 3])), [2, null, null, 3]);
  assert.deepEqual(positive([null, 5]), [null, 5]);
});

test('one tick row takes the observed ink, several take a phase ink each', () => {
  const colors = {obs: 'grey', phase: ['a', 'b']};
  assert.equal(phaseInk(colors, 0, 1), 'grey');
  assert.deepEqual([0, 1, 2].map((r) => phaseInk(colors, r, 3)), ['a', 'b', 'a']);
  assert.ok(tickHeight(2) > tickHeight(1));
});

// ------------------------------------------------------------------ D4
/** A body in `rietx.viz.packed`'s layout, for the cases below. `test_rxplot.py`
 *  decodes one Python wrote, which is the check that the two agree. */
function packed(header, arrays) {
  const specs = [];
  let offset = 0;
  for (const [name, a] of Object.entries(arrays)) {
    specs.push({name, dtype: a instanceof Float64Array ? '<f8' : '<i4', offset, length: a.length});
    offset += Math.ceil(a.byteLength / 8) * 8;
  }
  let head = JSON.stringify({...header, arrays: specs});
  head += ' '.repeat((8 - ((4 + head.length) % 8)) % 8);
  const buffer = new ArrayBuffer(4 + head.length + offset), view = new DataView(buffer);
  view.setUint32(0, head.length, true);
  new Uint8Array(buffer, 4).set(new TextEncoder().encode(head));
  for (const [i, a] of Object.values(arrays).entries()) {
    new Uint8Array(buffer, 4 + head.length + specs[i].offset).set(new Uint8Array(a.buffer));
  }
  return buffer;
}

test('a packed body decodes to its header and views on its arrays', () => {
  const buffer = packed({fit: true}, {
    two_theta: Float64Array.from([5, 5.5, 6]), fitted: Int32Array.from([0, 2, 7]),
    y: Float64Array.from([1.25])});
  const {header, arrays} = unpack(buffer);
  assert.deepEqual(header, {fit: true});
  assert.deepEqual(Array.from(arrays.two_theta), [5, 5.5, 6]);
  assert.deepEqual(Array.from(arrays.fitted), [0, 2, 7]);
  assert.deepEqual(Array.from(arrays.y), [1.25]);
  // a view, never a copy: 59 498 channels of five arrays is 2 MB
  assert.equal(arrays.two_theta.buffer, buffer);
});

test('a dtype no typed array reads is refused by name', () => {
  const buffer = packed({}, {y: Float64Array.from([1])});
  const n = new DataView(buffer).getUint32(0, true);
  const head = new TextDecoder().decode(new Uint8Array(buffer, 4, n)).replace('<f8', '<f4');
  new Uint8Array(buffer, 4).set(new TextEncoder().encode(head));
  assert.throws(() => unpack(buffer), /y is <f4/);
});

// ------------------------------------------------------------------ the overlay
test('a Miller index reads as a reader writes one', () => {
  assert.equal(hklLabel([1, 0, -1]), '(1 0 −1)');
  assert.equal(hklLabel([10, -4, 0]), '(10 −4 0)');
  assert.equal(hklLabel([1, 2]), '');
  assert.equal(hklLabel(null), '');
});

test('a difference is a subtraction on one grid, and two grids throw', () => {
  assert.deepEqual(Array.from(difference([3, 5, 9], [1, 1, 4])), [2, 4, 5]);
  assert.throws(() => difference([1, 2, 3], [1, 2]), /3 channels against 2/);
});

// ------------------------------------------------------------------ exports
test('upper is the first index past the value, so a view keeps both its ends', () => {
  const xs = [1, 2, 2, 3];
  assert.equal(upper(xs, 2), 3);
  assert.equal(upper(xs, 0), 0);
  assert.equal(upper(xs, 3), 4);
  assert.deepEqual(xs.slice(lower(xs, 2), upper(xs, 3)), [2, 2, 3]);
});

test('a table is tab-separated, every number in full and every gap empty', () => {
  const text = tsv(['x', 'y'], [[0.1 + 0.2, null], [2, NaN], [3, -Infinity], [4, 0]]);
  assert.equal(text, 'x\ty\n0.30000000000000004\t\n2\t\n3\t\n4\t0');
  assert.equal(tsv(['x'], []), 'x');
});
