"""Self-only settings; serialize writes on the owning identity, including the absent-row case."""

from uuid import UUID, uuid5

from sqlmodel.ext.asyncio.session import AsyncSession

from apps.media.application.service import UserUploadService
from apps.media.domain.entity import UserUploadEntity
from apps.users.domain.entity import UserEntity
from apps.users.domain.preferences import (
    PreferencesDTO,
    PreferencesPatch,
    ProfileDTO,
    ProfilePatch,
    UserPreferences,
)
from apps.users.domain.preferences_entity import UserPreferencesEntity
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, VersionConflictException


class PersonalSettingsService:
    """Callers commit; no shared cache, identity grants, tokens or external avatar URLs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _identifier(user_id: UUID) -> UUID:
        return uuid5(user_id, "personal-preferences:1")

    async def _active(self, actor: UserEntity, *, lock: bool = False) -> UserEntity:
        user = await self.session.get(
            UserEntity, actor.id, with_for_update=lock, populate_existing=True
        )
        if user is None or user.deleted_at is not None:
            raise NotFoundException("Active self profile not found")
        return user

    async def _row(self, user_id: UUID) -> UserPreferencesEntity | None:
        row = await self.session.get(
            UserPreferencesEntity, self._identifier(user_id), populate_existing=True
        )
        if row is not None and (row.user_id != user_id or row.deleted_at is not None):
            raise NotFoundException("Self preferences not found")
        return row

    def _dto(self, user_id: UUID, row: UserPreferencesEntity | None) -> PreferencesDTO:
        document = UserPreferences.model_validate(row.document) if row else UserPreferences()
        return PreferencesDTO(
            ref_id=create_ref_id(self._identifier(user_id), row.version if row else 0),
            **document.model_dump(),
        )

    async def read(self, actor: UserEntity) -> PreferencesDTO:
        """Return defaults without inserting a row or recording a user action."""
        user = await self._active(actor)
        return self._dto(user.id, await self._row(user.id))

    async def apply(self, actor: UserEntity, data: PreferencesPatch) -> PreferencesDTO:
        """Check current ownership/version, then atomically merge supplied fields in supplied groups."""
        user = await self._active(actor, lock=True)
        row = await self._row(user.id)
        identifier, expected = open_ref_id(data.ref_id)
        if identifier != self._identifier(user.id):
            raise NotFoundException("Self preferences not found")
        if expected != (row.version if row else 0):
            raise VersionConflictException("Self preferences reference is stale")
        current = self._dto(user.id, row)
        values = current.model_dump(exclude={"ref_id"})
        defaults = UserPreferences().model_dump()
        for group in data.model_fields_set - {"ref_id"}:
            supplied = getattr(data, group)
            values[group] = (
                defaults[group]
                if supplied is None
                else values[group] | supplied.model_dump(exclude_unset=True)
            )
        document = UserPreferences.model_validate(values).model_dump(mode="json")
        if document == current.model_dump(mode="json", exclude={"ref_id"}):
            return current
        if row is None:
            row = UserPreferencesEntity(
                id=self._identifier(user.id), user_id=user.id, document=document
            )
            self.session.add(row)
        else:
            row.document = document
            row.updated_at = get_datetime_utc()
        await self.session.flush()
        return self._dto(user.id, row)

    async def profile(self, actor: UserEntity) -> ProfileDTO:
        """Resolve a current private avatar reference without disclosing another owner's media."""
        user = await self._active(actor)
        row = await self._row(user.id)
        upload = (
            await self.session.get(UserUploadEntity, row.avatar_upload_id)
            if row and row.avatar_upload_id
            else None
        )
        avatar = (
            create_ref_id(upload.id, upload.version)
            if upload
            and upload.user_id == user.id
            and upload.kind == "image"
            and upload.deleted_at is None
            else None
        )
        return ProfileDTO(
            ref_id=create_ref_id(user.id, user.version),
            first_name=user.first_name,
            last_name=user.last_name,
            avatar_ref_id=avatar,
        )

    async def update_profile(self, actor: UserEntity, data: ProfilePatch) -> ProfileDTO:
        """Update only names and an owned image binding; contact/security fields stay with auth."""
        user = await self._active(actor, lock=True)
        identifier, expected = open_ref_id(data.ref_id)
        if identifier != user.id:
            raise NotFoundException("Self profile not found")
        if expected != user.version:
            raise VersionConflictException("Self profile reference is stale")
        avatar = None
        if "avatar_ref_id" in data.model_fields_set and data.avatar_ref_id is not None:
            avatar = await UserUploadService(self.session).get_for_download(
                data.avatar_ref_id, "image", user
            )
        changed = False
        for key in data.model_fields_set & {"first_name", "last_name"}:
            value = getattr(data, key)
            if getattr(user, key) != value:
                setattr(user, key, value)
                changed = True
        if "avatar_ref_id" in data.model_fields_set:
            row = await self._row(user.id)
            upload_id = avatar.id if avatar else None
            if upload_id != (row.avatar_upload_id if row else None):
                if row is None:
                    row = UserPreferencesEntity(
                        id=self._identifier(user.id),
                        user_id=user.id,
                        document=UserPreferences().model_dump(mode="json"),
                    )
                    self.session.add(row)
                row.avatar_upload_id = upload_id
                row.updated_at = get_datetime_utc()
                changed = True
        if changed:
            user.updated_at = get_datetime_utc()
            await self.session.flush()
        return await self.profile(user)
