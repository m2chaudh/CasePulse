"""Exhibit numbering systems for court filings."""
from __future__ import annotations

from casepulse.storage.database import Database


def generate_exhibit_label(case_id: int, db: Database) -> str:
    """Generate the next exhibit label for a case using its configured format."""
    case = db.get_case(case_id)
    if not case:
        return ""

    fmt = case.get("exhibit_format", "alpha")
    prefix = case.get("exhibit_prefix", "")
    num = db.get_next_exhibit_number(case_id)

    if fmt == "alpha":
        label = _num_to_alpha(num)
        return f"Exhibit {prefix}{label}" if not prefix else f"Exhibit {prefix}-{label}"
    elif fmt == "bates":
        bates_prefix = prefix or "BATES"
        return f"{bates_prefix}_{num:05d}"
    elif fmt == "numerical":
        return f"Exhibit {prefix}{num}" if not prefix else f"Exhibit {prefix}-{num}"
    elif fmt == "system":
        # System-generated: Page {prefix}-{num}
        return f"Page {prefix}-{num}" if prefix else f"Page {num}"
    else:
        return f"Exhibit {num}"


def _num_to_alpha(n: int) -> str:
    """Convert number to alphabetical exhibit label: 1=A, 2=B, ..., 26=Z, 27=AA, ..."""
    result = ""
    while n > 0:
        n -= 1
        result = chr(65 + (n % 26)) + result
        n //= 26
    return result


def preview_exhibit_labels(case_id: int, db: Database, count: int = 5) -> list[str]:
    """Preview the next N exhibit labels without consuming them."""
    case = db.get_case(case_id)
    if not case:
        return []

    fmt = case.get("exhibit_format", "alpha")
    prefix = case.get("exhibit_prefix", "")
    start = case.get("next_exhibit_num", 1)

    labels = []
    for i in range(count):
        num = start + i
        if fmt == "alpha":
            label = _num_to_alpha(num)
            labels.append(f"Exhibit {prefix}{label}" if not prefix else f"Exhibit {prefix}-{label}")
        elif fmt == "bates":
            bates_prefix = prefix or "BATES"
            labels.append(f"{bates_prefix}_{num:05d}")
        elif fmt == "numerical":
            labels.append(f"Exhibit {prefix}{num}" if not prefix else f"Exhibit {prefix}-{num}")
        elif fmt == "system":
            labels.append(f"Page {prefix}-{num}" if prefix else f"Page {num}")

    return labels


# Legal issue categories for family + criminal cases.
# These are the built-in defaults. Users can add custom issues through the
# Cases page; merged via `get_issues_for_type()` below.
LEGAL_ISSUES = {
    "family": [
        ("custody", "Custody / Decision-Making"),
        ("access", "Access / Parenting Time"),
        ("access_denial", "Access Denial"),
        ("financial", "Financial Disclosure"),
        ("support", "Child/Spousal Support"),
        ("property", "Property Division"),
        ("domestic_violence", "Domestic Violence"),
        ("false_allegations", "False Allegations"),
        ("parenting_coord", "Parenting Coordination"),
        ("cas_involvement", "CAS Involvement"),
        ("ocl_involvement", "OCL (Office of the Children's Lawyer)"),
        ("therapy", "Therapy / Counselling"),
        ("travel", "Travel / Mobility"),
        ("communication", "Communication Issues"),
        ("settlement", "Settlement Discussions"),
        ("court_order", "Court Orders"),
        ("contempt", "Contempt / Non-Compliance"),
        ("counsel_correspondence", "Counsel Correspondence"),
        ("lawyer_change", "Change of Lawyer / Counsel"),
        ("court_filing", "Court Filing / Pleading"),
    ],
    "criminal": [
        ("false_accusation", "False Accusation Defence"),
        ("alibi", "Alibi / Whereabouts"),
        ("disclosure", "Crown Disclosure"),
        ("bail_conditions", "Bail Conditions"),
        ("witness", "Witness Statements"),
        ("police_report", "Police Reports"),
        ("charges", "Charges / Information"),
        ("statement_inconsistency", "Statement Inconsistency"),
        ("character", "Character Evidence"),
        ("timeline_dispute", "Timeline / Dates in Dispute"),
        ("counsel_correspondence", "Counsel Correspondence"),
        ("lawyer_change", "Change of Lawyer / Counsel"),
        ("court_filing", "Court Filing / Pleading"),
    ],
}

