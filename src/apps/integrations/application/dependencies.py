"""Construct the existing connection owner without resolving any credential."""

from sqlmodel.ext.asyncio.session import AsyncSession

from apps.integrations.application.providers import StatusProvider
from apps.integrations.application.service import ConnectionService
from apps.integrations.data.secrets import EncryptedFileSecrets
from core.settings import settings


def connection_service(session: AsyncSession) -> ConnectionService:
    secrets = EncryptedFileSecrets(
        settings.INTEGRATION_SECRETS_DIR,
        [key.get_secret_value().encode() for key in settings.INTEGRATION_SECRET_KEYS],
    )
    return ConnectionService(session, StatusProvider(secrets, settings.INTEGRATION_HTTP_ENDPOINTS))
