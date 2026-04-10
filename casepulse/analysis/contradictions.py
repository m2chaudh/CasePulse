"""Contradiction Engine — multi-pass statement extraction and comparison."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Callable, Optional

from casepulse.storage.database import Database
from casepulse.llm.base import LLMProvider


def extract_statements(db: Database, llm: LLMProvider,
                       sender_email: str, sender_name: str = "",
                       batch_size: int = 15,
                       progress_cb: Optional[Callable] = None) -> list[dict]:
    """Pass 1: Extract factual claims and statements from a person's emails.

    Returns list of {date, statement, source_type, source_id, context}
    """
    statements = []

    # Get all emails from this sender
    emails = db.get_emails(sender_email=sender_email, limit=5000)
    if progress_cb:
        progress_cb(f"Found {len(emails)} emails from {sender_name or sender_email}")

    # Process in batches
    for batch_start in range(0, len(emails), batch_size):
        batch = emails[batch_start:batch_start + batch_size]
        if progress_cb:
            progress_cb(
                f"Extracting statements: batch {batch_start // batch_size + 1}/"
                f"{(len(emails) + batch_size - 1) // batch_size} "
                f"({len(statements)} found so far)"
            )

        # Build batch content
        batch_text = ""
        for i, e in enumerate(batch):
            date_str = (e.get("date_received") or "")[:10]
            subject = e.get("subject", "")
            body = (e.get("body_text") or "")[:1000]
            batch_text += f"Email {i+1} (Date: {date_str}, Subject: {subject}):\n{body}\n\n"

        prompt = f"""Extract all factual claims, promises, statements about events, dates, amounts,
and assertions from these emails by {sender_name or sender_email}.

For each statement, output EXACTLY this format (one per line):
DATE | STATEMENT | CATEGORY

Categories: access, custody, financial, incident, promise, legal, communication, other

Example:
2025-01-15 | Claims she never denied access to children | access
2025-01-20 | States income is $45,000 per year | financial
2025-02-01 | Promised to return children by 6pm Sunday | promise

Only extract concrete, specific claims. Skip greetings and filler.

Emails:
{batch_text}"""

        try:
            response = llm.query(
                system_prompt="You extract factual statements from legal case emails. Be precise. Include dates.",
                user_prompt=prompt,
            )

            for line in response.strip().split("\n"):
                line = line.strip()
                if "|" not in line:
                    continue
                parts = line.split("|")
                if len(parts) >= 2:
                    date_part = parts[0].strip()
                    statement = parts[1].strip()
                    category = parts[2].strip().lower() if len(parts) > 2 else "other"

                    if statement and len(statement) > 10:
                        # Find which email this relates to
                        source_email = batch[0]  # Default to first in batch
                        for e in batch:
                            if date_part in (e.get("date_received") or ""):
                                source_email = e
                                break

                        statements.append({
                            "date": date_part,
                            "statement": statement,
                            "category": category,
                            "sender": sender_email,
                            "sender_name": sender_name,
                            "source_type": "email",
                            "source_id": source_email["id"],
                            "source_subject": source_email.get("subject", ""),
                        })

        except Exception as e:
            if progress_cb:
                progress_cb(f"Error on batch: {e}")

    # Also extract from chat messages
    chats = db.get_chat_messages(sender=sender_email, limit=5000)
    if not chats:
        # Try by name match for WhatsApp
        chats = db.get_chat_messages(sender=sender_name, limit=5000) if sender_name else []

    if chats and progress_cb:
        progress_cb(f"Found {len(chats)} chat messages from {sender_name or sender_email}")

    # Group chats into conversation windows for batching
    chat_windows = []
    window = []
    for m in chats:
        if m.get("is_system"):
            continue
        window.append(m)
        if len(window) >= 30:
            chat_windows.append(window)
            window = []
    if window:
        chat_windows.append(window)

    for wi, win in enumerate(chat_windows):
        if progress_cb:
            progress_cb(f"Extracting from chats: window {wi + 1}/{len(chat_windows)}")

        chat_text = ""
        for m in win:
            ts = (m.get("timestamp") or "")[:16]
            sender = m.get("sender", "")
            text = m.get("message_text", "")
            chat_text += f"[{ts}] {sender}: {text}\n"

        prompt = f"""Extract factual claims and statements from these chat messages involving {sender_name or sender_email}.

Format: DATE | STATEMENT | CATEGORY
Categories: access, custody, financial, incident, promise, legal, communication, other

