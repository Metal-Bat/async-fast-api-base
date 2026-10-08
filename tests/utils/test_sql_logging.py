"""Tests for safe and readable SQL logging."""

import logging
from io import StringIO

from sqlalchemy import literal
from sqlmodel import Session, create_engine, select

from utils.sql_logging import SQLConsoleFormatter


def test_sql_is_indented_without_changing_literals_or_parameters() -> None:
    statement = "SELECT id, name FROM users WHERE name = $1 AND note = 'select from'"
    record = logging.LogRecord("sqlalchemy.engine.Engine", logging.INFO, "", 0, statement, (), None)
    output = SQLConsoleFormatter(colors=False).format(record)
    assert "SQL · SELECT" in output
    assert "SELECT" in output
    assert "FROM users" in output
    assert "$1" in output and "'select from'" in output
    assert record.msg == statement
    assert "\x1b[" not in output


def test_parameter_logs_are_not_parsed_as_sql() -> None:
    record = logging.LogRecord(
        "sqlalchemy.engine.Engine", logging.INFO, "", 0, "[cached] %r", (("name", 5),), None
    )
    output = SQLConsoleFormatter(colors=False).format(record)
    assert "SQL parameters" in output
    assert "[cached] ('name', 5)" in output


def test_terminal_output_has_syntax_colors_and_preserves_record() -> None:
    record = logging.LogRecord(
        "sqlalchemy.engine.Engine", logging.INFO, "", 0, "SELECT $1", (), None
    )
    assert "\x1b[" in SQLConsoleFormatter(colors=True).format(record)
    assert logging.Formatter().format(record) == "SELECT $1"


def test_transaction_is_compact_and_query_text_is_not_rich_markup() -> None:
    formatter = SQLConsoleFormatter(colors=False)
    record = logging.LogRecord("sqlalchemy.engine.Engine", logging.INFO, "", 0, "COMMIT", (), None)
    assert formatter.format(record) == "SQL transaction  COMMIT"
    record.msg = "SELECT '[bold]literal[/bold]'"
    assert "[bold]literal[/bold]" in formatter.format(record)


def test_real_sqlmodel_query_uses_panel_and_keeps_parameters_bound(monkeypatch) -> None:
    engine = create_engine("sqlite://", echo=True)
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(SQLConsoleFormatter(colors=False))
    logger = logging.getLogger("sqlalchemy.engine.Engine")
    monkeypatch.setattr(logger, "handlers", [handler])
    monkeypatch.setattr(logger, "propagate", False)
    try:
        with Session(engine) as session:
            assert session.exec(select(literal(7))).one() == 7
        log = output.getvalue()
        assert log.count("SQL · SELECT") == 1
        assert "SQL parameters" in log
        assert "SQL transaction" in log
    finally:
        engine.dispose()
