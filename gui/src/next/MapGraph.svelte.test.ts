// @vitest-environment jsdom
// The series Map graph at /next (WP-2243 task 7): its controls, its title, and
// asking again when the staged list moves. What it paints is a real browser's.
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

/** Three patterns on ten cells; the first two fitted. */
function answer(fitted = [true, true, false]): any {
  const n = 3, m = 10;
  return {
    header: { n_rows: n, n_cols: m, labels: ["T300", "T400", "T500"], x: [300, 400, 500],
              axis: "T", fitted, rwp: fitted.map((f) => (f ? 0.05 : null)), running: false },
    arrays: { two_theta: Float64Array.from({ length: m }, (_, i) => 10 + i),
              obs: Float64Array.from({ length: n * m }, (_, i) => i),
              diff: Float64Array.from({ length: n * m }, () => 0.5) },
  };
}

let payload: any = answer();
const seriesMap = vi.fn();
vi.mock("../api", async (original) => {
  const real = await original<typeof import("../api")>();
  return {
    ...real,
    api: { seriesMap: () => {
      seriesMap();
      return payload instanceof Error ? Promise.reject(payload) : Promise.resolve(new ArrayBuffer(0));
    } },
  };
});
vi.mock("./rxplot.mjs", async (original) => ({
  ...(await original<typeof import("./rxplot.mjs")>()),
  unpack: () => payload,
}));

import SeriesMap from "./SeriesMap.svelte";

let app: ReturnType<typeof mount> | null = null;
/** the title's parts, a space between each, as they read on screen */
const title = () => [...document.querySelector(".gtitle")!.children]
  .map((e) => e.textContent!.replace(/\s+/g, " ").trim()).join(" ");
const button = (name: string) => [...document.querySelectorAll("button")]
  .find((b) => b.textContent!.trim() === name || b.getAttribute("aria-label") === name)!;

async function settle(ready: () => boolean) {
  await vi.waitFor(() => { flushSync(); if (!ready()) throw new Error("not yet"); },
                   { timeout: 15000, interval: 20 });
  await tick();
  flushSync();
}

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  seriesMap.mockClear();
  payload = answer();
});

describe("the Map graph (WP-2243 task 7)", () => {
  it("names the selected pattern and offers the views round 12 drew", async () => {
    app = mount(SeriesMap, { target: document.body, props: { selected: 1 } });
    await settle(() => title() !== "");
    expect(title()).toBe("T400 T 400");
    const groups = [...document.querySelectorAll(".segmented")]
      .map((g) => [...g.querySelectorAll("button")].map((b) => b.textContent!.trim()));
    expect(groups).toEqual([["Map", "Waterfall"], ["Observed", "Difference"]]);
    // Map and Observed by default, Cuts on, nothing zoomed
    expect(button("Map").getAttribute("aria-pressed")).toBe("true");
    expect(button("Observed").getAttribute("aria-pressed")).toBe("true");
    expect(document.querySelector<HTMLInputElement>(".vg input[type=checkbox]")!.checked).toBe(true);
    expect(button("Show all").disabled).toBe(true);
    expect(button("Flip vertically").getAttribute("aria-pressed")).toBe("false");
  });

  it("reads the first pattern before any selection, and names no coordinate a series lacks", async () => {
    payload = { ...answer(), header: { ...answer().header, axis: "index", x: [300, null, 500] } };
    app = mount(SeriesMap, { target: document.body, props: {} });
    await settle(() => title() !== "");
    // the server's axis reads "index" until every pattern has a coordinate
    expect(title()).toBe("T300");
    button("Difference").click();
    flushSync();
    expect(button("Difference").getAttribute("aria-pressed")).toBe("true");
    expect(title()).toBe("T300");
    button("Flip vertically").click();
    flushSync();
    expect(button("Flip vertically").getAttribute("aria-pressed")).toBe("true");
  });

  it("asks again when the staged list moves, and says why it cannot draw", async () => {
    const props = $state({ stamp: 0 });
    app = mount(SeriesMap, { target: document.body, props });
    await settle(() => title() !== "");
    expect(seriesMap).toHaveBeenCalledTimes(1);
    payload = new Error("no series is staged; add patterns with PUT /api/series");
    props.stamp = 1;
    await settle(() => title().startsWith("no series"));
    expect(seriesMap).toHaveBeenCalledTimes(2);
  });

  it("keeps a selection inside a shorter list", async () => {
    const props = $state({ selected: 2 as number | null, stamp: 0 });
    app = mount(SeriesMap, { target: document.body, props });
    await settle(() => title() !== "");
    payload = { ...answer([true, true]), header: { ...answer().header, n_rows: 2,
                labels: ["T300", "T400"], x: [300, 400], fitted: [true, true], rwp: [0.05, 0.05] } };
    props.stamp = 1;
    await settle(() => title() === "T400 T 400");
  });
});
