import type { DailyMetrics } from "../types/api";
import { formatDeliveryDay, formatInteger, formatMW, formatSignedMW } from "../utils/format";

/** One row per delivery day: how accurate was the forecast the buyer saw the day before? */
export function DailyErrorTable({ daily }: { daily: DailyMetrics[] }) {
  const maxMae = Math.max(...daily.map((d) => d.mae), 1);

  return (
    <div className="table-wrap">
      <table className="table">
        <caption className="sr-only">Forecast error by delivery day</caption>
        <thead>
          <tr>
            <th scope="col">Delivery day</th>
            <th scope="col" className="num">
              Forecast periods
            </th>
            <th scope="col" className="num">
              MAE
            </th>
            <th scope="col" className="bar-col">
              <span className="sr-only">MAE relative to the worst day</span>
            </th>
            <th scope="col" className="num">
              RMSE
            </th>
            <th scope="col" className="num">
              Bias
            </th>
          </tr>
        </thead>
        <tbody>
          {daily.map((day) => (
            <tr key={day.delivery_date}>
              <th scope="row">{formatDeliveryDay(day.delivery_date)}</th>
              <td className="num">{formatInteger(day.n)}</td>
              <td className="num">{formatMW(day.mae)}</td>
              <td className="bar-col" aria-hidden="true">
                <div className="bar">
                  <div className="bar__fill" style={{ width: `${(day.mae / maxMae) * 100}%` }} />
                </div>
              </td>
              <td className="num">{formatMW(day.rmse)}</td>
              <td className={`num ${day.bias > 0 ? "pos" : day.bias < 0 ? "neg" : ""}`}>{formatSignedMW(day.bias)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
