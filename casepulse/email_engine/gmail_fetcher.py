"""Fetch emails from Gmail API."""
from __future__ import annotations

import base64
import hashlib
import time
from typing import Callable, Optional

from casepulse.config import get_data_dir
from casepulse.storage.database import Database


class GmailFetcher:
    """Fetches emails from a Gmail account via Gmail API."""

    def __init__(self, service, account_id: int, db: Database):
        """
        Args:
            service: Authenticated Gmail API service (from googleapiclient.discovery.build)
            account_id: Database ID for this account
            db: Database instance
        """
        self.service = service
        self.account_id = account_id
        self.db = db

    def scan_senders(self, date_start: str, date_end: str,
                     progress_cb: Optional[Callable] = None) -> list[dict]:
        """Scan all unique senders/recipients in date range.

        Date format: YYYY-MM-DD
        Uses Gmail batch API for speed (up to 100 messages per batch request).
        """
        # Convert dates to Gmail search format (YYYY/MM/DD)
        start = date_start.replace("-", "/")
        end = date_end.replace("-", "/")
        query = f"after:{start} before:{end}"

        contacts = {}
        page_token = None
        total_scanned = 0
        total_listed = 0

        # First, collect all message IDs
        if progress_cb:
            progress_cb("Listing emails in date range...")

        all_msg_ids = []
        while True:
            results = self.service.users().messages().list(
                userId="me",
                q=query,
                pageToken=page_token,
                maxResults=500,
            ).execute()

            messages = results.get("messages", [])
            if not messages:
                break

            all_msg_ids.extend([m["id"] for m in messages])
            total_listed += len(messages)

            if progress_cb:
                progress_cb(f"Found {total_listed} emails so far...")

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        if progress_cb:
            progress_cb(f"Total: {len(all_msg_ids)} emails to scan. Fetching headers...")

        # Fetch headers in batches using Gmail batch API
        BATCH_SIZE = 50

        for batch_start in range(0, len(all_msg_ids), BATCH_SIZE):
            batch_ids = all_msg_ids[batch_start:batch_start + BATCH_SIZE]
            batch_results = []

            def _make_callback(results_list):
                def callback(request_id, response, exception):
                    if exception is None:
                        results_list.append(response)
                return callback

            try:
                from googleapiclient.http import BatchHttpRequest
                batch_req = self.service.new_batch_http_request(callback=_make_callback(batch_results))

                for msg_id in batch_ids:
                    batch_req.add(
                        self.service.users().messages().get(
                            userId="me",
                            id=msg_id,
                            format="metadata",
                            metadataHeaders=["From", "To", "Cc"],
                        )
                    )

                batch_req.execute()

            except Exception:
                # Fallback to individual requests if batch fails
                for msg_id in batch_ids:
                    try:
                        msg = self.service.users().messages().get(
                            userId="me",
                            id=msg_id,
                            format="metadata",
                            metadataHeaders=["From", "To", "Cc"],
                        ).execute()
                        batch_results.append(msg)
                    except Exception:
                        continue

            # Process batch results
            for msg in batch_results:
                try:
                    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

                    # Parse From
                    from_header = headers.get("From", "")
                    email, name = self._parse_email_header(from_header)
                    if email:
                        if email not in contacts:
                            contacts[email] = {"email": email, "name": name, "count": 0}
                        contacts[email]["count"] += 1

                    # Parse To
                    for addr_str in self._split_address_list(headers.get("To", "")):
                        email, name = self._parse_email_header(addr_str)
                        if email:
                            if email not in contacts:
                                contacts[email] = {"email": email, "name": name, "count": 0}
                            contacts[email]["count"] += 1

                    # Parse Cc
                    for addr_str in self._split_address_list(headers.get("Cc", "")):
                        email, name = self._parse_email_header(addr_str)
                        if email:
                            if email not in contacts:
                                contacts[email] = {"email": email, "name": name, "count": 0}
                            contacts[email]["count"] += 1

                    total_scanned += 1
                except Exception:
                    continue

            if progress_cb:
                progress_cb(
                    f"Scanned {total_scanned}/{len(all_msg_ids)} emails... "
                    f"found {len(contacts)} contacts"
                )

        return sorted(contacts.values(), key=lambda x: x["count"], reverse=True)

    def fetch_emails(self, date_start: str, date_end: str,
                     sender_emails: Optional[list[str]] = None,
                     keywords: Optional[list[str]] = None,
                     progress_cb: Optional[Callable] = None) -> dict:
        """Fetch emails matching criteria and store in database."""
        sync_id = self.db.start_sync(self.account_id)
        total_fetched = 0
        total_attachments = 0
        total_skipped = 0
        errors = []

        try:
            start = date_start.replace("-", "/")
            end = date_end.replace("-", "/")
            date_query = f"after:{start} before:{end}"

            # Add keyword filter
            kw_part = ""
            if keywords:
                kw_query = " OR ".join(f'"{kw}"' for kw in keywords)
                kw_part = f" ({kw_query})"

            # List all matching message IDs
            # Gmail has a query length limit — batch senders into groups of 10
            if progress_cb:
                progress_cb("Listing matching emails...")

            all_msg_ids = set()  # Use set to deduplicate across batches

            if sender_emails:
                # Exclude user's own email addresses — otherwise every email matches
                own_emails = set()
                for acc in self.db.get_accounts():
                    own_emails.add(acc["email"].lower())
                filtered_senders = [e for e in sender_emails if e.lower() not in own_emails]

                if not filtered_senders:
                    # All selected senders are the user's own accounts — fetch nothing
                    filtered_senders = []

                SENDER_BATCH = 10
                for batch_start in range(0, len(filtered_senders), SENDER_BATCH):
                    batch = filtered_senders[batch_start:batch_start + SENDER_BATCH]
                    addr_queries = []
                    for addr in batch:
                        addr_queries.append(f"from:{addr}")
                        addr_queries.append(f"to:{addr}")
                    query = f"{date_query} ({' OR '.join(addr_queries)}){kw_part}"

                    page_token = None
                    while True:
                        results = self.service.users().messages().list(
                            userId="me",
                            q=query,
                            pageToken=page_token,
                            maxResults=500,
                        ).execute()

                        messages = results.get("messages", [])
                        if not messages:
                            break

                        for m in messages:
                            all_msg_ids.add(m["id"])

                        page_token = results.get("nextPageToken")
                        if not page_token:
                            break

                    if progress_cb:
                        progress_cb(
                            f"Scanning senders {batch_start + 1}-{min(batch_start + SENDER_BATCH, len(filtered_senders))}"
                            f"/{len(filtered_senders)}... {len(all_msg_ids)} emails found so far"
                        )
            else:
                # No sender filter — fetch all emails in date range
                query = f"{date_query}{kw_part}"
                page_token = None
                while True:
                    results = self.service.users().messages().list(
                        userId="me",
                        q=query,
                        pageToken=page_token,
                        maxResults=500,
                    ).execute()

                    messages = results.get("messages", [])
                    if not messages:
                        break

                    for m in messages:
                        all_msg_ids.add(m["id"])

                    if progress_cb:
                        progress_cb(f"Found {len(all_msg_ids)} emails...")

                    page_token = results.get("nextPageToken")
                    if not page_token:
                        break

            all_msg_ids = list(all_msg_ids)
            if progress_cb:
                progress_cb(f"Total: {len(all_msg_ids)} unique emails to fetch. Downloading...")

            # Process each message with per-message progress
            for i, msg_id in enumerate(all_msg_ids):
                try:
                    result = self._process_message(msg_id, sender_emails, keywords)
                    if result == "stored":
                        total_fetched += 1
                    elif result == "skipped":
                        total_skipped += 1
                    elif isinstance(result, int):
                        total_fetched += 1
                        total_attachments += result
                except Exception as e:
                    errors.append(f"Error processing {msg_id}: {str(e)}")

                if progress_cb and (i + 1) % 5 == 0:
                    progress_cb(
                        f"Fetching {i + 1}/{len(all_msg_ids)} — "
                        f"{total_fetched} stored, {total_skipped} skipped, "
                        f"{total_attachments} attachments"
                    )

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

    def _process_message(self, msg_id: str,
                         sender_emails: Optional[list[str]],
                         keywords: Optional[list[str]]) -> str | int:
        """Process a single Gmail message. Returns 'stored', 'skipped', or attachment count."""
        msg = self.service.users().messages().get(
            userId="me",
            id=msg_id,
            format="full",
        ).execute()

        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

        # Extract message ID
        message_id = headers.get("Message-ID", headers.get("Message-Id", ""))

        # Check duplicate
        if message_id and self.db.email_exists(message_id, self.account_id):
            return "skipped"

        # Extract sender
        from_header = headers.get("From", "")
        sender_email, sender_name = self._parse_email_header(from_header)

        # Extract recipients
        recipients = []
        for addr_str in self._split_address_list(headers.get("To", "")):
            email, name = self._parse_email_header(addr_str)
            if email:
                recipients.append({"email": email, "name": name})

        cc = []
        for addr_str in self._split_address_list(headers.get("Cc", "")):
            email, name = self._parse_email_header(addr_str)
            if email:
                cc.append({"email": email, "name": name})

        # Extract body
        body_text, body_html = self._extract_body(msg.get("payload", {}))

        # Determine direction
        # Check if the message was sent by this account
        account = self.db.get_accounts()
        my_emails = [a["email"].lower() for a in account]
        direction = "sent" if sender_email.lower() in my_emails else "received"

        subject = headers.get("Subject", "")

        # Content hash for dedup
        content_hash = Database.compute_content_hash(body_text, subject, sender_email)

        # Check for cross-account duplicate
        existing_id = self.db.content_hash_exists(content_hash)
        if existing_id:
            return "skipped"

        # Parse forwarded content
        from casepulse.email_engine.parser import detect_forwarded_content
        is_forwarded, original_sender, original_date = detect_forwarded_content(
            subject, body_text, headers
        )

        # Determine date
        date_received = headers.get("Date", "")
        from email.utils import parsedate_to_datetime
        try:
            dt = parsedate_to_datetime(date_received)
            date_received = dt.isoformat()
        except Exception:
            date_received = headers.get("Date", "")

        has_attachments = self._has_attachments(msg.get("payload", {}))

        # Store email
        email_db_id = self.db.insert_email(
            message_id=message_id,
            content_hash=content_hash,
            account_id=self.account_id,
            subject=subject,
            sender_email=sender_email,
            sender_name=sender_name,
            recipients=recipients,
            cc=cc,
            date_sent=date_received,
            date_received=date_received,
            body_text=body_text,
            body_html=body_html,
            folder="inbox" if direction == "received" else "sent",
            is_forwarded=is_forwarded,
            is_reply=subject.lower().startswith("re:"),
            original_sender=original_sender,
            original_date=original_date,
            direction=direction,
            raw_headers=dict(headers),
            importance=headers.get("Importance", "normal"),
            has_attachments=has_attachments,
            provider_msg_id=msg_id,
        )

        # Register senders
        self.db.upsert_sender(sender_email, sender_name)
        for r in recipients + cc:
            if r["email"]:
                self.db.upsert_sender(r["email"], r["name"])

        # Fetch attachments
        att_count = 0
        if has_attachments:
            att_count = self._fetch_attachments(msg.get("payload", {}), msg_id, email_db_id)

        return att_count if att_count > 0 else "stored"

    def _extract_body(self, payload: dict) -> tuple[str, str]:
        """Extract plain text and HTML body from Gmail message payload."""
        body_text = ""
        body_html = ""

        mime_type = payload.get("mimeType", "")

        if mime_type == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                body_text = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif mime_type == "text/html":
            data = payload.get("body", {}).get("data", "")
            if data:
                body_html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                from casepulse.email_engine.parser import html_to_text
                body_text = html_to_text(body_html)
        elif "multipart" in mime_type:
            for part in payload.get("parts", []):
                t, h = self._extract_body(part)
                if t and not body_text:
                    body_text = t
                if h and not body_html:
                    body_html = h

        return body_text, body_html

    def _has_attachments(self, payload: dict) -> bool:
        """Check if message has file attachments."""
        for part in payload.get("parts", []):
            if part.get("filename"):
                return True
            if "multipart" in part.get("mimeType", ""):
                if self._has_attachments(part):
                    return True
        return False

    def _fetch_attachments(self, payload: dict, msg_id: str, email_db_id: int) -> int:
        """Download attachments from a Gmail message."""
        count = 0
        att_dir = get_data_dir() / "attachments" / str(email_db_id)
        att_dir.mkdir(parents=True, exist_ok=True)

        for part in payload.get("parts", []):
            filename = part.get("filename", "")
            if not filename:
                if "multipart" in part.get("mimeType", ""):
                    count += self._fetch_attachments(part, msg_id, email_db_id)
                continue

            att_id = part.get("body", {}).get("attachmentId")
            if not att_id:
                continue

            att_data = self.service.users().messages().attachments().get(
                userId="me",
                messageId=msg_id,
                id=att_id,
            ).execute()

            raw = base64.urlsafe_b64decode(att_data.get("data", ""))
            file_path = att_dir / filename
            file_path.write_bytes(raw)

            content_hash = hashlib.sha256(raw).hexdigest()
            content_type = part.get("mimeType", "application/octet-stream")

            from casepulse.attachments.extractor import extract_text
            extracted_text = extract_text(str(file_path), content_type)

            attachment_id = self.db.insert_attachment(
                email_id=email_db_id,
                filename=filename,
                content_type=content_type,
                size_bytes=len(raw),
                file_path=str(file_path),
                extracted_text=extracted_text,
                content_hash=content_hash,
            )
            if content_type and content_type.startswith("image/"):
                from casepulse.case_theory.metadata_extractor import (
                    extract_image, persist_metadata,
                )
                md = extract_image(file_path)
                persist_metadata(self.db, md, source_table="attachments",
                                 source_row_id=attachment_id)
            count += 1

        return count

    @staticmethod
    def _parse_email_header(header: str) -> tuple[str, str]:
        """Parse 'Name <email@example.com>' into (email, name)."""
        header = header.strip()
        if not header:
            return "", ""
        if "<" in header and ">" in header:
            name = header[:header.index("<")].strip().strip('"').strip("'")
            email = header[header.index("<") + 1:header.index(">")].strip().lower()
            return email, name
        # Just an email address
        return header.lower(), ""

    @staticmethod
    def _split_address_list(header: str) -> list[str]:
        """Split a comma-separated list of email addresses, respecting quoted names."""
        if not header:
            return []
        results = []
        current = ""
        in_quotes = False
        in_angle = False
        for char in header:
            if char == '"':
                in_quotes = not in_quotes
            elif char == '<':
                in_angle = True
            elif char == '>':
                in_angle = False
            elif char == ',' and not in_quotes and not in_angle:
                if current.strip():
                    results.append(current.strip())
                current = ""
                continue
            current += char
        if current.strip():
            results.append(current.strip())
        return results
