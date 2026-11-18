"use client";

import { useRef, useState, type DragEvent } from "react";
import { FileVideo2, ImageUp, TriangleAlert, UploadCloud, X } from "lucide-react";
import type { ApiError, UploadLimits } from "@/lib/api/contract";
import { formatBytes } from "@/lib/format";
import { Button, cx } from "@/components/ui/primitives";

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
    const files = e.dataTransfer.files;
    if (files.length > 1) return; // tek dosya: belirsizlik yaratmamak için
    const file = files[0];
    if (file) onFile(file);
  };

  return (
    <div className="flex h-full min-h-[420px] flex-col items-center justify-center p-4">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cx(
          "relative flex w-full max-w-2xl flex-col items-center gap-4 rounded-2xl border border-dashed px-6 py-14 text-center transition-colors",
          dragging ? "border-accent bg-accent-soft/40" : "border-line-strong bg-raised/40",
        )}
      >
        <div className="grid size-14 place-items-center rounded-2xl border border-accent/30 bg-accent-soft/60 text-accent">
          <UploadCloud className="size-6" aria-hidden />
        </div>
        <div>
          <h3 className="text-base font-semibold text-ink">Termal görüntü veya video yükleyin</h3>
          <p className="mt-1.5 text-[13px] text-muted">Dosyayı buraya sürükleyin ya da bilgisayarınızdan seçin.</p>
        </div>
        <Button variant="primary" onClick={() => inputRef.current?.click()}>
          Dosya seç
        </Button>
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
        <dl className="mt-2 grid w-full max-w-md grid-cols-2 gap-3 text-left text-xs">
          <div className="rounded-lg border border-line bg-surface p-3">
            <dt className="flex items-center gap-1.5 text-muted"><ImageUp className="size-3.5" aria-hidden /> Görüntü</dt>
            <dd className="mt-1 text-subtle">JPEG, PNG, WebP · en fazla {formatBytes(limits.maxImageBytes)}</dd>
          </div>
          <div className="rounded-lg border border-line bg-surface p-3">
            <dt className="flex items-center gap-1.5 text-muted"><FileVideo2 className="size-3.5" aria-hidden /> Video</dt>
            <dd className="mt-1 text-subtle">MP4, WebM, MOV · en fazla {formatBytes(limits.maxVideoBytes)}, {Math.round(limits.maxVideoDurationSeconds / 60)} dk</dd>
          </div>
        </dl>
        <p className="text-[11px] text-subtle">
          Dosya tarayıcıda önizlenir. Şu an backend bağlı değilse hiçbir yere gönderilmez. Limitler öneridir (docs/api-contract.md).
        </p>
      </div>

      {error && (
        <div role="alert" className="animate-rise mt-4 flex w-full max-w-2xl items-start gap-3 rounded-lg border border-danger/40 bg-danger-soft px-4 py-3 text-[13px] text-danger">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <p className="flex-1 leading-snug">{error.message}</p>
          <button type="button" aria-label="Hatayı kapat" onClick={onDismissError} className="text-danger/80 hover:text-danger">
            <X className="size-4" />
          </button>
        </div>
      )}
    </div>
  );
}
