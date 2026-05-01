"""Regression tests for casepulse.setup_wizard.is_setup_complete."""
from unittest.mock import patch, MagicMock


def test_is_setup_complete_returns_true_with_modules_json(tmp_path):
    """Returns True when modules.json exists (original behaviour)."""
    modules_path = tmp_path / "installed_modules.json"
    modules_path.write_text("{}")
    with patch("casepulse.setup_wizard.get_modules_path", return_value=modules_path):
        from casepulse.setup_wizard import is_setup_complete
        assert is_setup_complete() is True


def test_is_setup_complete_returns_false_with_no_modules_and_no_accounts(tmp_path):
    """Returns False when neither modules.json nor any account exists."""
    from casepulse.storage.database import Database

    db_path = tmp_path / "test.db"
    db = Database(db_path)

    missing_path = tmp_path / "nonexistent.json"
    with patch("casepulse.setup_wizard.get_modules_path", return_value=missing_path):
        # Patch Database inside the casepulse.storage.database module so the
        # local import inside is_setup_complete picks up our empty instance.
        with patch("casepulse.storage.database.Database", return_value=db):
            from casepulse.setup_wizard import is_setup_complete
            result = is_setup_complete()
    assert result is False


def test_is_setup_complete_returns_true_when_account_exists_without_modules_json(
    tmp_path, tmp_db_with_case
):
    """Existing users with at least one account are treated as setup-complete
    even when modules.json does not exist."""
    db, case_id = tmp_db_with_case
    # Insert a row directly into the accounts table
    conn = db._get_conn()
    conn.execute(
        "INSERT INTO accounts (provider, email, display_name, token_file, client_id) "
        "VALUES ('microsoft', 'user@example.com', 'Test User', 'tok.json', 'client123')"
    )
    conn.commit()

    missing_path = tmp_path / "nonexistent.json"
    with patch("casepulse.setup_wizard.get_modules_path", return_value=missing_path):
        with patch("casepulse.storage.database.Database", return_value=db):
            from casepulse.setup_wizard import is_setup_complete
            result = is_setup_complete()
    assert result is True, (
        "is_setup_complete() must return True when account exists without modules.json"
    )
