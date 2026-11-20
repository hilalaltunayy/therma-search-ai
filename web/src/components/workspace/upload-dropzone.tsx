"use client";

import { useRef, useState, type DragEvent } from "react";
import { TriangleAlert, UploadCloud, X } from "lucide-react";
import type { ApiError, UploadLimits } from "@/lib/api/contract";
import { formatBytes } from "@/lib/format";
import { cx } from "@/components/ui/primitives";

interface Props {
  limits: UploadLimits;
  error: ApiError | null;
  onDismissError: () => void;
  onFile: (file: File) => void;
}

export function UploadDropzone({ limits, error, onDismissError, onFile }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const accept = [...limits.imageMimeTypes, ...limits.videoMimeTypes].join(",");

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length !== 1) return; // tek dosya
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  };

  return (
    <div className="flex h-full min-h-[420px] flex-col items-center justify-center gap-4 p-4 sm:p-6">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cx(
          "group relative flex w-full max-w-3xl flex-1 flex-col items-center justify-center gap-4 rounded-2xl border-[1.5px] border-dashed px-6 py-12 text-center transition-[border-color,background-color] duration-200",
          dragging ? "border-cyan bg-cyan-soft" : "border-cyan/30 hover:border-cyan/55 hover:bg-cyan/[0.03]",
        )}
      >
        <div
          className={cx(
            "grid size-16 place-items-center rounded-2xl border border-cyan/35 bg-cyan-soft text-cyan transition-transform duration-200",
            dragging ? "scale-105" : "group-hover:-translate-y-0.5",
          )}
        >
          <UploadCloud className="size-7" aria-hidden />
        </div>
        <div>
          <h3 className="text-xl font-semibold text-ink">Termal görüntü veya video bırakın</h3>
          <p className="mt-1.5 text-[15px] text-muted">
            ya da{" "}
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="rounded font-semibold text-cyan underline-offset-4 hover:underline"
            >
              dosya seçin
            </button>{" "}
            · tek dosya
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="sr-only"
          aria-label="Görüntü veya video dosyası seç"
          tabIndex={-1}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onFile(f);
            e.target.value = ""; // aynı dosya yeniden seçilebilsin
          }}
        />
        <div className="mt-1 flex flex-wrap justify-center gap-2">
          <span className="hud-chip h-8 text-[13px]">JPEG · PNG · WebP ≤ {formatBytes(limits.maxImageBytes)}</span>
          <span className="hud-chip h-8 text-[13px]">
            MP4 · WebM · MOV ≤ {formatBytes(limits.maxVideoBytes)} · {Math.round(limits.maxVideoDurationSeconds / 60)} dk
          </span>
        </div>
        <p className="max-w-md text-[13px] text-subtle">
          Dosya tarayıcıda önizlenir; backend bağlı değilken hiçbir yere gönderilmez. Limitler öneridir (docs/api-contract.md).
        </p>
      </div>

      {error && (
        <div role="alert" className="animate-rise flex w-full max-w-3xl items-start gap-3 rounded-xl border border-danger/45 bg-danger-soft px-4 py-3 text-sm text-danger">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <p className="flex-1 leading-snug">{error.message}</p>
          <button type="button" aria-label="Hatayı kapat" onClick={onDismissError} className="grid size-7 place-items-center rounded-md text-danger/80 hover:bg-danger/15 hover:text-danger">
            <X className="size-4" />
          </button>
        </div>
      )}
    </div>
  );
}
