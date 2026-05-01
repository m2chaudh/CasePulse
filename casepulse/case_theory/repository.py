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


# ---------------------------------------------------------------------------
# Evidence CRUD + argument_evidence linking
# ---------------------------------------------------------------------------

def _compute_source_hash(db: Database, source_table: str,
                          source_row_id: int) -> "str | None":
    """Compute SHA-256 of the source row's primary text."""
    conn = db._get_conn()
    cur = conn.cursor()
    text_cols = {
        "emails": "body_text",
        "chat_messages": "message_text",
        "attachments": "extracted_text",
        "documents": "extracted_text",
        "annotations": "note_text",
    }
    col = text_cols.get(source_table)
    if not col:
        return None
    cur.execute(f"SELECT {col} FROM {source_table} WHERE id = ?",
                (source_row_id,))
    row = cur.fetchone()
    if not row or row[0] is None:
        return None
    return hashlib.sha256(row[0].encode("utf-8")).hexdigest()


def create_evidence(db: Database, e: Evidence) -> Evidence:
    """Insert Evidence row. If source_hash is None, computes from source row."""
    conn = db._get_conn()
    cur = conn.cursor()
    if e.source_hash is None:
        e.source_hash = _compute_source_hash(db, e.source_table, e.source_row_id)
    try:
        cur.execute("""
            INSERT INTO evidence (evidence_kind, source_table, source_row_id,
                                   char_start, char_end, snippet, source_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (e.evidence_kind.value, e.source_table, e.source_row_id,
              e.char_start, e.char_end, e.snippet, e.source_hash))
        e.id = cur.lastrowid
    except sqlite3.IntegrityError:
        # Same (source_table, source_row_id, char_start, char_end) already exists
        cur.execute("""
            SELECT id FROM evidence
            WHERE source_table = ? AND source_row_id = ?
              AND COALESCE(char_start, -1) = COALESCE(?, -1)
              AND COALESCE(char_end, -1) = COALESCE(?, -1)
        """, (e.source_table, e.source_row_id, e.char_start, e.char_end))
        e.id = cur.fetchone()[0]
    conn.commit()
    return e


def attach_evidence_to_argument(
    db: Database, argument_id: int, evidence_id: int,
    *, role: EvidenceRole = EvidenceRole.SUPPORTS,
    display_order: int = 0, notes: Optional[str] = None,
) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO argument_evidence
        (argument_id, evidence_id, role, display_order, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (argument_id, evidence_id, role.value, display_order, notes))
    conn.commit()


def detach_evidence_from_argument(db: Database, argument_id: int,
                                    evidence_id: int) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM argument_evidence
        WHERE argument_id = ? AND evidence_id = ?
    """, (argument_id, evidence_id))
    conn.commit()


def list_evidence_for_argument(db: Database,
                                 argument_id: int) -> list[dict]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.id, e.evidence_kind, e.source_table, e.source_row_id,
               e.char_start, e.char_end, e.snippet, e.source_hash,
               ae.role, ae.display_order, ae.notes
        FROM evidence e
        JOIN argument_evidence ae ON ae.evidence_id = e.id
        WHERE ae.argument_id = ?
        ORDER BY ae.display_order, ae.added_at
    """, (argument_id,))
    out = []
    for r in cur.fetchall():
        out.append({
            "evidence": Evidence(
                id=r[0], evidence_kind=EvidenceKind(r[1]),
                source_table=r[2], source_row_id=r[3],
                char_start=r[4], char_end=r[5], snippet=r[6],
                source_hash=r[7],
            ),
            "role": EvidenceRole(r[8]),
            "display_order": r[9],
            "notes": r[10],
        })
    return out
