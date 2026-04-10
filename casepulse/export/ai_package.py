"""AI Analysis Package — export everything in a format optimized for Claude/AI consumption."""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from casepulse.storage.database import Database
from casepulse.config import get_data_dir


def build_ai_package(db: Database, output_dir: str,
                     case_name: str = "",
                     my_emails: list[str] = None,
                     date_start: str = "", date_end: str = "",
                     include_chats: bool = True,
                     include_documents: bool = True,
                     progress_cb=None) -> dict:
    """Build a complete AI analysis package.

    Creates:
    - MEGA_FILE.md — single file with everything for 1M context window
    - INDEX.md — case summary and file listing
    - INSTRUCTIONS.md — how to analyze this data
    - emails/ — individual markdown files per email
    - chats/ — WhatsApp conversations by month
    - documents/ — extracted text from imported documents
    - analysis/ — timeline + contradiction report if available
    - attachments/ — copies of key attachments

    Returns: {total_emails, total_chats, total_documents, mega_file_size, output_dir}
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for sub in ["emails", "chats", "documents", "analysis", "attachments"]:
        (out / sub).mkdir(exist_ok=True)

    if my_emails is None:
        my_emails = [a["email"].lower() for a in db.get_accounts()]

    # ── Gather all data ──
    if progress_cb:
        progress_cb("Gathering emails...")

    emails = db.get_emails(date_start=date_start, date_end=date_end, limit=50000)
    account_map = {a["id"]: a["email"] for a in db.get_accounts()}

    if progress_cb:
        progress_cb(f"Found {len(emails)} emails")

    chats = []
    if include_chats:
        chats = db.get_chat_messages(date_start=date_start, date_end=date_end,
                                      include_system=False, limit=100000)
        if progress_cb:
            progress_cb(f"Found {len(chats)} chat messages")

    documents = []
    if include_documents:
        documents = db.get_documents(ocr_status="done")
        if progress_cb:
            progress_cb(f"Found {len(documents)} documents")

    # Get sender categories
    from casepulse.storage.database import Database as _DB
    sender_info = {}
    for s in db.get_senders():
        cats = _DB.parse_categories(s.get("category"))
        sender_info[s["email"]] = {
            "name": s.get("display_name", ""),
            "categories": cats,
        }

    # Get evidence tags
    cases = db.get_cases()
    tag_map = {}
    for case in cases:
        for t in db.get_evidence_tags_for_case(case["id"]):
            key = f"{t['item_type']}_{t['item_id']}"
            tag_map[key] = t

    # ══════════════════════════════════════════════════
    # BUILD MEGA FILE (single file, everything)
    # ══════════════════════════════════════════════════
    if progress_cb:
        progress_cb("Building mega file...")

    mega = []
    mega.append(f"# CASEPULSE AI ANALYSIS PACKAGE\n")
    mega.append(f"**Case:** {case_name}")
    mega.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    mega.append(f"**Date Range:** {date_start} to {date_end}")
    mega.append(f"**Emails:** {len(emails):,} | **Chat Messages:** {len(chats):,} | **Documents:** {len(documents)}")
    mega.append(f"\n---\n")

    # Instructions section
    mega.append("# HOW TO ANALYZE THIS DATA\n")
    mega.append("""You are analyzing evidence for a legal case. This file contains ALL communications
(emails + chat messages) and document extracts, organized chronologically.

**Key tasks:**
1. Build a chronological timeline of key events
2. Find contradictions in any party's statements across sources
3. Identify evidence of cooperative co-parenting communication
4. Flag any communication that could be relevant to allegations
5. Note where formal documents (affidavits, police reports) contradict the actual communication record
6. Identify patterns — access denial, financial discussions, settlement offers

