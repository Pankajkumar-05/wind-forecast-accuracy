import type { ConfigResponse } from "../types/api";

const ROWS: { term: string; formula: string; meaning: string }[] = [
  {
    term: "Signed error",
    formula: "forecast − actual",
    meaning: "Positive: forecast too high (you would have bought too little other power). Negative: forecast too low (you would have over-bought).",
  },
  { term: "Absolute error", formula: "|forecast − actual|", meaning: "How far off the forecast was, ignoring direction." },
  { term: "MAE", formula: "mean of absolute errors", meaning: "The typical miss in MW. Easy to explain and not distorted by a few huge errors." },
  { term: "RMSE", formula: "√ mean of squared errors", meaning: "Like MAE but large misses count more. If RMSE is much bigger than MAE, there are occasional big surprises." },
  { term: "Bias", formula: "mean of signed errors", meaning: "Whether forecasts lean high or low on average. Over- and under-forecasts cancel out, so it can be near zero while MAE is large." },
  { term: "MAPE", formula: "mean of |error| ÷ actual × 100", meaning: "Error as a percentage of actual output. Forecast periods with very low wind are excluded because dividing by (almost) zero is meaningless." },
];

export function MetricGlossary({ config }: { config: ConfigResponse }) {
  return (
    <details className="glossary">
      <summary>How are these numbers calculated?</summary>
      <div className="glossary__body">
        <p>
          <strong>Which forecast is used?</strong> Many forecasts are published for the same forecast period. For each one we use the most
          recent forecast published <em>before the day-ahead decision cutoff</em> ({config.decision_rule.description}), because a
          forecast published later could not have informed the purchase. This cutoff is an assumption and is configurable.
        </p>
        <dl className="glossary__terms">
          {ROWS.map((row) => (
            <div key={row.term}>
              <dt>
                {row.term} <code>{row.formula}</code>
              </dt>
              <dd>{row.meaning}</dd>
            </div>
          ))}
        </dl>
        <p className="glossary__foot">
          MAPE ignores forecast periods where actual generation is below {config.mape_min_actual_mw} MW. All times are UK local time.
          Source: {config.data_source}.
        </p>
        <p className="glossary__foot">
          <strong>Time grids.</strong> Forecasts are evaluated only where a forecast and an actual share exactly the same start time. Nothing
          is interpolated, repeated or averaged to fill gaps between forecast periods.
        </p>
      </div>
    </details>
  );
}
