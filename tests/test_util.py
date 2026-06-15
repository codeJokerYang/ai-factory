import pytest

from orchestration.util import extract_json


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
