"""Published workflow interfaces and subprocess call validation."""

import pytest

from apps.workflows.domain.subprocess import (
    SubprocessCall,
    SubprocessInterface,
    SubprocessPort,
)


def test_subprocess_interface_requires_unique_typed_names() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        SubprocessInterface(
            inputs=[
                SubprocessPort(name="reviewer", value_schema={"type": "string"}),
                SubprocessPort(name="reviewer", value_schema={"type": "integer"}),
            ],
            outcomes={"approved": "finish"},
        )


def test_subprocess_call_rejects_undeclared_lifecycle_options() -> None:
    with pytest.raises(ValueError):
        SubprocessCall.model_validate(
            {
                "workflow_version_ref": "opaque",
                "inputs": [],
                "on_child_cancel": "retry",
            }
        )


def test_subprocess_interface_reserves_failure_for_engine_errors() -> None:
    with pytest.raises(ValueError, match="reserved"):
        SubprocessInterface(outcomes={"failure": "finish"})
