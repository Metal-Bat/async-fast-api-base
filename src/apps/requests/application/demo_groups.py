"""Create explicitly owned demo groups once without repairing revoked membership."""

from uuid import uuid5

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.users.domain.bootstrap import BootstrapManifest
from apps.users.domain.entity import UserEntity
from apps.work_groups.application.service import WorkGroupService
from apps.work_groups.domain.dto import WorkGroupCreateDTO
from apps.work_groups.domain.entity import WorkGroupEntity
from core.ref_id import create_ref_id
from utils.exceptions import VersionConflictException


async def install_demo_groups(
    session: AsyncSession, manifest: BootstrapManifest, *, check_only: bool = False
) -> dict[str, str]:
    service = WorkGroupService(session)
    owner_id = uuid5(manifest.installation_id, "user:designer")
    result = {}
    for persona in ("requester", "reviewer"):
        user = await session.get(UserEntity, uuid5(manifest.installation_id, f"user:{persona}"))
        if user is None or user.deleted_at is not None:
            raise VersionConflictException("Demo group identity unavailable")
        identifier = uuid5(manifest.installation_id, f"group:{persona}")
        code = f"demo.{manifest.installation_id.hex}.{persona}"
        group = await session.get(WorkGroupEntity, identifier)
        if group is None:
            if check_only:
                raise VersionConflictException("Demo group is missing")
            if (
                await session.exec(select(WorkGroupEntity).where(WorkGroupEntity.code == code))
            ).first() is not None:
                raise VersionConflictException("Demo group code is owned by another identity")
            group = await service.create_group(
                WorkGroupCreateDTO(
                    code=code,
                    name=f"Synthetic {persona} / گروه آزمایشی",
                    description="Owned synthetic demo group",
                ),
                owner_id,
                identifier=identifier,
            )
            await service.add_member(
                create_ref_id(group.id, group.version), user.id, actor_id=owner_id
            )
        elif group.deleted_at is not None or not group.is_active or group.code != code:
            raise VersionConflictException(
                "Demo group removed or changed; operator intervention required"
            )
        result[persona] = create_ref_id(group.id, group.version)
    return result
