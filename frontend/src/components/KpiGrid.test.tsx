import { render, screen, within } from "@testing-library/react";
import { metrics, partialQuality } from "../test/fixtures";
import { DataQualityPanel } from "./DataQualityPanel";
import { KpiGrid } from "./KpiGrid";

function kpi(label: RegExp) {
  const term = screen.getByText(label);
  return within(term.parentElement as HTMLElement);
}

describe("KpiGrid", () => {
  it("shows MAE, RMSE, bias, MAPE and the number of evaluated periods", () => {
    render(<KpiGrid metrics={metrics} mapeMinActualMw={50} />);
    expect(kpi(/^MAE/).getByText("812 MW")).toBeInTheDocument();
    expect(kpi(/^RMSE/).getByText("1,035 MW")).toBeInTheDocument();
    expect(kpi(/^Bias/).getByText("−120 MW")).toBeInTheDocument();
    expect(kpi(/^MAPE/).getByText("14.2%")).toBeInTheDocument();
    expect(kpi(/Forecast periods evaluated/).getByText("100")).toBeInTheDocument();
  });

  it("explains the bias direction in words", () => {
    render(<KpiGrid metrics={metrics} mapeMinActualMw={50} />);
    expect(screen.getByText(/too low \(under-forecast\)/i)).toBeInTheDocument();
  });

  it("is transparent about forecast periods excluded from MAPE", () => {
    render(<KpiGrid metrics={metrics} mapeMinActualMw={50} />);
    expect(screen.getByText(/Excludes 3 forecast periods with wind under 50 MW/)).toBeInTheDocument();
  });

  it("shows dashes rather than zeros when there is no data", () => {
    const empty = {
      ...metrics,
      overall: { ...metrics.overall, n: 0, mae: null, rmse: null, bias: null, mape: null, mape_excluded: 0, mae_pct_of_mean_actual: null, p90_abs_error: null },
    };
    render(<KpiGrid metrics={empty} mapeMinActualMw={50} />);
    expect(kpi(/^MAE/).getByText("—")).toBeInTheDocument();
    expect(kpi(/^MAPE/).getByText("—")).toBeInTheDocument();
  });
});

describe("DataQualityPanel", () => {
  it("shows a Partial data badge and the warning when data is missing", () => {
    render(<DataQualityPanel quality={partialQuality} />);
    expect(screen.getByText("Partial data")).toBeInTheDocument();
    expect(screen.getByText(/no actual generation value/i)).toBeInTheDocument();
    // "60" is bold inside the sentence, so match on the element's combined text.
    expect(
      screen.getByText((_, element) => element?.tagName === "SPAN" && /60 of 100 hourly forecast periods have both/.test(element.textContent ?? "")),
    ).toBeInTheDocument();
  });

  it("shows Complete when there are no warnings", () => {
    render(<DataQualityPanel quality={metrics.quality} />);
    expect(screen.getByText("Complete")).toBeInTheDocument();
  });

  it("shows Complete and explains the 30-minute actuals without calling them missing forecasts", () => {
    render(<DataQualityPanel quality={metrics.quality} />);
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.queryByText("Partial data")).not.toBeInTheDocument();
    expect(screen.getByText(/Why not every half-hour\?/)).toBeInTheDocument();
    expect(screen.getByText(/nothing is interpolated, repeated or averaged/i)).toBeInTheDocument();
    expect(screen.getByText("Actual periods with no forecast")).toBeInTheDocument();
    expect(screen.queryByText(/half-hours evaluated/i)).not.toBeInTheDocument();
  });
});
