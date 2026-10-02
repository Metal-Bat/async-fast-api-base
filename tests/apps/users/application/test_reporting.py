"""Tests for user report selection and transformation."""

from uuid import uuid7

from apps.reporting.application.base import ReportActor
from apps.users.application.reporting import UserPolarsReport
from apps.users.domain.dto import UserQuery
from utils.pagination import FilterCriteria, FilterOperation, SortOperation, SortOrder


def test_user_report_uses_validated_filters_and_system_first_ordering() -> None:
    query = UserQuery(
        filters=[
            FilterCriteria(field_name="username", operation=FilterOperation.CONTAINS, value="admin")
        ],
        sort_orders=[SortOrder(field_name="username", operation=SortOperation.ASC)],
    )
    actor = ReportActor(id=uuid7(), is_superuser=True)
    statement = str(UserPolarsReport.build_statement(query, actor))
    count = str(UserPolarsReport.build_count_statement(query, actor))

    assert '"USERNAME"' in statement and "WHERE" in statement
    assert statement.index('"CREATED_AT" DESC') < statement.index('"USERNAME" ASC')
    assert statement.index('"USERNAME" ASC') < statement.index('"ID" ASC')
    assert '"ID" ASC' in statement
    assert "ORDER BY" not in count and "LIMIT" not in count
