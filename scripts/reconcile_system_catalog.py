"""Install/check code-owned catalogs; roles are explicit options and never assigned to users."""

import argparse
import asyncio

from apps.step_types.application.registry import get_registry
from apps.step_types.application.service import StepTypeService
from apps.users.application.permission_catalog import ROLE_TEMPLATES, reconcile_permissions
from core.deps import SessionFactory, engine


async def reconcile(roles: tuple[str, ...], check_only: bool) -> int:
    try:
        async with SessionFactory() as session, session.begin():
            summary = await reconcile_permissions(session, roles=roles, check_only=check_only)
            if not check_only:
                await StepTypeService(session, get_registry()).reconcile()
            print(summary.model_dump_json())
            return (
                2
                if summary.missing_permissions
                or summary.deleted_permissions
                or summary.blocked_roles
                else 0
            )
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report without writing")
    parser.add_argument("--role", action="append", choices=tuple(ROLE_TEMPLATES), default=[])
    options = parser.parse_args()
    return asyncio.run(reconcile(tuple(options.role), options.check))


if __name__ == "__main__":
    raise SystemExit(main())
