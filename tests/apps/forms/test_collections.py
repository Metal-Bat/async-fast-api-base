"""Collection identities stay stable when positions change."""

import pytest

from apps.forms.application.collections import CollectionError, edit_collection, initialize_identity


def test_nested_reorder_preserves_keys_and_descendants():
    data = {"rows": [{"children": [{"value": "a"}]}, {"children": [{"value": "b"}]}]}
    identity = initialize_identity(data)
    first, second = identity["/rows"]
    child = identity["/rows/0/children"][0]
    result = edit_collection(data, identity, "/rows", "reorder", item_key=first, target_index=1)
    assert result.data["rows"][1]["children"][0]["value"] == "a"
    assert result.identity["/rows"] == [second, first]
    assert result.identity["/rows/1/children"] == [child]


def test_duplicate_assigns_new_keys_recursively_and_rejects_stale_identity():
    data = {"rows": [{"children": [{"value": "a"}]}]}
    identity = initialize_identity(data)
    source = identity["/rows"][0]
    result = edit_collection(data, identity, "/rows", "duplicate", item_key=source)
    assert len(result.data["rows"]) == 2
    assert result.identity["/rows"][1] != source
    assert result.identity["/rows/1/children"][0] != identity["/rows/0/children"][0]
    with pytest.raises(CollectionError, match="collection.item_key"):
        edit_collection(data, identity, "/rows", "remove", item_key="stale")


def test_repeated_attachment_paths_materialize_after_reorder():
    from apps.forms.application.attachments import _collections, _set_pointer

    render = {
        "root": {
            "component": "vertical",
            "children": [
                {
                    "component": "attachment_collection",
                    "scope": "/properties/rows/items/properties/files",
                }
            ],
        }
    }
    data = {"rows": [{"files": []}, {"files": []}]}
    found = _collections(render, data)
    assert set(found) == {"/rows/0/files", "/rows/1/files"}
    _set_pointer(data, "/rows/1/files", ["upload-ref"])
    assert data["rows"][1]["files"] == ["upload-ref"]


def test_validation_issues_map_to_stable_nested_item_keys():
    from apps.forms.application.collections import issue_item_keys

    data = {"rows": [{"children": [{"value": "x"}]}]}
    identity = initialize_identity(data)
    assert issue_item_keys("/data/rows/0/children/0/value", identity) == [
        identity["/rows"][0],
        identity["/rows/0/children"][0],
    ]
