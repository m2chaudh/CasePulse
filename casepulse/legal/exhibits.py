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


# Legal issue categories for family + criminal cases
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
        ("therapy", "Therapy / Counselling"),
        ("travel", "Travel / Mobility"),
        ("communication", "Communication Issues"),
        ("settlement", "Settlement Discussions"),
        ("court_order", "Court Orders"),
        ("contempt", "Contempt / Non-Compliance"),
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
]