{chat_text}"""

        try:
            response = llm.query(
                system_prompt="You extract factual statements from chat messages for a legal case. Be precise.",
                user_prompt=prompt,
            )

            for line in response.strip().split("\n"):
                line = line.strip()
                if "|" not in line:
                    continue
                parts = line.split("|")
                if len(parts) >= 2:
                    statements.append({
                        "date": parts[0].strip(),
                        "statement": parts[1].strip(),
                        "category": parts[2].strip().lower() if len(parts) > 2 else "other",
                        "sender": sender_email or sender_name,
                        "sender_name": sender_name,
                        "source_type": "chat",
                        "source_id": win[0]["id"],
                        "source_subject": f"Chat: {win[0].get('chat_name', '')}",
                    })

        except Exception as e:
            if progress_cb:
                progress_cb(f"Chat batch error: {e}")

    # Also extract from email attachments (PDFs, Word docs)
    if progress_cb:
        progress_cb(f"Scanning attachments from {sender_name or sender_email}...")

    import sqlite3 as _sql
    _att_conn = _sql.connect(str(db.db_path))
    _att_conn.row_factory = _sql.Row
    att_rows = _att_conn.execute("""
        SELECT a.id, a.filename, a.extracted_text, a.email_id, e.date_received, e.subject
        FROM attachments a
        JOIN emails e ON a.email_id = e.id
        WHERE e.sender_email = ? AND a.extracted_text IS NOT NULL AND a.extracted_text != ''
        ORDER BY e.date_received
    """, (sender_email,)).fetchall()
    _att_conn.close()

    if att_rows:
        if progress_cb:
            progress_cb(f"Found {len(att_rows)} attachments with text from {sender_name or sender_email}")

        for att in att_rows:
            text = att["extracted_text"][:2000]
            if len(text) < 50:
                continue

            date_str = (att["date_received"] or "")[:10]
            prompt = f"""Extract factual claims and allegations from this document attached to an email
from {sender_name or sender_email} dated {date_str}.

Document: {att['filename']}
Content:
{text}

Format: DATE | STATEMENT | CATEGORY
Categories: access, custody, financial, incident, promise, legal, allegation, other"""

            try:
                response = llm.query(
                    system_prompt="You extract factual claims from legal documents. Focus on allegations, dates, and specific claims.",
                    user_prompt=prompt,
                )

                for line in response.strip().split("\n"):
                    line = line.strip()
                    if "|" not in line:
                        continue
                    parts = line.split("|")
                    if len(parts) >= 2 and len(parts[1].strip()) > 10:
                        statements.append({
                            "date": parts[0].strip(),
                            "statement": parts[1].strip(),
                            "category": parts[2].strip().lower() if len(parts) > 2 else "allegation",
                            "sender": sender_email,
                            "sender_name": sender_name,
                            "source_type": "attachment",
                            "source_id": att["email_id"],
                            "source_subject": f"Attachment: {att['filename']} (from: {att['subject']})",
                        })

            except Exception as e:
                if progress_cb:
                    progress_cb(f"Attachment error ({att['filename']}): {e}")

    # Also extract from imported documents
    docs = db.get_documents(ocr_status="done")
    if docs:
        if progress_cb:
            progress_cb(f"Scanning {len(docs)} imported documents...")

        for doc in docs:
            text = doc.get("extracted_text", "")[:2000]
            if len(text) < 50:
                continue

            prompt = f"""Extract factual claims, allegations, and key statements from this document.

Document: {doc['filename']}
Content:
{text}

