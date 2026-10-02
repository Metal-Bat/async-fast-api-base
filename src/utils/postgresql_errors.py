from dataclasses import dataclass

from asyncpg import exceptions as asyncpg_exceptions
from sqlalchemy.exc import SQLAlchemyError


@dataclass(frozen=True, slots=True)
class PostgreSQLError:
    """Normalized database error details suitable for an i18n message catalog."""

    sqlstate: str
    name: str
    message_key: str


def _error_catalog() -> dict[str, PostgreSQLError]:
    """Build the SQLSTATE lookup from asyncpg's exception hierarchy."""
    catalog: dict[str, PostgreSQLError] = {}
    for name in dir(asyncpg_exceptions):
        error_type = getattr(asyncpg_exceptions, name)
        if not isinstance(error_type, type):
            continue
        sqlstate = getattr(error_type, "sqlstate", None)
        if isinstance(sqlstate, str):
            catalog[sqlstate] = PostgreSQLError(
                sqlstate=sqlstate,
                name=name,
                message_key=f"postgresql.{sqlstate}",
            )
    return catalog


# asyncpg generates its exception hierarchy from PostgreSQL's complete SQLSTATE catalog.
POSTGRESQL_ERRORS = _error_catalog()


def _driver_error(exc: BaseException) -> BaseException:
    """Unwrap SQLAlchemy's driver exception without parsing its message."""
    if isinstance(exc, SQLAlchemyError):
        original = getattr(exc, "orig", None)
        if isinstance(original, BaseException):
            return original
    return exc


def postgresql_sqlstate(exc: BaseException) -> str | None:
    """Read a SQLSTATE from a direct or SQLAlchemy-wrapped driver error."""
    driver_error = _driver_error(exc)
    for source in (driver_error, driver_error.__cause__):
        if source is None:
            continue
        sqlstate = getattr(source, "sqlstate", None) or getattr(source, "pgcode", None)
        if isinstance(sqlstate, str) and len(sqlstate) == 5:
            return sqlstate
    return None


def postgresql_constraint_name(exc: BaseException) -> str | None:
    """Read a driver constraint name for an internal allowlist check."""
    driver_error = _driver_error(exc)
    for source in (driver_error, driver_error.__cause__):
        if source is None:
            continue
        name = getattr(source, "constraint_name", None)
        if isinstance(name, str):
            return name
    return None


def localizable_postgresql_error(exc: BaseException) -> PostgreSQLError:
    """Return a stable localization key, including for future unknown SQLSTATE values."""
    sqlstate = postgresql_sqlstate(exc) or "unknown"
    return POSTGRESQL_ERRORS.get(
        sqlstate,
        PostgreSQLError(
            sqlstate=sqlstate,
            name=type(_driver_error(exc)).__name__,
            message_key=f"postgresql.{sqlstate}",
        ),
    )
