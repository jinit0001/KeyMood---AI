"""
Structured (JSON) logging, per DEPLOYMENT.md §4: logs are shipped to a log
aggregator and correlated by request ID across a request's lifecycle.
"""
import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        # Include any extra= fields attached to the record.
        reserved = set(vars(logging.LogRecord("", 0, "", 0, "", (), None)))
        for key, value in vars(record).items():
            if key not in reserved and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Keep noisy third-party loggers at a sane level.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
