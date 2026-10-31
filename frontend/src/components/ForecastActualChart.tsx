import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ComparisonPoint } from "../types/api";
import { formatDateTime, formatDayShort, formatMW, formatShortDateTime, formatSignedMW } from "../utils/format";

export interface ChartRow {
  ts: number;
  forecast: number;
  actual: number;
  error: number;
  publishedAt: string;
  startTime: string;
}

export function toChartRows(points: ComparisonPoint[]): ChartRow[] {
  return points.map((p) => ({
    ts: new Date(p.start_time).getTime(),
    forecast: p.forecast_mw,
    actual: p.actual_mw,
    error: p.error_mw,
    publishedAt: p.forecast_publish_time,
    startTime: p.start_time,
  }));
}

interface TooltipProps {
  active?: boolean;
  payload?: { payload: ChartRow }[];
}

function ComparisonTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="tooltip">
      <div className="tooltip__title">{formatDateTime(row.startTime)} (UK time)</div>
      <div className="tooltip__row tooltip__row--forecast">
        <span>Forecast</span>
        <strong>{formatMW(row.forecast)}</strong>
      </div>
      <div className="tooltip__row tooltip__row--actual">
        <span>Actual</span>
        <strong>{formatMW(row.actual)}</strong>
      </div>
      <div className="tooltip__row">
        <span>Error (forecast − actual)</span>
        <strong>{formatSignedMW(row.error)}</strong>
      </div>
      <div className="tooltip__foot">Forecast published {formatDateTime(row.publishedAt)}</div>
    </div>
  );
}

/** Spans of one day or less get a time-of-day axis; longer spans get a date axis. */
function useTickFormatter(rows: ChartRow[]) {
  return useMemo(() => {
    const spanMs = rows.length ? rows[rows.length - 1].ts - rows[0].ts : 0;
    return spanMs <= 2 * 86_400_000 ? (value: number) => formatShortDateTime(value) : (value: number) => formatDayShort(value);
  }, [rows]);
}

export function ForecastActualChart({ rows }: { rows: ChartRow[] }) {
  const tickFormatter = useTickFormatter(rows);
  const first = rows[0];
  const last = rows[rows.length - 1];
  const label = `Line chart of forecast and actual wind generation in megawatts, ${rows.length} forecast periods from ${formatDateTime(first.startTime)} to ${formatDateTime(last.startTime)}.`;

  return (
    <div className="chart">
      {/* HTML legend instead of Recharts' own: it wraps cleanly on narrow screens. Line style
          (solid vs dashed) as well as colour tells the series apart. */}
      <ul className="legend" aria-label="Chart legend">
        <li>
          <svg width="28" height="10" aria-hidden="true">
            <line x1="0" y1="5" x2="28" y2="5" stroke="var(--c-actual)" strokeWidth="2.5" />
          </svg>
          Actual wind generation
        </li>
        <li>
          <svg width="28" height="10" aria-hidden="true">
            <line x1="0" y1="5" x2="28" y2="5" stroke="var(--c-forecast)" strokeWidth="2.5" strokeDasharray="6 4" />
          </svg>
          Forecast at decision time
        </li>
      </ul>
      <div role="img" aria-label={label}>
      <ResponsiveContainer width="100%" height={360}>
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
          <CartesianGrid stroke="var(--c-grid)" vertical={false} />
          <XAxis
            dataKey="ts"
            type="number"
            scale="time"
            domain={["dataMin", "dataMax"]}
            tickFormatter={tickFormatter}
            tick={{ fill: "var(--c-muted)", fontSize: 12 }}
            stroke="var(--c-axis)"
            minTickGap={48}
          />
          <YAxis
            tickFormatter={(v: number) => v.toLocaleString("en-GB")}
            tick={{ fill: "var(--c-muted)", fontSize: 12 }}
            stroke="var(--c-axis)"
            width={64}
            label={{ value: "MW", angle: -90, position: "insideLeft", fill: "var(--c-muted)", fontSize: 12 }}
          />
          <Tooltip content={<ComparisonTooltip />} isAnimationActive={false} />
          <Line
            name="Actual wind generation"
            dataKey="actual"
            stroke="var(--c-actual)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            activeDot={{ r: 4 }}
          />
          <Line
            name="Forecast at decision time"
            dataKey="forecast"
            stroke="var(--c-forecast)"
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={false}
            isAnimationActive={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
      </div>
    </div>
  );
}
