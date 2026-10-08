"""Seed fresh disposable accounts without printing credentials."""

import asyncio
import json
import os
from pathlib import Path


async def main():
    import tests.conftest  # noqa: F401 -- initialize the disposable test environment
    from tests.integration.test_frontend_journey import _prepare_journey

    from core.deps import engine

    users, password, request_type = await _prepare_journey()
    destination = Path(os.getenv("BROWSER_ACCOUNTS_FILE", "/tmp/frontend-steps-accounts.json"))
    destination.write_text(
        json.dumps({"users": users, "password": password, "request_type": request_type})
    )
    destination.chmod(0o600)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
