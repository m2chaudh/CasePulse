"""ChatVault export registration and deep-link helpers.

A ChatVault export is a folder produced by `chatvault appclose <pdf>` or
the WhatsApp pipeline — it contains an `index.html` with bubble anchors
(`id="msg-N"`) and a `media/` subfolder. This module:

  - registers/lists/removes exports in the `chatvault_exports` table
  - manages symlinks under `<project_root>/static/chatvault/<safe_name>/`
    so Streamlit (with enableStaticServing=true) serves them at
    `/app/static/chatvault/<safe_name>/index.html#msg-N`
  - exposes anchor lookups that the day-drawer uses to add deep-link
    buttons to chat-message bubbles

The actual matching of `msg-N` anchors to `chat_messages.id` is in
`casepulse.scripts.index_chatvault_export` (the indexer).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from casepulse.config import get_project_root
from casepulse.storage.database import Database


# Where Streamlit serves files from when enableStaticServing=true.
STATIC_CHATVAULT_DIR = "static/chatvault"

# URL prefix Streamlit exposes static files at.
STATIC_URL_PREFIX = "/app/static/chatvault"


def _safe_name(name: str) -> str:
    """Filesystem-safe slug for export name → symlink folder."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip())
    return s.strip("-_.") or "export"


def static_root() -> Path:
    """Absolute path to <project_root>/static/chatvault/, created lazily."""
    p = get_project_root() / STATIC_CHATVAULT_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def symlink_path_for(name: str) -> Path:
    """Where the symlink for an export of this name lives."""
    return static_root() / _safe_name(name)


def url_for(name: str, anchor_id: Optional[str] = None) -> str:
    """Streamlit-served URL for an export's index.html, optionally
    with a `#msg-N` fragment."""
    safe = _safe_name(name)
    base = f"{STATIC_URL_PREFIX}/{safe}/index.html"
    if anchor_id:
        return f"{base}#{anchor_id}"
    return base


def _create_or_refresh_symlink(name: str, source_dir: str) -> Path:
    """Create (or replace) the symlink under static/chatvault/<safe_name>/
    pointing at the export's source dir. Returns the symlink path."""
    src = Path(source_dir).resolve()
    if not src.is_dir():
        raise ValueError(f"Source dir does not exist: {source_dir}")
    if not (src / "index.html").exists():
        raise ValueError(f"No index.html in source dir: {source_dir}")

    link = symlink_path_for(name)
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(src, target_is_directory=True)
    return link


def detect_platform(source_dir: str) -> str:
    """Read source_dir/index.html and infer the platform."""
    idx = Path(source_dir) / "index.html"
    if not idx.exists():
        return ""
    head = idx.read_text(encoding="utf-8", errors="replace")[:8192]
    low = head.lower()
    if "appclose" in low:
        return "appclose"
    if "whatsapp" in low:
        return "whatsapp"
    return ""


def detect_chat_name(source_dir: str) -> str:
    """Read source_dir/index.html <title> and extract the conversation name.

    ChatVault titles look like 'Manisha — ChatVault' or 'AppClose Conversations
    — ChatVault'. Strip the suffix.
    """
    idx = Path(source_dir) / "index.html"
    if not idx.exists():
        return ""
    head = idx.read_text(encoding="utf-8", errors="replace")[:8192]
    m = re.search(r"<title>([^<]+)</title>", head, re.IGNORECASE)
    if not m:
        return ""
    raw = m.group(1).strip()
    # "Manisha — ChatVault" → "Manisha"; also handle '–' (en dash)
    for sep in (" — ", " – ", " - "):
        if sep in raw:
            raw = raw.split(sep)[0]
            break
    return raw.strip()


# ── Database operations ───────────────────────────────────────────────────

def register_export(
    db: Database,
    name: str,
    source_dir: str,
    *,
    platform: Optional[str] = None,
    chat_name: Optional[str] = None,
    notes: str = "",
) -> int:
    """Register a ChatVault export and create the static symlink.

    Returns the new export id. Raises ValueError on bad input.
    """
    name = name.strip()
    if not name:
        raise ValueError("Export name cannot be empty.")

    src = Path(source_dir).expanduser().resolve()
    if not src.is_dir():
        raise ValueError(f"Source dir does not exist: {source_dir}")
    if not (src / "index.html").exists():
        raise ValueError(f"No index.html in source dir: {source_dir}")

    if platform is None:
        platform = detect_platform(str(src)) or "unknown"
    if chat_name is None:
        chat_name = detect_chat_name(str(src))

    _create_or_refresh_symlink(name, str(src))

    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO chatvault_exports
               (name, source_dir, platform, chat_name, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (name, str(src), platform, chat_name or "", notes),
        )
        return cur.lastrowid


def remove_export(db: Database, export_id: int) -> None:
    """Remove an export: drop DB row (cascades anchors) + remove symlink."""
    with db._get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM chatvault_exports WHERE id = ?", (export_id,)
        ).fetchone()
        if row:
            conn.execute(
                "DELETE FROM chatvault_exports WHERE id = ?", (export_id,)
            )
            link = symlink_path_for(row["name"])
            if link.is_symlink() or link.exists():
                try:
                    link.unlink()
                except OSError:
                    pass


