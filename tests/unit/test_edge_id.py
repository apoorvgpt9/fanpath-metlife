"""Unit tests for :mod:`app.graph.edge_id` — canonical, direction-agnostic ids."""

from __future__ import annotations

import pytest

from app.graph.edge_id import edge_id, parse_edge_id


def test_encoding_is_direction_agnostic() -> None:
    assert edge_id("alpha", "beta") == edge_id("beta", "alpha")


def test_encoding_sorts_alphabetically() -> None:
    assert edge_id("beta", "alpha") == "alpha__beta"


def test_round_trip() -> None:
    encoded = edge_id("gate_a", "gate_b")
    assert parse_edge_id(encoded) == ("gate_a", "gate_b")


def test_round_trip_stable_after_multiple_orderings() -> None:
    e1 = edge_id("x", "y")
    e2 = edge_id("y", "x")
    assert parse_edge_id(e1) == parse_edge_id(e2)


def test_empty_endpoint_raises() -> None:
    with pytest.raises(ValueError):
        edge_id("", "x")
    with pytest.raises(ValueError):
        edge_id("x", "")


def test_endpoint_containing_separator_raises() -> None:
    with pytest.raises(ValueError):
        edge_id("a__b", "c")


def test_parse_rejects_missing_separator() -> None:
    with pytest.raises(ValueError):
        parse_edge_id("no_separator_here")


def test_parse_rejects_non_string() -> None:
    with pytest.raises(ValueError):
        parse_edge_id(None)  # type: ignore[arg-type]


def test_parse_rejects_empty_half() -> None:
    with pytest.raises(ValueError):
        parse_edge_id("__b")
    with pytest.raises(ValueError):
        parse_edge_id("a__")


def test_parse_rejects_more_than_two_parts() -> None:
    with pytest.raises(ValueError):
        parse_edge_id("a__b__c")
