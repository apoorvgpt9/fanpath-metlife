"""HTTP handlers for the six-endpoint surface (DECISIONS.md Entry #19).

Kept out of ``app/main.py`` so ``main.py`` stays focused on app assembly.

Design constraints applied throughout:

* Every fan handler depends on :func:`app.auth.firebase.verify_fan_token`.
* Every staff handler depends on :func:`app.auth.staff.verify_staff_token`.
* ``/navigate`` reads ``venue_state`` fresh via
  :func:`app.firestore.venue_state.read_state` on every call (Entry #16),
  decodes closed_edges via :func:`app.graph.edge_id.parse_edge_id`, and hands
  the resulting sets to :func:`app.pathfinding.engine.find_route`.
* ``AmbiguousRequest`` and ``RouteBlocked`` are 200 responses (Entry #17),
  not errors.
* Every rate-limited endpoint takes ``request: Request`` so ``slowapi`` can
  read the header for its key function.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from google.cloud import firestore

from app.agents.gemini_factory import GeminiError, GeminiTimeoutError
from app.agents.guide import explain_route
from app.agents.intent import extract_profile, parse_navigation_request
from app.agents.schemas import (
    AmbiguousRequest,
    ProfileComplete,
    ProfileFailed,
    ProfileIncomplete,
    ResolvedRequest,
    UnresolvableRequest,
)
from app.auth.firebase import verify_fan_token
from app.auth.staff import verify_staff_token
from app.errors import raise_error
from app.firestore import fans as fans_repo
from app.firestore import venue_state as venue_repo
from app.graph.edge_id import edge_id, parse_edge_id
from app.graph.loader import Graph
from app.pathfinding.engine import (
    RouteBlocked,
    RouteFound,
    RouteImpossible,
    find_nearest_amenity,
    find_route,
)
from app.rate_limit import FAN_LIMIT, STAFF_LIMIT, limiter
from app.rendering.svg_renderer import render_route
from app.schemas import (
    ClosureStateResponse,
    ClosureToggleRequest,
    NavigateRequest,
    NavigateResponse,
    ProfileFailedResponse,
    ProfileIncompleteResponse,
    ProfileOnboardRequest,
    ProfileResponse,
)


def _firestore_client(request: Request) -> firestore.Client:
    """Return a Firestore client via the app-state factory (test seam)."""
    factory = request.app.state.firestore_client_factory
    client: firestore.Client = factory()
    return client


def _graph(request: Request) -> Graph:
    """Return the graph loaded once at startup and cached on ``app.state``."""
    graph: Graph = request.app.state.graph
    return graph


FanUid = Annotated[str, Depends(verify_fan_token)]
StaffAuth = Annotated[None, Depends(verify_staff_token)]
FirestoreClient = Annotated[firestore.Client, Depends(_firestore_client)]
GraphDep = Annotated[Graph, Depends(_graph)]


router = APIRouter()


def _map_gemini_error(exc: GeminiError) -> None:
    """Map agent exceptions onto the two-category error contract."""
    logging.getLogger("app.routes").warning("gemini_error: %s: %s", type(exc).__name__, exc)
    if isinstance(exc, GeminiTimeoutError):
        raise_error(status.HTTP_504_GATEWAY_TIMEOUT, "transient", "Upstream timeout.", str(exc))
    raise_error(status.HTTP_502_BAD_GATEWAY, "transient", "Upstream service error.", str(exc))


# ---------------------------------------------------------------------------
# /profile
# ---------------------------------------------------------------------------


@router.post("/profile")
@limiter.limit(FAN_LIMIT)
async def post_profile(
    request: Request,
    body: ProfileOnboardRequest,
    uid: FanUid,
    fs: FirestoreClient,
) -> ProfileResponse | ProfileIncompleteResponse | ProfileFailedResponse:
    """Extract a fan profile from NL input and persist it (Entry #7)."""
    try:
        result = await extract_profile(body.nl_input)
    except GeminiError as exc:
        _map_gemini_error(exc)
    if isinstance(result, ProfileIncomplete):
        return ProfileIncompleteResponse(
            missing=list(result.missing),
            followup_question=result.followup_question,
        )
    if isinstance(result, ProfileFailed):
        return ProfileFailedResponse(reason=result.reason)
    assert isinstance(result, ProfileComplete)
    document = fans_repo.write_profile(
        fs,
        uid=uid,
        seat_section=result.seat_section,
        accessibility_flags=[f.value for f in result.accessibility_flags],
        preferred_language=result.preferred_language.value,
    )
    return ProfileResponse(
        uid=uid,
        seat_section=document[fans_repo.FIELD_SEAT_SECTION],
        accessibility_flags=list(result.accessibility_flags),
        preferred_language=result.preferred_language,
        created_at=document[fans_repo.FIELD_CREATED_AT],
    )


@router.get("/profile")
@limiter.limit(FAN_LIMIT)
def get_profile(
    request: Request,
    uid: FanUid,
    fs: FirestoreClient,
) -> ProfileResponse:
    """Return the stored profile for this anonymous UID."""
    profile = fans_repo.read_profile(fs, uid)
    if profile is None:
        raise_error(status.HTTP_404_NOT_FOUND, "permanent", "Profile not found.")
    return ProfileResponse(
        uid=profile.uid,
        seat_section=profile.seat_section,
        accessibility_flags=list(profile.accessibility_flags),
        preferred_language=profile.preferred_language,
        created_at=profile.created_at,
    )


# ---------------------------------------------------------------------------
# /navigate
# ---------------------------------------------------------------------------


def _decode_closures(state: venue_repo.VenueState) -> tuple[set[str], set[tuple[str, str]]]:
    """Decode a :class:`VenueState` into node and canonical edge closure sets."""
    closed_nodes = set(state.closed_nodes)
    closed_edges: set[tuple[str, str]] = set()
    for eid in state.closed_edges:
        closed_edges.add(parse_edge_id(eid))
    return closed_nodes, closed_edges


def _resolve_route(
    parsed: ResolvedRequest,
    profile: fans_repo.FanProfile,
    graph: Graph,
    closed_nodes: set[str],
    closed_edges: set[tuple[str, str]],
) -> RouteFound | RouteBlocked | RouteImpossible:
    """Dispatch to ``find_route`` or ``find_nearest_amenity`` per the parsed request."""
    flags = [f.value for f in profile.accessibility_flags]
    if parsed.destination_amenity_type is not None:
        return find_nearest_amenity(
            graph,
            origin=parsed.origin,
            amenity_type=parsed.destination_amenity_type.value,
            accessibility_flags=flags,
            closed_nodes=closed_nodes,
            closed_edges=closed_edges,
        )
    assert parsed.destination is not None
    return find_route(
        graph,
        origin=parsed.origin,
        destination=parsed.destination,
        accessibility_flags=flags,
        closed_nodes=closed_nodes,
        closed_edges=closed_edges,
    )


async def _handle_navigation_parse(
    parsed: ResolvedRequest | AmbiguousRequest | UnresolvableRequest,
    body: NavigateRequest,
    profile: fans_repo.FanProfile,
    graph: Graph,
    closed_nodes: set[str],
    closed_edges: set[tuple[str, str]],
) -> NavigateResponse:
    """Turn a discriminated-union parse into the final ``NavigateResponse``."""
    if isinstance(parsed, AmbiguousRequest):
        return NavigateResponse(directions=parsed.clarification_question, route_image=None)
    if isinstance(parsed, UnresolvableRequest):
        raise_error(status.HTTP_400_BAD_REQUEST, "permanent", parsed.reason)
    route = _resolve_route(parsed, profile, graph, closed_nodes, closed_edges)
    if isinstance(route, RouteImpossible):
        raise_error(status.HTTP_400_BAD_REQUEST, "permanent", route.reason)
    assert isinstance(route, RouteFound | RouteBlocked)
    amenity = parsed.destination_amenity_type
    directions = await explain_route(
        route,
        body.query,
        profile,
        amenity_type=amenity.value if amenity is not None else None,
    )
    image = (
        render_route(route, graph, closed_nodes, closed_edges)
        if isinstance(route, RouteFound)
        else None
    )
    return NavigateResponse(directions=directions, route_image=image)


@router.post("/navigate")
@limiter.limit(FAN_LIMIT)
async def post_navigate(
    request: Request,
    body: NavigateRequest,
    uid: FanUid,
    fs: FirestoreClient,
    graph: GraphDep,
) -> NavigateResponse:
    """Core navigation endpoint: NL query in, directions + SVG out (Entry #9)."""
    profile = fans_repo.read_profile(fs, uid)
    if profile is None:
        raise_error(status.HTTP_404_NOT_FOUND, "permanent", "Profile not found.")
    state = venue_repo.read_state(fs)
    try:
        closed_nodes, closed_edges = _decode_closures(state)
    except ValueError as exc:
        raise_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "permanent",
            "Corrupt venue_state: unparseable edge id.",
            str(exc),
        )
    try:
        parsed = await parse_navigation_request(body.query, profile, list(body.history), graph)
    except GeminiError as exc:
        _map_gemini_error(exc)
    return await _handle_navigation_parse(
        parsed, body, profile, graph, closed_nodes, closed_edges
    )


