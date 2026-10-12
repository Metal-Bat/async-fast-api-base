"""Owned restore evidence must close each read-only sandbox connection."""

import sqlite3
from contextlib import closing
from typing import override

from tests.integration.test_restore_protected_fixture import order_count


def test_order_count_closes_each_read_only_connection(tmp_path, monkeypatch):
    database = tmp_path / "order-sandbox.sqlite3"
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO orders DEFAULT VALUES")
    monkeypatch.setenv("ORDER_SANDBOX_FAULT_FILE", str(tmp_path / "fault.txt"))
    original = sqlite3.connect
    opened = []
    closed = []

    class TrackedConnection(sqlite3.Connection):
        @override
        def close(self):
            closed.append(self)
            super().close()

    def connect(*args, **kwargs):
        connection = original(*args, factory=TrackedConnection, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", connect)
    try:
        assert [order_count() for _ in range(4)] == [1, 1, 1, 1]
        assert closed == opened
    finally:
        for connection in opened:
            if connection not in closed:
                connection.close()
