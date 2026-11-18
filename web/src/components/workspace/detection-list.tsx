"use client";

import { ScanSearch } from "lucide-react";
import type { Detection } from "@/lib/api/contract";
import { bandOf } from "@/lib/detections/utils";
import { formatConfidence } from "@/lib/format";
import { Panel, cx } from "@/components/ui/primitives";

const bar = { high: "bg-accent", medium: "bg-electric", low: "bg-warn" } as const;

interface Props {
  detections: readonly Detection[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  contextLabel: string;
  mock: boolean;
}

export function DetectionList({ detections, selectedId, onSelect, contextLabel, mock }: Props) {
  const sorted = [...detections].sort((a, b) => b.confidence - a.confidence);
  return (
    <Panel
      title="Tespitler"
      aside={<span className="tnum">{contextLabel}{mock ? " · demo" : ""}</span>}
      padded={false}
    >
      {sorted.length === 0 ? (
        <div className="flex flex-col items-center gap-2 px-4 py-8 text-center text-[13px] text-muted">
          <ScanSearch className="size-5 text-subtle" aria-hidden />
          Bu karede eşik üstü tespit yok.
        </div>
      ) : (
        <ul className="max-h-72 divide-y divide-line overflow-y-auto">
          {sorted.map((d) => (
            <li key={d.id}>
              <button
                type="button"
                aria-pressed={d.id === selectedId}
                onClick={() => onSelect(d.id === selectedId ? null : d.id)}
                className={cx("flex w-full flex-col gap-1.5 px-4 py-2.5 text-left transition-colors hover:bg-raised", d.id === selectedId && "bg-overlay")}
              >
                <span className="flex items-baseline justify-between gap-2 text-[13px]">
                  <span className="font-medium capitalize text-ink">{d.className}</span>
                  <span className="tnum font-mono text-xs text-ink">{formatConfidence(d.confidence)}</span>
                </span>
                <span className="h-1 overflow-hidden rounded-full bg-line-strong">
                  <span className={cx("block h-full rounded-full", bar[bandOf(d.confidence)])} style={{ width: `${d.confidence * 100}%` }} />
                </span>
                <span className="tnum font-mono text-[10px] text-subtle">
                  x {Math.round(d.box.x)} · y {Math.round(d.box.y)} · {Math.round(d.box.width)}×{Math.round(d.box.height)} px
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
