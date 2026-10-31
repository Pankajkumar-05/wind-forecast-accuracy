import { useMemo, useState } from "react";
import { Card } from "../components/Card";
import { DailyErrorTable } from "../components/DailyErrorTable";
import { DataQualityPanel } from "../components/DataQualityPanel";
import { DateRangeFilter } from "../components/DateRangeFilter";
import { ErrorChart } from "../components/ErrorChart";
import { ForecastActualChart, toChartRows } from "../components/ForecastActualChart";
import { KpiGrid } from "../components/KpiGrid";
import { LatestForecastCard } from "../components/LatestForecastCard";
import { MetricGlossary } from "../components/MetricGlossary";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateViews";
import { useAsync, type AsyncState } from "../hooks/useAsync";
import { api } from "../services/api";
import type { ConfigResponse, DateRange } from "../types/api";
import { formatDeliveryDay } from "../utils/format";

/** Renders loading / error / empty for an async section and hands the data to `children` on success. */
function Section<T>({
  state,
  onRetry,
  loadingLabel,
  loadingHeight,
  isEmpty,
  emptyTitle,
  emptyText,
  children,
}: {
  state: AsyncState<T>;
  onRetry: () => void;
  loadingLabel: string;
  loadingHeight?: number;
  isEmpty?: (data: T) => boolean;
  emptyTitle: string;
  emptyText: string;
  children: (data: T) => JSX.Element;
}) {
  if (state.status === "loading") return <LoadingBlock label={loadingLabel} height={loadingHeight} />;
  if (state.status === "error") {
    return state.error.status === 404 ? (
      <EmptyBlock title={emptyTitle}>{state.error.message}</EmptyBlock>
    ) : (
      <ErrorBlock error={state.error} onRetry={onRetry} />
    );
  }
  if (isEmpty?.(state.data)) return <EmptyBlock title={emptyTitle}>{emptyText}</EmptyBlock>;
  return children(state.data);
}

function DashboardBody({ config }: { config: ConfigResponse }) {
  const [range, setRange] = useState<DateRange>({ start: config.window_start, end: config.window_end });

  const latest = useAsync((signal) => api.latestForecast(signal), []);
  const comparison = useAsync((signal) => api.comparison(range, signal), [range.start, range.end]);
  const metrics = useAsync((signal) => api.metrics(range, signal), [range.start, range.end]);

  const rows = useMemo(() => (comparison.state.status === "success" ? toChartRows(comparison.state.data.points) : []), [comparison.state]);
  const rangeLabel =
    range.start === range.end ? formatDeliveryDay(range.start) : `${formatDeliveryDay(range.start)} → ${formatDeliveryDay(range.end)}`;

  return (
    <>
      <Card
        id="latest"
        title="Latest forecast available for the day-ahead decision"
        subtitle="The forecast a buyer would have had on the morning before delivery."
      >
        <Section
          state={latest.state}
          onRetry={latest.reload}
          loadingLabel="Loading latest forecast…"
          loadingHeight={220}
          emptyTitle="No forecast available yet"
          emptyText="There is no decision-time forecast for the configured period."
        >
          {(data) => <LatestForecastCard latest={data} rule={config.decision_rule} />}
        </Section>
      </Card>

      <div className="toolbar">
        <div>
          <h2 className="toolbar__title">Forecast accuracy</h2>
          <p className="toolbar__range">Delivery days: {rangeLabel}</p>
        </div>
        <DateRangeFilter value={range} min={config.window_start} max={config.window_end} onChange={setRange} />
      </div>

      <Section
        state={metrics.state}
        onRetry={metrics.reload}
        loadingLabel="Calculating accuracy metrics…"
        isEmpty={(data) => data.overall.n === 0}
        emptyTitle="No evaluated forecast periods in this range"
        emptyText="No forecast period has both a forecast and an actual for these days. Try a different date range."
      >
        {(data) => <KpiGrid metrics={data} mapeMinActualMw={config.mape_min_actual_mw} />}
      </Section>

      <Card
        id="comparison"
        title="Forecast vs actual wind generation"
        subtitle="National wind output (MW) at each forecast period. Forecast = the version published before the decision cutoff."
      >
        <Section
          state={comparison.state}
          onRetry={comparison.reload}
          loadingLabel="Loading chart data…"
          loadingHeight={380}
          isEmpty={(data) => data.points.length === 0}
          emptyTitle="Nothing to chart for these dates"
          emptyText="No forecast periods in this range have both a forecast and an actual value."
        >
          {() => <ForecastActualChart rows={rows} />}
        </Section>
      </Card>

      <Card id="error" title="Forecast error over time" subtitle="Signed error per forecast period (forecast − actual), and a day-by-day summary.">
        <Section
          state={comparison.state}
          onRetry={comparison.reload}
          loadingLabel="Loading error data…"
          loadingHeight={260}
          isEmpty={(data) => data.points.length === 0}
          emptyTitle="No error data for these dates"
          emptyText="Errors can only be calculated where both a forecast and an actual exist."
        >
          {() => <ErrorChart rows={rows} />}
        </Section>
        <Section
          state={metrics.state}
          onRetry={metrics.reload}
          loadingLabel="Loading daily summary…"
          isEmpty={(data) => data.daily.length === 0}
          emptyTitle="No daily summary"
          emptyText="No complete delivery days in this range."
        >
          {(data) => <DailyErrorTable daily={data.daily} />}
        </Section>
      </Card>

      <Card id="quality" title="Data quality and coverage" subtitle="How complete is the data behind these numbers?">
        <Section
          state={metrics.state}
          onRetry={metrics.reload}
          loadingLabel="Checking data coverage…"
          emptyTitle="No coverage information"
          emptyText=""
        >
          {(data) => <DataQualityPanel quality={data.quality} />}
        </Section>
      </Card>

      <MetricGlossary config={config} />
    </>
  );
}

export function DashboardPage() {
  const config = useAsync((signal) => api.config(signal), []);

  return (
    <div className="app">
      <header className="masthead">
        <div className="masthead__brand">
          <span className="logo" aria-hidden="true">
            <svg viewBox="0 0 32 32" width="28" height="28">
              <path d="M5 19c4-8 6 8 11 0s7 8 11 0" stroke="currentColor" strokeWidth="2.6" fill="none" strokeLinecap="round" />
            </svg>
          </span>
          <div>
            <h1>Wind Forecast Accuracy</h1>
            <p>Day-ahead purchasing desk · Great Britain · Elexon data</p>
          </div>
        </div>
        {config.state.status === "success" && (
          <p className="masthead__rule">
            Decision cutoff: <strong>{config.state.data.decision_rule.description}</strong>
          </p>
        )}
      </header>

      <main>
        {config.state.status === "loading" && <LoadingBlock label="Starting up…" height={240} />}
        {config.state.status === "error" && <ErrorBlock error={config.state.error} onRetry={config.reload} />}
        {config.state.status === "success" && <DashboardBody config={config.state.data} />}
      </main>

      <footer className="footer">
        Data: Elexon BMRS (FUELHH actuals, WINDFOR forecasts), used under the BMRS Data Licence. Forecast figures are for evaluation of
        past decisions and are not a trading recommendation.
      </footer>
    </div>
  );
}
