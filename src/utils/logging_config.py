import logging
import logging.config

import structlog

from core.settings import settings


def setup_logging() -> None:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json_formatter": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.processors.JSONRenderer(),
                "foreign_pre_chain": [
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.stdlib.add_log_level,
                    structlog.stdlib.add_logger_name,
                ],
            },
            "plain_console": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.dev.ConsoleRenderer(),
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "plain_console",
            },
            "json_file": {
                "level": "INFO",
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": settings.LOG_FILE,
                "when": "midnight",
                "backupCount": 30,
                "formatter": "json_formatter",
                "encoding": "utf-8",
                "utc": True,
            },
        },
        "loggers": {
            "json_logger": {
                "handlers": ["json_file"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }

    if settings.ENVIRONMENT == settings.LOCAL_ENVIRONMENT:
        LOGGING["loggers"] = {
            "json_logger": {
                "handlers": ["json_file", "console"],
                "level": "DEBUG",
            },
        }

    logging.config.dictConfig(LOGGING)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