**Important:**
- Cite specific dates, senders, and subjects when referencing evidence
- Distinguish between what was said in email vs chat (formal vs informal)
- Note the direction of each email (sent vs received)
- Attachments have their extracted text included inline
""")

    # Parties section
    mega.append("\n# PARTIES AND CONTACTS\n")
    mega.append(f"**My email addresses:** {', '.join(my_emails)}\n")

    # Group contacts by category
    cat_groups = {}
    for email_addr, info in sender_info.items():
        if email_addr.lower() in [e.lower() for e in my_emails]:
            continue
        for cat in info.get("categories", ["other"]):
            if cat not in cat_groups:
                cat_groups[cat] = []
            cat_groups[cat].append(f"{info['name']} ({email_addr})" if info["name"] else email_addr)

    for cat, contacts in sorted(cat_groups.items()):
        mega.append(f"**{cat}:** {', '.join(contacts)}")
    mega.append("")

    # ── Emails chronologically ──
    mega.append("\n# EMAILS (CHRONOLOGICAL)\n")
    mega.append(f"Total: {len(emails):,} emails\n")

    email_counter = 0
    current_month = ""
    for e in emails:
        dt = e.get("date_received", "") or ""
        month = dt[:7] if dt else ""
        if month and month != current_month:
            current_month = month
            try:
                month_label = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
            except ValueError:
                month_label = month
            mega.append(f"\n## {month_label}\n")

        email_counter += 1
        sender = e.get("sender_email", "")
        sender_name = e.get("sender_name", "")
        subject = e.get("subject", "(no subject)")
        direction = e.get("direction", "")
        body = e.get("body_text", "") or ""
        is_fwd = "[FORWARDED] " if e.get("is_forwarded") else ""
        mailbox = account_map.get(e.get("account_id"), "")

        # Evidence tag
        tag_key = f"email_{e['id']}"
        tag = tag_map.get(tag_key)
        exhibit = f" | Exhibit: {tag['exhibit_label']}" if tag and tag.get("exhibit_label") else ""
        flag = f" | Flag: {tag['flag']}" if tag and tag.get("flag") and tag["flag"] != "none" else ""

        mega.append(f"### [{email_counter}] {dt[:16]} | {direction} | {sender_name or sender}")
        mega.append(f"**From:** {sender_name} <{sender}>")
        mega.append(f"**Subject:** {is_fwd}{subject}")
        mega.append(f"**Date:** {dt[:19]} | **Direction:** {direction} | **Mailbox:** {mailbox}{exhibit}{flag}")

        if e.get("is_forwarded") and e.get("original_sender"):
            mega.append(f"**Originally from:** {e['original_sender']} ({e.get('original_date', '')})")

        mega.append(f"\n{body}\n")

        # Inline attachment text
        attachments = db.get_attachments_for_email(e["id"])
        if attachments:
            for att in attachments:
                mega.append(f"**Attachment: {att['filename']}**")
                if att.get("extracted_text"):
                    mega.append(f"```\n{att['extracted_text'][:5000]}\n```")
            mega.append("")

        # Also write individual email file
        safe_sender = sender.split("@")[0][:20].replace(".", "_")
        safe_subject = "".join(c if c.isalnum() or c in " _-" else "" for c in subject)[:40].strip().replace(" ", "_")
        email_filename = f"{email_counter:04d}_{dt[:10]}_{safe_sender}_{safe_subject}.md"

        email_md = f"# Email: {subject}\n"
        email_md += f"- **From:** {sender_name} <{sender}>\n"
        email_md += f"- **Date:** {dt[:19]}\n"
        email_md += f"- **Direction:** {direction}\n"
        email_md += f"- **Mailbox:** {mailbox}\n"
        if tag and tag.get("exhibit_label"):
            email_md += f"- **Exhibit:** {tag['exhibit_label']}\n"
        email_md += f"\n---\n\n{body}\n"
        if attachments:
            email_md += "\n## Attachments\n"
            for att in attachments:
                email_md += f"- {att['filename']}\n"
                if att.get("extracted_text"):
                    email_md += f"```\n{att['extracted_text'][:5000]}\n```\n"

        (out / "emails" / email_filename).write_text(email_md, encoding="utf-8")

        if progress_cb and email_counter % 200 == 0:
            progress_cb(f"Processed {email_counter}/{len(emails)} emails...")

    # ── Chat messages ──
    if chats:
        mega.append("\n# CHAT MESSAGES (CHRONOLOGICAL)\n")
        mega.append(f"Total: {len(chats):,} messages\n")

        current_month = ""
        chat_month_lines = {}  # For individual month files

        for m in chats:
            ts = m.get("timestamp", "") or ""
            month = ts[:7] if ts else ""
            sender = m.get("sender", "")
            text = m.get("message_text", "") or ""
            chat_name = m.get("chat_name", "")
            platform = m.get("platform", "")

            if month and month != current_month:
                current_month = month
                try:
                    month_label = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
                except ValueError:
                    month_label = month
                mega.append(f"\n## {month_label} — {chat_name} ({platform})\n")

            mega.append(f"[{ts[:16]}] **{sender}:** {text}")

            # Collect for monthly files
            if month not in chat_month_lines:
                chat_month_lines[month] = []
            chat_month_lines[month].append(f"[{ts[:16]}] {sender}: {text}")

        # Write monthly chat files
        for month, lines in chat_month_lines.items():
            chat_filename = f"chat_{month}.md"
            chat_content = f"# Chat Messages — {month}\n\n" + "\n".join(lines)
            (out / "chats" / chat_filename).write_text(chat_content, encoding="utf-8")

        if progress_cb:
            progress_cb(f"Processed {len(chats):,} chat messages")

    # ── Documents ──
    if documents:
        mega.append("\n# DOCUMENTS\n")
        mega.append(f"Total: {len(documents)} documents\n")

        for doc in documents:
            text = doc.get("extracted_text", "") or ""
            if not text:
                continue
            mega.append(f"\n## Document: {doc['filename']}\n")
            mega.append(f"```\n{text[:10000]}\n```\n")

            # Write individual document file
            doc_filename = f"{doc['filename']}.md"
            doc_content = f"# Document: {doc['filename']}\n\n{text}"
            (out / "documents" / doc_filename).write_text(doc_content, encoding="utf-8")

        if progress_cb:
            progress_cb(f"Processed {len(documents)} documents")

    # ── Write mega file ──
    mega_content = "\n".join(mega)
    mega_path = out / "MEGA_FILE.md"
    mega_path.write_text(mega_content, encoding="utf-8")

    if progress_cb:
        progress_cb(f"Mega file: {len(mega_content):,} characters ({len(mega_content) // 4:,} estimated tokens)")

    # ── Write INDEX.md ──
    index = f"""# CasePulse AI Analysis Package

