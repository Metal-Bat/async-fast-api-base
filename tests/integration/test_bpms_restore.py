"""Opt-in consistent PostgreSQL, private S3 and encrypted credential restore drill."""

import hashlib
import json
import os
import subprocess
from uuid import uuid7

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.forms.application.attachments import AttachmentService
from apps.forms.application.service import FormService
from apps.forms.domain.attachment_dto import AttachmentAddDTO
from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO
from apps.integrations.data.secrets import EncryptedFileSecrets, SecretUnavailable
from apps.integrations.domain.entity import IntegrationConnectionEntity
from apps.media.application.service import UserUploadService
from apps.media.domain.entity import UserUploadEntity
from apps.processes.application.service import ProcessService
from apps.processes.domain.entity import ProcessInstanceEntity
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import (
    BusinessRequestCreateDTO,
    BusinessRequestSubmitDTO,
    RequestTypeCreateDTO,
)
from apps.requests.domain.entity import FormSubmissionAttachmentEntity, FormSubmissionEntity
from apps.users.domain.entity import UserEntity
from apps.workflows.domain.entity import WorkflowDefinitionEntity, WorkflowVersionEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from core.settings import settings
from tests.integration.test_processes import _start_waiting_process
from utils.s3 import delete_object, get_object, put_object, s3_client

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_BPMS_RESTORE") != "1",
        reason="requires disposable PostgreSQL/S3 and Docker CLI",
    ),
]


def _postgres(command: str, *arguments: str, input_data: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "sh", "-c", command, "drill", *arguments],
        input=input_data,
        capture_output=True,
        check=True,
    )
    return result.stdout


