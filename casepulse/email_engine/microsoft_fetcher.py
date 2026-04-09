"""Fetch emails from Microsoft Graph API (Outlook/Hotmail)."""
from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Callable, Optional

import requests

from casepulse.config import get_data_dir
from casepulse.storage.database import Database

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Fields to request from the API
EMAIL_FIELDS = (
    "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
    "sentDateTime,body,hasAttachments,importance,internetMessageHeaders,"
    "parentFolderId,internetMessageId,isDraft,isRead"
)


class MicrosoftFetcher:
    """Fetches emails from a Microsoft account via Graph API."""

    def __init__(self, access_token: str, account_id: int, db: Database):
        self.access_token = access_token
        self.account_id = account_id
        self.db = db
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        })

    def _graph_get(self, url: str, params: Optional[dict] = None) -> dict:
        """Make a GET request to Graph API with retry logic."""
        for attempt in range(3):
            resp = self._session.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                # Rate limited - wait and retry
                retry_after = int(resp.headers.get("Retry-After", 5))
                time.sleep(retry_after)
                continue
            if resp.status_code == 401:
                raise PermissionError("Access token expired. Please re-authenticate.")
            resp.raise_for_status()
            return resp.json()
        raise Exception("Rate limited after 3 retries")

    def scan_senders(self, date_start: str, date_end: str,
                     progress_cb: Optional[Callable] = None) -> list[dict]:
        """Scan all unique senders/recipients in date range without storing full emails.

        Returns list of {email, name, count} dicts.
        """
        senders = {}
        url = f"{GRAPH_BASE}/me/messages"
        params = {
            "$filter": (
                f"receivedDateTime ge {date_start}T00:00:00Z "
                f"and receivedDateTime le {date_end}T23:59:59Z"
            ),
            "$select": "from,toRecipients,ccRecipients,sentDateTime",
            "$orderby": "receivedDateTime asc",
            "$top": 250,
        }

        page = 0
        while url:
            data = self._graph_get(url, params if page == 0 else None)
            messages = data.get("value", [])

            for msg in messages:
                # Sender
                frm = msg.get("from", {}).get("emailAddress", {})
                sender_email = frm.get("address", "").lower()
                sender_name = frm.get("name", "")
                if sender_email:
                    if sender_email not in senders:
                        senders[sender_email] = {"email": sender_email, "name": sender_name, "count": 0}
                    senders[sender_email]["count"] += 1

                # Recipients
                for recip in msg.get("toRecipients", []):
                    addr = recip.get("emailAddress", {})
                    email = addr.get("address", "").lower()
                    name = addr.get("name", "")
                    if email:
                        if email not in senders:
                            senders[email] = {"email": email, "name": name, "count": 0}
                        senders[email]["count"] += 1

                # CC
                for recip in msg.get("ccRecipients", []):
                    addr = recip.get("emailAddress", {})
                    email = addr.get("address", "").lower()
                    name = addr.get("name", "")
                    if email:
                        if email not in senders:
                            senders[email] = {"email": email, "name": name, "count": 0}
                        senders[email]["count"] += 1

            if progress_cb:
                progress_cb(f"Scanned {len(messages)} emails on page {page + 1}... found {len(senders)} contacts")

            url = data.get("@odata.nextLink")
            page += 1

        return sorted(senders.values(), key=lambda x: x["count"], reverse=True)

    def fetch_emails(self, date_start: str, date_end: str,
                     sender_emails: Optional[list[str]] = None,
                     keywords: Optional[list[str]] = None,
                     progress_cb: Optional[Callable] = None) -> dict:
        """Fetch emails matching criteria and store in database.

        Returns summary dict with counts.
        """
        sync_id = self.db.start_sync(self.account_id)
        total_fetched = 0
        total_attachments = 0
        total_skipped = 0
        errors = []

        try:
            # Fetch from Inbox and Sent Items
            for folder, direction in [("inbox", "received"), ("sentitems", "sent")]:
                url = f"{GRAPH_BASE}/me/mailFolders/{folder}/messages"
                params = {
                    "$filter": (
                        f"receivedDateTime ge {date_start}T00:00:00Z "
                        f"and receivedDateTime le {date_end}T23:59:59Z"
                    ),
                    "$select": EMAIL_FIELDS,
                    "$orderby": "receivedDateTime asc",
                    "$top": 100,
                }

                page = 0
                while url:
                    data = self._graph_get(url, params if page == 0 else None)
                    messages = data.get("value", [])

                    for msg in messages:
                        try:
                            result = self._process_message(msg, direction, sender_emails, keywords)
                            if result == "stored":
                                total_fetched += 1
                                if msg.get("hasAttachments"):
                                    att_count = self._fetch_attachments(msg["id"], total_fetched)
                                    total_attachments += att_count
                            elif result == "skipped":
                                total_skipped += 1
                        except Exception as e:
                            errors.append(f"Error processing {msg.get('id', '?')}: {str(e)}")

                    if progress_cb:
                        progress_cb(
                            f"[{folder}] Page {page + 1}: "
                            f"{total_fetched} stored, {total_skipped} skipped, "
                            f"{total_attachments} attachments"
                        )

                    url = data.get("@odata.nextLink")
                    page += 1

            self.db.update_sync(sync_id, total_fetched, total_attachments, total_skipped)
            self.db.complete_sync(sync_id, "completed", "; ".join(errors) if errors else "")
            self.db.update_last_synced(self.account_id)

        except Exception as e:
            self.db.complete_sync(sync_id, "failed", str(e))
            raise

        return {
            "emails_fetched": total_fetched,
            "attachments_downloaded": total_attachments,
            "duplicates_skipped": total_skipped,
            "errors": errors,
        }

    def _process_message(self, msg: dict, direction: str,
                         sender_emails: Optional[list[str]],
                         keywords: Optional[list[str]]) -> str:
        """Process a single message. Returns 'stored', 'skipped', or 'filtered'."""
        # Skip drafts
        if msg.get("isDraft"):
            return "skipped"

        # Extract sender
        frm = msg.get("from", {}).get("emailAddress", {})
        sender_email = frm.get("address", "").lower()
        sender_name = frm.get("name", "")

        # Extract recipients
        recipients = []
        for r in msg.get("toRecipients", []):
            addr = r.get("emailAddress", {})
            recipients.append({
                "email": addr.get("address", "").lower(),
                "name": addr.get("name", ""),
            })

        cc = []
        for r in msg.get("ccRecipients", []):
            addr = r.get("emailAddress", {})
            cc.append({
                "email": addr.get("address", "").lower(),
                "name": addr.get("name", ""),
            })

        # Filter by sender if specified
        if sender_emails:
            all_addrs = [sender_email] + [r["email"] for r in recipients] + [r["email"] for r in cc]
            if not any(addr in sender_emails for addr in all_addrs):
                return "filtered"

        # Extract body
        body = msg.get("body", {})
        body_text = ""
        body_html = ""
        if body.get("contentType") == "html":
            body_html = body.get("content", "")
            # Convert HTML to text
            from casepulse.email_engine.parser import html_to_text
            body_text = html_to_text(body_html)
        else:
            body_text = body.get("content", "")

        # Filter by keywords if specified
        if keywords:
            searchable = f"{msg.get('subject', '')} {body_text}".lower()
            if not any(kw.lower() in searchable for kw in keywords):
                return "filtered"

        # Check for duplicate by message ID (same account)
        message_id = msg.get("internetMessageId", "")
        if message_id and self.db.email_exists(message_id, self.account_id):
            return "skipped"

        # Compute content hash for cross-account dedup
        subject = msg.get("subject", "")
        content_hash = Database.compute_content_hash(body_text, subject, sender_email)

        # Check for cross-account duplicate (same email in another mailbox)
        existing_id = self.db.content_hash_exists(content_hash)
        if existing_id:
            return "skipped"

        # Extract internet message headers
        headers = {}
        for h in msg.get("internetMessageHeaders", []):
            headers[h.get("name", "")] = h.get("value", "")

        # Parse forwarded message info
        from casepulse.email_engine.parser import detect_forwarded_content
        is_forwarded, original_sender, original_date = detect_forwarded_content(
            subject, body_text, headers
        )

        # Store email
        self.db.insert_email(
            message_id=message_id,
            content_hash=content_hash,
            account_id=self.account_id,
            subject=subject,
            sender_email=sender_email,
            sender_name=sender_name,
            recipients=recipients,
            cc=cc,
            date_sent=msg.get("sentDateTime"),
            date_received=msg.get("receivedDateTime"),
            body_text=body_text,
            body_html=body_html,
            folder=direction,
            is_forwarded=is_forwarded,
            is_reply=subject.lower().startswith("re:"),
            original_sender=original_sender,
            original_date=original_date,
            direction=direction,
            raw_headers=headers,
            importance=msg.get("importance", "normal"),
            has_attachments=msg.get("hasAttachments", False),
            provider_msg_id=msg.get("id"),
        )

        # Register sender in senders table
        self.db.upsert_sender(sender_email, sender_name)
        for r in recipients + cc:
            if r["email"]:
                self.db.upsert_sender(r["email"], r["name"])

        return "stored"

    def _fetch_attachments(self, message_graph_id: str, email_db_id: int) -> int:
        """Download attachments for a message. Returns count."""
        url = f"{GRAPH_BASE}/me/messages/{message_graph_id}/attachments"
        data = self._graph_get(url)
        attachments = data.get("value", [])
        count = 0

        att_dir = get_data_dir() / "attachments" / str(email_db_id)
        att_dir.mkdir(parents=True, exist_ok=True)

        for att in attachments:
            if att.get("@odata.type") == "#microsoft.graph.fileAttachment":
                filename = att.get("name", "unknown")
                content_type = att.get("contentType", "application/octet-stream")
                content_bytes = att.get("contentBytes", "")

                if not content_bytes:
                    continue

                import base64
                raw = base64.b64decode(content_bytes)
                file_path = att_dir / filename
                file_path.write_bytes(raw)

                content_hash = hashlib.sha256(raw).hexdigest()

                # Extract text from documents
                extracted_text = ""
                from casepulse.attachments.extractor import extract_text
                extracted_text = extract_text(str(file_path), content_type)

                self.db.insert_attachment(
                    email_id=email_db_id,
                    filename=filename,
                    content_type=content_type,
                    size_bytes=len(raw),
                    file_path=str(file_path),
                    extracted_text=extracted_text,
                    content_hash=content_hash,
                )
                count += 1

        return count
