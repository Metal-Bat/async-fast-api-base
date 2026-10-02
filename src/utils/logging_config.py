import logging
import logging.config

import structlog

from core.settings import settings


def setup_logging(log_level: int | str | None = None) -> None:
    """Configure standard logging and structlog for the current environment."""
    effective_level = settings.LOG_LEVEL if log_level is None else log_level
    configured_handlers = [
        handler
        for output, handler in (("console", "console"), ("file", "json_file"))
        if output in settings.LOG_OUTPUTS
    ]
    handler_definitions = {
        "console": {
            "level": effective_level,
            "class": "logging.StreamHandler",
            "formatter": "plain_console",
        },
        "json_file": {
            "level": effective_level,
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": settings.LOG_FILE,
            "when": "midnight",
            "backupCount": 30,
            "formatter": "json_formatter",
            "encoding": "utf-8",
            "utc": True,
        },
    }
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "sql_console": {"()": "utils.sql_logging.SQLConsoleFormatter"},
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
        "handlers": {name: handler_definitions[name] for name in configured_handlers},
        "loggers": {
            "sqlalchemy.engine.Engine": {
                "handlers": configured_handlers,
                "level": effective_level,
                "propagate": False,
            },
            "json_logger": {
                "handlers": configured_handlers,
                "level": effective_level,
                "propagate": False,
            },
        },
        "root": {"handlers": configured_handlers, "level": effective_level},
    }

    if settings.SQL_PRETTY_LOGS and "console" in settings.LOG_OUTPUTS:
        LOGGING["handlers"]["sql_console"] = {
            "class": "logging.StreamHandler",
            "level": effective_level,
            "formatter": "sql_console",
        }
        LOGGING["loggers"]["sqlalchemy.engine.Engine"] = {
            "handlers": [
                "sql_console" if name == "console" else name for name in configured_handlers
            ],
            "level": effective_level,
            "propagate": False,
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
        wrapper_class=structlog.make_filtering_bound_logger(effective_level),
        cache_logger_on_first_use=True,
    )
