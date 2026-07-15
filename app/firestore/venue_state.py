"""``venue_state`` Firestore document — closed nodes and edges.

Per DECISIONS.md Entry #15 (single document) and Entry #16 (read on every
navigate request, no cache).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from google.cloud import firestore

COLLECTION = "venue_state"
DOCUMENT_ID = "current"

FIELD_CLOSED_NODES = "closed_nodes"
FIELD_CLOSED_EDGES = "closed_edges"
FIELD_UPDATED_AT = "updated_at"


@dataclass(frozen=True)
class VenueState:
    """Immutable snapshot of the closed-nodes/edges in ``venue_state/current``."""

    closed_nodes: tuple[str, ...] = field(default_factory=tuple)
    closed_edges: tuple[str, ...] = field(default_factory=tuple)
    updated_at: str = ""


def _iso_z(dt: datetime) -> str:
    """Format ``dt`` as a UTC ISO-8601 string with the trailing ``Z``."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _doc(client: firestore.Client) -> firestore.DocumentReference:
    """Return the single ``venue_state/current`` document reference."""
    return client.collection(COLLECTION).document(DOCUMENT_ID)


def read_state(client: firestore.Client) -> VenueState:
    """Return the current closure state. Empty state if the doc does not exist."""
    snapshot = _doc(client).get()
    if not snapshot.exists:
        return VenueState()
    data = snapshot.to_dict() or {}
    return VenueState(
        closed_nodes=tuple(data.get(FIELD_CLOSED_NODES, [])),
        closed_edges=tuple(data.get(FIELD_CLOSED_EDGES, [])),
        updated_at=data.get(FIELD_UPDATED_AT, ""),
    )


def write_state(
    client: firestore.Client,
    closed_nodes: list[str] | tuple[str, ...],
    closed_edges: list[str] | tuple[str, ...],
    now: datetime | None = None,
) -> dict:
    """Overwrite the single ``venue_state`` document."""
    if not all(isinstance(x, str) for x in closed_nodes):
        raise ValueError("closed_nodes must be a sequence of strings")
    if not all(isinstance(x, str) for x in closed_edges):
        raise ValueError("closed_edges must be a sequence of strings")
    payload = {
        FIELD_CLOSED_NODES: sorted(set(closed_nodes)),
        FIELD_CLOSED_EDGES: sorted(set(closed_edges)),
        FIELD_UPDATED_AT: _iso_z(now or datetime.now(UTC)),
    }
    _doc(client).set(payload)
    return payload
