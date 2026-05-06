"""Aggregator performance budget. Seeds a 100K-row mixed corpus and
asserts a single-day aggregate completes under the budget."""

import time
import pytest
from datetime import date, timedelta
from casepulse.binder.aggregator import aggregate


@pytest.fixture
def seeded_100k(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    start = date(2020, 1, 1)
    with db._get_conn() as conn:
        # 60K emails
        for i in range(60_000):
            d = start + timedelta(days=i % 1500)
            ts = f"{d.isoformat()}T{(i % 24):02d}:{(i*7 % 60):02d}:00"
            cur = conn.execute(
                """INSERT INTO emails (subject, sender_email, date_received)
                   VALUES (?, ?, ?)""",
                (f"S{i}", f"a{i % 100}@x.com", ts),
            )
            conn.execute(
                """INSERT INTO evidence_tags (item_type, item_id, case_id)
                   VALUES ('email', ?, ?)""", (cur.lastrowid, case_id),
            )
        # 30K chats
        for i in range(30_000):
            d = start + timedelta(days=i % 1500)
            ts = f"{d.isoformat()}T{(i % 24):02d}:{(i*11 % 60):02d}:00"
            cur = conn.execute(
                """INSERT INTO chat_messages (source_type, platform, sender, timestamp, message_text)
                   VALUES ('whatsapp','whatsapp',?,?,?)""",
                (f"u{i % 50}", ts, f"msg {i}"),
            )
            conn.execute(
                """INSERT INTO evidence_tags (item_type, item_id, case_id)
                   VALUES ('chat', ?, ?)""", (cur.lastrowid, case_id),
            )
        # 10K documents
        for i in range(10_000):
            d = start + timedelta(days=i % 1500)
            ts = f"{d.isoformat()}T08:00:00"
            cur = conn.execute(
                """INSERT INTO documents (filename, file_path, content_hash, created_at)
                   VALUES (?, ?, ?, ?)""",
                (f"f{i}.pdf", f"/tmp/{i}.pdf", f"h{i}", ts),
            )
            conn.execute(
                """INSERT INTO evidence_tags (item_type, item_id, case_id)
                   VALUES ('document', ?, ?)""", (cur.lastrowid, case_id),
            )
    return db, case_id


def test_single_day_under_budget(seeded_100k):
    db, case_id = seeded_100k
    target = date(2022, 6, 14)
    t0 = time.perf_counter()
    items = aggregate(db, case_id=case_id,
                      date_start=target, date_end=target)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"\n[perf] single-day aggregate: {elapsed_ms:.1f}ms, {len(items)} items")
    assert elapsed_ms < 200, f"single-day aggregate took {elapsed_ms:.1f}ms, budget 200ms"
