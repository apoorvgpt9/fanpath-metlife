"""``fans`` Firestore collection — read/write for fan profiles.

Per DECISIONS.md Entry #15 (schema) and Entry #25 (three-field profile).
Keyed by Firebase Anonymous UID. Fields on every document:

    seat_section        str
    accessibility_flags list[AccessibilityFlag]
    preferred_language  PreferredLanguage (default en)
    created_at          ISO-Z timestamp

The Firestore client is injected so unit tests can pass a mock. Production
callers use :func:`get_default_client`. Not wired into any endpoint yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from google.cloud import firestore

from app.models.enums import (
    DEFAULT_LANGUAGE,
    AccessibilityFlag,
    PreferredLanguage,
)

COLLECTION = "fans"

FIELD_SEAT_SECTION = "seat_section"
FIELD_ACCESSIBILITY_FLAGS = "accessibility_flags"
FIELD_PREFERRED_LANGUAGE = "preferred_language"
FIELD_CREATED_AT = "created_at"


@dataclass(frozen=True)
class FanProfile:
    """Immutable in-memory view of a fan profile document."""

    uid: str
    seat_section: str
    accessibility_flags: tuple[AccessibilityFlag, ...]
    preferred_language: PreferredLanguage
    created_at: str


def _iso_z(dt: datetime) -> str:
    """Firestore-friendly ISO-8601 timestamp with Z suffix."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_flags(flags: list[str] | tuple[str, ...]) -> tuple[AccessibilityFlag, ...]:
    validated = tuple(AccessibilityFlag(f) for f in flags)
    return validated


def _validate_language(language: str) -> PreferredLanguage:
    return PreferredLanguage(language)


def get_default_client() -> firestore.Client:
    return firestore.Client()


def build_profile_document(
    seat_section: str,
    accessibility_flags: list[str] | tuple[str, ...],
    preferred_language: str = DEFAULT_LANGUAGE.value,
    now: datetime | None = None,
) -> dict:
    """Return the Firestore-ready dict for a new fan profile. Validates enums."""
    if not seat_section or not isinstance(seat_section, str):
        raise ValueError("seat_section must be a non-empty string")
    flags = _validate_flags(accessibility_flags)
    lang = _validate_language(preferred_language)
    return {
        FIELD_SEAT_SECTION: seat_section,
        FIELD_ACCESSIBILITY_FLAGS: [f.value for f in flags],
        FIELD_PREFERRED_LANGUAGE: lang.value,
        FIELD_CREATED_AT: _iso_z(now or datetime.now(UTC)),
    }


def write_profile(
    client: firestore.Client,
    uid: str,
    seat_section: str,
    accessibility_flags: list[str] | tuple[str, ...],
    preferred_language: str = DEFAULT_LANGUAGE.value,
    now: datetime | None = None,
) -> dict:
    """Create or overwrite the fan's profile document. Returns the written dict."""
    document = build_profile_document(
        seat_section=seat_section,
        accessibility_flags=accessibility_flags,
        preferred_language=preferred_language,
        now=now,
    )
    client.collection(COLLECTION).document(uid).set(document)
    return document


def read_profile(client: firestore.Client, uid: str) -> FanProfile | None:
    """Return the fan's profile or ``None`` if the document does not exist."""
    snapshot = client.collection(COLLECTION).document(uid).get()
    if not snapshot.exists:
        return None
    data = snapshot.to_dict() or {}
    return FanProfile(
        uid=uid,
        seat_section=data.get(FIELD_SEAT_SECTION, ""),
        accessibility_flags=_validate_flags(data.get(FIELD_ACCESSIBILITY_FLAGS, [])),
        preferred_language=_validate_language(
            data.get(FIELD_PREFERRED_LANGUAGE, DEFAULT_LANGUAGE.value)
        ),
        created_at=data.get(FIELD_CREATED_AT, ""),
    )
