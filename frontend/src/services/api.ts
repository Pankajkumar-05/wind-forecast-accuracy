import type {
  ComparisonResponse,
  ConfigResponse,
  DateRange,
  LatestForecastResponse,
  MetricsResponse,
} from "../types/api";

// Empty by default: the dev server and the production host both serve /api on the same origin.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export class ApiError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }

  /** Worth showing a "Retry" button: network problems and server-side failures. */
  get isRetryable(): boolean {
    return this.status === null || this.status >= 500;
  }
}

async function getJson<T>(path: string, params: Record<string, string | undefined>, signal?: AbortSignal): Promise<T> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) query.set(key, value);
  });
  const url = `${API_BASE_URL}${path}${query.size ? `?${query}` : ""}`;

  let response: Response;
  try {
    response = await fetch(url, { signal, headers: { Accept: "application/json" } });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("Could not reach the server. Check your connection and try again.", null);
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* body was not JSON: keep the generic message */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export const api = {
  config: (signal?: AbortSignal) => getJson<ConfigResponse>("/api/config", {}, signal),
  latestForecast: (signal?: AbortSignal) => getJson<LatestForecastResponse>("/api/forecasts/latest", {}, signal),
  comparison: (range: DateRange, signal?: AbortSignal) => getJson<ComparisonResponse>("/api/comparison", range as unknown as Record<string, string>, signal),
  metrics: (range: DateRange, signal?: AbortSignal) => getJson<MetricsResponse>("/api/metrics", range as unknown as Record<string, string>, signal),
};
