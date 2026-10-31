import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ChartRow } from "./ForecastActualChart";
import { formatDateTime, formatDayShort, formatShortDateTime, formatSignedMW } from "../utils/format";

function ErrorTooltip({ active, payload }: { active?: boolean; payload?: { payload: ChartRow }[] }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="tooltip">
      <div className="tooltip__title">{formatDateTime(row.startTime)} (UK time)</div>
      <div className="tooltip__row">
        <span>Error (forecast − actual)</span>
        <strong>{formatSignedMW(row.error)}</strong>
      </div>
      <div className="tooltip__foot">{row.error > 0 ? "Forecast was too high" : row.error < 0 ? "Forecast was too low" : "Exact match"}</div>
    </div>
  );
}

/** Signed error over time. Above the zero line = over-forecast; below = under-forecast. */
export function ErrorChart({ rows }: { rows: ChartRow[] }) {
  const spanMs = rows.length ? rows[rows.length - 1].ts - rows[0].ts : 0;
  const tickFormatter = spanMs <= 2 * 86_400_000 ? formatShortDateTime : formatDayShort;

  return (
    <div className="chart" role="img" aria-label="Area chart of the signed forecast error in megawatts over time. Above zero means the forecast was too high.">
      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
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
            label={{ value: "Error (MW)", angle: -90, position: "insideLeft", fill: "var(--c-muted)", fontSize: 12 }}
          />
          <Tooltip content={<ErrorTooltip />} isAnimationActive={false} />
          <ReferenceLine y={0} stroke="var(--c-axis)" strokeWidth={1.5} />
          <Area
            dataKey="error"
            name="Forecast error"
            type="monotone"
            stroke="var(--c-error)"
            fill="var(--c-error)"
            fillOpacity={0.22}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
      <p className="chart__caption">
        <span className="swatch swatch--error" aria-hidden="true" /> Above the line: forecast too high · Below the line: forecast too low
      </p>
    </div>
  );
}
