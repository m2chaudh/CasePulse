import hashlib
import sqlite3
from typing import Optional

from casepulse.case_theory.models import (
    Theme, Allegation, AllegationStatus,
    Contradiction, ContradictionStatus,
    Argument, ArgumentType, Strength,
    Evidence, EvidenceKind, EvidenceRole,
    Witness, WitnessType, WitnessStatus,
    WitnessStatement, WitnessStatementStatus,
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
    """Compute SHA-256 of the source row's primary text.

    For chat_messages the canonical formula is sha256(f"{timestamp}|{sender}|{message_text}")
    — matching both the importer (casepulse/chat_engine/importer.py) and the migration
    backfill in _run_migrations. This makes the hash collision-resistant even when multiple
    senders send the same text in the same chat.

    For all other source tables, sha256(primary_text_column) is used.
    """
    conn = db._get_conn()
    cur = conn.cursor()

    if source_table == "chat_messages":
        cur.execute(
            "SELECT timestamp, sender, message_text FROM chat_messages WHERE id = ?",
            (source_row_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        ts, sender, text = row[0], row[1], row[2]
        return hashlib.sha256(
            f"{ts or ''}|{sender or ''}|{text or ''}".encode("utf-8")
        ).hexdigest()

    text_cols = {
        "emails": "body_text",
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


# ---------------------------------------------------------------------------
# Evidence hash verification
# ---------------------------------------------------------------------------

def verify_evidence_hash(db: Database, evidence_id: int) -> bool:
    """Re-compute source hash and compare to stored Evidence.source_hash.

    Returns True if match (or if both None — nothing to compare),
    False on mismatch.
    """
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT source_table, source_row_id, source_hash FROM evidence
        WHERE id = ?
    """, (evidence_id,))
    row = cur.fetchone()
    if not row:
        return False
    source_table, source_row_id, stored_hash = row
    fresh = _compute_source_hash(db, source_table, source_row_id)
    if stored_hash is None and fresh is None:
        return True
    return stored_hash == fresh


# ---------------------------------------------------------------------------
# Argument picker (for UI dropdowns)
# ---------------------------------------------------------------------------

def list_recent_arguments_for_picker(db: Database, case_id: int,
                                      limit: int = 50) -> list[dict]:
    """Return arguments for picker UIs. Most-recently-edited first.

    Each row: {argument_id, argument_title, contradiction_id,
              contradiction_headline, theme_title}.
    """
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, a.title, c.id, c.headline, t.title
        FROM arguments a
        JOIN contradictions c ON c.id = a.contradiction_id
        LEFT JOIN themes t ON t.id = c.theme_id
        WHERE c.case_id = ?
        ORDER BY a.updated_at DESC
        LIMIT ?
    """, (case_id, limit))
    return [{
        "argument_id": r[0],
        "argument_title": r[1],
        "contradiction_id": r[2],
        "contradiction_headline": r[3],
        "theme_title": r[4],
    } for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Evidence snippet refinement
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Photo metadata attestations
# ---------------------------------------------------------------------------

def record_attestation(
    db: Database, *,
    photo_metadata_id: int,
    field_name: str,
    status: str,  # "struck" | "attested"
    reason: "str | None" = None,
    attestation_text: "str | None" = None,
    attested_by: "str | None" = None,
    attested_at: "str | None" = None,
) -> int:
    """Insert a metadata_attestations row. Returns the new row id."""
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO metadata_attestations
        (photo_metadata_id, field_name, status, reason,
         attestation_text, attested_by, attested_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (photo_metadata_id, field_name, status, reason,
          attestation_text, attested_by, attested_at))
    conn.commit()
    return cur.lastrowid


def list_attestations_for_metadata(db: Database, *,
                                    photo_metadata_id: int) -> list[dict]:
    """Return all attestation rows for a photo_metadata record, ordered by creation time."""
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, photo_metadata_id, field_name, status, reason,
               attestation_text, attested_by, attested_at, created_at
        FROM metadata_attestations
        WHERE photo_metadata_id = ?
        ORDER BY created_at
    """, (photo_metadata_id,))
    return [{
        "id": r[0], "photo_metadata_id": r[1], "field_name": r[2],
        "status": r[3], "reason": r[4], "attestation_text": r[5],
        "attested_by": r[6], "attested_at": r[7], "created_at": r[8],
    } for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Evidence snippet refinement
# ---------------------------------------------------------------------------

def update_evidence_snippet(db: Database, evidence_id: int, *,
                             char_start: int | None = None,
                             char_end: int | None = None,
                             snippet: str | None = None) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE evidence SET char_start = ?, char_end = ?, snippet = ?
        WHERE id = ?
    """, (char_start, char_end, snippet, evidence_id))
    conn.commit()


# ---------------------------------------------------------------------------
# Witness CRUD
# ---------------------------------------------------------------------------

def create_witness(db: Database, witness: Witness) -> Witness:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO witnesses
            (case_id, name, relationship, witness_type, contact_info, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        witness.case_id, witness.name, witness.relationship,
        witness.witness_type.value if witness.witness_type else None,
        witness.contact_info,
        witness.status.value,
        witness.notes,
    ))
    conn.commit()
    witness.id = cur.lastrowid
    return witness


def get_witness(db: Database, witness_id: int) -> Optional[Witness]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, case_id, name, relationship, witness_type, contact_info,
               status, notes, created_at, updated_at
        FROM witnesses WHERE id = ?
    """, (witness_id,))
    row = cur.fetchone()
    if not row:
        return None
    return Witness(
        id=row[0], case_id=row[1], name=row[2], relationship=row[3],
        witness_type=WitnessType(row[4]) if row[4] else None,
        contact_info=row[5],
        status=WitnessStatus(row[6]),
        notes=row[7],
    )


def list_witnesses(db: Database, case_id: int) -> list[Witness]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, case_id, name, relationship, witness_type, contact_info,
               status, notes, created_at, updated_at
        FROM witnesses WHERE case_id = ?
        ORDER BY name, id
    """, (case_id,))
    return [Witness(
        id=r[0], case_id=r[1], name=r[2], relationship=r[3],
        witness_type=WitnessType(r[4]) if r[4] else None,
        contact_info=r[5],
        status=WitnessStatus(r[6]),
        notes=r[7],
    ) for r in cur.fetchall()]


def update_witness(db: Database, witness: Witness) -> Witness:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE witnesses
        SET name = ?, relationship = ?, witness_type = ?, contact_info = ?,
            status = ?, notes = ?, updated_at = datetime('now')
        WHERE id = ?
    """, (
        witness.name, witness.relationship,
        witness.witness_type.value if witness.witness_type else None,
        witness.contact_info,
        witness.status.value,
        witness.notes,
        witness.id,
    ))
    conn.commit()
    return witness


def delete_witness(db: Database, witness_id: int) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM witnesses WHERE id = ?", (witness_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# WitnessStatement CRUD
# ---------------------------------------------------------------------------

def create_witness_statement(db: Database,
                              statement: WitnessStatement) -> WitnessStatement:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO witness_statements
            (witness_id, statement_text, statement_date,
             contradiction_id, argument_id, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        statement.witness_id, statement.statement_text, statement.statement_date,
        statement.contradiction_id, statement.argument_id,
        statement.status.value,
    ))
    conn.commit()
    statement.id = cur.lastrowid
    return statement


def _row_to_statement(r) -> WitnessStatement:
    return WitnessStatement(
        id=r[0], witness_id=r[1], statement_text=r[2],
        statement_date=r[3], contradiction_id=r[4], argument_id=r[5],
        status=WitnessStatementStatus(r[6]),
    )


def list_statements_for_witness(db: Database,
                                 witness_id: int) -> list[WitnessStatement]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, witness_id, statement_text, statement_date,
               contradiction_id, argument_id, status
        FROM witness_statements WHERE witness_id = ?
        ORDER BY id
    """, (witness_id,))
    return [_row_to_statement(r) for r in cur.fetchall()]


def list_statements_for_argument(db: Database,
                                  argument_id: int) -> list[WitnessStatement]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, witness_id, statement_text, statement_date,
               contradiction_id, argument_id, status
        FROM witness_statements WHERE argument_id = ?
        ORDER BY id
    """, (argument_id,))
    return [_row_to_statement(r) for r in cur.fetchall()]


def update_witness_statement(db: Database,
                              statement: WitnessStatement) -> WitnessStatement:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE witness_statements
        SET statement_text = ?, statement_date = ?,
            contradiction_id = ?, argument_id = ?, status = ?
        WHERE id = ?
    """, (
        statement.statement_text, statement.statement_date,
        statement.contradiction_id, statement.argument_id,
        statement.status.value,
        statement.id,
    ))
    conn.commit()
    return statement


def delete_witness_statement(db: Database, statement_id: int) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM witness_statements WHERE id = ?", (statement_id,))
    conn.commit()