# ---------------------------------------------------------------------------
# /staff/closures
# ---------------------------------------------------------------------------


def _validate_node_target(graph: Graph, target_id: str) -> None:
    """Reject an unknown zone_id with the Entry #23 permanent-error payload."""
    if target_id not in graph.nodes:
        raise_error(
            status.HTTP_400_BAD_REQUEST,
            "permanent",
            f"Unknown zone_id: {target_id!r}.",
        )


def _validate_edge_target(graph: Graph, target_id: str) -> str:
    """Return the canonical edge id after checking both endpoints and edge existence."""
    try:
        a, b = parse_edge_id(target_id)
    except ValueError as exc:
        raise_error(
            status.HTTP_400_BAD_REQUEST,
            "permanent",
            "Edge id must be encoded as 'a__b'.",
            str(exc),
        )
    if a not in graph.nodes or b not in graph.nodes:
        raise_error(
            status.HTTP_400_BAD_REQUEST,
            "permanent",
            f"Edge references unknown zone(s): {(a, b)!r}.",
        )
    canonical = edge_id(a, b)
    real_edges = {edge_id(e.from_id, e.to_id) for e in graph.edges}
    if canonical not in real_edges:
        raise_error(
            status.HTTP_400_BAD_REQUEST,
            "permanent",
            f"Edge {(a, b)!r} does not exist in the graph.",
        )
    return canonical