Format: DATE | STATEMENT | CATEGORY
Categories: access, custody, financial, incident, promise, legal, allegation, police_report, court_order, other"""

            try:
                response = llm.query(
                    system_prompt="You extract factual claims from legal documents. Focus on allegations, police findings, court orders, and specific claims with dates.",
                    user_prompt=prompt,
                )

                for line in response.strip().split("\n"):
                    line = line.strip()
                    if "|" not in line:
                        continue
                    parts = line.split("|")
                    if len(parts) >= 2 and len(parts[1].strip()) > 10:
                        statements.append({
                            "date": parts[0].strip(),
                            "statement": parts[1].strip(),
                            "category": parts[2].strip().lower() if len(parts) > 2 else "other",
                            "sender": "document",
                            "sender_name": doc["filename"],
                            "source_type": "document",
                            "source_id": doc["id"],
                            "source_subject": f"Document: {doc['filename']}",
                        })

            except Exception as e:
                if progress_cb:
                    progress_cb(f"Document error ({doc['filename']}): {e}")

    if progress_cb:
        progress_cb(f"Done: {len(statements)} statements extracted from {sender_name or sender_email} (emails + chats + attachments + documents)")

    return statements


def find_contradictions(llm: LLMProvider, statements: list[dict],
                        person_name: str = "",
                        progress_cb: Optional[Callable] = None) -> list[dict]:
    """Pass 2: Find contradictions within a person's statements.

    Returns list of {statement_a, statement_b, contradiction_type, explanation, severity}
    """
    if len(statements) < 2:
        return []

    if progress_cb:
        progress_cb(f"Analyzing {len(statements)} statements from {person_name} for contradictions...")

    # Build statements text
    stmts_text = ""
    for i, s in enumerate(statements):
        stmts_text += f"{i+1}. [{s['date']}] ({s['category']}) {s['statement']} (Source: {s['source_type']} - {s['source_subject']})\n"

    # If too many statements, batch them
    if len(statements) > 80:
        # Split by category and analyze each
        categories = {}
        for s in statements:
            cat = s.get("category", "other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(s)

        all_contradictions = []
        for cat, cat_stmts in categories.items():
            if len(cat_stmts) < 2:
                continue
            if progress_cb:
                progress_cb(f"Checking {cat}: {len(cat_stmts)} statements...")
            contras = find_contradictions(llm, cat_stmts, person_name, progress_cb=None)
            all_contradictions.extend(contras)

        return all_contradictions

    prompt = f"""Analyze these statements by {person_name} and find ALL contradictions,
inconsistencies, and changing narratives.

For each contradiction found, output EXACTLY this format:
STMT_A_NUM | STMT_B_NUM | TYPE | SEVERITY | EXPLANATION

Types: date_inconsistency, factual_contradiction, changing_narrative, amount_discrepancy, denial_vs_evidence
Severity: high, medium, low

Example:
3 | 12 | factual_contradiction | high | Statement 3 claims "never denied access" but statement 12 says "you can't see them this weekend"

Only report genuine contradictions with clear evidence from the statements.

Statements:
{stmts_text}"""

    contradictions = []
    try:
        response = llm.query(
            system_prompt="You are a legal analyst finding contradictions in witness statements. Be thorough but precise. Only flag genuine contradictions.",
            user_prompt=prompt,
        )

        for line in response.strip().split("\n"):
            line = line.strip()
            if "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 5:
                try:
                    a_idx = int(parts[0]) - 1
                    b_idx = int(parts[1]) - 1
                    if 0 <= a_idx < len(statements) and 0 <= b_idx < len(statements):
                        contradictions.append({
                            "statement_a": statements[a_idx],
                            "statement_b": statements[b_idx],
                            "contradiction_type": parts[2],
                            "severity": parts[3],
                            "explanation": parts[4],
                            "person": person_name,
                        })
                except (ValueError, IndexError):
                    continue

    except Exception as e:
        if progress_cb:
            progress_cb(f"Contradiction analysis error: {e}")

    if progress_cb:
        progress_cb(f"Found {len(contradictions)} contradictions for {person_name}")

    return contradictions


def cross_source_comparison(llm: LLMProvider,
                            email_statements: list[dict],
                            chat_statements: list[dict],
                            person_name: str = "",
                            progress_cb: Optional[Callable] = None) -> list[dict]:
    """Pass 3: Compare what was said in email vs chat."""
    if not email_statements or not chat_statements:
        return []

    if progress_cb:
        progress_cb(f"Comparing {len(email_statements)} email statements vs {len(chat_statements)} chat statements for {person_name}...")

    email_text = "\n".join(f"- [{s['date']}] {s['statement']}" for s in email_statements[:50])
    chat_text = "\n".join(f"- [{s['date']}] {s['statement']}" for s in chat_statements[:50])

    prompt = f"""Compare what {person_name} said in emails vs what they said in chat messages.
Find any contradictions, different versions of events, or things said privately in chat
that contradict their formal email statements.

EMAIL STATEMENTS:
{email_text}

CHAT STATEMENTS:
{chat_text}

For each cross-source contradiction, output:
EMAIL_STATEMENT | CHAT_STATEMENT | EXPLANATION | SEVERITY

