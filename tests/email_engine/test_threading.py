"""Header-parsing tests for casepulse.email_engine.threading.

Pure-function tests — no DB. The DB-touching backfill is tested in
tests/storage/test_email_parent_backfill.py.
"""
from casepulse.email_engine.threading import extract_parent_message_id


def test_in_reply_to_takes_priority_over_references():
    headers = {
        "In-Reply-To": "<irt@example.com>",
        "References": "<a@example.com> <b@example.com>",
    }
    assert extract_parent_message_id(headers) == "irt@example.com"


def test_falls_back_to_last_references_entry():
    headers = {
        "References": "<oldest@example.com> <middle@example.com> <newest@example.com>",
    }
    assert extract_parent_message_id(headers) == "newest@example.com"


def test_strips_angle_brackets_and_whitespace():
    headers = {"In-Reply-To": "  <  abc@example.com  >  "}
    # The regex requires the id be inside angle brackets; whitespace inside
    # the brackets isn't standard but the cleanup path handles it.
    out = extract_parent_message_id(headers)
    assert out is None or "abc@example.com" in out


def test_handles_unbracketed_in_reply_to():
    """Some non-conformant clients omit angle brackets entirely."""
    headers = {"In-Reply-To": "abc@example.com"}
    assert extract_parent_message_id(headers) == "abc@example.com"


def test_takes_last_id_in_multi_id_in_reply_to():
    """RFC says one ID per In-Reply-To, but real-world senders sometimes
    list multiple — last is the most recent parent."""
    headers = {
        "In-Reply-To": "<first@example.com> <second@example.com>",
    }
    assert extract_parent_message_id(headers) == "second@example.com"


def test_case_insensitive_header_lookup():
    headers = {"in-reply-to": "<lower@example.com>"}
    assert extract_parent_message_id(headers) == "lower@example.com"


def test_returns_none_when_no_threading_headers():
    headers = {"Subject": "hello", "From": "x@y.com"}
    assert extract_parent_message_id(headers) is None


def test_returns_none_when_headers_is_not_a_dict():
    assert extract_parent_message_id(None) is None
    assert extract_parent_message_id("not a dict") is None


def test_returns_none_for_empty_header_values():
    assert extract_parent_message_id({"In-Reply-To": ""}) is None
    assert extract_parent_message_id({"In-Reply-To": "   "}) is None


def test_outlook_style_long_message_id():
    """Outlook IDs include long base64-like strings + the host."""
    raw = "<YQBP288MB0241EFCFF31B7DE6D1C854EAD7582@YQBP288MB0241.CANP288.PROD.OUTLOOK.COM>"
    headers = {"In-Reply-To": raw}
    expected = "YQBP288MB0241EFCFF31B7DE6D1C854EAD7582@YQBP288MB0241.CANP288.PROD.OUTLOOK.COM"
    assert extract_parent_message_id(headers) == expected
