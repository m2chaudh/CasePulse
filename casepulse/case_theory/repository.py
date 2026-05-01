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


# ---------------------------------------------------------------------------
# Contradiction CRUD + allegation linking
# ---------------------------------------------------------------------------

def create_contradiction(db: Database, c: Contradiction) -> Contradiction:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO contradictions (case_id, headline, status, theme_id,
                                     display_order, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (c.case_id, c.headline, c.status.value, c.theme_id,
          c.display_order, c.notes))
    conn.commit()
    c.id = cur.lastrowid
    return c


def get_contradiction(db: Database, cid: int) -> Optional[Contradiction]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, case_id, headline, status, theme_id, display_order, notes
        FROM contradictions WHERE id = ?
    """, (cid,))
    row = cur.fetchone()
    if not row:
        return None
    return Contradiction(
        id=row[0], case_id=row[1], headline=row[2],
        status=ContradictionStatus(row[3]), theme_id=row[4],
        display_order=row[5], notes=row[6],
    )


def list_contradictions(db: Database, case_id: int,
                         status: Optional[ContradictionStatus] = None
                         ) -> list[Contradiction]:
    conn = db._get_conn()
    cur = conn.cursor()
    if status:
        cur.execute("""
            SELECT id, case_id, headline, status, theme_id, display_order, notes
            FROM contradictions WHERE case_id = ? AND status = ?
            ORDER BY display_order, id
        """, (case_id, status.value))
    else:
        cur.execute("""
            SELECT id, case_id, headline, status, theme_id, display_order, notes
            FROM contradictions WHERE case_id = ?
            ORDER BY display_order, id
        """, (case_id,))
    return [Contradiction(
        id=r[0], case_id=r[1], headline=r[2],
        status=ContradictionStatus(r[3]), theme_id=r[4],
        display_order=r[5], notes=r[6],
    ) for r in cur.fetchall()]


def update_contradiction(db: Database, c: Contradiction) -> Contradiction:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE contradictions SET headline = ?, status = ?, theme_id = ?,
                                    display_order = ?, notes = ?,
                                    updated_at = datetime('now')
        WHERE id = ?
    """, (c.headline, c.status.value, c.theme_id, c.display_order, c.notes, c.id))
    conn.commit()
    return c


def link_allegation_to_contradiction(db: Database, contradiction_id: int,
                                       allegation_id: int) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO contradiction_allegations
        (contradiction_id, allegation_id) VALUES (?, ?)
    """, (contradiction_id, allegation_id))
    conn.commit()


def list_allegations_for_contradiction(db: Database,
                                         contradiction_id: int
                                         ) -> list[Allegation]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, a.case_id, a.title, a.claim_text, a.claimed_date,
               a.source_evidence_id, a.status, a.notes
        FROM allegations a
        JOIN contradiction_allegations ca ON ca.allegation_id = a.id
        WHERE ca.contradiction_id = ?
    """, (contradiction_id,))
    return [Allegation(
        id=r[0], case_id=r[1], title=r[2], claim_text=r[3],
        claimed_date=r[4], source_evidence_id=r[5],
        status=AllegationStatus(r[6]), notes=r[7],
    ) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Argument CRUD
# ---------------------------------------------------------------------------

def create_argument(db: Database, a: Argument) -> Argument:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO arguments (contradiction_id, title, reasoning_text,
                                argument_type, strength, sequence)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (a.contradiction_id, a.title, a.reasoning_text,
          a.argument_type.value if a.argument_type else None,
          a.strength.value if a.strength else None, a.sequence))
    conn.commit()
    a.id = cur.lastrowid
    return a


def get_argument(db: Database, arg_id: int) -> Optional[Argument]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, contradiction_id, title, reasoning_text, argument_type,
               strength, sequence FROM arguments WHERE id = ?
    """, (arg_id,))
    row = cur.fetchone()
    if not row:
        return None
    return Argument(
        id=row[0], contradiction_id=row[1], title=row[2],
        reasoning_text=row[3],
        argument_type=ArgumentType(row[4]) if row[4] else None,
        strength=Strength(row[5]) if row[5] else None,
        sequence=row[6],
    )


def list_arguments_for_contradiction(db: Database,
                                       contradiction_id: int) -> list[Argument]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, contradiction_id, title, reasoning_text, argument_type,
               strength, sequence
        FROM arguments WHERE contradiction_id = ?
        ORDER BY sequence, id
    """, (contradiction_id,))
    return [Argument(
        id=r[0], contradiction_id=r[1], title=r[2], reasoning_text=r[3],
        argument_type=ArgumentType(r[4]) if r[4] else None,
        strength=Strength(r[5]) if r[5] else None,
        sequence=r[6],
    ) for r in cur.fetchall()]


def update_argument(db: Database, a: Argument) -> Argument:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE arguments SET title = ?, reasoning_text = ?,
                              argument_type = ?, strength = ?, sequence = ?,
                              updated_at = datetime('now')
        WHERE id = ?
    """, (a.title, a.reasoning_text,
          a.argument_type.value if a.argument_type else None,
          a.strength.value if a.strength else None, a.sequence, a.id))
    conn.commit()
    return a


def delete_argument(db: Database, arg_id: int) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM arguments WHERE id = ?", (arg_id,))
    conn.commit()
