import type { AnalysisService } from "./contract";
import { createHttpAnalysisService } from "./http-client";
import { createMockAnalysisService } from "./mock-service";

export type ApiMode = "mock" | "http";

export function resolveApiMode(raw: string | undefined): ApiMode {
  return raw === "http" ? "http" : "mock";
}

/**
 * Servis seçimi tek yerde yapılır. Varsayılan `mock`: backend olmadığı için gerçek istemci
 * yalnızca NEXT_PUBLIC_THERMA_API_MODE=http ile açıkça etkinleştirilir.
 */
export function createAnalysisService(): AnalysisService {
  const mode = resolveApiMode(process.env.NEXT_PUBLIC_THERMA_API_MODE);
  if (mode === "http") {
    return createHttpAnalysisService({ baseUrl: process.env.NEXT_PUBLIC_THERMA_API_URL ?? "http://localhost:8000" });
  }
  return createMockAnalysisService();
}

export * from "./contract";
