import { describe, it, expect } from "vitest";
import {
  parseMoney,
  splitPreview,
  formatMoney,
  personLabel,
  customPreview,
  validPhoto,
} from "./domain";
describe("exact expense preview", () => {
  it("allocates every paise deterministically to all members", () => {
    expect(splitPreview("100.00", [{ id: 3 }, { id: 1 }, { id: 2 }])).toEqual([
      { id: 1, minor: 3334 },
      { id: 2, minor: 3333 },
      { id: 3, minor: 3333 },
    ]);
  });
  it.each(["0", "-1", "1.001", "NaN", "1e2", "", "10000000.01"])(
    "rejects invalid money %s",
    (value) => expect(parseMoney(value)).toBeNull(),
  );
  it("accepts whole and exact decimals", () => {
    expect(parseMoney(" 12.3 ")).toBe(1230);
    expect(parseMoney("0.01")).toBe(1);
    expect(splitPreview("1", [])).toEqual([]);
  });
  it("does not merge people with duplicate names", () =>
    expect(personLabel({ id: 21, name: "Aman" })).toBe("Aman · #21"));
  it("formats financial amounts to two decimals", () =>
    expect(formatMoney(123450)).toContain("1,234.50"));
  it("accepts zero custom shares but enforces an exact total and complete roster", () => {
    expect(
      customPreview("10", [{ id: 1 }, { id: 2 }], { 1: "10", 2: "0" }),
    ).toMatchObject({ valid: true, total: 1000, remaining: 0 });
    expect(
      customPreview("10", [{ id: 1 }, { id: 2 }], { 1: "9", 2: "0" }),
    ).toMatchObject({ valid: false, remaining: 100 });
    expect(
      customPreview("10", [{ id: 1 }, { id: 2 }], { 1: "10", 2: "" }),
    ).toMatchObject({ valid: false });
  });
  it("validates optional bill photos before sending them", () => {
    expect(
      validPhoto(new File(["x"], "bill.png", { type: "image/png" })),
    ).toBeNull();
    expect(
      validPhoto(new File(["x"], "bill.svg", { type: "image/svg+xml" })),
    ).toContain("JPEG");
    expect(
      validPhoto(
        new File([new Uint8Array(5242881)], "large.png", { type: "image/png" }),
      ),
    ).toContain("5 MB");
  });
});
