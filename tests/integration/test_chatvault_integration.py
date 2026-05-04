"""ChatVault integration: register exports, scan parents, index msg-N
anchors against chat_messages, look up anchors for the day-drawer.

Synthetic ChatVault index.html fixtures live inline here; we don't
depend on a real ChatVault build.
"""
import sqlite3
from pathlib import Path
from textwrap import dedent

import pytest

from casepulse.chatvault_integration import (
    detect_chat_name, detect_platform, get_anchors_for_messages,
    list_exports, register_export, remove_export, scan_for_exports,
    static_root, symlink_path_for, url_for,
)
from casepulse.scripts.index_chatvault_export import (
    _combine_minute, _norm_body, _to_minute, index_export,
    parse_chatvault_index,
)


def _write_fixture(out_dir: Path, *, platform: str = "whatsapp",
                   chat_name: str = "Manisha",
                   messages: list[dict] | None = None) -> Path:
    """Write a minimal ChatVault-shaped index.html into out_dir.

    Each message dict: {id, sender, date ('YYYY-MM-DD' or pretty), time,
    body, is_system?}. Date separators are emitted automatically when
    the date changes.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "media").mkdir(exist_ok=True)
    title_app = "AppClose" if platform == "appclose" else "WhatsApp"
    title = f"{chat_name} — {title_app} Archive — ChatVault"
    parts = [
        "<!DOCTYPE html><html><head>",
        f"<title>{title}</title>",
        "</head><body>",
        '<main class="chat">',
    ]
    last_date = None
    for m in messages or []:
        if m["date"] != last_date:
            parts.append(
                f'<div class="date-separator">{m["date"]}</div>'
            )
            last_date = m["date"]
        cls = "message system" if m.get("is_system") else "message received"
        parts.append(
            f'<div class="{cls}" id="msg-{m["id"]}">'
            f'<div class="bubble">'
            f'<div class="sender-name">{m["sender"]}</div>'
            f'<div class="msg-text">{m["body"]}</div>'
            f'<div class="meta">{m["time"]}</div>'
            f'</div></div>'
        )
    parts.append("</main></body></html>")
    idx = out_dir / "index.html"
    idx.write_text("\n".join(parts), encoding="utf-8")
    return idx


@pytest.fixture
def tmp_export(tmp_path):
    """A synthetic ChatVault export folder with a minimal index.html."""
    folder = tmp_path / "Manisha"
    _write_fixture(folder, platform="whatsapp", chat_name="Manisha", messages=[
        {"id": 0, "sender": "Manisha", "date": "August 19, 2024",
         "time": "6:50 PM", "body": "Can I see the kids please"},
        {"id": 1, "sender": "Mani", "date": "August 19, 2024",
         "time": "6:55 PM", "body": "Yes — coming home soon"},
    ])
    return folder


@pytest.fixture
def isolated_static(monkeypatch, tmp_path):
    """Redirect static_root() to a tmp dir so symlinks don't leak into
    the real project tree."""
    fake_root = tmp_path / "static_chatvault"
    fake_root.mkdir(parents=True)
    monkeypatch.setattr(
        "casepulse.chatvault_integration.static_root", lambda: fake_root
    )
    return fake_root


# ── Helpers ───────────────────────────────────────────────────────────────

def test_detect_platform_from_title(tmp_path):
    folder = tmp_path / "WAExport"
    _write_fixture(folder, platform="whatsapp")
    assert detect_platform(str(folder)) == "whatsapp"

    folder2 = tmp_path / "ACExport"
    _write_fixture(folder2, platform="appclose", chat_name="Conversations")
    assert detect_platform(str(folder2)) == "appclose"


def test_detect_chat_name_from_title(tmp_path):
    folder = tmp_path / "X"
    _write_fixture(folder, platform="whatsapp", chat_name="Manisha")
    assert detect_chat_name(str(folder)) == "Manisha"


def test_url_for_emits_anchor():
    assert url_for("My Export").endswith("/My-Export/index.html")
    assert url_for("My Export", "msg-42").endswith(
        "/My-Export/index.html#msg-42"
    )


# ── scan_for_exports ──────────────────────────────────────────────────────

def test_scan_for_exports_lists_only_index_dirs(tmp_path):
    parent = tmp_path / "out"
    parent.mkdir()
    # Two exports, one bare folder
    _write_fixture(parent / "A", chat_name="Alice")
    _write_fixture(parent / "B", chat_name="Bob")
    (parent / "skipme").mkdir()
    found = scan_for_exports(str(parent))
    names = [f["name"] for f in found]
    assert names == ["A", "B"]
    assert all(f["has_media"] for f in found)


# ── register / list / remove ──────────────────────────────────────────────

def test_register_export_creates_row_and_symlink(
    tmp_db, tmp_export, isolated_static,
):
    export_id = register_export(tmp_db, "Manisha WA", str(tmp_export))
    assert export_id > 0

    rows = list_exports(tmp_db)
    assert len(rows) == 1
    assert rows[0]["name"] == "Manisha WA"
    assert rows[0]["platform"] == "whatsapp"
    assert rows[0]["chat_name"] == "Manisha"

    link = symlink_path_for("Manisha WA")
    assert link.is_symlink()
    assert link.resolve() == tmp_export.resolve()


def test_register_rejects_missing_index(tmp_db, tmp_path, isolated_static):
    bad = tmp_path / "no_html"
    bad.mkdir()
    with pytest.raises(ValueError, match="No index.html"):
        register_export(tmp_db, "broken", str(bad))


def test_remove_export_deletes_row_and_symlink(
    tmp_db, tmp_export, isolated_static,
):
    export_id = register_export(tmp_db, "Manisha WA", str(tmp_export))
    link = symlink_path_for("Manisha WA")
    assert link.is_symlink()

    remove_export(tmp_db, export_id)
    assert list_exports(tmp_db) == []
    assert not link.exists() and not link.is_symlink()


def test_remove_export_cascades_anchors(
    tmp_db, tmp_export, isolated_static,
):
    """When an export is removed, its anchors are cleaned up too
    (FK CASCADE)."""
    export_id = register_export(tmp_db, "Manisha WA", str(tmp_export))
    with tmp_db._get_conn() as conn:
        # Insert a fake chat_messages row + anchor
        conn.execute(
            "INSERT INTO chat_messages (source_type, sender, timestamp, "
            "message_text) VALUES ('whatsapp', 'Manisha', "
            "'2024-08-19T18:50', 'hi')"
        )
        cm_id = conn.execute(
            "SELECT id FROM chat_messages ORDER BY id DESC LIMIT 1"
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO chatvault_anchors (chat_message_id, export_id, "
            "anchor_id) VALUES (?, ?, ?)",
            (cm_id, export_id, "msg-0"),
        )
    remove_export(tmp_db, export_id)
    with tmp_db._get_conn() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS c FROM chatvault_anchors"
        ).fetchone()["c"]
    assert n == 0


# ── Indexer ───────────────────────────────────────────────────────────────

def test_parse_chatvault_index_extracts_messages(tmp_export):
    records = parse_chatvault_index(tmp_export / "index.html")
    assert len(records) == 2
    assert records[0]["anchor_id"] == "msg-0"
    assert records[0]["sender"] == "Manisha"
    assert records[0]["date"] == "2024-08-19"
    assert records[0]["time"].startswith("6:50")
    assert records[0]["body"].startswith("Can I see")


def test_combine_minute_iso():
    assert _combine_minute("2024-08-19", "6:50 PM") == "2024-08-19T18:50"
    assert _combine_minute("2024-08-19", "06:50") == "2024-08-19T06:50"
    assert _combine_minute("2024-08-19", "") == "2024-08-19"


def test_norm_body_collapses_whitespace_and_lowercases():
    assert _norm_body("  Hi   THERE\n\nfriend") == "hi there friend"


def test_index_export_matches_chat_messages(
    tmp_db, tmp_export, isolated_static,
):
    """ChatVault entries that align by (minute, sender, body) → anchored."""
    # Seed chat_messages: one matches, one doesn't (different body)
    with tmp_db._get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages (source_type, platform, sender, "
            "timestamp, message_text) VALUES "
            "('whatsapp', 'WhatsApp', 'Manisha', '2024-08-19T18:50:00', "
            "'Can I see the kids please')"
        )
        conn.execute(
            "INSERT INTO chat_messages (source_type, platform, sender, "
            "timestamp, message_text) VALUES "
            "('whatsapp', 'WhatsApp', 'Mani', '2024-08-19T18:55:00', "
            "'something else entirely')"
        )

    export_id = register_export(tmp_db, "Manisha WA", str(tmp_export))
    stats = index_export(tmp_db, export_id)
    assert stats["cv_messages"] == 2
    assert stats["matched"] == 1
    assert stats["unmatched_cv"] == 1
    assert stats["unmatched_cm"] == 1

    with tmp_db._get_conn() as conn:
        rows = conn.execute(
            "SELECT chat_message_id, anchor_id FROM chatvault_anchors"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["anchor_id"] == "msg-0"


def test_index_export_is_idempotent(
    tmp_db, tmp_export, isolated_static,
):
    with tmp_db._get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages (source_type, platform, sender, "
            "timestamp, message_text) VALUES "
            "('whatsapp', 'WhatsApp', 'Manisha', '2024-08-19T18:50:00', "
            "'Can I see the kids please')"
        )
    export_id = register_export(tmp_db, "M", str(tmp_export))
    s1 = index_export(tmp_db, export_id)
    s2 = index_export(tmp_db, export_id)
    assert s1["matched"] == s2["matched"] == 1

    with tmp_db._get_conn() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS c FROM chatvault_anchors WHERE "
            "export_id = ?", (export_id,)
        ).fetchone()["c"]
    assert n == 1  # not duplicated


def test_index_export_no_lax_match_when_bodies_differ(
    tmp_db, tmp_path, isolated_static,
):
    """If a (minute, sender) pair has the same count on both sides but
    the bodies disagree, we DON'T blindly anchor — false positives are
    worse than missing matches for legal evidence."""
    folder = tmp_path / "Mismatch"
    _write_fixture(folder, platform="whatsapp", chat_name="X", messages=[
        {"id": 0, "sender": "A", "date": "August 19, 2024",
         "time": "6:50 PM", "body": "Yes — coming home soon"},
    ])
    with tmp_db._get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages (source_type, platform, sender, "
            "timestamp, message_text) VALUES "
            "('whatsapp', 'WhatsApp', 'A', '2024-08-19T18:50:00', "
            "'something else entirely')"
        )
    export_id = register_export(tmp_db, "MM", str(folder))
    stats = index_export(tmp_db, export_id)
    assert stats["matched"] == 0
    assert stats["unmatched_cv"] == 1
    assert stats["unmatched_cm"] == 1


def test_index_export_lax_match_for_placeholder_bodies(
    tmp_db, tmp_path, isolated_static,
):
    """Action-only chat_messages rows (body = '[sent a photo]') DO
    match a CV bubble with no text body via the lax fallback — the
    image is rendered in HTML but the text body is empty."""
    folder = tmp_path / "Photo"
    _write_fixture(folder, platform="appclose", chat_name="X", messages=[
        {"id": 0, "sender": "A", "date": "August 19, 2024",
         "time": "6:50 PM", "body": ""},
    ])
    with tmp_db._get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages (source_type, platform, sender, "
            "timestamp, message_text) VALUES "
            "('appclose', 'AppClose', 'A', '2024-08-19T18:50:00', "
            "'[sent a photo]')"
        )
    export_id = register_export(tmp_db, "Photo", str(folder))
    stats = index_export(tmp_db, export_id)
    assert stats["matched"] == 1


# ── Bulk anchor lookup ────────────────────────────────────────────────────

def test_get_anchors_for_messages_returns_per_id_dict(
    tmp_db, tmp_export, isolated_static,
):
    with tmp_db._get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages (source_type, platform, sender, "
            "timestamp, message_text) VALUES "
            "('whatsapp', 'WhatsApp', 'Manisha', '2024-08-19T18:50:00', "
            "'Can I see the kids please')"
        )
        cm_id = conn.execute(
            "SELECT id FROM chat_messages ORDER BY id DESC LIMIT 1"
        ).fetchone()["id"]
    export_id = register_export(tmp_db, "M", str(tmp_export))
    index_export(tmp_db, export_id)

    out = get_anchors_for_messages(tmp_db, [cm_id, 99999])
    assert cm_id in out
    assert out[cm_id]["anchor_id"] == "msg-0"
    assert out[cm_id]["export_name"] == "M"
    assert 99999 not in out


def test_get_anchors_handles_empty_list(tmp_db):
    assert get_anchors_for_messages(tmp_db, []) == {}


# ── Foreign-key CASCADE on chat_messages delete ───────────────────────────

def test_chat_message_delete_cascades_anchor(
    tmp_db, tmp_export, isolated_static,
):
    with tmp_db._get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages (source_type, platform, sender, "
            "timestamp, message_text) VALUES "
            "('whatsapp', 'WhatsApp', 'Manisha', '2024-08-19T18:50:00', "
            "'Can I see the kids please')"
        )
        cm_id = conn.execute(
            "SELECT id FROM chat_messages ORDER BY id DESC LIMIT 1"
        ).fetchone()["id"]
    export_id = register_export(tmp_db, "M", str(tmp_export))
    index_export(tmp_db, export_id)

    with tmp_db._get_conn() as conn:
        conn.execute("DELETE FROM chat_messages WHERE id = ?", (cm_id,))
        n = conn.execute(
            "SELECT COUNT(*) AS c FROM chatvault_anchors"
        ).fetchone()["c"]
    assert n == 0
