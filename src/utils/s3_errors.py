from botocore.exceptions import BotoCoreError, ClientError

from utils.external_errors import ExternalError


def localizable_s3_error(exc: BaseException) -> ExternalError:
    """Extract AWS's error code without exposing provider messages."""
    if isinstance(exc, ClientError):
        error = exc.response.get("Error", {})
        code = str(error.get("Code", "ClientError"))
    elif isinstance(exc, BotoCoreError):
        code = type(exc).__name__
    else:
        code = type(exc).__name__
    return ExternalError("s3", code, type(exc).__name__, f"s3.{code}")
