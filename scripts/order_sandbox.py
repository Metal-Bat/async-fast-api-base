"""Explicit local HTTP order sandbox; receipts persist in an owned SQLite file.

This is a disposable demo service, not a vendor adapter or a production purchase.
Faults are controlled by an owned local file and have no HTTP control endpoint.
"""

import hmac
import json
import os
import secrets
import socket
import sqlite3
import ssl
import threading
import time
from collections.abc import Generator
from contextlib import closing, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import override
from uuid import UUID, uuid7

from cryptography.fernet import Fernet
from pydantic import ValidationError

from apps.integrations.domain.orders import (
    SandboxCancellationReceipt,
    SandboxOrderPayload,
    SandboxOrderReceipt,
    payload_hash,
)

SANDBOX_CONNECTION_CODE = "owned-order"


@contextmanager
def order_sandbox(directory: Path, environment: dict[str, str]) -> Generator[dict[str, str]]:
    """Reuse the owned TLS/secret provisioning while running a separate HTTPS service."""
    database = directory / "order-sandbox.sqlite3"
    fault_path = directory / "order-sandbox-fault"
    credential = secrets.token_urlsafe(32)
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS orders (identity TEXT PRIMARY KEY, receipt TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS cancellations (identity TEXT PRIMARY KEY, order_identity TEXT NOT NULL UNIQUE, receipt TEXT NOT NULL)"
        )
    os.chmod(database, 0o600)
    fault_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        @override
        def log_message(self, format, *args):
            return

        @override
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def _authorized(self):
            if not hmac.compare_digest(
                self.headers.get("Authorization", ""), "Bearer " + credential
            ):
                self.send_error(403)
                return False
            return True

        def _response(self, receipt: str):
            body = receipt.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _fault(self):
            with fault_lock:
                fault = fault_path.read_text().strip() if fault_path.exists() else ""
                fault_path.unlink(missing_ok=True)
            return fault

        def _effect_response(self, receipt: str, fault: str):
            if fault == "lose_reply":
                self.close_connection = True
                self.connection.shutdown(socket.SHUT_RDWR)
                return
            if fault == "delay_reply":
                time.sleep(2)
            self._response(receipt)

        def do_HEAD(self):
            if not self._authorized():
                return
            self.send_response(200 if self.path == "/orders" else 404)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            if not self._authorized():
                return
            try:
                if not self.path.startswith("/orders/"):
                    raise ValueError
                cancellation = self.path.endswith("/cancellation")
                target = self.path.removeprefix("/orders/")
                identity = str(
                    UUID(target.removesuffix("/cancellation") if cancellation else target)
                )
            except ValueError:
                self.send_error(404)
                return
            with closing(sqlite3.connect(database, timeout=2)) as connection, connection:
                query = (
                    "SELECT receipt FROM cancellations WHERE order_identity = ?"
                    if cancellation
                    else "SELECT receipt FROM orders WHERE identity = ?"
                )
                row = connection.execute(query, (identity,)).fetchone()
            if row is None:
                self.send_error(404)
                return
            self._response(row[0])

        def _cancel(self):
            try:
                order_id = UUID(self.path.removeprefix("/orders/").removesuffix("/cancel"))
                identity = UUID(self.headers.get("Idempotency-Key", ""))
                if (
                    self.headers.get("Transfer-Encoding") is not None
                    or int(self.headers.get("Content-Length", "0")) != 0
                ):
                    raise ValueError
            except ValueError:
                self.send_error(422)
                return
            fault = self._fault()
            if fault == "reject_before_effect":
                self.send_error(503)
                return
            with closing(sqlite3.connect(database, timeout=2)) as connection, connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT receipt FROM orders WHERE identity = ?", (str(order_id),)
                ).fetchone()
                if row is None:
                    self.send_error(404)
                    return
                existing = connection.execute(
                    "SELECT receipt FROM cancellations WHERE identity = ? OR order_identity = ?",
                    (str(identity), str(order_id)),
                ).fetchone()
                if existing is not None:
                    cancellation = SandboxCancellationReceipt.model_validate_json(existing[0])
                    if (
                        cancellation.operation_id != identity
                        or cancellation.order_operation_id != order_id
                    ):
                        self.send_error(409)
                        return
                    body = existing[0]
                else:
                    original = SandboxOrderReceipt.model_validate_json(row[0])
                    body = SandboxCancellationReceipt(
                        operation_id=identity,
                        order_operation_id=order_id,
                        receipt_id=uuid7(),
                        state="CANCELLED",
                        payload_hash=original.payload_hash,
                    ).model_dump_json()
                    connection.execute(
                        "INSERT INTO cancellations (identity, order_identity, receipt) VALUES (?, ?, ?)",
                        (str(identity), str(order_id), body),
                    )
                    original.state = "CANCELLED"
                    connection.execute(
                        "UPDATE orders SET receipt = ? WHERE identity = ?",
                        (original.model_dump_json(), str(order_id)),
                    )
            self._effect_response(body, fault)

        def do_POST(self):
            if not self._authorized():
                return
            if self.path.startswith("/orders/") and self.path.endswith("/cancel"):
                self._cancel()
                return
            if self.path != "/orders":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if self.headers.get("Transfer-Encoding") is not None or not 0 < length <= 8192:
                    self.send_error(413)
                    return
                identity = UUID(self.headers.get("Idempotency-Key", ""))
                payload = SandboxOrderPayload.model_validate_json(self.rfile.read(length))
            except ValueError, ValidationError, TimeoutError:
                self.send_error(422)
                return
            fault = self._fault()
            if fault == "reject_before_effect":
                self.send_error(503)
                return
            digest = payload_hash(payload.model_dump(mode="json"))
            with closing(sqlite3.connect(database, timeout=2)) as connection, connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT receipt FROM orders WHERE identity = ?", (str(identity),)
                ).fetchone()
                if row is not None:
                    if SandboxOrderReceipt.model_validate_json(row[0]).payload_hash != digest:
                        self.send_error(409)
                        return
                    receipt = row[0]
                else:
                    receipt = SandboxOrderReceipt(
                        operation_id=identity,
                        receipt_id=uuid7(),
                        state="CREATED",
                        payload_hash=digest,
                    ).model_dump_json()
                    connection.execute(
                        "INSERT INTO orders (identity, receipt) VALUES (?, ?)",
                        (str(identity), receipt),
                    )
            self._effect_response(receipt, fault)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(directory / "gateway-ca.pem", directory / "gateway-key.pem")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    provisioned = Path(environment["INTEGRATION_SECRETS_DIR"])
    encryption = json.loads(environment["INTEGRATION_SECRET_KEYS"])[0].encode()
    secret_file = provisioned / f"{SANDBOX_CONNECTION_CODE}.1.enc"
    secret_file.write_bytes(
        Fernet(encryption).encrypt(
            json.dumps(
                {"connection": SANDBOX_CONNECTION_CODE, "version": "1", "token": credential}
            ).encode()
        )
    )
    os.chmod(secret_file, 0o600)
    endpoint = f"https://127.0.0.1:{server.server_port}/orders"
    endpoints = json.loads(environment["INTEGRATION_HTTP_ENDPOINTS"]) | {"owned_orders": endpoint}
    configured = environment | {
        "INTEGRATION_HTTP_ENDPOINTS": json.dumps(endpoints),
        "RUN_SANDBOX_WORKER": "1",
        "ORDER_SANDBOX_TEST_BEARER": credential,
        "ORDER_SANDBOX_FAULT_FILE": str(fault_path),
    }
    thread.start()
    try:
        yield configured
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
