"""Fixed enums for fanpath-metlife.

One source of truth for every closed-domain value referenced by DECISIONS.md.
The verify_docs.py claims 6-9 assert the exact membership of these enums.
"""

from __future__ import annotations

from enum import Enum


class AccessibilityFlag(str, Enum):
    """Fan-profile accessibility constraints (DECISIONS.md Entry #7)."""

    WHEELCHAIR = "wheelchair"
    NO_STAIRS = "no_stairs"
    STROLLER = "stroller"
    VISUAL_IMPAIRMENT = "visual_impairment"


class PreferredLanguage(str, Enum):
    """Fan-profile output language (DECISIONS.md Entry #25)."""

    EN = "en"
    ES = "es"
    FR = "fr"
    PT = "pt"
    AR = "ar"


class AmenityType(str, Enum):
    """Zone amenity types (DECISIONS.md Entry #11)."""

    RESTROOM = "restroom"
    FOOD = "food"
    MERCHANDISE = "merchandise"
    ATM = "atm"
    FIRST_AID = "first_aid"
    CHARGING_STATION = "charging_station"


class EdgeAccessibility(str, Enum):
    """Edge accessibility classification for Dijkstra filtering (Entry #8)."""

    STAIRS_ONLY = "stairs_only"
    RAMP = "ramp"
    ELEVATOR = "elevator"
    LEVEL = "level"


DEFAULT_LANGUAGE = PreferredLanguage.EN
