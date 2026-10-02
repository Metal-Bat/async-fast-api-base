"""Tests for the registered task catalog application service."""

import pytest

from apps.tasks.application.service import TaskCatalogService
from utils.exceptions import NotFoundException


def test_task_catalog_exposes_registered_task_and_queue_select_options() -> None:
    catalog = TaskCatalogService()

    task_options = catalog.task_options()
    queue_options = catalog.queue_options()

    assert any(option.key == "system.ping" for option in task_options)
    assert [option.key for option in task_options] == sorted(option.key for option in task_options)
    assert {option.key for option in queue_options} >= {
        "sample.default",
        "reporting",
    }


def test_task_catalog_rejects_unregistered_task_names() -> None:
    with pytest.raises(NotFoundException):
        TaskCatalogService().get_by_name("unregistered.task")
