"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type ReactNode } from "react";
import {
  ApiRequestError,
  DEFAULT_UPLOAD_LIMITS,
  TERMINAL_JOB_STATUSES,
  type AnalysisResult,
  type AnalysisService,
  type ApiError,
  type Capabilities,
  type Job,
  type MediaKind,
  type ServiceHealth,
} from "@/lib/api/contract";
import { createAnalysisService } from "@/lib/api";
import { probeMedia, type MediaProbe } from "@/lib/media/probe";
import { validateMediaFile } from "@/lib/media/validate";

/**
 * Çalışma alanının tek yaşam döngüsü. Her faz arayüzde ayrı bir görünümdür:
 *   empty → ready → submitting → processing → succeeded | failed | canceled
 */
export type Phase = "empty" | "ready" | "submitting" | "processing" | "succeeded" | "failed" | "canceled";

export interface AnalysisState {
  phase: Phase;
  file: File | null;
  mediaUrl: string | null;
  kind: MediaKind | null;
  probe: MediaProbe | null;
  /** Dosya seçimi/ön doğrulama hatası (iş oluşturulmadan önce). */
  selectionError: ApiError | null;
  job: Job | null;
  result: AnalysisResult | null;
  /** İş oluşturma/sorgulama/sonuç hatası veya failed iş hatası. */
  error: ApiError | null;
}

const initialState: AnalysisState = {
  phase: "empty",
  file: null,
  mediaUrl: null,
  kind: null,
  probe: null,
  selectionError: null,
  job: null,
  result: null,
  error: null,
};

type Action =
  | { type: "selectionFailed"; error: ApiError }
  | { type: "fileSelected"; file: File; mediaUrl: string; probe: MediaProbe }
  | { type: "submitting" }
  | { type: "jobUpdated"; job: Job }
  | { type: "succeeded"; result: AnalysisResult; job: Job }
  | { type: "failed"; error: ApiError; job?: Job }
  | { type: "canceled"; job: Job | null }
  | { type: "selectionDismissed" }
  | { type: "cleared" };

export function analysisReducer(state: AnalysisState, action: Action): AnalysisState {
  switch (action.type) {
    case "selectionFailed":
      return { ...state, selectionError: action.error };
    case "fileSelected":
      return { ...initialState, phase: "ready", file: action.file, mediaUrl: action.mediaUrl, probe: action.probe, kind: action.probe.kind };
    case "submitting":
      return { ...state, phase: "submitting", error: null, job: null, result: null, selectionError: null };
    case "jobUpdated":
      return { ...state, phase: "processing", job: action.job };
    case "succeeded":
      return { ...state, phase: "succeeded", job: action.job, result: action.result, error: null };
    case "failed":
      return { ...state, phase: "failed", error: action.error, job: action.job ?? state.job };
    case "canceled":
      return { ...state, phase: "canceled", job: action.job ?? state.job };
    case "selectionDismissed":
      return { ...state, selectionError: null };
    case "cleared":
      return initialState;
  }
}

function toApiError(e: unknown): ApiError {
  if (e instanceof ApiRequestError) return e.error;
  return { code: "internal_error", message: e instanceof Error ? e.message : "Beklenmeyen hata.", retryable: false };
}

interface AnalysisContextValue {
  state: AnalysisState;
  service: AnalysisService;
  capabilities: Capabilities | null;
  health: ServiceHealth | null;
  selectFile: (file: File) => Promise<void>;
  start: () => Promise<void>;
  cancel: () => Promise<void>;
  clear: () => void;
  dismissSelectionError: () => void;
  /** Gösterim eşiği (0–1). Yalnızca arayüz filtresi: sunucu tabanından (minConfidenceApplied) düşük olamaz. */
  threshold: number;
  setThreshold: (v: number) => void;
}

/** UI varsayılanı; kalibre edilmiş veya doğrulanmış bir işletim eşiği DEĞİLDİR. */
export const DEFAULT_DISPLAY_THRESHOLD = 0.25;

const AnalysisContext = createContext<AnalysisContextValue | null>(null);

const POLL_INTERVAL_MS = 500;
const MAX_POLL_FAILURES = 3;

