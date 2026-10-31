import logging


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    # httpx logs every request at INFO; keep our own logs readable.
    logging.getLogger("httpx").setLevel(logging.WARNING)
