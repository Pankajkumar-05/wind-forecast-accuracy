import type { ReactNode } from "react";
import type { ApiError } from "../services/api";

export function LoadingBlock({ label = "Loading…", height = 120 }: { label?: string; height?: number }) {
  return (
    <div className="state state--loading" role="status" aria-live="polite" style={{ minHeight: height }}>
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorBlock({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div className="state state--error" role="alert">
      <strong>Something went wrong</strong>
      <p>{error.message}</p>
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyBlock({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state state--empty" role="status">
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  );
}
