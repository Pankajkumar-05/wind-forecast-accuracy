import { Area, AreaChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import type { ConfigResponse, LatestForecastResponse } from "../types/api";
import { formatDateTime, formatDeliveryDay, formatInteger, formatMW, formatTime } from "../utils/format";

interface LatestForecastCardProps {
  latest: LatestForecastResponse;
  rule: ConfigResponse["decision_rule"];
}

function Fact({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="fact">
      <dt>{label}</dt>
      <dd>{value}</dd>
      {note && <dd className="fact__note">{note}</dd>}
    </div>
  );
}

/** Answers: what is the forecast, for when, and when was it published? */
export function LatestForecastCard({ latest, rule }: LatestForecastCardProps) {
  const spark = latest.periods.map((p) => ({ ts: new Date(p.start_time).getTime(), mw: p.forecast_mw }));
  const sameInstant = latest.earliest_publish_time === latest.latest_publish_time;

  return (
    <div className="latest">
      <div className="latest__headline">
        <p className="eyebrow">Forecast for delivery on</p>
        <p className="latest__day">{formatDeliveryDay(latest.delivery_date)}</p>
        <p className="latest__value">
          {formatMW(latest.mean_mw)} <span>average wind forecast</span>
        </p>
        <p className="latest__published">
          Published {sameInstant ? formatDateTime(latest.latest_publish_time) : `${formatDateTime(latest.earliest_publish_time)} – ${formatDateTime(latest.latest_publish_time)}`}
        </p>
      </div>

      <div className="latest__spark" role="img" aria-label="Forecast wind generation across the delivery day">
        <ResponsiveContainer width="100%" height={92}>
          <AreaChart data={spark} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
            <XAxis dataKey="ts" type="number" scale="time" domain={["dataMin", "dataMax"]} hide />
            <YAxis hide domain={[0, "dataMax"]} />
            <Area dataKey="mw" stroke="var(--c-forecast)" fill="var(--c-forecast)" fillOpacity={0.18} strokeWidth={1.8} dot={false} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <dl className="facts">
        <Fact label="Peak" value={formatMW(latest.peak_mw)} note={`at ${formatTime(latest.peak_time)}`} />
        <Fact label="Lowest" value={formatMW(latest.min_mw)} />
        <Fact label="Forecast periods" value={formatInteger(latest.period_count)} />
        <Fact
          label="Actual average"
          value={latest.actual_mean_mw !== null ? formatMW(latest.actual_mean_mw) : "Not yet published"}
          note={latest.actual_mean_mw !== null ? "at the forecast periods" : undefined}
        />
        <Fact label="Decision cutoff" value={formatDateTime(latest.decision_cutoff)} note={rule.description} />
      </dl>
    </div>
  );
}
