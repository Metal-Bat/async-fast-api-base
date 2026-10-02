"""Database-backed source visibility, selected lookups and revocation."""

import os
from uuid import uuid7

import pytest

from apps.forms.application.options import OptionService, encode_choice_key
from apps.forms.application.validation import FormValidator
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.options import OptionQuery
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.exceptions import ValidationDetailsException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_domain_options_filter_before_pagination_and_recheck_revocations():
    try:
        async with SessionFactory() as session:
            actor, target, outsider = [
                UserEntity(username=f"options-{label}-{uuid7().hex}", hashed_password="hash")
                for label in ("a", "b", "c")
            ]
            group = WorkGroupEntity(code=f"O{uuid7().hex}", name="Option group")
            session.add_all([actor, target, outsider, group])
            await session.flush()
            own = WorkGroupMemberEntity(work_group_id=group.id, user_id=actor.id)
            other = WorkGroupMemberEntity(work_group_id=group.id, user_id=target.id)
            session.add_all([own, other])
            await session.flush()
            group_ref = create_ref_id(group.id, group.version)
            target_ref = create_ref_id(target.id, target.version)
            outsider_ref = create_ref_id(outsider.id, outsider.version)
            doc = FormDocuments(
                data_schema={
                    "type": "object",
                    "properties": {"group": {"type": "string"}, "person": {"type": "string"}},
                },
                render_schema={
                    "root": {
                        "component": "vertical",
                        "children": [
                            {
                                "component": "group",
                                "scope": "/properties/group",
                                "source": {"kind": "domain", "selector": "work_groups"},
                            },
                            {
                                "component": "user",
                                "scope": "/properties/person",
                                "source": {
                                    "kind": "domain",
                                    "selector": "users",
                                    "dependencies": {"group_ref": "/properties/group"},
                                },
                            },
                        ],
                    }
                },
            )
            assert FormValidator().validate(doc).valid
            data = {"group": group_ref, "person": target_ref}
            service = OptionService(session)
            query = OptionQuery(node_pointer="/root/children/1", data=data, size=1)
            page = await service.resolve(doc, query, actor)
            assert page.total == 2 and len(page.items) == 1
            page = await service.resolve(
                doc,
                query.model_copy(update={"selected_keys": [encode_choice_key(target_ref)]}),
                actor,
            )
            assert page.total == 1 and page.items[0].key == encode_choice_key(target_ref)
            hidden = await service.resolve(
                doc,
                query.model_copy(update={"selected_keys": [encode_choice_key(outsider_ref)]}),
                actor,
            )
            assert hidden.total == 0
            await service.validate_submission(doc, data, actor)
            other.is_active = False
            await session.flush()
            with pytest.raises(ValidationDetailsException):
                await service.validate_submission(doc, data, actor)
            other.is_active = True
            await session.flush()
            target.username += "-updated"
            await session.flush()
            with pytest.raises(ValidationDetailsException):
                await service.validate_submission(doc, data, actor)
            own.is_active = False
            await session.flush()
            assert (await service.resolve(doc, query, actor)).total == 0
            await session.rollback()
    finally:
        await engine.dispose()
