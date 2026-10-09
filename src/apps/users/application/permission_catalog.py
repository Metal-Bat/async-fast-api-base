"""Reconcile missing code-owned capabilities without changing existing operator grants."""

from types import MappingProxyType

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.users.domain.auth_entity import PermissionEntity, RoleEntity, RolePermissionEntity
from apps.users.domain.catalog import PermissionSeedSummary

PERMISSIONS = MappingProxyType(
    {
        "admin.users.manage": "Manage ordinary users; superuser changes require superuser authority.",
        "admin.permissions.manage": "Manage permission definitions and role assignments.",
        "admin.work_groups.manage": "Manage work groups and administrative resource selectors.",
        "admin.history.read": "Read authorized administrative history.",
        "admin.tasks.manage": "Manage task definitions, schedules and execution operations.",
        "forms.manage": "Author forms, reusable form definitions and client catalog entries.",
        "workflows.manage": "Author workflows, step catalogs, agents and designer metadata.",
        "requests.manage": "Manage request types and their application configuration.",
        "requests.start": "Use requests and work items subject to current resource eligibility.",
        "integrations.manage": "Manage governed integration connections and grants.",
        "integration.connection.use": "Use an explicitly granted integration connection.",
        "processes.recover": "Enter recovery routes; recovery service also requires a superuser.",
        "support.incidents.manage": "Read and acknowledge sanitized support incidents; correlation grants no access.",
    }
)
ROLE_TEMPLATES = MappingProxyType(
    {
        "requester": ("requests.start",),
        "reviewer": ("requests.start",),
        "designer": ("forms.manage", "workflows.manage"),
        "administrator": tuple(key for key in PERMISSIONS if key != "processes.recover"),
        "operator": ("requests.start", "admin.tasks.manage"),
        "auditor": ("admin.history.read",),
    }
)


async def reconcile_permissions(
    session: AsyncSession, *, roles: tuple[str, ...] = (), check_only: bool = False
) -> PermissionSeedSummary:
    """Create absent definitions/optional roles; caller owns commit and transaction scope."""
    if len(set(roles)) != len(roles) or any(role not in ROLE_TEMPLATES for role in roles):
        raise ValueError("Role installation must use distinct registered templates")
    summary = PermissionSeedSummary()
    if not check_only:
        await session.exec(select(func.pg_advisory_xact_lock(0x4150504245303034)))
    permissions = {
        row.name: row
        for row in (
            await session.exec(
                select(PermissionEntity).where(col(PermissionEntity.name).in_(PERMISSIONS))
            )
        ).all()
    }
    for name, description in PERMISSIONS.items():
        row = permissions.get(name)
        if row is None:
            if check_only:
                summary.missing_permissions.append(name)
                continue
            row = PermissionEntity(name=name, description=description)
            session.add(row)
            permissions[name] = row
            summary.created_permissions.append(name)
        elif row.deleted_at is not None:
            summary.deleted_permissions.append(name)
    if not check_only:
        await session.flush()
    for template in roles:
        name = f"app.{template}.v1"
        existing = (
            await session.exec(select(RoleEntity).where(RoleEntity.name == name))
        ).one_or_none()
        if existing is not None:
            # Existing templates become operator-managed immediately after installation.
            summary.preserved_roles.append(name)
            continue
        if check_only or any(
            permission not in permissions or permissions[permission].deleted_at is not None
            for permission in ROLE_TEMPLATES[template]
        ):
            summary.blocked_roles.append(name)
            continue
        role = RoleEntity(name=name, description=f"Optional application {template} template v1")
        session.add(role)
        await session.flush()
        session.add_all(
            RolePermissionEntity(role_id=role.id, permission_id=permissions[permission].id)
            for permission in ROLE_TEMPLATES[template]
        )
        summary.created_roles.append(name)
    if not check_only:
        await session.flush()
    return summary
