from fastapi import APIRouter, Depends

from apps.ai.presentation.routes import router as ai_agents_router
from apps.calendar.presentation.routes import router as calendar_router
from apps.clients.presentation.routes import releases_router as client_releases_router
from apps.clients.presentation.routes import router as clients_router
from apps.designer.presentation.library_routes import router as definition_library_router
from apps.designer.presentation.resource_links import router as resource_links_router
from apps.designer.presentation.routes import router as designer_router
from apps.forms.presentation.library_routes import (
    component_router,
    component_versions_router,
    data_type_router,
    data_type_versions_router,
)
from apps.forms.presentation.routes import router as forms_router
from apps.forms.presentation.routes import versions_router as form_versions_router
from apps.health.setup_routes import router as setup_router
from apps.integrations.presentation.routes import router as integrations_router
from apps.media.presentation.routes import router as media_router
from apps.notifications.presentation.inbox import router as inbox_router
from apps.notifications.presentation.routes import router as notifications_router
from apps.processes.presentation.routes import events_router
from apps.processes.presentation.routes import router as processes_router
from apps.reporting.presentation.analytics import router as analytics_router
from apps.reporting.presentation.routes import router as reporting_router
from apps.requests.presentation.routes import requests_router, types_router
from apps.step_types.presentation.routes import router as step_types_router
from apps.support.presentation.routes import router as support_router
from apps.tasks.presentation.routes import router as tasks_router
from apps.users.presentation.admin import router as admin_router
from apps.users.presentation.collections import favorites, views
from apps.users.presentation.help_state import router as help_state_router
from apps.users.presentation.history import router as history_router
from apps.users.presentation.login import router as login_router
from apps.users.presentation.personal import router as personal_router
from apps.work_groups.presentation.routes import router as work_groups_router
from apps.work_groups.presentation.routes import user_selector_router
from apps.work_items.presentation.routes import router as work_items_router
from apps.workflows.presentation.routes import router as workflows_router
from apps.workflows.presentation.routes import versions_router as workflow_versions_router
from utils.base_schema import get_request_user_agent

api_router = APIRouter(dependencies=[Depends(get_request_user_agent)])
api_router.include_router(designer_router)
api_router.include_router(setup_router)
api_router.include_router(support_router)
api_router.include_router(calendar_router)
api_router.include_router(resource_links_router)
api_router.include_router(analytics_router)
api_router.include_router(definition_library_router)
api_router.include_router(clients_router)
api_router.include_router(client_releases_router)
api_router.include_router(step_types_router)
api_router.include_router(component_router)
api_router.include_router(component_versions_router)
api_router.include_router(data_type_router)
api_router.include_router(data_type_versions_router)
api_router.include_router(forms_router)
api_router.include_router(form_versions_router)
api_router.include_router(workflows_router)
api_router.include_router(workflow_versions_router)
api_router.include_router(types_router)
api_router.include_router(requests_router)
api_router.include_router(processes_router)
api_router.include_router(events_router)
api_router.include_router(work_items_router)
api_router.include_router(integrations_router)
api_router.include_router(ai_agents_router)
api_router.include_router(notifications_router)
api_router.include_router(inbox_router)
api_router.include_router(login_router)
api_router.include_router(personal_router)
api_router.include_router(views)
api_router.include_router(favorites)
api_router.include_router(help_state_router)
api_router.include_router(admin_router)
api_router.include_router(work_groups_router)
api_router.include_router(user_selector_router)
api_router.include_router(media_router)
api_router.include_router(reporting_router)
api_router.include_router(tasks_router)
api_router.include_router(history_router)
