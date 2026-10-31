"""HTTP layer: thin routes that validate input and delegate to AnalysisService."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Request

from app.schemas import api as schemas
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/api")

APP_VERSION = "1.0.0"


def get_service(request: Request) -> AnalysisService:
    return request.app.state.analysis_service


StartQuery = Query(None, description="First delivery day (YYYY-MM-DD, UK local date). Defaults to window start.")
EndQuery = Query(None, description="Last delivery day (YYYY-MM-DD, UK local date). Defaults to window end.")


@router.get("/health", response_model=schemas.HealthResponse, tags=["system"])
async def health() -> schemas.HealthResponse:
    """Liveness check. Does not call Elexon."""
    return schemas.HealthResponse(status="ok", version=APP_VERSION)


@router.get("/config", response_model=schemas.ConfigResponse, tags=["system"])
async def config(service: AnalysisService = Depends(get_service)) -> schemas.ConfigResponse:
    """The active scope and the decision-time business rule (so the UI can explain it)."""
    settings = service._settings  # noqa: SLF001 - read-only view of configuration
    rule = service.rule
    return schemas.ConfigResponse(
        data_source="Elexon BMRS: FUELHH (actual wind) and WINDFOR (wind forecast)",
        window_start=settings.delivery_window_start,
        window_end=settings.delivery_window_end,
        decision_rule=schemas.DecisionRuleInfo(
            cutoff_time=rule.cutoff_time.strftime("%H:%M"),
            timezone=rule.timezone.key,
            days_ahead=rule.days_ahead,
            description=rule.describe(),
        ),
        mape_min_actual_mw=settings.mape_min_actual_mw,
        forecast_resolution_minutes=settings.forecast_resolution_minutes,
    )


@router.get("/forecasts/latest", response_model=schemas.LatestForecastResponse, tags=["forecasts"])
async def latest_forecast(
    delivery_date: date | None = Query(None, description="Delivery day; defaults to the latest day with a forecast."),
    service: AnalysisService = Depends(get_service),
) -> schemas.LatestForecastResponse:
    """The forecast a buyer would have had at the decision cutoff for one delivery day."""
    latest = await service.latest_forecast(delivery_date)
    forecasts = latest.forecasts
    peak = max(forecasts, key=lambda f: f.generation_mw)
    return schemas.LatestForecastResponse(
        delivery_date=latest.delivery_date,
        decision_cutoff=latest.decision_cutoff,
        latest_publish_time=max(f.publish_time for f in forecasts),
        earliest_publish_time=min(f.publish_time for f in forecasts),
        period_count=len(forecasts),
        mean_mw=sum(f.generation_mw for f in forecasts) / len(forecasts),
        peak_mw=peak.generation_mw,
        peak_time=peak.start_time,
        min_mw=min(f.generation_mw for f in forecasts),
        actual_mean_mw=latest.actual_mean_mw,
        periods=[
            schemas.LatestForecastPeriod(start_time=f.start_time, publish_time=f.publish_time, forecast_mw=f.generation_mw)
            for f in forecasts
        ],
    )


@router.get("/forecasts", response_model=schemas.ForecastsResponse, tags=["forecasts"])
async def forecasts(
    start: date | None = StartQuery, end: date | None = EndQuery, service: AnalysisService = Depends(get_service)
) -> schemas.ForecastsResponse:
    """Decision-time forecast for every forecast period (WINDFOR target) in the range."""
    start, end, records = await service.decision_forecasts(start, end)
    return schemas.ForecastsResponse(
        start=start,
        end=end,
        forecasts=[
            schemas.ForecastPointOut(
                start_time=r.start_time,
                publish_time=r.publish_time,
                forecast_mw=r.generation_mw,
                lead_time_hours=(r.start_time - r.publish_time).total_seconds() / 3600.0,
            )
            for r in records
        ],
    )


@router.get("/actuals", response_model=schemas.ActualsResponse, tags=["actuals"])
async def actuals(
    start: date | None = StartQuery, end: date | None = EndQuery, service: AnalysisService = Depends(get_service)
) -> schemas.ActualsResponse:
    """Actual national wind generation (FUELHH, fuelType WIND) for every 30-minute period in the range."""
    start, end, records = await service.actuals(start, end)
    return schemas.ActualsResponse(
        start=start,
        end=end,
        actuals=[schemas.ActualPointOut(start_time=r.start_time, actual_mw=r.generation_mw) for r in records],
    )


@router.get("/comparison", response_model=schemas.ComparisonResponse, tags=["analysis"])
async def comparison(
    start: date | None = StartQuery, end: date | None = EndQuery, service: AnalysisService = Depends(get_service)
) -> schemas.ComparisonResponse:
    """Decision-time forecast vs actual, with per-period errors, for every exactly matched forecast period."""
    result = await service.comparison(start, end)
    return schemas.ComparisonResponse.model_validate(result)


@router.get("/metrics", response_model=schemas.MetricsResponse, tags=["analysis"])
async def metrics(
    start: date | None = StartQuery, end: date | None = EndQuery, service: AnalysisService = Depends(get_service)
) -> schemas.MetricsResponse:
    """MAE, RMSE, bias, MAPE and more, overall and per delivery day."""
    result = await service.metrics(start, end)
    return schemas.MetricsResponse.model_validate(result)
