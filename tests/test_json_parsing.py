import pytest

from utils.json_parsing import extract_json


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_strips_markdown_fence():
    raw = '```json\n{"a": 1, "b": [1, 2]}\n```'
    assert extract_json(raw) == {"a": 1, "b": [1, 2]}


def test_extract_json_strips_surrounding_prose():
    raw = 'Sure, here is the JSON:\n{"a": 1}\nHope that helps!'
    assert extract_json(raw) == {"a": 1}


def test_extract_json_raises_on_garbage():
    with pytest.raises(Exception):
        extract_json("not json at all")


def test_extract_json_tolerates_raw_newline_in_string_value():
    # This is the exact failure mode from the notebook agent: the model
    # put a literal newline inside a JSON string instead of escaping it
    # as \n. Strict JSON rejects this; we deliberately don't.
    raw = '{"cell_type": "code", "content": "x = 1\ny = 2"}'
    assert extract_json(raw) == {"cell_type": "code", "content": "x = 1\ny = 2"}
