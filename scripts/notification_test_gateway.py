"""Owned loopback HTTPS email gateway with real TLS and idempotent receipt capture."""

import ipaddress
import json
import os
import secrets
import ssl
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


@contextmanager
def notification_gateway(directory: Path, environment: dict[str, str]) -> Iterator[dict[str, str]]:
    """Keep credentials/certificates private and close only the owned ephemeral server."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Owned notification test")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    ca, private = directory / "gateway-ca.pem", directory / "gateway-key.pem"
    ca.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    private.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    os.chmod(ca, 0o600)
    os.chmod(private, 0o600)
    credential = secrets.token_urlsafe(32)
    receipts: dict[str, dict[str, str]] = {}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_POST(self):
            if self.path != "/email" or self.headers.get("Authorization") != "Bearer " + credential:
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 32768:
                self.send_error(413)
                return
            payload = json.loads(self.rfile.read(length))
            identity = self.headers.get("Idempotency-Key")
            if (
                identity is None
                or len(identity) > 128
                or set(payload) != {"channel", "destination", "subject", "content"}
            ):
                self.send_error(422)
                return
            with lock:
                if identity in receipts and receipts[identity] != payload:
                    self.send_error(409)
                    return
                receipts[identity] = payload
            self.send_response(200)
            self.send_header("X-Message-ID", identity)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            if (
                self.path != "/receipts"
                or self.headers.get("Authorization") != "Bearer " + credential
            ):
                self.send_error(403)
                return
            with lock:
                result = json.dumps(receipts).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            self.wfile.write(result)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(ca, private)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    provisioned = directory / "notification-secrets"
    provisioned.mkdir(mode=0o700)
    encryption = Fernet.generate_key()
    secret_file = provisioned / "owned-email.1.enc"
    secret_file.write_bytes(
        Fernet(encryption).encrypt(
            json.dumps({"connection": "owned-email", "version": "1", "token": credential}).encode()
        )
    )
    os.chmod(secret_file, 0o600)
    configured = environment | {
        "INTEGRATION_TLS_CA_FILE": str(ca),
        "INTEGRATION_SECRETS_DIR": str(provisioned),
        "INTEGRATION_SECRET_KEYS": json.dumps([encryption.decode()]),
        "INTEGRATION_HTTP_ENDPOINTS": json.dumps(
            {"owned_email": f"https://127.0.0.1:{server.server_port}/email"}
        ),
        "RUN_NOTIFICATION_WORKER": "1",
        "NOTIFICATION_TEST_RECEIPTS": f"https://127.0.0.1:{server.server_port}/receipts",
        "NOTIFICATION_TEST_BEARER": credential,
    }
    try:
        yield configured
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
