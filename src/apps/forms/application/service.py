"""Form authoring lifecycle; callers authorize and commit the transaction."""

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from apps.clients.domain.entity import ClientEntity
from apps.forms.application.library import LibraryService
from apps.forms.application.validation import FormValidator
from apps.forms.domain.dto import FormCreateDTO, FormDocuments, FormVersionCreateDTO
from apps.forms.domain.entity import FormDefinitionEntity, FormVersionEntity
from apps.users.domain.entity import UserEntity
from core.ref_id import open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, ValidationDetailsException, VersionConflictException


class FormService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.validator = FormValidator()

    async def get(self, ref_id: str, *, update: bool = False) -> FormDefinitionEntity:
        entity_id, version = open_ref_id(ref_id)
        row = await self.session.get(
            FormDefinitionEntity, entity_id, with_for_update=update, populate_existing=update
        )
        if row is None or row.deleted_at:
            raise NotFoundException("Form not found")
        if update and row.version != version:
            raise VersionConflictException("Form is stale")
        return row

    async def create(self, data: FormCreateDTO, actor_id: UUID) -> FormDefinitionEntity:
        row = FormDefinitionEntity(**data.model_dump(), owner_user_id=actor_id)
        self.session.add(row)
        await self.session.flush()
        return row

    async def update(self, ref_id: str, data: FormCreateDTO) -> FormDefinitionEntity:
        row = await self.get(ref_id, update=True)
        row.sqlmodel_update(data.model_dump())
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return row

    async def delete(self, ref_id: str) -> None:
        row = await self.get(ref_id, update=True)
        row.deleted_at = get_datetime_utc()
        row.is_active = False
        await self.session.flush()

    async def get_version(self, ref_id: str, *, update: bool = False) -> FormVersionEntity:
        entity_id, version = open_ref_id(ref_id)
        row = await self.session.get(
            FormVersionEntity, entity_id, with_for_update=update, populate_existing=update
        )
        if row is None or row.deleted_at:
            raise NotFoundException("Form version not found")
        if update and row.version != version:
            raise VersionConflictException("Form version is stale")
        return row

    def _validate(self, data: FormDocuments, *, publication: bool = False) -> str:
        result = self.validator.validate(data, publication=publication)
        if not result.valid:
            raise ValidationDetailsException([issue.model_dump() for issue in result.issues])
        if result.checksum is None:
            raise RuntimeError("Valid form documents must include a checksum")
        return result.checksum

    async def _validate_target_clients(self, documents: FormDocuments) -> None:
        for variant in documents.variants:
            if variant.client_ref_id is None:
                continue
            client_id, _ = open_ref_id(variant.client_ref_id)
            client = await self.session.get(ClientEntity, client_id)
            if client is None or client.deleted_at or not client.is_active:
                raise VersionConflictException("Target client is unavailable")
            if variant.kind is not None and variant.kind != client.kind:
                raise ValidationDetailsException(
                    [{"pointer": "/variants", "code": "variant.client_kind"}]
                )

    async def _resolve_reuse(
        self, documents: FormDocuments, actor: UserEntity | None
    ) -> tuple[FormDocuments, list[dict[str, Any]] | None]:
        if not bool(documents.reuse_instances):
            return documents, None
        if actor is None:
            raise ValidationDetailsException(
                [{"pointer": "/reuse_instances", "code": "reuse.actor_required"}]
            )
        return await LibraryService(self.session).resolve_form(
            documents,
            [item.model_dump() for item in documents.reuse_instances],
            actor,
        )

    async def create_version(
        self, data: FormVersionCreateDTO, actor: UserEntity | None = None
    ) -> FormVersionEntity:
        root = await self.get(data.form_ref_id, update=True)
        if not root.is_active:
            raise VersionConflictException("Form is inactive")
        authored = FormDocuments(**data.model_dump(exclude={"form_ref_id", "number"}))
        documents, manifest = await self._resolve_reuse(authored, actor)
        self._validate(documents)
        await self._validate_target_clients(documents)
        row = FormVersionEntity(
            form_definition_id=root.id,
            number=data.number,
            **documents.model_dump(exclude={"reuse_instances"}),
            reuse_instances=[item.model_dump() for item in authored.reuse_instances]
            if bool(authored.reuse_instances)
            else None,
            reuse_source=authored.model_dump() if bool(authored.reuse_instances) else None,
            reuse_manifest=manifest,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def update_version(
        self, ref_id: str, data: FormDocuments, actor: UserEntity | None = None
    ) -> FormVersionEntity:
        row = await self.get_version(ref_id, update=True)
        if row.status != "DRAFT":
            raise VersionConflictException("Form version is immutable")
        documents, manifest = await self._resolve_reuse(data, actor)
        self._validate(documents)
        await self._validate_target_clients(documents)
        row.sqlmodel_update(documents.model_dump(exclude={"reuse_instances"}))
        row.reuse_instances = (
            [item.model_dump() for item in data.reuse_instances]
            if bool(data.reuse_instances)
            else None
        )
        row.reuse_source = data.model_dump() if bool(data.reuse_instances) else None
        row.reuse_manifest = manifest
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return row

    async def publish(self, ref_id: str, actor_id: UUID) -> FormVersionEntity:
        row = await self.get_version(ref_id, update=True)
        if row.status != "DRAFT":
            raise VersionConflictException("Form version is immutable")
        root = await self.session.get(
            FormDefinitionEntity,
            row.form_definition_id,
            with_for_update=True,
            populate_existing=True,
        )
        if root is None or not root.is_active or root.deleted_at:
            raise VersionConflictException("Form is inactive")
        documents = (
            FormDocuments.model_validate(row.reuse_source)
            if bool(row.reuse_source)
            else FormDocuments.model_validate(row, from_attributes=True)
        )
        if bool(row.reuse_source):
            actor = await self.session.get(UserEntity, actor_id)
            if actor is None:
                raise VersionConflictException("Publisher is unavailable")
            documents, manifest = await self._resolve_reuse(documents, actor)
            row.sqlmodel_update(documents.model_dump(exclude={"reuse_instances"}))
            row.reuse_manifest = manifest
        await self._validate_target_clients(documents)
        document_checksum = self._validate(documents, publication=True)
        row.checksum = (
            hashlib.sha256(
                json.dumps(
                    {"documents": document_checksum, "dependencies": row.reuse_manifest},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            if bool(row.reuse_manifest)
            else document_checksum
        )
        row.status = "PUBLISHED"
        row.published_by_user_id = actor_id
        row.published_at = get_datetime_utc()
        row.updated_at = row.published_at
        await self.session.flush()
        return row

    async def retire(self, ref_id: str) -> FormVersionEntity:
        row = await self.get_version(ref_id, update=True)
        if row.status != "PUBLISHED":
            raise VersionConflictException("Only published forms can be retired")
        row.status = "RETIRED"
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return row

    async def delete_version(self, ref_id: str) -> None:
        row = await self.get_version(ref_id, update=True)
        if row.status != "DRAFT":
            raise VersionConflictException("Form version is immutable")
        row.deleted_at = get_datetime_utc()
        await self.session.flush()
