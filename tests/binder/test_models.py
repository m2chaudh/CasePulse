import pytest
from pydantic import ValidationError
from casepulse.binder.models import (
    CourtAppearanceMetadata,
    DisclosureMetadata,
    CounselCorrespondenceMetadata,
    PersonalEventMetadata,
    BinderCategory,
    Forum,
    DisclosureKind,
    CounselParty,
)


def test_court_appearance_minimal():
    m = CourtAppearanceMetadata(forum=Forum.CRIMINAL, court_name="OCJ Toronto")
    assert m.forum == Forum.CRIMINAL
    assert m.delay_attribution is None


def test_court_appearance_with_delay_attribution():
    m = CourtAppearanceMetadata(
        forum=Forum.CRIMINAL,
        court_name="OCJ",
        delay_attribution={"category": "crown", "days": 14, "note": "n/a"},
    )
    assert m.delay_attribution.days == 14


def test_disclosure_kind_required():
    with pytest.raises(ValidationError):
        DisclosureMetadata(direction="received")  # missing kind


def test_disclosure_outstanding_default_false():
    m = DisclosureMetadata(kind=DisclosureKind.CROWN, direction="received")
    assert m.outstanding_flag is False


def test_counsel_party_enum():
    m = CounselCorrespondenceMetadata(party=CounselParty.OPPOSING_COUNSEL)
    assert m.party == CounselParty.OPPOSING_COUNSEL


def test_personal_event_no_id_arrays():
    fields = set(PersonalEventMetadata.model_fields.keys())
    forbidden = {"witness_ids", "photo_metadata_ids", "document_ids",
                 "attachment_ids", "email_ids"}
    assert fields & forbidden == set(), \
        f"PersonalEventMetadata must not carry id arrays; found {fields & forbidden}"


def test_binder_category_values():
    assert BinderCategory.COURT_APPEARANCE.value == "court_appearance"
    assert BinderCategory.DISCLOSURE.value == "disclosure"
    assert BinderCategory.COUNSEL_CORRESPONDENCE.value == "counsel_correspondence"
    assert BinderCategory.PERSONAL_EVENT.value == "personal_event"
