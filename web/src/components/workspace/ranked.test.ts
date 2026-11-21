import { describe, expect, it } from "vitest";
import type { Detection } from "@/lib/api/contract";
import { rankDetections } from "./ranked";

const d = (id: string, confidence: number): Detection => ({ id, classId: 0, className: "person", confidence, box: { x: 0, y: 0, width: 1, height: 1 } });

describe("rankDetections", () => {
  it("skora göre azalan sıra ve 1 tabanlı kare içi sıra verir", () => {
    expect(rankDetections([d("a", 0.3), d("b", 0.9), d("c", 0.6)]).map((r) => [r.detection.id, r.rank])).toEqual([["b", 1], ["c", 2], ["a", 3]]);
  });
  it("girdi dizisini değiştirmez", () => {
    const input = [d("a", 0.1), d("b", 0.2)];
    rankDetections(input);
    expect(input.map((x) => x.id)).toEqual(["a", "b"]);
  });
});
