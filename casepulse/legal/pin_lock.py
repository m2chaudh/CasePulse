"""App PIN lock — protects CasePulse from unauthorized access."""
from __future__ import annotations

import hashlib
import secrets

from casepulse.storage.database import Database


def _hash_pin(pin: str, salt: str = "") -> str:
    """Hash a PIN with salt using SHA-256. Simple but sufficient for local app lock."""
    if not salt:
        salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{pin}".encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_pin(pin: str, stored: str) -> bool:
    """Verify a PIN against a stored hash."""
    if ":" not in stored:
        return False
    salt = stored.split(":")[0]
    expected = _hash_pin(pin, salt)
    return secrets.compare_digest(expected, stored)


def is_pin_set(db: Database) -> bool:
    """Check if a PIN has been configured."""
    return bool(db.get_setting("pin_hash"))


def set_pin(db: Database, pin: str):
    """Set or change the app PIN."""
    hashed = _hash_pin(pin)
    db.set_setting("pin_hash", hashed)
    db.log_action("pin_set", "App PIN was set/changed")


def verify_pin(db: Database, pin: str) -> bool:
    """Verify a PIN attempt."""
    stored = db.get_setting("pin_hash")
    if not stored:
        return True  # No PIN set, always pass
    result = _verify_pin(pin, stored)
    if not result:
        db.log_action("pin_failed", "Failed PIN attempt")
    return result


def remove_pin(db: Database, current_pin: str) -> bool:
    """Remove the PIN (requires current PIN to confirm)."""
    if not verify_pin(db, current_pin):
        return False
    db.set_setting("pin_hash", "")
    db.log_action("pin_removed", "App PIN was removed")
    return True


def render_pin_gate(db: Database):
    """Render the PIN lock gate in Streamlit. Call at top of every page.

    Returns True if unlocked, False if locked (page should st.stop()).
    """
    import streamlit as st

    if not is_pin_set(db):
        return True

    if st.session_state.get("pin_unlocked"):
        return True

    st.markdown("## CasePulse - Locked")
    st.markdown("Enter your PIN to access CasePulse.")

    pin = st.text_input("PIN", type="password", key="pin_input", max_chars=20)

    if st.button("Unlock"):
        if verify_pin(db, pin):
            st.session_state["pin_unlocked"] = True
            db.log_action("pin_unlock", "App unlocked successfully")
            st.rerun()
        else:
            st.error("Incorrect PIN.")

    return False