def export_health(export: dict) -> dict:
    """Filesystem-state check for a registered export. Returns a dict
    with `status` and a human-readable `message`. Does no DB writes.

    status values:
      - 'ok'            : source_dir exists, has index.html, symlink works
      - 'missing-source': source_dir does not exist on disk
      - 'missing-index' : source_dir exists but no index.html in it
      - 'broken-symlink': symlink under static/chatvault/ is gone or points
                          somewhere unexpected (registration was wiped or
                          static_root() is on a different volume now)
    """
    src = Path(export["source_dir"])
    if not src.exists():
        return {"status": "missing-source",
                "message": f"Source folder is gone: {src}"}
    if not src.is_dir():
        return {"status": "missing-source",
                "message": f"Source path is not a directory: {src}"}
    if not (src / "index.html").exists():
        return {"status": "missing-index",
                "message": f"index.html no longer in {src}"}

    link = symlink_path_for(export["name"])
    if not link.is_symlink() and not link.exists():
        return {"status": "broken-symlink",
                "message": (f"Static symlink missing at {link}. "
                            f"Use Re-link to recreate it.")}
    # If the symlink points somewhere different than the recorded source_dir,
    # treat that as broken so the user re-links explicitly.
    try:
        if link.is_symlink() and link.resolve() != src.resolve():
            return {"status": "broken-symlink",
                    "message": (f"Symlink target diverged: points to "
                                f"{link.resolve()} but registry says {src}.")}
    except OSError:
        return {"status": "broken-symlink",
                "message": f"Cannot resolve symlink at {link}."}
    return {"status": "ok", "message": ""}


def relink_export(db: Database, export_id: int, new_source_dir: str) -> None:
    """Repair an export by pointing it at a new source folder. Updates the
    DB row and refreshes the static symlink. Anchors are kept (you should
    re-index right after — content fingerprint may have shifted)."""
    src = Path(new_source_dir).expanduser().resolve()
    if not src.is_dir():
        raise ValueError(f"Source dir does not exist: {new_source_dir}")
    if not (src / "index.html").exists():
        raise ValueError(f"No index.html in source dir: {new_source_dir}")
    with db._get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM chatvault_exports WHERE id = ?",
            (export_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"export {export_id} not found")
        _create_or_refresh_symlink(row["name"], str(src))
        conn.execute(
            "UPDATE chatvault_exports SET source_dir = ? WHERE id = ?",
            (str(src), export_id),
        )


def list_exports(db: Database) -> list[dict]:
    """All registered exports, newest first. Each row includes a
    `health` dict from export_health()."""
    with db._get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, source_dir, platform, chat_name, "
            "registered_at, last_indexed_at, message_count, notes "
            "FROM chatvault_exports ORDER BY id DESC"
        ).fetchall()
    out = [dict(r) for r in rows]
    for e in out:
        e["health"] = export_health(e)
    return out


def get_export(db: Database, export_id: int) -> Optional[dict]:
    with db._get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM chatvault_exports WHERE id = ?", (export_id,)
        ).fetchone()
    return dict(row) if row else None


def set_indexed(db: Database, export_id: int, message_count: int) -> None:
    """Stamp last_indexed_at + message_count after a successful index run."""
    with db._get_conn() as conn:
        conn.execute(
            "UPDATE chatvault_exports SET last_indexed_at=datetime('now'), "
            "message_count=? WHERE id=?",
            (message_count, export_id),
        )


def get_anchors_for_messages(
    db: Database, message_ids: list[int]
) -> dict[int, dict]:
    """Bulk lookup: chat_messages.id → most-recent matching anchor info.

    Returns {chat_message_id: {anchor_id, export_id, export_name,
    platform, broken}}. If a message has anchors in multiple exports,
    the most recent export (highest export_id) wins. The `broken` flag
    is True when the export's source/symlink is not reachable — caller
    should skip or grey-out the deep link in that case.
    """
    if not message_ids:
        return {}
    placeholders = ",".join("?" * len(message_ids))
    with db._get_conn() as conn:
        rows = conn.execute(
            f"""SELECT a.chat_message_id, a.anchor_id, a.export_id,
                       e.name AS export_name, e.platform, e.source_dir
                FROM chatvault_anchors a
                JOIN chatvault_exports e ON e.id = a.export_id
                WHERE a.chat_message_id IN ({placeholders})
                ORDER BY a.export_id DESC""",
            message_ids,
        ).fetchall()
    out: dict[int, dict] = {}
    health_cache: dict[int, bool] = {}  # export_id → broken?
    for r in rows:
        if r["chat_message_id"] in out:
            continue  # Highest export_id wins; first row per id is it
        eid = r["export_id"]
        if eid not in health_cache:
            h = export_health({
                "name": r["export_name"], "source_dir": r["source_dir"],
            })
            health_cache[eid] = (h["status"] != "ok")
        out[r["chat_message_id"]] = {
            "anchor_id": r["anchor_id"],
            "export_id": eid,
            "export_name": r["export_name"],
            "platform": r["platform"],
            "broken": health_cache[eid],
        }
    return out


# ── Settings: scan parent ─────────────────────────────────────────────────

SCAN_PARENT_KEY = "chatvault_scan_parent"


def get_scan_parent(db: Database) -> str:
    with db._get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (SCAN_PARENT_KEY,),
        ).fetchone()
    return row["value"] if row else ""


def set_scan_parent(db: Database, path: str) -> None:
    with db._get_conn() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (SCAN_PARENT_KEY, path.strip()),
        )


def scan_for_exports(parent_dir: str) -> list[dict]:
    """List candidate ChatVault export folders under parent_dir.

    A candidate is any direct child folder containing an `index.html`.
    Returns [{path, name, has_media, platform, chat_name}] sorted by name.
    """
    out: list[dict] = []
    p = Path(parent_dir).expanduser()
    if not p.is_dir():
        return out
    for child in sorted(p.iterdir(), key=lambda c: c.name.lower()):
        if not child.is_dir():
            continue
        idx = child / "index.html"
        if not idx.exists():
            continue
        out.append({
            "path": str(child),
            "name": child.name,
            "has_media": (child / "media").is_dir(),
            "platform": detect_platform(str(child)),
            "chat_name": detect_chat_name(str(child)),
        })
    return out
