"""Concurrent-call regression test for exhibit numbering.

The bug: get_next_exhibit_number was a SELECT followed by UPDATE.
Two threads could SELECT the same value before either UPDATEd,
producing duplicate exhibit labels — a court-bundle inadmissibility
risk.

The fix uses UPDATE ... RETURNING so the read and increment happen
in one statement under the write lock.
"""
import threading

from casepulse.storage.database import Database


def test_sequential_calls_return_distinct_numbers(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    seen = [db.get_next_exhibit_number(case_id) for _ in range(5)]
    assert seen == [1, 2, 3, 4, 5]


def test_concurrent_calls_return_distinct_numbers(tmp_db_with_case):
    """20 threads each claim 10 numbers → must see 200 distinct values
    with no duplicates."""
    db, case_id = tmp_db_with_case
    results: list[int] = []
    lock = threading.Lock()

    def worker():
        # Each thread opens its own Database() because sqlite3
        # connections aren't shareable across threads.
        thread_db = Database(db.db_path)
        local = [thread_db.get_next_exhibit_number(case_id) for _ in range(10)]
        with lock:
            results.extend(local)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 200
    assert len(set(results)) == 200, (
        f"duplicates among {len(results)} claims — race not fixed"
    )


def test_missing_case_returns_safe_default(tmp_db):
    """Calling on a nonexistent case_id returns 1 (legacy behavior) so
    callers don't crash; the downstream FK will reject the tag anyway."""
    assert tmp_db.get_next_exhibit_number(99999) == 1
