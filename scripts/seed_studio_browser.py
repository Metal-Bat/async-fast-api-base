"""Seed an ordinary studio author in disposable infrastructure; never log credentials."""

import asyncio
import json
import os
from pathlib import Path
from uuid import uuid7


async def main():
    import tests.conftest  # noqa: F401
    from sqlmodel import select
    from tests.integration.test_studio_workspace import seed_studio

    from apps.clients.application.service import ClientService
    from apps.clients.domain.dto import ClientCreateDTO, ClientReleaseCreateDTO
    from apps.forms.application.service import FormService
    from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO
    from apps.requests.application.service import RequestService
    from apps.requests.domain.dto import RequestTypeClientTargetDTO, RequestTypeCreateDTO
    from apps.users.domain.entity import UserEntity
    from core.deps import SessionFactory, engine
    from core.ref_id import create_ref_id

    fixture = await seed_studio()
    async with SessionFactory() as session:
        author = (
            await session.exec(select(UserEntity).where(UserEntity.username == fixture["username"]))
        ).one()
        forms = FormService(session)
        form = await forms.create(
            FormCreateDTO(code="BROWSER" + uuid7().hex, name="Browser author form"), author.id
        )
        version = await forms.create_version(
            FormVersionCreateDTO(
                form_ref_id=create_ref_id(form.id, form.version),
                number=1,
                data_schema={"type": "object", "properties": {}},
                render_schema={"root": {"component": "vertical", "children": []}},
            )
        )
        clients = ClientService(session)
        client, _secret = await clients.create_client(
            ClientCreateDTO(
                code="CLIENT" + uuid7().hex,
                name="Restricted studio client",
                kind="WEB",
                platform="test",
                confidential=True,
            )
        )
        client_ref = create_ref_id(client.id, client.version)
        release = await clients.create_release(
            client.id, ClientReleaseCreateDTO(version="1.0", api_version="v1")
        )
        request_type = await RequestService(session).create_type(
            RequestTypeCreateDTO(
                code="TYPE" + uuid7().hex,
                name="Restricted studio request",
                workflow_ref_id=fixture["workflow_ref"],
                form_ref_id=create_ref_id(form.id, form.version),
                client_targets=[
                    RequestTypeClientTargetDTO(
                        client_ref_id=client_ref,
                        minimum_release="1.0",
                        maximum_release_exclusive="2.0",
                    )
                ],
            )
        )
        fixture["client_ref"] = client_ref
        fixture["release_ref"] = create_ref_id(release.id, release.version)
        fixture["request_type_ref"] = create_ref_id(request_type.id, request_type.version)
        await session.commit()
        fixture["form_ref"] = create_ref_id(version.id, version.version)
    destination = Path(os.getenv("BROWSER_ACCOUNTS_FILE", "/tmp/studio-browser-accounts.json"))
    destination.write_text(json.dumps(fixture))
    destination.chmod(0o600)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
