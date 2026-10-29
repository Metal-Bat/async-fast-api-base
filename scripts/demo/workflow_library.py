"""Small reusable workflow library; every insert explains its intended use."""

from dataclasses import asdict, dataclass
from hashlib import sha256
from json import dumps
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.forms.application.library import LibraryService
from apps.forms.domain.library import (
    ComponentDocument,
    LibraryCreate,
    LibraryVersionCreate,
    TypeDocument,
)
from apps.forms.domain.library_entity import (
    ComponentEntity,
    ComponentVersionEntity,
    DataTypeEntity,
    DataTypeVersionEntity,
)
from apps.step_types.application.registry import get_registry
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.entity import StepTypeVersionEntity
from apps.users.domain.bootstrap import BootstrapManifest
from apps.users.domain.entity import UserEntity
from apps.workflows.domain.dto import GraphBinding, GraphSnapshot, GraphStep, GraphTransition
from apps.workflows.domain.subprocess import SubprocessInterface, SubprocessOutput, SubprocessPort
from core.ref_id import create_ref_id
from utils.exceptions import VersionConflictException


@dataclass(frozen=True)
class PrimitiveExample:
    key: str
    handler: str
    config: dict[str, Any]
    inputs: dict[str, Any]
    expected: Any
    purpose: str
    persian: str


def primitive_examples() -> tuple[PrimitiveExample, ...]:
    """Each example becomes a published reusable subprocess with typed input ports."""
    math = (
        ("add", 7, "Combine two quantities or scores.", "جمع دو مقدار یا امتیاز."),
        (
            "subtract",
            1,
            "Calculate remaining quantity or the difference between scores.",
            "محاسبه مقدار باقی‌مانده یا اختلاف امتیازها.",
        ),
        (
            "multiply",
            12,
            "Calculate quantity times a rate or weight.",
            "محاسبه حاصل‌ضرب مقدار در ضریب.",
        ),
        (
            "divide",
            4 / 3,
            "Calculate a ratio; a zero divisor fails instead of producing invalid data.",
            "محاسبه نسبت؛ مخرج صفر خطا می‌دهد.",
        ),
        (
            "remainder",
            1,
            "Find the remainder for batch grouping or cyclic allocation.",
            "محاسبه باقی‌مانده برای دسته‌بندی یا تخصیص چرخه‌ای.",
        ),
    )
    comparisons = (
        ("eq", False, "Check whether two numbers are equal.", "بررسی برابری دو عدد."),
        ("ne", True, "Detect a changed or mismatched numeric value.", "تشخیص تفاوت دو مقدار عددی."),
        ("lt", False, "Check a strict upper limit.", "بررسی کمتر بودن از حد مجاز."),
        ("lte", False, "Check an inclusive upper limit.", "بررسی کمتر یا مساوی بودن با حد مجاز."),
        ("gt", True, "Detect a quantity exceeding a threshold.", "تشخیص عبور مقدار از آستانه."),
        (
            "gte",
            True,
            "Check a minimum required quantity or score.",
            "بررسی حداقل مقدار یا امتیاز لازم.",
        ),
    )
    return (
        *(
            PrimitiveExample(
                "math." + key,
                "arithmetic",
                {"operation": key},
                {"left": 4, "right": 3},
                expected,
                reason,
                fa,
            )
            for key, expected, reason, fa in math
        ),
        *(
            PrimitiveExample(
                "compare." + key,
                "number_compare",
                {"operation": key},
                {"left": 4, "right": 3},
                expected,
                reason,
                fa,
            )
            for key, expected, reason, fa in comparisons
        ),
        PrimitiveExample(
            "logic.and",
            "boolean_logic",
            {"operation": "and"},
            {"left": True, "right": False},
            False,
            "Require both conditions before continuing.",
            "لزوم برقرار بودن هر دو شرط.",
        ),
        PrimitiveExample(
            "logic.or",
            "boolean_logic",
            {"operation": "or"},
            {"left": True, "right": False},
            True,
            "Continue when either condition is satisfied.",
            "ادامه در صورت برقرار بودن یکی از شرط‌ها.",
        ),
        PrimitiveExample(
            "logic.not",
            "boolean_logic",
            {"operation": "not"},
            {"left": False},
            True,
            "Invert a boolean condition for an exclusion rule.",
            "معکوس کردن شرط برای قانون استثنا.",
        ),
        PrimitiveExample(
            "control.if_else",
            "if_else",
            {},
            {"condition": True},
            True,
            "Route execution to the true or false branch; both finishes are connected.",
            "هدایت اجرا به شاخه درست یا نادرست؛ هر دو مسیر متصل‌اند.",
        ),
        PrimitiveExample(
            "data.select",
            "select_value",
            {},
            {"condition": False, "if_true": "expedited", "if_false": "standard"},
            "standard",
            "Choose a value without changing the execution path; for example choose a processing label.",
            "انتخاب مقدار بدون تغییر مسیر اجرا؛ مانند انتخاب برچسب پردازش.",
        ),
    )


