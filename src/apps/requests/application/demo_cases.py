"""Synthetic demo cases follow the same request and human-command lifecycle as HTTP callers."""

from typing import Literal

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.requests.application.service import RequestService
from apps.requests.domain.dto import BusinessRequestCreateDTO, BusinessRequestSubmitDTO
from apps.requests.domain.entity import (
    BusinessRequestEntity,
    FormSubmissionEntity,
    RequestTypeEntity,
)
from apps.users.domain.entity import UserEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.dto import CorrectionFeedbackInput
from apps.work_items.domain.entity import WorkItemEntity
from core.ref_id import create_ref_id
from utils.exceptions import VersionConflictException

SCENARIOS = ("draft", "waiting", "correction", "rejected", "completed")
DECISIONS: dict[str, tuple[Literal["complete", "reject", "return"], str]] = {
    "completed": ("complete", "approve"),
    "rejected": ("reject", "reject"),
    "correction": ("return", "return"),
}


async def install_cases(
    session: AsyncSession,
    kind: RequestTypeEntity,
    requester: UserEntity,
    reviewer: UserEntity,
    *,
    check_only: bool = False,
) -> dict[str, str]:
    """Existing cases are returned in their current state, never reset or completed again."""
    existing = (
        await session.exec(
            select(BusinessRequestEntity, FormSubmissionEntity)
            .join(
                FormSubmissionEntity,
                col(FormSubmissionEntity.business_request_id) == col(BusinessRequestEntity.id),
            )
            .where(
                BusinessRequestEntity.request_type_id == kind.id,
                BusinessRequestEntity.requester_user_id == requester.id,
                col(FormSubmissionEntity.step_execution_id).is_(None),
            )
        )
    ).all()
    by_title = {submission.data.get("title"): request for request, submission in existing}
    if existing:
        for scenario in SCENARIOS:
            if (
                sum(
                    submission.data.get("title") == f"Synthetic {scenario}"
                    for _, submission in existing
                )
                != 1
            ):
                raise VersionConflictException("Demo case ownership is ambiguous")
        if any(
            f"Synthetic {scenario}" not in by_title
            or by_title[f"Synthetic {scenario}"].deleted_at is not None
            for scenario in SCENARIOS
        ):
            raise VersionConflictException("Demo cases were changed; refusing duplicate fixtures")
        return {
            scenario: create_ref_id(
                by_title[f"Synthetic {scenario}"].id, by_title[f"Synthetic {scenario}"].version
            )
            for scenario in SCENARIOS
        }
    if check_only:
        raise VersionConflictException("Demo cases are missing")
    requests = RequestService(session)
    work_items = WorkItemService(session)
    result = {}
    for scenario in SCENARIOS:
        data = {
            "title": f"Synthetic {scenario}",
            "amount": "125.00",
            "reason": "Synthetic fixture; no payment or external integration performed.",
        }
        request, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(kind.id, kind.version), data=data
            ),
            requester,
        )
        if scenario != "draft":
            await requests.submit(
                create_ref_id(request.id, request.version),
                BusinessRequestSubmitDTO(submit_key=f"demo:{scenario}:{kind.id}"),
                requester,
            )
        if scenario in {"correction", "rejected", "completed"}:
            item = (
                await session.exec(
                    select(WorkItemEntity).where(
                        WorkItemEntity.business_request_id == request.id,
                        WorkItemEntity.status == "OPEN",
                    )
                )
            ).one()
            item = await work_items.claim(
                create_ref_id(item.id, item.version), f"demo:claim:{scenario}", reviewer
            )
            action, outcome = DECISIONS[scenario]
            await work_items.finish(
                create_ref_id(item.id, item.version),
                action,
                f"demo:finish:{scenario}",
                outcome,
                data,
                reviewer,
                comment="Synthetic demo decision",
                feedback=[
                    CorrectionFeedbackInput(
                        scope="/properties/title", message="Please clarify the synthetic title."
                    )
                ]
                if scenario == "correction"
                else None,
            )
        result[scenario] = create_ref_id(request.id, request.version)
    return result
