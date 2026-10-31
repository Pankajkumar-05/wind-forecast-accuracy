import type { DataQuality } from "../types/api";
import { describeResolution, formatDateTime, formatInteger } from "../utils/format";

/**
 * Tells the user exactly how complete the evaluation is. This is deliberate: a number that
 * silently ignores missing data would look more trustworthy than it is.
 *
 * Coverage is measured on the forecast grid (hourly for WINDFOR). Actual periods that fall between
 * forecast periods (the :30 half-hours of FUELHH) are explained, never counted as missing forecasts.
 */
export function DataQualityPanel({ quality }: { quality: DataQuality }) {
  const { coverage } = quality;
  const resolution = describeResolution(coverage.forecast_resolution_minutes);
  const percent = coverage.expected_forecast_periods ? (coverage.matched_periods / coverage.expected_forecast_periods) * 100 : 0;
  const healthy = quality.warnings.length === 0;

  return (
    <div className="quality">
      <div className="quality__summary">
        <span className={`badge ${healthy ? "badge--ok" : "badge--warn"}`}>{healthy ? "Complete" : "Partial data"}</span>
        <span>
          <strong>{formatInteger(coverage.matched_periods)}</strong> of {formatInteger(coverage.expected_forecast_periods)} {resolution}{" "}
          forecast periods have both a forecast and an actual ({percent.toFixed(1)}%)
        </span>
      </div>

      <div className="meter" role="img" aria-label={`${percent.toFixed(1)} percent of ${resolution} forecast periods evaluated`}>
        <div className="meter__fill" style={{ width: `${Math.min(percent, 100)}%` }} />
      </div>

      <p className="quality__note">
        <strong>Why not every half-hour?</strong> Actual wind output (FUELHH) is reported every 30 minutes, but wind forecasts (WINDFOR)
        are published for {resolution} periods only. Each forecast is compared with the actual that has exactly the same start time.
        The in-between actual periods have no forecast to compare with, so they are left out. They are not missing forecasts, and
        nothing is interpolated, repeated or averaged to fill them.
      </p>

      {quality.warnings.length > 0 && (
        <ul className="quality__warnings">
          {quality.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      <dl className="quality__facts">
        <div>
          <dt>Missing forecasts</dt>
          <dd>{formatInteger(coverage.missing_forecast_periods)}</dd>
        </div>
        <div>
          <dt>Missing actuals</dt>
          <dd>{formatInteger(coverage.missing_actual_periods)}</dd>
        </div>
        <div>
          <dt>Actual periods with no forecast</dt>
          <dd>{formatInteger(coverage.actual_periods_off_forecast_grid)}</dd>
        </div>
        <div>
          <dt>Late forecasts excluded</dt>
          <dd>{formatInteger(quality.forecasts_published_after_cutoff_excluded)}</dd>
        </div>
        <div>
          <dt>Duplicates removed</dt>
          <dd>{formatInteger(quality.duplicates_removed)}</dd>
        </div>
        <div>
          <dt>Malformed rows skipped</dt>
          <dd>{formatInteger(quality.malformed_rows_skipped)}</dd>
        </div>
        <div>
          <dt>Data fetched</dt>
          <dd>{formatDateTime(quality.fetched_at)}</dd>
        </div>
      </dl>
    </div>
  );
}
