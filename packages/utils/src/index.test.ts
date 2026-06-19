import { describe, expect, it } from "vitest";
import { add, greet } from "./index.js";

describe("utils", () => {
  it("add 返回两数之和", () => {
    expect(add(2, 3)).toBe(5);
  });

  it("greet 返回问候语", () => {
    expect(greet("world")).toBe("Hello, world!");
  });
});
