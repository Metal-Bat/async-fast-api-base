"""Compatibility exports for the focused domain entity modules."""

from apps.work_groups.domain.entities.group import WorkGroupEntity, WorkGroupHistoryTable
from apps.work_groups.domain.entities.member import WorkGroupMemberEntity

__all__ = ["WorkGroupEntity", "WorkGroupHistoryTable", "WorkGroupMemberEntity"]
