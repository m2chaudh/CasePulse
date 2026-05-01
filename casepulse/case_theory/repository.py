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


# ---------------------------------------------------------------------------
# Allegation CRUD
# ---------------------------------------------------------------------------

def create_allegation(db: Database, a: Allegation) -> Allegation:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO allegations (case_id, title, claim_text, claimed_date,
                                  source_evidence_id, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (a.case_id, a.title, a.claim_text, a.claimed_date,
          a.source_evidence_id, a.status.value, a.notes))
    conn.commit()
    a.id = cur.lastrowid
    return a


def get_allegation(db: Database, allegation_id: int) -> Optional[Allegation]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, case_id, title, claim_text, claimed_date,
               source_evidence_id, status, notes
        FROM allegations WHERE id = ?
    """, (allegation_id,))
    row = cur.fetchone()
    if not row:
        return None
    return Allegation(
        id=row[0], case_id=row[1], title=row[2], claim_text=row[3],
        claimed_date=row[4], source_evidence_id=row[5],
        status=AllegationStatus(row[6]), notes=row[7],
    )


def list_allegations(db: Database, case_id: int) -> list[Allegation]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, case_id, title, claim_text, claimed_date,
               source_evidence_id, status, notes
        FROM allegations WHERE case_id = ? ORDER BY claimed_date, id
    """, (case_id,))
    return [Allegation(
        id=r[0], case_id=r[1], title=r[2], claim_text=r[3],
        claimed_date=r[4], source_evidence_id=r[5],
        status=AllegationStatus(r[6]), notes=r[7],
    ) for r in cur.fetchall()]


def update_allegation(db: Database, a: Allegation) -> Allegation:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE allegations SET title = ?, claim_text = ?, claimed_date = ?,
                                source_evidence_id = ?, status = ?, notes = ?
        WHERE id = ?
    """, (a.title, a.claim_text, a.claimed_date, a.source_evidence_id,
          a.status.value, a.notes, a.id))
    conn.commit()
    return a


def delete_allegation(db: Database, allegation_id: int) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM allegations WHERE id = ?", (allegation_id,))
    conn.commit()
