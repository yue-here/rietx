import { describe, expect, it } from "vitest";
import { EXPORT_KINDS, type Entry, type MenuItem, type MenuState, exportBlocked, fileMenu,
         folderOf, keyLabel, projectStem, shortcut } from "./filemenu";

const OPEN: MenuState = {
  hasProject: true, busy: false, hasResult: true, nPhases: 2, mode: "rietveld",
  recent: [{ path: "/w/a.rex", name: "a.rex" }, { path: "/w/b.rex", name: "b.rex" },
           { path: "/w/gone.rex", name: "gone.rex", missing: true }],
  current: "/w/a.rex", mac: true,
};

function item(entries: Entry[], id: string): MenuItem {
  return entries.find((e) => e !== "-" && e.id === id) as MenuItem;
}

describe("the File menu", () => {
  it("lists the round-6 items in order, with no Save", () => {
    const ids = fileMenu(OPEN).map((e) => (e === "-" ? "-" : e.id));
    expect(ids).toEqual(["new", "open", "recent", "-", "copy", "rename", "move", "-",
                         "export", "-", "close"]);
    expect(fileMenu(OPEN).some((e) => e !== "-" && /^Save$/.test(e.label))).toBe(false);
  });

  it("spells each shortcut for the platform", () => {
    expect(item(fileMenu(OPEN), "open").key).toBe("⌘O");
    expect(item(fileMenu(OPEN), "copy").key).toBe("⇧⌘S");
    expect(item(fileMenu({ ...OPEN, mac: false }), "copy").key).toBe("Ctrl+Shift+S");
    expect(keyLabel(false, false, "O")).toBe("Ctrl+O");
  });

  it("leaves the open project off Open recent and disables a missing one", () => {
    const sub = item(fileMenu(OPEN), "recent").sub!;
    const rows = sub.filter((e): e is MenuItem => e !== "-");
    expect(rows.map((r) => r.id)).toEqual(["recent:/w/b.rex", "recent:/w/gone.rex", "recent-clear"]);
    expect(rows[0].label).toBe("b");
    expect(rows[1].disabled).toBe(true);
    expect(rows[1].title).toBe("Not found: /w/gone.rex");
    expect(rows[2].disabled).toBe(false);
  });

  it("disables Open recent when only the open project is listed", () => {
    const s = { ...OPEN, recent: [{ path: "/w/a.rex", name: "a.rex" }] };
    expect(item(fileMenu(s), "recent").disabled).toBe(true);
  });

  it("holds the folder verbs without a project and while a run is in flight", () => {
    for (const [s, why] of [[{ ...OPEN, hasProject: false, current: null }, "No project is open"],
                            [{ ...OPEN, busy: true }, "A run is in flight"]] as const) {
      for (const id of ["copy", "rename", "move", "close"]) {
        expect(item(fileMenu(s), id).disabled).toBe(true);
        expect(item(fileMenu(s), id).title).toBe(why);
      }
    }
    expect(item(fileMenu({ ...OPEN, hasProject: false }), "new").disabled).toBe(false);
    expect(item(fileMenu({ ...OPEN, busy: true }), "open").disabled).toBe(true);
    for (const id of ["copy", "rename", "move", "close", "export"]) {
      expect(item(fileMenu(OPEN), id).disabled).toBe(false);
    }
  });

  it("says why each export is unavailable", () => {
    const k = (kind: string) => EXPORT_KINDS.find((e) => e.kind === kind)!;
    expect(exportBlocked(k("cif"), OPEN)).toBeUndefined();
    expect(exportBlocked(k("cif"), { ...OPEN, hasResult: false })).toBe("Run a fit first");
    // the instrument profile is answered from the project, fit or no fit
    expect(exportBlocked(k("instrument_profile"), { ...OPEN, hasResult: false })).toBeUndefined();
    expect(exportBlocked(k("qpa"), { ...OPEN, nPhases: 1 })).toBe("One phase: nothing to quantify");
    expect(exportBlocked(k("qpa"), { ...OPEN, mode: "lebail" }))
      .toBe("Phase fractions need a Rietveld fit");
    expect(exportBlocked(k("html"), { ...OPEN, busy: true })).toBe("A run is in flight");
    const sub = item(fileMenu({ ...OPEN, nPhases: 1 }), "export").sub!
      .filter((e): e is MenuItem => e !== "-");
    expect(sub.map((e) => e.id)).toEqual(EXPORT_KINDS.map((e) => `export:${e.kind}`));
    expect(sub.find((e) => e.id === "export:qpa")!.disabled).toBe(true);
  });

  it("reads ⌘O, ⇧⌘S and ⌘S, and leaves ⌘N, ⌘W and ⌥ to the browser", () => {
    const ev = (key: string, mods: Partial<Record<"metaKey" | "ctrlKey" | "shiftKey" | "altKey", boolean>>) =>
      ({ key, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false, ...mods });
    expect(shortcut(ev("o", { metaKey: true }))).toBe("open");
    expect(shortcut(ev("S", { metaKey: true, shiftKey: true }))).toBe("copy");
    expect(shortcut(ev("s", { ctrlKey: true }))).toBe("saved");
    expect(shortcut(ev("n", { metaKey: true }))).toBeNull();
    expect(shortcut(ev("w", { metaKey: true }))).toBeNull();
    expect(shortcut(ev("s", { metaKey: true, altKey: true }))).toBeNull();
    expect(shortcut(ev("s", {}))).toBeNull();
  });

  it("splits a project path into its folder and its name", () => {
    expect(projectStem("/a/b/sample.rex")).toBe("sample");
    expect(folderOf("/a/b/sample.rex")).toBe("/a/b");
    // a project at the root sits in the root, not in itself
    expect(folderOf("/sample.rex")).toBe("/");
    expect(projectStem("C:\\w\\x.rex")).toBe("x");
  });
});
