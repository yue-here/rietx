import { describe, expect, it } from "vitest";

import { py } from "./py";

describe("py", () => {
  it("spaces a dict and a list as Python's repr does", () => {
    expect(py({ "instrument.zero_shift": 0.01 })).toBe('{"instrument.zero_shift": 0.01}');
    expect(py({ a: 1, b: [2, 3] })).toBe('{"a": 1, "b": [2, 3]}');
    expect(py([[10, 12], [30.5, 31]])).toBe("[[10, 12], [30.5, 31]]");
    expect(py(["a", "b"])).toBe('["a", "b"]');
  });

  it("writes the empty containers", () => {
    expect(py({})).toBe("{}");
    expect(py([])).toBe("[]");
  });

  it("writes Python's constants, never JSON's", () => {
    expect(py({ a: true, b: false, c: null })).toBe('{"a": True, "b": False, "c": None}');
  });

  it("drops a key holding undefined, as the request body's JSON does", () => {
    expect(py({ a: 1, b: undefined })).toBe('{"a": 1}');
  });

  it("writes a non-finite number as the call Python needs", () => {
    expect(py([Infinity, -Infinity, NaN])).toBe('[float("inf"), float("-inf"), float("nan")]');
  });

  it("keeps a string's escapes, which mean the same in Python", () => {
    expect(py('a "b"\n')).toBe('"a \\"b\\"\\n"');
  });
});
