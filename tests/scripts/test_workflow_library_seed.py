"""Every workflow-library seed has an executable purpose and valid sample."""

from jsonschema import Draft202012Validator
from scripts.demo.workflow_library import primitive_examples, type_documents


def test_types_are_general_workflow_values_with_valid_explained_samples():
    documents = type_documents()
    assert {
        "text",
        "integer",
        "number",
        "boolean",
        "date",
        "date_time",
        "number_list",
        "record",
    } <= documents.keys()
    for document in documents.values():
        assert document.category.startswith("workflow")
        assert document.help_messages["en"]["description"]
        assert document.help_messages["fa"]["description"]
        Draft202012Validator(document.data_schema).validate(document.sample_input)


def test_examples_cover_every_math_logic_comparison_and_control_operation():
    examples = primitive_examples()
    assert len({example.key for example in examples}) == len(examples)
    assert {example.handler for example in examples} == {
        "arithmetic",
        "number_compare",
        "boolean_logic",
        "if_else",
        "select_value",
    }
    for example in examples:
        assert example.purpose and example.persian
        assert example.inputs
        assert example.expected is not None
