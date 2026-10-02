import os
from uuid import uuid7

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormDocuments, FormVersionCreateDTO
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.exceptions import VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_form_publish_is_immutable_and_pins_exact_documents() -> None:
    async with SessionFactory() as session:
        user = UserEntity(username=f"form-{uuid7().hex}", hashed_password="hash")
        session.add(user)
        await session.flush()
        service = FormService(session)
        form = await service.create(FormCreateDTO(code=f"F{uuid7().hex}", name="Form"), user.id)
        doc = FormDocuments(
            data_schema={"type": "object", "properties": {}},
            render_schema={"root": {"component": "vertical"}},
        )
        version = await service.create_version(
            FormVersionCreateDTO(
                **doc.model_dump(), form_ref_id=create_ref_id(form.id, form.version), number=1
            )
        )
        ref = create_ref_id(version.id, version.version)
        await service.update_version(ref, doc)
        with pytest.raises(VersionConflictException):
            await service.publish(ref, user.id)
        published = await service.publish(create_ref_id(version.id, version.version), user.id)
        assert published.checksum is not None
        assert len(published.checksum) == 64
        assert published.published_by_user_id == user.id
        ref = create_ref_id(published.id, published.version)
        assert (await service.get_version(ref)).data_schema == doc.data_schema
        with pytest.raises(VersionConflictException):
            await service.update_version(ref, doc)
        await service.retire(ref)
        assert (await service.get_version(ref)).status == "RETIRED"
        await session.commit()
        version_id = published.id
    async with SessionFactory() as session:
        with pytest.raises(DBAPIError, match="immutable"):
            await (await session.connection()).execute(
                text('UPDATE "FORM_VERSION" SET "DATA_SCHEMA" = \'{}\' WHERE "ID" = :id'),
                {"id": version_id},
            )
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_form_publication_has_one_winner() -> None:
    from anyio import create_task_group

    async with SessionFactory() as session:
        actor = UserEntity(username=f"form-race-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        service = FormService(session)
        root = await service.create(
            FormCreateDTO(code=f"F{uuid7().hex}", name="Concurrent"), actor.id
        )
        draft = await service.create_version(
            FormVersionCreateDTO(
                form_ref_id=create_ref_id(root.id, root.version),
                number=1,
                data_schema={"type": "object"},
                render_schema={"root": {"component": "vertical"}},
            )
        )
        ref, actor_id = create_ref_id(draft.id, draft.version), actor.id
        await session.commit()

    results = []

    async def publish() -> None:
        async with SessionFactory() as session:
            try:
                await FormService(session).publish(ref, actor_id)
                await session.commit()
                results.append("published")
            except VersionConflictException:
                await session.rollback()
                results.append("conflict")

    async with create_task_group() as tasks:
        tasks.start_soon(publish)
        tasks.start_soon(publish)
    assert sorted(results) == ["conflict", "published"]
    await engine.dispose()


@pytest.mark.anyio
async def test_published_form_variants_are_persisted_and_database_immutable() -> None:
    from apps.clients.application.service import ClientService
    from apps.clients.domain.contracts import ClientContext
    from apps.clients.domain.dto import ClientCreateDTO
    from apps.forms.application.designs import resolve_form_documents
    from apps.forms.domain.dto import FormDesignVariantDTO

    async with SessionFactory() as session:
        actor = UserEntity(username=f"form-variant-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        client, _ = await ClientService(session).create_client(
            ClientCreateDTO(
                code=f"DESKTOP_{uuid7().hex}",
                name="Desktop",
                kind="DESKTOP",
                platform="linux",
                confidential=True,
            )
        )
        service = FormService(session)
        root = await service.create(
            FormCreateDTO(code=f"F{uuid7().hex}", name="Variants"), actor.id
        )
        documents = FormVersionCreateDTO(
            form_ref_id=create_ref_id(root.id, root.version),
            number=1,
            data_schema={"type": "object", "properties": {}},
            render_schema={"root": {"component": "vertical"}},
            page_settings={"toolbar": {"color": "black"}},
            variants=[
                FormDesignVariantDTO(
                    key="desktop",
                    priority=10,
                    client_ref_id=create_ref_id(client.id, client.version),
                    condition='version_in_range(client.release, "2.10", null)',
                    render_schema={"root": {"component": "grid"}},
                    page_settings={"toolbar": {"color": "blue"}},
                )
            ],
        )
        draft = await service.create_version(documents)
        published = await service.publish(create_ref_id(draft.id, draft.version), actor.id)
        selected = resolve_form_documents(
            FormDocuments.model_validate(published, from_attributes=True),
            ClientContext(client_id=client.id, kind="DESKTOP", release="2.10"),
        )
        assert (
            published.variants[0]["condition"] == 'version_in_range(client.release, "2.10", null)'
        )
        assert selected.key == "desktop"
        assert selected.page_settings == {
            "toolbar": {"color": "blue"},
            "schema_version": "bpms.page/1",
        }
        await session.commit()
        version_id = published.id
    async with SessionFactory() as session:
        with pytest.raises(DBAPIError, match="immutable"):
            await (await session.connection()).execute(
                text('UPDATE "FORM_VERSION" SET "VARIANTS" = \'[]\'::jsonb WHERE "ID" = :id'),
                {"id": version_id},
            )
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_localization_draft_publish_history_and_historical_reads() -> None:
    from copy import deepcopy

    from apps.clients.domain.contracts import ClientContext
    from apps.forms.application.designs import resolve_form_documents
    from apps.forms.application.validation import FormValidator
    from apps.forms.domain.entity import FormVersionEntity
    from tests.apps.forms.test_localization import catalog_documents
    from utils.exceptions import ValidationDetailsException

    async with SessionFactory() as session:
        actor = UserEntity(username=f"catalog-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        service = FormService(session)
        root = await service.create(FormCreateDTO(code=f"C{uuid7().hex}", name="Catalog"), actor.id)
        payload = catalog_documents()
        translation = payload["localization"]["catalogs"].pop("fa")
        draft = await service.create_version(
            FormVersionCreateDTO(
                **payload, form_ref_id=create_ref_id(root.id, root.version), number=1
            )
        )
        with pytest.raises(ValidationDetailsException):
            await service.publish(create_ref_id(draft.id, draft.version), actor.id)
        assert draft.status == "DRAFT"
        payload["localization"]["catalogs"]["fa"] = translation
        draft = await service.update_version(
            create_ref_id(draft.id, draft.version), FormDocuments.model_validate(payload)
        )
        first = await service.publish(create_ref_id(draft.id, draft.version), actor.id)
        first_id, first_checksum = first.id, first.checksum
        old_catalog = deepcopy(first.localization)
        payload["localization"]["catalogs"]["en"]["email"]["text"] = "Work email"
        payload["localization"]["catalogs"]["fa"]["email"]["text"] = "ایمیل کاری"
        revision = (
            FormValidator()
            .validate(FormDocuments.model_validate(payload))
            .source_revisions["email"]
        )
        payload["localization"]["catalogs"]["fa"]["email"]["source_revision"] = revision
        second = await service.create_version(
            FormVersionCreateDTO(
                **payload, form_ref_id=create_ref_id(root.id, root.version), number=2
            )
        )
        await service.publish(create_ref_id(second.id, second.version), actor.id)
        assert second.checksum != first_checksum
        await session.commit()
    async with SessionFactory() as session:
        first = await session.get(FormVersionEntity, first_id)
        assert (
            first is not None
            and first.localization == old_catalog
            and first.checksum == first_checksum
        )
        result = resolve_form_documents(
            FormDocuments.model_validate(first, from_attributes=True),
            ClientContext.legacy(),
            locale="fa",
        )
        assert result.render_schema["root"]["label"] == "ایمیل"
        history = (
            await (await session.connection()).execute(
                text(
                    'SELECT "FROM_LOCALIZATION", "TO_LOCALIZATION" FROM "FORM_VERSION_HISTORY" WHERE "ENTITY_ID" = :id'
                ),
                {"id": first_id},
            )
        ).all()
        assert any(
            before is not None and "fa" not in before["catalogs"] and after == old_catalog
            for before, after in history
        )
        with pytest.raises(DBAPIError, match="immutable"):
            await (await session.connection()).execute(
                text('UPDATE "FORM_VERSION" SET "LOCALIZATION" = :catalog WHERE "ID" = :id'),
                {"id": first_id, "catalog": "{}"},
            )
        await session.rollback()
    await engine.dispose()
