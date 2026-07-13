"""Unit tests for enum membership (also asserted by verify_docs claims 6-9)."""

from __future__ import annotations

from app.models.enums import (
    AccessibilityFlag,
    AmenityType,
    EdgeAccessibility,
    PreferredLanguage,
)


def test_accessibility_flag_values() -> None:
    assert {f.value for f in AccessibilityFlag} == {
        "wheelchair",
        "no_stairs",
        "stroller",
        "visual_impairment",
    }


def test_preferred_language_values() -> None:
    assert {lang.value for lang in PreferredLanguage} == {"en", "es", "fr", "pt", "ar"}


def test_amenity_type_values() -> None:
    assert {a.value for a in AmenityType} == {
        "restroom",
        "food",
        "merchandise",
        "atm",
        "first_aid",
        "charging_station",
    }


def test_edge_accessibility_values() -> None:
    assert {e.value for e in EdgeAccessibility} == {
        "stairs_only",
        "ramp",
        "elevator",
        "level",
    }