@pytest.mark.anyio
async def test_restore_preserves_pins_private_attachments_and_secret_versions(
    tmp_path, monkeypatch
) -> None:
    source_database = make_url(settings.DATABASE_DSN).database
    assert source_database and source_database.startswith("bpms016_"), (
        "Use an explicitly disposable source database"
    )
    target = "bpms016_restore_" + uuid7().hex
    bucket = "restore-" + uuid7().hex
    key = "restore-drill/" + uuid7().hex
    body = b"%PDF-1.4\nBPMS recovery evidence\n%%EOF"
    source_bucket = settings.S3_BUCKET
    restored_engine = None
    created_database = False
    created_bucket = False
    try:
        await put_object(key, body, "application/pdf")
        async with SessionFactory() as session:
            owner = UserEntity(
                username=f"restore-{uuid7()}", hashed_password="unused", is_superuser=True
            )
            session.add(owner)
            await session.flush()
            seed_process, _ = await _start_waiting_process(session, owner, "TIMER")
            workflow_version = await session.get(
                WorkflowVersionEntity, seed_process.workflow_version_id
            )
            assert workflow_version is not None
            workflow = await session.get(
                WorkflowDefinitionEntity, workflow_version.workflow_definition_id
            )
            assert workflow is not None
            forms = FormService(session)
            form = await forms.create(
                FormCreateDTO(code=f"RF{uuid7().hex}", name="Restore evidence"), owner.id
            )
            version = await forms.create_version(
                FormVersionCreateDTO(
                    form_ref_id=create_ref_id(form.id, form.version),
                    number=1,
                    data_schema={
                        "type": "object",
                        "properties": {"evidence": {"type": "array", "items": {"type": "string"}}},
                    },
                    render_schema={
                        "dialect": "bpms.render/1",
                        "root": {
                            "component": "attachment_collection",
                            "scope": "/properties/evidence",
                            "options": {
                                "allowed_kinds": ["file"],
                                "allowed_mime_types": ["application/pdf"],
                                "max_items": 2,
                            },
                        },
                    },
                )
            )
            await forms.publish(create_ref_id(version.id, version.version), owner.id)
            requests = RequestService(session)
            kind = await requests.create_type(
                RequestTypeCreateDTO(
                    code=f"RT{uuid7().hex}",
                    name="Restore",
                    workflow_ref_id=create_ref_id(workflow.id, workflow.version),
                    form_ref_id=create_ref_id(form.id, form.version),
                )
            )
            draft, _ = await requests.create_draft(
                BusinessRequestCreateDTO(
                    request_type_ref_id=create_ref_id(kind.id, kind.version), data={}
                ),
                owner,
            )
            upload = UserUploadEntity(
                user_id=owner.id,
                kind="file",
                object_key=key,
                original_filename="evidence.pdf",
                content_type="application/pdf",
                size_bytes=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
            )
            session.add(upload)
            await session.flush()
            draft, attachment = await AttachmentService(session).add(
                create_ref_id(draft.id, draft.version),
                AttachmentAddDTO(
                    field_path="/evidence", upload_ref_id=create_ref_id(upload.id, upload.version)
                ),
                owner,
            )
            await requests.submit(
                create_ref_id(draft.id, draft.version),
                BusinessRequestSubmitDTO(submit_key="restore-drill"),
                owner,
            )
            process = (
                await session.exec(
                    select(ProcessInstanceEntity).where(
                        ProcessInstanceEntity.business_request_id == draft.id
                    )
                )
            ).one()
            connection = IntegrationConnectionEntity(
                code=f"RC{uuid7().hex}",
                name="Restore credential",
                provider="https_status",
                kind="SERVICE",
                non_secret_config={"endpoint_key": "approved"},
                secret_ref="restore",
                secret_version="v1",
                owner_user_id=owner.id,
            )
            session.add(connection)
            await session.commit()
            owner_id, upload_id, attachment_id, process_id, connection_id = (
                owner.id,
                upload.id,
                attachment.id,
                process.id,
                connection.id,
            )
            workflow_pin, form_pin = process.workflow_version_id, version.id

        # Quiescent test source: database snapshot, referenced object bytes and ciphertext form one set.
        dump = _postgres('exec pg_dump -U "$POSTGRES_USER" -Fc "$1"', source_database)
        object_backup = await get_object(key)
        encryption_key = Fernet.generate_key()
        encrypted_backup = Fernet(encryption_key).encrypt(
            json.dumps(
                {"connection": "restore", "version": "v1", "token": "disposable-credential"}
            ).encode()
        )
        _postgres('exec createdb -U "$POSTGRES_USER" "$1"', target)
        created_database = True
        _postgres(
            'exec pg_restore -U "$POSTGRES_USER" --exit-on-error --no-owner -d "$1"',
            target,
            input_data=dump,
        )
        async with s3_client() as client:
            await client.create_bucket(Bucket=bucket)
            created_bucket = True
            await client.put_object(
                Bucket=bucket,
                Key=key,
                Body=object_backup,
                ContentType="application/pdf",
                Metadata={"sha256": hashlib.sha256(object_backup).hexdigest()},
            )
        (tmp_path / "restore.v1.enc").write_bytes(encrypted_backup)
        (tmp_path / "restore.v1.enc").chmod(0o600)
        monkeypatch.setattr(settings, "S3_BUCKET", bucket)
        restored_engine = create_async_engine(
            make_url(settings.DATABASE_DSN).set(database=target), poolclass=NullPool
        )
        async with AsyncSession(restored_engine, expire_on_commit=False) as session:
            actor = await session.get(UserEntity, owner_id)
            restored_upload = await session.get(UserUploadEntity, upload_id)
            restored_attachment = await session.get(FormSubmissionAttachmentEntity, attachment_id)
            assert actor and restored_upload and restored_attachment
            submission = await session.get(
                FormSubmissionEntity, restored_attachment.form_submission_id
            )
            assert (
                submission
                and submission.status == "SUBMITTED"
                and submission.form_version_id == form_pin
            )
            assert restored_attachment.user_upload_id == restored_upload.id
            authorized = await UserUploadService(session).get_for_download(
                create_ref_id(restored_upload.id, restored_upload.version), "file", actor
            )
            assert (
                authorized.sha256
                == hashlib.sha256(await get_object(authorized.object_key)).hexdigest()
            )
            restored_connection = await session.get(IntegrationConnectionEntity, connection_id)
            assert restored_connection
            store = EncryptedFileSecrets(tmp_path, [encryption_key])
            assert (
                store.resolve(
                    restored_connection.secret_ref, restored_connection.secret_version
                ).get_secret_value()
                == "disposable-credential"
            )
            with pytest.raises(SecretUnavailable):
                EncryptedFileSecrets(tmp_path, [Fernet.generate_key()]).resolve("restore", "v1")
            process = await session.get(ProcessInstanceEntity, process_id)
            assert (
                process
                and process.workflow_version_id == workflow_pin
                and process.status == "WAITING"
            )
            await ProcessService(session).resume(
                create_ref_id(process.id, process.version), "restored-timer", "elapsed", {}
            )
            await session.commit()
            assert process.status == "COMPLETED"
    finally:
        monkeypatch.setattr(settings, "S3_BUCKET", source_bucket)
        if restored_engine:
            await restored_engine.dispose()
        await engine.dispose()
        if created_database:
            _postgres('exec dropdb -U "$POSTGRES_USER" "$1"', target)
        if created_bucket:
            async with s3_client() as client:
                await client.delete_object(Bucket=bucket, Key=key)
                await client.delete_bucket(Bucket=bucket)
        await delete_object(key)
