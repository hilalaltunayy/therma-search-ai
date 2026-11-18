"use client";

import { SlidersHorizontal } from "lucide-react";
import type { ModelClass } from "@/lib/api/contract";
import { Panel, Segmented, Switch } from "@/components/ui/primitives";
import type { ViewPrefs } from "./view-prefs";

interface Props {
  disabled: boolean;
  prefs: ViewPrefs;
  onPrefsChange: (p: ViewPrefs) => void;
  threshold: number;
  onThresholdChange: (v: number) => void;
  /** Sunucu tabanı: bunun altına inmek anlamsız (sunucu bu tespitleri göndermedi). */
  minThreshold: number;
  classes: readonly ModelClass[];
}

export function ControlsPanel({ disabled, prefs, onPrefsChange, threshold, onThresholdChange, minThreshold, classes }: Props) {
  const fill = `${threshold * 100}%`;
  return (
    <Panel title="Görünüm ve eşik" aside={<SlidersHorizontal className="size-3.5" aria-hidden />}>
      <div className="space-y-5">
        <div>
          <div className="mb-2 flex items-baseline justify-between">
            <label htmlFor="threshold" className="text-[13px] text-ink">Güven eşiği</label>
            <output htmlFor="threshold" className="tnum font-mono text-sm font-semibold text-accent">{threshold.toFixed(2)}</output>
          </div>
          <input
            id="threshold"
            type="range"
            className="range w-full"
            min={0}
            max={1}
            step={0.01}
            value={threshold}
            style={{ ["--fill" as string]: fill }}
            onChange={(e) => onThresholdChange(Math.max(minThreshold, Number(e.target.value)))}
            aria-valuetext={`${threshold.toFixed(2)} ve üzeri skorlar gösterilir`}
          />
          <p className="mt-1.5 text-[11px] leading-snug text-subtle">
            Yalnızca görüntüleme filtresi; model çıktısını değiştirmez. Varsayılan 0.25 kalibre edilmiş bir işletim eşiği değildir.
            {minThreshold > 0 && ` Sunucu tabanı: ${minThreshold.toFixed(2)}.`}
          </p>
        </div>

        <div>
          <p className="mb-2 text-[11px] uppercase tracking-[0.08em] text-subtle">Karşılaştırma</p>
          <Segmented
            label="Görünüm modu"
            value={prefs.mode}
            onChange={(mode) => onPrefsChange({ ...prefs, mode })}
            options={[
              { value: "overlay", label: "İşlenmiş", disabled },
              { value: "original", label: "Orijinal", disabled },
              { value: "split", label: "Bölünmüş", disabled },
            ]}
          />
        </div>

        <div className="space-y-3">
          <Switch label="Kutuları göster" checked={prefs.showBoxes} disabled={disabled} onChange={(showBoxes) => onPrefsChange({ ...prefs, showBoxes })} />
          <Switch label="Skor etiketlerini göster" checked={prefs.showLabels} disabled={disabled || !prefs.showBoxes} onChange={(showLabels) => onPrefsChange({ ...prefs, showLabels })} />
          {classes.map((c) => (
            <Switch
              key={c.id}
              label={`Sınıf: ${c.name}`}
              checked={!prefs.hiddenClasses.has(c.id)}
              disabled={disabled || !prefs.showBoxes}
              onChange={(on) => {
                const next = new Set(prefs.hiddenClasses);
                if (on) next.delete(c.id);
                else next.add(c.id);
                onPrefsChange({ ...prefs, hiddenClasses: next });
              }}
            />
          ))}
        </div>
      </div>
    </Panel>
  );
}
