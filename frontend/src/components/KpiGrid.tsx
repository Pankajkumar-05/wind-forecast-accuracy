import type { MetricsResponse } from "../types/api";
import { describeBias, describeResolution, formatInteger, formatMW, formatPercent, formatSignedMW } from "../utils/format";

interface KpiProps {
  label: string;
  value: string;
  hint: string;
  tone?: "neutral" | "warn";
}

function Kpi({ label, value, hint, tone = "neutral" }: KpiProps) {
  return (
    <div className={`kpi kpi--${tone}`}>
      <dt className="kpi__label">{label}</dt>
      <dd className="kpi__value">{value}</dd>
      <dd className="kpi__hint">{hint}</dd>
    </div>
  );
}

/** Headline accuracy numbers. Every card says what the number means in plain English. */
export function KpiGrid({ metrics, mapeMinActualMw }: { metrics: MetricsResponse; mapeMinActualMw: number }) {
  const { overall, quality } = metrics;
  const expected = quality.coverage.expected_forecast_periods;
  const lowCoverage = expected > 0 && overall.n / expected < 0.9;

  return (
    <dl className="kpi-grid" aria-label="Forecast accuracy summary">
      <Kpi
        label="MAE · typical miss"
        value={formatMW(overall.mae)}
        hint={
          overall.mae_pct_of_mean_actual !== null
            ? `${formatPercent(overall.mae_pct_of_mean_actual)} of average wind output`
            : "Average size of the error, ignoring direction"
        }
      />
      <Kpi
        label="RMSE · big-miss penalty"
        value={formatMW(overall.rmse)}
        hint={overall.p90_abs_error !== null ? `90% of forecast periods missed by less than ${formatMW(overall.p90_abs_error)}` : "Penalises large errors more than MAE"}
      />
      <Kpi label="Bias · mean error" value={formatSignedMW(overall.bias)} hint={describeBias(overall.bias)} />
      <Kpi
        label="MAPE · % error"
        value={formatPercent(overall.mape)}
        hint={
          overall.mape_excluded > 0
            ? `Excludes ${formatInteger(overall.mape_excluded)} forecast periods with wind under ${formatMW(mapeMinActualMw)}`
            : "Average error as a share of actual output"
        }
      />
      <Kpi
        label="Forecast periods evaluated"
        value={formatInteger(overall.n)}
        hint={`of ${formatInteger(expected)} ${describeResolution(quality.coverage.forecast_resolution_minutes)} forecast periods in range`}
        tone={lowCoverage ? "warn" : "neutral"}
      />
    </dl>
  );
}
