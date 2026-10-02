"""Tests for localizable application error catalogs."""

from botocore.exceptions import ClientError, ConnectTimeoutError
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.exc import IntegrityError

from utils.broker_errors import localizable_broker_error
from utils.cache_errors import localizable_cache_error
from utils.postgresql_errors import POSTGRESQL_ERRORS, localizable_postgresql_error
from utils.s3_errors import localizable_s3_error


def test_postgresql_errors_are_localizable() -> None:
    assert POSTGRESQL_ERRORS["23505"].message_key == "postgresql.23505"
    unknown = type("FutureDatabaseError", (Exception,), {"sqlstate": "XX999"})()
    assert localizable_postgresql_error(unknown).message_key == "postgresql.XX999"
    wrapped = IntegrityError("query", None, unknown)
    assert localizable_postgresql_error(wrapped).message_key == "postgresql.XX999"


def test_external_error_catalogs_cover_known_and_unknown_errors() -> None:
    assert localizable_cache_error(RedisConnectionError()).message_key == "cache.ConnectionError"
    assert localizable_cache_error(RuntimeError()).message_key == "cache.RuntimeError"
    assert localizable_broker_error(RuntimeError()).message_key == "broker.RuntimeError"

    client_error = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
    assert localizable_s3_error(client_error).message_key == "s3.NoSuchKey"
    timeout = ConnectTimeoutError(endpoint_url="http://minio")
    assert localizable_s3_error(timeout).message_key == "s3.ConnectTimeoutError"
    assert localizable_s3_error(RuntimeError()).message_key == "s3.RuntimeError"