def _mutate_state(
    body: ClosureToggleRequest,
    state: venue_repo.VenueState,
    canonical_edge: str | None,
) -> tuple[set[str], set[str]]:
    """Apply a single close/open toggle to the current closure sets."""
    closed_nodes = set(state.closed_nodes)
    closed_edges = set(state.closed_edges)
    if body.target_type == "node":
        if body.action == "close":
            closed_nodes.add(body.target_id)
        else:
            closed_nodes.discard(body.target_id)
    else:
        assert canonical_edge is not None
        if body.action == "close":
            closed_edges.add(canonical_edge)
        else:
            closed_edges.discard(canonical_edge)
    return closed_nodes, closed_edges


@router.post("/staff/closures")
@limiter.limit(STAFF_LIMIT)
def post_staff_closures(
    request: Request,
    body: ClosureToggleRequest,
    _auth: StaffAuth,
    fs: FirestoreClient,
    graph: GraphDep,
) -> ClosureStateResponse:
    """Toggle a node or edge open/closed and return the new closure state."""
    canonical_edge: str | None = None
    if body.target_type == "node":
        _validate_node_target(graph, body.target_id)
    else:
        canonical_edge = _validate_edge_target(graph, body.target_id)
    state = venue_repo.read_state(fs)
    closed_nodes, closed_edges = _mutate_state(body, state, canonical_edge)
    written = venue_repo.write_state(fs, list(closed_nodes), list(closed_edges))
    return ClosureStateResponse(
        closed_nodes=list(written[venue_repo.FIELD_CLOSED_NODES]),
        closed_edges=list(written[venue_repo.FIELD_CLOSED_EDGES]),
        updated_at=written[venue_repo.FIELD_UPDATED_AT],
    )


@router.get("/staff/closures")
@limiter.limit(STAFF_LIMIT)
def get_staff_closures(
    request: Request,
    _auth: StaffAuth,
    fs: FirestoreClient,
) -> ClosureStateResponse:
    """Return the current closure snapshot (Entry #15)."""
    state = venue_repo.read_state(fs)
    return ClosureStateResponse(
        closed_nodes=list(state.closed_nodes),
        closed_edges=list(state.closed_edges),
        updated_at=state.updated_at,
    )


__all__ = ["router"]