# Evidence flags
FLAGS = [
    ("none", "No Flag"),
    ("critical", "Critical Evidence"),
    ("needs_review", "Needs Review"),
    ("for_lawyer", "For Lawyer"),
    ("privileged", "Privileged (Attorney-Client)"),
    ("corroborating", "Corroborating"),
    ("contradicting", "Contradicting"),
    ("affidavit", "Sworn Affidavit"),
    ("court_filed", "Filed with Court"),
]


# ---------------------------------------------------------------------------
# Custom issues + flags (persisted in app_settings)
# ---------------------------------------------------------------------------

import json
from typing import Optional


def _load_custom(db, key: str) -> list:
    try:
        with db._get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?", (key,),
            ).fetchone()
        if row and row["value"]:
            data = json.loads(row["value"])
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def _save_custom(db, key: str, items: list) -> None:
    with db._get_conn() as conn:
        conn.execute(
            """INSERT INTO app_settings (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, json.dumps(items)),
        )


def get_custom_issues(db, case_type: str) -> list[tuple[str, str]]:
    raw = _load_custom(db, f"legal_issues.custom_{case_type}")
    return [(d["code"], d["label"]) for d in raw if "code" in d and "label" in d]


def get_custom_flags(db) -> list[tuple[str, str]]:
    raw = _load_custom(db, "flags.custom")
    return [(d["code"], d["label"]) for d in raw if "code" in d and "label" in d]


def get_issues_for_type(db, case_type: str) -> list[tuple[str, str]]:
    """Return built-in + user-added issues for a case type."""
    builtin = list(LEGAL_ISSUES.get(case_type, []))
    builtin_codes = {c for c, _ in builtin}
    custom = [c for c in get_custom_issues(db, case_type) if c[0] not in builtin_codes]
    return builtin + custom


def get_flags(db) -> list[tuple[str, str]]:
    """Return built-in + user-added flags."""
    builtin_codes = {c for c, _ in FLAGS}
    custom = [c for c in get_custom_flags(db) if c[0] not in builtin_codes]
    return list(FLAGS) + custom


def add_custom_issue(db, case_type: str, code: str, label: str) -> None:
    code = code.strip().lower().replace(" ", "_")
    label = label.strip()
    if not code or not label:
        raise ValueError("code and label are required")
    if code in {c for c, _ in LEGAL_ISSUES.get(case_type, [])}:
        raise ValueError(f"'{code}' is a built-in issue and can't be re-added")
    items = _load_custom(db, f"legal_issues.custom_{case_type}")
    if any(d.get("code") == code for d in items):
        return  # already custom
    items.append({"code": code, "label": label})
    _save_custom(db, f"legal_issues.custom_{case_type}", items)


def remove_custom_issue(db, case_type: str, code: str) -> None:
    items = _load_custom(db, f"legal_issues.custom_{case_type}")
    items = [d for d in items if d.get("code") != code]
    _save_custom(db, f"legal_issues.custom_{case_type}", items)


def add_custom_flag(db, code: str, label: str) -> None:
    code = code.strip().lower().replace(" ", "_")
    label = label.strip()
    if not code or not label:
        raise ValueError("code and label are required")
    if code in {c for c, _ in FLAGS}:
        raise ValueError(f"'{code}' is a built-in flag and can't be re-added")
    items = _load_custom(db, "flags.custom")
    if any(d.get("code") == code for d in items):
        return
    items.append({"code": code, "label": label})
    _save_custom(db, "flags.custom", items)


def remove_custom_flag(db, code: str) -> None:
    items = _load_custom(db, "flags.custom")
    items = [d for d in items if d.get("code") != code]
    _save_custom(db, "flags.custom", items)