Severity: high, medium, low"""

    contradictions = []
    try:
        response = llm.query(
            system_prompt="You compare formal email statements against informal chat messages to find contradictions in a legal case.",
            user_prompt=prompt,
        )

        for line in response.strip().split("\n"):
            line = line.strip()
            if "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                contradictions.append({
                    "email_statement": parts[0],
                    "chat_statement": parts[1],
                    "explanation": parts[2],
                    "severity": parts[3],
                    "person": person_name,
                    "type": "cross_source",
                })

    except Exception as e:
        if progress_cb:
            progress_cb(f"Cross-source error: {e}")

    return contradictions


def run_full_analysis(db: Database, llm: LLMProvider,
                      target_senders: list[dict],
                      batch_size: int = 15,
                      progress_cb: Optional[Callable] = None) -> dict:
    """Run the complete contradiction analysis pipeline.

    Args:
        target_senders: [{email, name, category}] — contacts to analyze
        batch_size: emails per LLM call

    Returns: {
        statements: {sender: [statements]},
        contradictions: {sender: [contradictions]},
        cross_source: {sender: [cross_source_contradictions]},
        summary: str,
    }
    """
    all_statements = {}
    all_contradictions = {}
    all_cross_source = {}

    for i, sender in enumerate(target_senders):
        email = sender.get("email", "")
        name = sender.get("name", sender.get("display_name", ""))
        if progress_cb:
            progress_cb(f"\n=== Analyzing {name or email} ({i+1}/{len(target_senders)}) ===")

        # Pass 1: Extract statements
        stmts = extract_statements(db, llm, email, name, batch_size, progress_cb)
        all_statements[email] = stmts

        if len(stmts) < 2:
            if progress_cb:
                progress_cb(f"Only {len(stmts)} statements — skipping contradiction check")
            continue

        # Pass 2: Find contradictions
        contras = find_contradictions(llm, stmts, name or email, progress_cb)
        all_contradictions[email] = contras

        # Pass 3: Cross-source (email vs chat)
        email_stmts = [s for s in stmts if s["source_type"] == "email"]
        chat_stmts = [s for s in stmts if s["source_type"] == "chat"]
        if email_stmts and chat_stmts:
            cross = cross_source_comparison(llm, email_stmts, chat_stmts, name or email, progress_cb)
            all_cross_source[email] = cross

    # Build summary
    total_stmts = sum(len(s) for s in all_statements.values())
    total_contras = sum(len(c) for c in all_contradictions.values())
    total_cross = sum(len(c) for c in all_cross_source.values())

    # Pass 4: Cross-reference attachments vs statements
    # Compare what's in documents (affidavits, police reports) against email/chat statements
    doc_stmts = []
    for stmts in all_statements.values():
        doc_stmts.extend([s for s in stmts if s["source_type"] in ("attachment", "document")])

    non_doc_stmts = []
    for stmts in all_statements.values():
        non_doc_stmts.extend([s for s in stmts if s["source_type"] in ("email", "chat")])

    doc_vs_communication = []
    if doc_stmts and non_doc_stmts and progress_cb:
        progress_cb("Pass 4: Comparing document claims against email/chat evidence...")
        doc_text = "\n".join(f"- [{s['date']}] [{s['source_subject']}] {s['statement']}" for s in doc_stmts[:60])
        comm_text = "\n".join(f"- [{s['date']}] [{s['source_type']}] {s['statement']}" for s in non_doc_stmts[:60])

        prompt = f"""Compare claims made in legal DOCUMENTS (affidavits, police reports, court filings)
against what was actually said in EMAILS and CHAT messages.

Find where a document makes a claim that is contradicted by the actual email/chat evidence.
This is critical for defense — it shows where formal allegations don't match the real communication record.

DOCUMENT CLAIMS (from affidavits, police reports, court orders):
{doc_text}

ACTUAL EMAIL/CHAT EVIDENCE:
{comm_text}

For each contradiction, output:
DOCUMENT_CLAIM | ACTUAL_EVIDENCE | TYPE | SEVERITY | DEFENSE_VALUE

Types: allegation_vs_evidence, date_mismatch, event_not_supported, exaggeration, omission
Severity: high, medium, low
Defense_value: brief note on why this helps the defense"""

        try:
            response = llm.query(
                system_prompt="You are a criminal defense analyst comparing formal allegations against actual communication evidence. Focus on where allegations are unsupported or contradicted by real evidence.",
                user_prompt=prompt,
            )

            for line in response.strip().split("\n"):
                line = line.strip()
                if "|" not in line:
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 5:
                    doc_vs_communication.append({
                        "document_claim": parts[0],
                        "actual_evidence": parts[1],
                        "type": parts[2],
                        "severity": parts[3],
                        "defense_value": parts[4],
                    })

        except Exception as e:
            if progress_cb:
                progress_cb(f"Document vs communication error: {e}")

    return {
        "statements": all_statements,
        "contradictions": all_contradictions,
        "cross_source": all_cross_source,
        "doc_vs_communication": doc_vs_communication,
        "total_statements": total_stmts,
        "total_contradictions": total_contras,
        "total_cross_source": total_cross,
        "total_doc_conflicts": len(doc_vs_communication),
        "analyzed_contacts": len(target_senders),
    }
