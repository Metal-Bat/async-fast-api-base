import logging
import sys
from typing import override

import sqlparse
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text


class SQLConsoleFormatter(logging.Formatter):
    """Highlight SQL in panels and label parameters without modifying log records."""

    def __init__(self, *, colors: bool | None = None) -> None:
        """Detect terminal color support unless explicitly overridden."""
        super().__init__()
        self.console = Console(
            file=sys.stderr,
            force_terminal=colors,
            color_system="standard" if colors is True else "auto",
            no_color=False if colors is True else None,
            width=100,
        )

    @override
    def format(self, record: logging.LogRecord) -> str:
        """Render queries, parameters, and transactions as distinct console entries."""
        message = record.getMessage()
        first_word = message.lstrip().split(None, 1)[0].upper() if message.strip() else ""
        if first_word in {
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "WITH",
            "CREATE",
            "ALTER",
            "DROP",
            "SHOW",
            "EXPLAIN",
        }:
            statement = sqlparse.format(message, reindent=True, keyword_case="upper")
            rendered = Panel(
                Syntax(
                    statement,
                    "postgresql",
                    theme="ansi_dark",
                    word_wrap=True,
                    background_color="default",
                ),
                title=Text(f"SQL · {first_word}", style="bold cyan"),
                subtitle=Text(self.formatTime(record, "%H:%M:%S"), style="dim"),
                border_style="cyan",
                expand=False,
            )
        else:
            label = "SQL parameters" if message.startswith("[") else "SQL transaction"
            rendered = Text.assemble((f"{label}  ", "bold dim"), (message, "dim"))
        with self.console.capture() as capture:
            self.console.print(rendered)
        return capture.get().rstrip("\n")
