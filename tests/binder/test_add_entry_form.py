import json
from casepulse.binder.add_entry_form import save_court_appearance
from casepulse.binder.repository import get_binder_entry


def test_save_court_appearance(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    entry_id = save_court_appearance(
        db, case_id=case_id, date_str="2024-03-14", time_str="09:00",
        forum="criminal", court_name="OCJ Toronto", judge="Justice X",
        own_counsel="Smith", opposing_counsel="Doe",
        purpose="first_appearance", outcome="set date Mar 20",
        delay_attribution=None,
    )
    row = get_binder_entry(db, entry_id)
    assert row["category"] == "court_appearance"
    md = json.loads(row["metadata_json"])
    assert md["forum"] == "criminal"
    assert md["court_name"] == "OCJ Toronto"
    assert md["delay_attribution"] is None


def test_save_court_appearance_with_delay(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    entry_id = save_court_appearance(
        db, case_id=case_id, date_str="2024-03-14", time_str="",
        forum="criminal", court_name="OCJ", judge="",
        own_counsel="", opposing_counsel="", purpose="set_date",
        outcome="",
        delay_attribution={"category": "crown", "days": 14, "note": ""},
    )
    md = json.loads(get_binder_entry(db, entry_id)["metadata_json"])
    assert md["delay_attribution"]["days"] == 14


from casepulse.binder.add_entry_form import save_disclosure


def test_save_disclosure(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    entry_id = save_disclosure(
        db, case_id=case_id, date_str="2024-03-14", time_str="",
        kind="crown", direction="received", page_count=47,
        items="synopsis, police report",
        completion_status="expecting_more",
        expected_completion_date="2024-04-13",
        follow_up_email_id=None,
    )
    row = get_binder_entry(db, entry_id)
    md = json.loads(row["metadata_json"])
    assert md["kind"] == "crown"
    assert md["page_count"] == 47
    assert md["completion_status"] == "expecting_more"
    assert md["outstanding_flag"] is False
