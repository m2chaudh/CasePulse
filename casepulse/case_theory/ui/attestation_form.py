"""Per-field strike/attest controls for photo metadata.

Renders a table of photo EXIF fields with their values and allows the analyst
to mark fields as "struck" (unreliable/falsified) or "attested" (verified with
a written statement).
"""
import streamlit as st

from casepulse.case_theory.repository import (
    record_attestation, list_attestations_for_metadata,
)


# Columns present in the photo_metadata table
PHOTO_FIELDS = [
    "taken_at", "camera_make", "camera_model", "lens",
    "software", "gps_lat", "gps_lon", "orientation",
]


def render(db, *, photo_metadata_id: int, photo_metadata: dict) -> None:
    """Render per-field strike/attest controls for one photo_metadata row.

    Args:
        db: Database instance.
        photo_metadata_id: Primary key of the photo_metadata row.
        photo_metadata: Dict of field values (keys match PHOTO_FIELDS).
    """
    existing = list_attestations_for_metadata(
        db, photo_metadata_id=photo_metadata_id,
    )
    # Keep the most recent attestation per field
    by_field: dict[str, dict] = {}
    for a in existing:
        by_field[a["field_name"]] = a

    for field in PHOTO_FIELDS:
        value = photo_metadata.get(field)
        existing_a = by_field.get(field)

        col_value, col_status, col_action = st.columns([2, 1, 1])

        with col_value:
            if existing_a and existing_a["status"] == "struck":
                st.markdown(f"~~**{field}**: {value if value is not None else '[missing]'}~~")
            else:
                val_display = value if value is not None else "_[missing]_"
                st.markdown(f"**{field}**: {val_display}")

        with col_status:
            if existing_a:
                if existing_a["status"] == "struck":
                    st.markdown("✗ struck")
                elif existing_a["status"] == "attested":
                    st.markdown("✓ attested")
            elif value is None:
                st.markdown("✗ stripped")
            else:
                st.markdown("✓ reliable")

        with col_action:
            if existing_a:
                # Already actioned — show badge only, no button
                pass
            elif value is not None:
                # Field has a value — offer to strike it
                if st.button("Strike", key=f"attest_strike_{photo_metadata_id}_{field}"):
                    record_attestation(
                        db,
                        photo_metadata_id=photo_metadata_id,
                        field_name=field,
                        status="struck",
                        reason="Manually marked unreliable",
                    )
                    st.rerun()
            else:
                # Field is missing — offer an attestation (e.g. "I know when it was taken")
                if st.button("Attest", key=f"attest_attest_{photo_metadata_id}_{field}"):
                    # Use a text_input to capture the attestation text inline.
                    # Because we can't show a dialog inside a column we store
                    # a flag in session state and render the form on next run.
                    st.session_state[f"_attest_pending_{photo_metadata_id}_{field}"] = True
                    st.rerun()

            # Render pending attestation form (after button click)
            pending_key = f"_attest_pending_{photo_metadata_id}_{field}"
            if st.session_state.get(pending_key):
                text_val = st.text_input(
                    f"Attestation text for {field}",
                    key=f"attest_text_{photo_metadata_id}_{field}",
                )
                if st.button("Save attestation",
                             key=f"attest_save_{photo_metadata_id}_{field}"):
                    if text_val:
                        record_attestation(
                            db,
                            photo_metadata_id=photo_metadata_id,
                            field_name=field,
                            status="attested",
                            attestation_text=text_val,
                        )
                        del st.session_state[pending_key]
                        st.rerun()
                    else:
                        st.warning("Enter attestation text first.")
