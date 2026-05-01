import hashlib
import sqlite3
from typing import Optional

from casepulse.case_theory.models import (
    Theme, Allegation, AllegationStatus,
    Contradiction, ContradictionStatus,
    Argument, ArgumentType, Strength,
    Evidence, EvidenceKind, EvidenceRole,
)
from casepulse.storage.database import Database


# ---------------------------------------------------------------------------
# Theme CRUD
# ---------------------------------------------------------------------------

def create_theme(db: Database, theme: Theme) -> Theme:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO themes (case_id, title, description, display_order)
        VALUES (?, ?, ?, ?)
    """, (theme.case_id, theme.title, theme.description, theme.display_order))
    conn.commit()
    theme.id = cur.lastrowid
    return theme


def get_theme(db: Database, theme_id: int) -> Optional[Theme]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, case_id, title, description, display_order, "
                "created_at FROM themes WHERE id = ?", (theme_id,))
    row = cur.fetchone()
    if not row:
        return None
    return Theme(
        id=row[0], case_id=row[1], title=row[2], description=row[3],
        display_order=row[4],
    )


def list_themes(db: Database, case_id: int) -> list[Theme]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, case_id, title, description, display_order "
                "FROM themes WHERE case_id = ? ORDER BY display_order, id",
                (case_id,))
    return [Theme(id=r[0], case_id=r[1], title=r[2], description=r[3],
                  display_order=r[4]) for r in cur.fetchall()]


def update_theme(db: Database, theme: Theme) -> Theme:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE themes SET title = ?, description = ?, display_order = ?
        WHERE id = ?
    """, (theme.title, theme.description, theme.display_order, theme.id))
    conn.commit()
    return theme


def delete_theme(db: Database, theme_id: int) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM themes WHERE id = ?", (theme_id,))
    conn.commit()
