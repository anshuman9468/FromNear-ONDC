import logging
import logging.config
import json
from contextvars import ContextVar
from typing import Any

# Global context variable for tracking correlation ID across async tasks
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_ctx.get() or "N/A"
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "correlation_id": getattr(record, "correlation_id", "N/A"),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if they exist in record.__dict__ and are not standard
        extra_fields = {
            k: v
            for k, v in record.__dict__.items()
            if k not in {
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "module", "msecs",
                "message", "msg", "name", "pathname", "process", "processName",
                "relativeCreated", "stack_info", "thread", "threadName", "correlation_id"
            }
        }
        if extra_fields:
            log_record["extra"] = extra_fields
        return json.dumps(log_record)


def setup_logging(use_json: bool = False) -> None:
    log_format = "[%(asctime)s] [%(correlation_id)s] %(levelname)s in %(name)s: %(message)s"
    
    formatter_class = (
        "app.core.logging.JSONFormatter"
        if use_json
        else "logging.Formatter"
    )

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "correlation_id": {
                "()": "app.core.logging.CorrelationIDFilter"
            }
        },
        "formatters": {
            "default": {
                "()": formatter_class,
                "format": log_format,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "filters": ["correlation_id"],
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["console"],
        },
        "loggers": {
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(logging_config)
