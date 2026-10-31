"""Domain-specific exceptions. API handlers translate these into HTTP responses."""


class ElexonError(Exception):
    """Base class for problems talking to the Elexon API."""


class ElexonUpstreamError(ElexonError):
    """Elexon was unreachable or kept returning errors after all retries."""


class ElexonResponseError(ElexonError):
    """Elexon answered, but the payload was not in the expected shape."""


class InvalidDateRangeError(ValueError):
    """The requested date range is invalid or outside the supported scope."""


class NoDataError(LookupError):
    """There is no data for the request (for example no forecast for a delivery day)."""