**Case:** {case_name}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Date Range:** {date_start} to {date_end}

## Contents
- **MEGA_FILE.md** — Everything in one file ({len(mega_content):,} chars, ~{len(mega_content) // 4:,} tokens). Upload this to Claude.ai for full-case analysis.
- **emails/** — {len(emails):,} individual email files (one per email)
- **chats/** — {len(chat_month_lines) if chats else 0} monthly chat files
- **documents/** — {len(documents)} document extracts
- **analysis/** — Timeline and contradiction reports (if generated)

## My Email Addresses
{', '.join(my_emails)}

## Key Contacts
"""
    for cat, contacts in sorted(cat_groups.items()):
        index += f"- **{cat}:** {', '.join(contacts[:5])}\n"

    index += f"""
## How to Use

### Option 1: Upload MEGA_FILE.md to Claude.ai
Upload the single mega file. Claude's 1M context window can handle the entire case.
Ask anything — Claude has all emails, chats, and documents in context.

### Option 2: Upload specific files
Upload INDEX.md first for context, then specific email/chat files as needed.

### Option 3: Use with Claude Code
Point Claude Code at this directory: `{output_dir}`
It can read every file and cross-reference.
"""
    (out / "INDEX.md").write_text(index, encoding="utf-8")

    # ── Write INSTRUCTIONS.md ──
    instructions = """# Instructions for AI Analysis

You are analyzing evidence for a family law and criminal defence case.

## Priority Analysis Tasks

### 1. Communication Tone Analysis
- Scan ALL WhatsApp messages for any evidence of abusive, threatening, or controlling language
- Characterize the overall tone: cooperative co-parenting? hostile? neutral?
- Note specific messages that demonstrate cooperative communication about children

### 2. Contradiction Detection
- Compare statements made in formal documents (affidavits, police reports) against actual emails and chats
- Find where the accuser's story changes across different sources
- Note date inconsistencies in allegations

### 3. Access/Custody Timeline
- Build a timeline of all access denial incidents
- Note every time visitation was discussed, agreed, or refused
- Identify patterns

### 4. Financial Analysis
- Extract all financial discussions, amounts, agreements
- Note any discrepancies between stated income and evidence

### 5. Evidence Strength Assessment
For each key finding, rate:
- **Strong:** Direct contradiction with documentary evidence
- **Moderate:** Inconsistency that needs context
- **Weak:** Minor discrepancy

## Citation Format
Always cite: [Email #N, date, sender] or [Chat, date, sender] or [Document: filename]

## Important Notes
- The person asking you is the DEFENDANT — analyze from a defense perspective
- Focus on evidence that contradicts allegations made against them
- Flag anything that supports a motion to amend a no-contact order
- Note cooperative communication as evidence of non-threatening behavior
"""
    (out / "INSTRUCTIONS.md").write_text(instructions, encoding="utf-8")

    # ── Copy key attachments ──
    if progress_cb:
        progress_cb("Copying key attachments...")

    att_count = 0
    for e in emails:
        attachments = db.get_attachments_for_email(e["id"])
        for att in attachments:
            src = att.get("file_path", "")
            if src and Path(src).exists():
                dst = out / "attachments" / att["filename"]
                if not dst.exists():
                    try:
                        shutil.copy2(src, str(dst))
                        att_count += 1
                    except Exception:
                        pass

    mega_size = mega_path.stat().st_size
    est_tokens = len(mega_content) // 4

    if progress_cb:
        progress_cb(
            f"Done! Package at: {output_dir}\n"
            f"Mega file: {mega_size // 1024:,} KB (~{est_tokens:,} tokens)\n"
            f"Files: {len(emails):,} emails, {len(chats):,} chats, {len(documents)} docs, {att_count} attachments"
        )

    return {
        "total_emails": len(emails),
        "total_chats": len(chats),
        "total_documents": len(documents),
        "total_attachments": att_count,
        "mega_file_size": mega_size,
        "estimated_tokens": est_tokens,
        "output_dir": output_dir,
    }
