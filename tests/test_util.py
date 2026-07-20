import pytest

from orchestration.util import (
    extract_json,
    normalize_relative_path,
    npm_package_name,
    resolve_within,
    safe_path_component,
)


def test_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_markdown_fence_with_lang():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_markdown_fence_no_lang():
    assert extract_json('```\n{"a": 1}\n```') == {"a": 1}


def test_surrounding_text():
    assert extract_json("好的，结果如下:\n{\"a\": 1}\n以上。") == {"a": 1}


def test_nested_json():
    assert extract_json('{"a": {"b": [1, 2]}}') == {"a": {"b": [1, 2]}}


def test_no_json_raises():
    with pytest.raises(Exception):
        extract_json("这里没有 JSON")


def test_path_helpers_reject_traversal_and_keep_output_inside_root(tmp_path):
    assert normalize_relative_path(r"app\\page.tsx") == "app/page.tsx"
    assert resolve_within(tmp_path, "app/page.tsx") == tmp_path.resolve() / "app" / "page.tsx"
    with pytest.raises(ValueError):
        normalize_relative_path("../outside.txt")
    with pytest.raises(ValueError):
        normalize_relative_path("C:/outside.txt")


def test_safe_names_are_portable():
    assert safe_path_component("  Demo / App  ") == "Demo-App"
    assert safe_path_component("CON", fallback="job-123") == "job-123"
    assert npm_package_name("产品 Demo") == "demo"
    assert npm_package_name("产品") == "ai-generated-app"
