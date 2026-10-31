import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach } from "vitest";
import { comparison, config, latest, metrics } from "../test/fixtures";
import { DashboardPage } from "./DashboardPage";

type Handler = (url: URL) => Response | Promise<Response>;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function mockApi(overrides: Record<string, Handler> = {}) {
  const handlers: Record<string, Handler> = {
    "/api/config": () => json(config),
    "/api/forecasts/latest": () => json(latest),
    "/api/comparison": () => json(comparison),
    "/api/metrics": () => json(metrics),
    ...overrides,
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), "http://localhost");
    const handler = handlers[url.pathname];
    if (!handler) return json({ detail: "not found" }, 404);
    return handler(url);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe("DashboardPage", () => {
  it("shows a loading state first, then the dashboard", async () => {
    mockApi();
    render(<DashboardPage />);
    expect(screen.getByRole("status")).toHaveTextContent(/starting up/i);

    expect(await screen.findByText(/Forecast for delivery on/i)).toBeInTheDocument();
    expect(screen.getByText("Sun, 1 Feb 2026")).toBeInTheDocument();
    expect(await screen.findByText("812 MW")).toBeInTheDocument();
  });

  it("answers the key questions: forecast value, delivery period, publication time, actual", async () => {
    mockApi();
    render(<DashboardPage />);
    expect(await screen.findByText(/7,422 MW/)).toBeInTheDocument(); // forecast
    expect(screen.getByText(/Published 31 Jan 2026/)).toBeInTheDocument(); // publication time
    expect(screen.getByText("7,300 MW")).toBeInTheDocument(); // actual average
    expect(screen.getAllByText(/1 day\(s\) before delivery at 09:00 Europe\/London/).length).toBeGreaterThan(0);
  });

  it("renders the charts with accessible descriptions", async () => {
    mockApi();
    render(<DashboardPage />);
    expect(await screen.findByRole("img", { name: /forecast and actual wind generation/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /signed forecast error/i })).toBeInTheDocument();
  });

  it("shows the daily error table", async () => {
    mockApi();
    render(<DashboardPage />);
    expect(await screen.findByRole("table", { name: /error by delivery day/i })).toBeInTheDocument();
    expect(screen.getByText("Fri, 2 Jan 2026")).toBeInTheDocument();
  });

  it("shows an error with a Retry button when the config request fails, and recovers on retry", async () => {
    let failing = true;
    mockApi({ "/api/config": () => (failing ? json({ detail: "The Elexon data service is unavailable." }, 502) : json(config)) });
    render(<DashboardPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable/i);
    failing = false;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(/Forecast for delivery on/i)).toBeInTheDocument();
  });

  it("isolates failures: an error in metrics does not hide the chart", async () => {
    mockApi({ "/api/metrics": () => json({ detail: "The Elexon data service is unavailable." }, 502) });
    render(<DashboardPage />);
    expect(await screen.findByRole("img", { name: /forecast and actual wind generation/i })).toBeInTheDocument();
    expect((await screen.findAllByRole("alert")).length).toBeGreaterThan(0);
  });

  it("shows a friendly empty state when no forecast periods can be evaluated", async () => {
    mockApi({
      "/api/comparison": () => json({ ...comparison, points: [] }),
      "/api/metrics": () => json({ ...metrics, overall: { ...metrics.overall, n: 0, mae: null }, daily: [] }),
    });
    render(<DashboardPage />);
    expect(await screen.findByText(/No evaluated forecast periods in this range/i)).toBeInTheDocument();
    expect(screen.getByText(/Nothing to chart for these dates/i)).toBeInTheDocument();
  });

  it("treats a 404 for the latest forecast as 'nothing yet', not as a failure", async () => {
    mockApi({ "/api/forecasts/latest": () => json({ detail: "No decision-time forecasts are available" }, 404) });
    render(<DashboardPage />);
    expect(await screen.findByText(/No forecast available yet/i)).toBeInTheDocument();
  });

  it("re-queries the API with the new dates when a preset is chosen", async () => {
    const fetchMock = mockApi();
    render(<DashboardPage />);
    await screen.findByText("812 MW");

    await userEvent.click(screen.getByRole("button", { name: "Last 7 days" }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map(([input]) => String(input));
      expect(urls.some((u) => u.includes("/api/metrics?start=2026-01-26&end=2026-02-01"))).toBe(true);
      expect(urls.some((u) => u.includes("/api/comparison?start=2026-01-26&end=2026-02-01"))).toBe(true);
    });
  });
});