def type_documents() -> dict[str, TypeDocument]:
    """Scalar and structured values used by workflow inputs, calculations and bindings."""
    specifications = (
        (
            "text",
            {"type": "string"},
            "standard",
            "Labels, identifiers and text carried between steps.",
            "برچسب، شناسه و متن بین مراحل.",
        ),
        (
            "integer",
            {"type": "integer"},
            3,
            "Whole item counts and loop or batch counters.",
            "تعداد صحیح اقلام و شمارنده دسته‌ها.",
        ),
        (
            "number",
            {"type": "number"},
            12.5,
            "Fractional quantities, ratios and calculation results.",
            "مقادیر اعشاری، نسبت‌ها و نتایج محاسبه.",
        ),
        (
            "boolean",
            {"type": "boolean"},
            True,
            "Conditions consumed by logic and if/else controls.",
            "شرط مورد استفاده در منطق و کنترل اگر/وگرنه.",
        ),
        (
            "date",
            {"type": "string", "format": "date"},
            "2026-10-17",
            "Calendar dates without a time or timezone.",
            "تاریخ تقویمی بدون ساعت یا منطقه زمانی.",
        ),
        (
            "date_time",
            {"type": "string", "format": "date-time"},
            "2026-10-17T12:00:00Z",
            "Timestamp values for deadlines and recorded events.",
            "زمان دقیق برای مهلت‌ها و رویدادهای ثبت‌شده.",
        ),
        (
            "number_list",
            {"type": "array", "items": {"type": "number"}, "maxItems": 256},
            [2, 3.5],
            "A bounded collection of numeric measurements or scores.",
            "مجموعه محدود اندازه‌گیری‌ها یا امتیازهای عددی.",
        ),
        (
            "record",
            {
                "type": "object",
                "properties": {"label": {"type": "string"}, "value": {"type": "number"}},
                "required": ["label", "value"],
                "additionalProperties": False,
            },
            {"label": "quantity", "value": 12.5},
            "Keep a named numeric result together as a structured step value.",
            "نگهداری نام و نتیجه عددی در یک مقدار ساختاریافته.",
        ),
    )
    return {
        key: TypeDocument(
            data_schema=schema,
            category="workflow.values",
            sample_input=sample,
            help_messages={"en": {"description": purpose}, "fa": {"description": fa}},
        )
        for key, schema, sample, purpose, fa in specifications
    }


