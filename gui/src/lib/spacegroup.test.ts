import { describe, expect, it } from "vitest";
import { spaceGroupText, typesetSpaceGroup } from "./spacegroup";

describe("space-group typesetting (WP-2126)", () => {
  it("joins the words with no space and no comma", () => {
    expect(spaceGroupText("P 63/m")).toBe("P6_3/m");
    expect(spaceGroupText("F m -3 m")).toBe("Fm-3m");
    expect(spaceGroupText("I 21 3")).toBe("I2_13");
  });

  it("makes a screw a subscript, a rotoinversion an overbar, a letter italic", () => {
    expect(typesetSpaceGroup("P 63/m")).toEqual([
      { kind: "italic", text: "P" }, { kind: "screw", text: "6", sub: "3" },
      { kind: "slash" }, { kind: "italic", text: "m" }]);
    expect(typesetSpaceGroup("F m -3 m")).toEqual([
      { kind: "italic", text: "Fm" }, { kind: "bar", text: "3" }, { kind: "italic", text: "m" }]);
  });

  it("keeps an axes choice small after the symbol", () => {
    expect(typesetSpaceGroup("R -3 c:H").at(-1)).toEqual({ kind: "ext", text: ":H" });
  });
});
