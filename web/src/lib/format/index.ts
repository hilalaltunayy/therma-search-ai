export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value >= 100 || i === 0 ? Math.round(value) : value.toFixed(1)} ${units[i]}`;
}

/** 83_500 ms → "01:23.5"; 3_723_000 ms → "1:02:03". */
export function formatTimestamp(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "—";
  const totalSeconds = ms / 1000;
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  if (h > 0) return `${h}:${pad(m)}:${pad(Math.floor(s))}`;
  return `${pad(m)}:${s.toFixed(1).padStart(4, "0")}`;
}

export function formatDurationMs(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "—";
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`;
}

export function formatPercent(ratio: number, digits = 0): string {
  return Number.isFinite(ratio) ? `${(ratio * 100).toFixed(digits)}%` : "—";
}

export function formatConfidence(c: number): string {
  return Number.isFinite(c) ? c.toFixed(2) : "—";
}