def component_documents() -> dict[str, ComponentDocument]:
    """Reusable input panels corresponding to the actual primitive input contracts."""
    specifications = (
        (
            "numeric_operands",
            {"left": {"type": "number"}, "right": {"type": "number"}},
            {"left": 4, "right": 3},
            "Enter two operands for arithmetic or numeric comparison.",
            "ورود دو عملوند برای محاسبه یا مقایسه عددی.",
        ),
        (
            "boolean_conditions",
            {"left": {"type": "boolean"}, "right": {"type": "boolean"}},
            {"left": True, "right": False},
            "Enter conditions to combine with AND or OR.",
            "ورود شرط‌ها برای ترکیب با و یا یا.",
        ),
        (
            "conditional_labels",
            {
                "condition": {"type": "boolean"},
                "if_true": {"type": "string"},
                "if_false": {"type": "string"},
            },
            {"condition": False, "if_true": "expedited", "if_false": "standard"},
            "Choose between two text labels using a boolean condition.",
            "انتخاب یکی از دو برچسب متنی براساس شرط.",
        ),
    )
    return {
        key: ComponentDocument(
            data_schema={
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
            render_schema={
                "root": {
                    "component": "vertical",
                    "children": [
                        {
                            "component": {
                                "number": "number",
                                "boolean": "boolean",
                                "string": "text",
                            }[schema["type"]],
                            "scope": "/properties/" + name,
                            "label": name.replace("_", " ").title(),
                        }
                        for name, schema in properties.items()
                    ],
                }
            },
            category="workflow.inputs",
            sample_input=sample,
            help_messages={"en": {"description": purpose}, "fa": {"description": fa}},
        )
        for key, properties, sample, purpose, fa in specifications
    }


def example_graph(example: PrimitiveExample, refs: dict[str, str]) -> GraphSnapshot:
    registry = get_registry()
    definition = registry.resolve(example.handler, "1")
    inputs = [
        port
        for port in definition.ports
        if port.direction == "INPUT" and port.port_key in example.inputs
    ]
    output = next(port for port in definition.ports if port.direction == "OUTPUT")
    outcomes = definition.outcomes or ("next",)
    return GraphSnapshot(
        interface=SubprocessInterface(
            inputs=[
                SubprocessPort(name=port.port_key, value_schema=port.metadata().value_schema)
                for port in inputs
            ],
            outputs=[
                SubprocessOutput(
                    name="result",
                    value_schema=output.metadata().value_schema,
                    source_step="operation",
                    source_port="result",
                )
            ],
            outcomes={outcome: "finish_" + outcome for outcome in outcomes},
            category="workflow." + definition.category.lower(),
            help_messages={"en": example.purpose, "fa": example.persian},
            sample_inputs=example.inputs,
        ),
        steps=[
            GraphStep(key="start", type_code="START", type_version_ref=refs["start"]),
            GraphStep(
                key="operation",
                type_code=definition.code,
                type_version_ref=refs[example.handler],
                config=example.config,
            ),
            *(
                GraphStep(
                    key="finish_" + outcome, type_code="FINISH", type_version_ref=refs["finish"]
                )
                for outcome in outcomes
            ),
        ],
        bindings=[
            GraphBinding(
                step="operation",
                target_port=port.port_key,
                target_schema=port.metadata().value_schema,
                source_kind="REQUEST",
                source_path="/" + port.port_key,
            )
            for port in inputs
        ],
        transitions=[
            GraphTransition(source="start", target="operation", outcome="next"),
            *(
                GraphTransition(source="operation", target="finish_" + outcome, outcome=outcome)
                for outcome in outcomes
            ),
        ],
    )


async def install_workflow_library(
    session: AsyncSession, manifest: BootstrapManifest, owner: UserEntity
) -> dict[str, int]:
    """Add missing version-one seeds; never overwrite operator edits or published pins."""
    from scripts.demo.catalog import install_workflow

    prefix = "wf." + manifest.installation_id.hex[:16] + "."
    service = StepTypeService(session, get_registry())
    primitive_keys = {example.handler for example in primitive_examples()}
    for version in await service.reconcile():
        if version.handler_key in primitive_keys and version.status == "DRAFT":
            await service.publish(create_ref_id(version.id, version.version))
    refs = {
        version.handler_key: create_ref_id(version.id, version.version)
        for version in (
            await session.exec(
                select(StepTypeVersionEntity).where(StepTypeVersionEntity.status == "PUBLISHED")
            )
        ).all()
        if version.handler_key in primitive_keys | {"start", "finish"}
        and version.handler_version == "1"
    }
    if refs.keys() != primitive_keys | {"start", "finish"}:
        raise VersionConflictException(
            "Required workflow primitives are unavailable; preserve retired versions"
        )
    library = LibraryService(session)
    for kind, documents, root_model, version_model in (
        ("data_type", type_documents(), DataTypeEntity, DataTypeVersionEntity),
        ("component", component_documents(), ComponentEntity, ComponentVersionEntity),
    ):
        for key, document in documents.items():
            code = prefix + kind + "." + key
            root = (
                await session.exec(select(root_model).where(root_model.code == code))
            ).one_or_none()
            if root is not None:
                version = (
                    await session.exec(
                        select(version_model).where(
                            version_model.root_id == root.id, version_model.number == 1
                        )
                    )
                ).one_or_none()
                if (
                    root.owner_user_id != owner.id
                    or root.deleted_at is not None
                    or not root.is_active
                    or version is None
                    or version.status != "PUBLISHED"
                    or version.document != document.model_dump(mode="json")
                ):
                    raise VersionConflictException(
                        "Workflow library seed changed; no data overwritten"
                    )
                continue
            root = await library.create_definition(
                kind, LibraryCreate(code=code, name=key.replace("_", " ").title()), owner
            )
            version = await library.create_version(
                kind,
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(root.id, root.version),
                    number=1,
                    document=document.model_dump(mode="json"),
                ),
                owner,
            )
            await library.publish(kind, create_ref_id(version.id, version.version), owner)
    for example in primitive_examples():
        await install_workflow(
            session,
            prefix + example.key,
            example.key.replace(".", " / ").replace("_", " ").title(),
            example_graph(example, refs),
            owner,
            {
                "installation_id": str(manifest.installation_id),
                "seed_version": 1,
                "template_key": example.key,
                "source_hash": sha256(dumps(asdict(example), sort_keys=True).encode()).hexdigest(),
            },
            lifecycle_examples=False,
        )
    return {
        "workflow_primitives": len(primitive_keys),
        "workflow_examples": len(primitive_examples()),
        "workflow_data_types": len(type_documents()),
        "workflow_components": len(component_documents()),
    }
