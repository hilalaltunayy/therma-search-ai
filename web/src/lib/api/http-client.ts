import {
  ApiRequestError,
  type AnalysisResult,
  type AnalysisService,
  type ApiError,
  type Capabilities,
  type CreateAnalysisInput,
  type Job,
  type RequestOptions,
  type ServiceHealth,
} from "./contract";
import { assertAnalysisResult, assertJob, isApiErrorEnvelope } from "./guards";
import { resolveMimeType } from "@/lib/media/validate";

export interface HttpClientConfig {
  baseUrl: string;
  /** Test için enjekte edilebilir. */
  fetchImpl?: typeof fetch;
  /** Küçük JSON istekleri için zaman aşımı (yükleme hariç). */
  timeoutMs?: number;
}

/**
 * FastAPI istemcisi — `docs/api-contract.md` sözleşmesinin İSTEMCİ tarafı.
 * DURUM: Backend yok; bu istemci gerçek bir sunucuya karşı DENENMEMİŞTİR. Yalnızca sahte `fetch`
 * ile birim test edilir. UI bu istemciyi yalnızca NEXT_PUBLIC_THERMA_API_MODE=http iken kullanır.
 */
export function createHttpAnalysisService(config: HttpClientConfig): AnalysisService {
  const base = config.baseUrl.replace(/\/+$/, "");
  const doFetch = config.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
  const timeoutMs = config.timeoutMs ?? 15_000;

  async function request<T>(
    path: string,
    init: RequestInit & { timeout?: boolean },
    parse: (json: unknown) => T,
    opts?: RequestOptions,
  ): Promise<T> {
    const controller = new AbortController();
    let timedOut = false;
    const timer = init.timeout === false ? null : setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    const onAbort = () => controller.abort();
    opts?.signal?.addEventListener("abort", onAbort, { once: true });

    try {
      const res = await doFetch(`${base}${path}`, { ...init, signal: controller.signal });
      let body: unknown = null;
      try {
        body = await res.json();
      } catch {
        body = null;
      }
      if (!res.ok) {
        if (isApiErrorEnvelope(body)) throw new ApiRequestError(body.error, res.status);
        throw new ApiRequestError(
          { code: "internal_error", message: `Sunucu hatası (HTTP ${res.status}).`, retryable: res.status >= 500 },
          res.status,
        );
      }
      return parse(body);
    } catch (e) {
      if (e instanceof ApiRequestError) throw e;
      const aborted = e instanceof DOMException && e.name === "AbortError";
      const error: ApiError = aborted
        ? timedOut
          ? { code: "timeout", message: "Sunucu zamanında yanıt vermedi.", retryable: true }
          : { code: "aborted", message: "İstek iptal edildi.", retryable: false }
        : { code: "network_error", message: "Sunucuya ulaşılamadı.", retryable: true };
      throw new ApiRequestError(error);
    } finally {
      if (timer) clearTimeout(timer);
      opts?.signal?.removeEventListener("abort", onAbort);
    }
  }

  return {
    mode: "http",

    getCapabilities: (opts) =>
      request<Capabilities>("/api/v1/capabilities", { method: "GET" }, (j) => j as Capabilities, opts),

    async getHealth(opts): Promise<ServiceHealth> {
      try {
        return await request<ServiceHealth>("/api/v1/health", { method: "GET" }, (j) => j as ServiceHealth, opts);
      } catch (e) {
        if (e instanceof ApiRequestError && e.error.code === "aborted") throw e;
        return {
          status: "unreachable",
          backendConnected: false,
          provenance: "model",
          modelLoaded: null,
          checkedAt: new Date().toISOString(),
        };
      }
    },

    createAnalysis({ file, options }: CreateAnalysisInput, opts) {
      const isVideo = resolveMimeType(file).startsWith("video/");
      const form = new FormData();
      form.append("file", file, file.name);
      if (options) form.append("options", JSON.stringify(options));
      return request<Job>(
        `/api/v1/analyses/${isVideo ? "video" : "image"}`,
        { method: "POST", body: form, timeout: false }, // büyük yüklemelerde sabit zaman aşımı kullanılmaz
        assertJob,
        opts,
      );
    },

    getJob: (id, opts) => request<Job>(`/api/v1/jobs/${encodeURIComponent(id)}`, { method: "GET" }, assertJob, opts),

    getResult: (id, opts) =>
      request<AnalysisResult>(`/api/v1/jobs/${encodeURIComponent(id)}/result`, { method: "GET" }, assertAnalysisResult, opts),

    cancelJob: (id, opts) => request<Job>(`/api/v1/jobs/${encodeURIComponent(id)}`, { method: "DELETE" }, assertJob, opts),
  };
}