export function AnalysisProvider({ children, service: injected }: { children: ReactNode; service?: AnalysisService }) {
  const [service] = useState<AnalysisService>(() => injected ?? createAnalysisService());
  const [state, dispatch] = useReducer(analysisReducer, initialState);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [health, setHealth] = useState<ServiceHealth | null>(null);
  const [threshold, setThreshold] = useState(DEFAULT_DISPLAY_THRESHOLD);
  const urlRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    service.getCapabilities({ signal: controller.signal }).then(setCapabilities).catch(() => setCapabilities(null));
    service.getHealth({ signal: controller.signal }).then(setHealth).catch(() => undefined);
    return () => controller.abort();
  }, [service]);

  useEffect(
    () => () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    },
    [],
  );

  const revokeUrl = () => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
  };

  const selectFile = useCallback(
    async (file: File) => {
      const limits = capabilities?.limits ?? DEFAULT_UPLOAD_LIMITS;
      const verdict = validateMediaFile(file, limits);
      if (!verdict.ok) {
        dispatch({ type: "selectionFailed", error: verdict.error });
        return;
      }
      let probe: MediaProbe;
      try {
        probe = await probeMedia(file, verdict.kind);
      } catch (e) {
        dispatch({
          type: "selectionFailed",
          error: { code: "media_decode_failed", message: e instanceof Error ? e.message : "Medya çözülemedi.", retryable: false },
        });
        return;
      }
      if (probe.kind === "video" && probe.durationMs && probe.durationMs / 1000 > limits.maxVideoDurationSeconds) {
        dispatch({
          type: "selectionFailed",
          error: { code: "video_too_long", message: `Video çok uzun. Sınır ${limits.maxVideoDurationSeconds} sn.`, retryable: false },
        });
        return;
      }
      abortRef.current?.abort();
      revokeUrl();
      const mediaUrl = URL.createObjectURL(file);
      urlRef.current = mediaUrl;
      dispatch({ type: "fileSelected", file, mediaUrl, probe });
    },
    [capabilities],
  );

  const clear = useCallback(() => {
    abortRef.current?.abort();
    revokeUrl();
    dispatch({ type: "cleared" });
  }, []);

  const start = useCallback(async () => {
    const file = state.file;
    if (!file) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const { signal } = controller;
    dispatch({ type: "submitting" });

    try {
      let job = await service.createAnalysis({ file }, { signal });
      dispatch({ type: "jobUpdated", job });
      let failures = 0;
      while (!TERMINAL_JOB_STATUSES.includes(job.status)) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
        if (signal.aborted) return;
        try {
          job = await service.getJob(job.id, { signal });
          failures = 0;
          dispatch({ type: "jobUpdated", job });
        } catch (e) {
          const err = toApiError(e);
          failures += 1;
          if (err.code === "aborted" || !err.retryable || failures >= MAX_POLL_FAILURES) throw e;
        }
      }
      if (job.status === "succeeded") {
        const result = await service.getResult(job.id, { signal });
        dispatch({ type: "succeeded", result, job });
      } else if (job.status === "failed") {
        dispatch({
          type: "failed",
          job,
          error: job.error ?? { code: "internal_error", message: "İş başarısız oldu.", retryable: true },
        });
      } else {
        dispatch({ type: "canceled", job });
      }
    } catch (e) {
      if (signal.aborted) return;
      dispatch({ type: "failed", error: toApiError(e) });
    }
  }, [service, state.file]);

  const cancel = useCallback(async () => {
    const job = state.job;
    abortRef.current?.abort();
    if (!job) {
      dispatch({ type: "canceled", job: null });
      return;
    }
    try {
      dispatch({ type: "canceled", job: await service.cancelJob(job.id) });
    } catch (e) {
      dispatch({ type: "failed", error: toApiError(e) });
    }
  }, [service, state.job]);

  const dismissSelectionError = useCallback(() => {
    dispatch({ type: "selectionDismissed" });
  }, []);

  const value = useMemo<AnalysisContextValue>(
    () => ({ state, service, capabilities, health, selectFile, start, cancel, clear, dismissSelectionError, threshold, setThreshold }),
    [state, service, capabilities, health, selectFile, start, cancel, clear, dismissSelectionError, threshold],
  );

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>;
}

export function useAnalysis(): AnalysisContextValue {
  const ctx = useContext(AnalysisContext);
  if (!ctx) throw new Error("useAnalysis, AnalysisProvider içinde kullanılmalıdır.");
  return ctx;
}
