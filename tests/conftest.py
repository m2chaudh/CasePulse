"""Shared pytest fixtures."""
import pytest
import sqlite3
from pathlib import Path
from casepulse.storage.database import Database


@pytest.fixture
def tmp_db(tmp_path):
    """Empty database with schema applied."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    yield db


@pytest.fixture
def tmp_db_with_case(tmp_db):
    """Database with one fixture case row."""
    case_id = tmp_db.create_case(
        name="Test Family Matter",
        case_type="family",
        case_number="FC-2024-001",
    )
    yield tmp_db, case_id
