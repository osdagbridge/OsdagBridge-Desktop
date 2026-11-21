
import pytest

from osdagbridge.core.bridge_types.plate_girder.bridge_geometry import (
    create_default_load_placement,
)


@pytest.fixture
def one_footpath_manager():
    return create_default_load_placement(
        span=30.0,
        carriageway_width=7.5,
        crash_barrier_width=0.45,
        no_of_footpaths=1,
        footpath_width=1.5,
        railing_width=0.3,
        median_width=1.2,
    )


@pytest.fixture
def two_footpath_manager():
    return create_default_load_placement(
        span=30.0,
        carriageway_width=7.5,
        crash_barrier_width=0.45,
        no_of_footpaths=2,
        footpath_width=1.5,
        railing_width=0.3,
        median_width=1.2,
    )


def test_deck_load_covers_entire_bridge(one_footpath_manager):
    load = one_footpath_manager.deck_load()

    assert load.p1.x == pytest.approx(0.0)
    assert load.p2.x == pytest.approx(11.4)
    assert load.p3.z == pytest.approx(30.0)
    assert load.p4.z == pytest.approx(30.0)


def test_overlay_load_respects_edge_clearance(one_footpath_manager):
    load = one_footpath_manager.overlay_load(0.5)

    assert load.p1.x == pytest.approx(0.5)
    assert load.p2.x == pytest.approx(10.9)
    assert load.p3.x == pytest.approx(10.9)
    assert load.p4.x == pytest.approx(0.5)


def test_left_footpath_geometry(one_footpath_manager):
    load = one_footpath_manager.footpath_load("left")

    assert load.p1.x == pytest.approx(0.3)
    assert load.p2.x == pytest.approx(1.8)
    assert load.p3.z == pytest.approx(30.0)


def test_right_footpath_geometry(two_footpath_manager):
    load = two_footpath_manager.footpath_load("right")

    assert load.p1.x == pytest.approx(11.4)
    assert load.p2.x == pytest.approx(12.9)
    assert load.p3.z == pytest.approx(30.0)


def test_right_footpath_is_unavailable_with_one_footpath(
    one_footpath_manager,
):
    with pytest.raises(KeyError):
        one_footpath_manager.footpath_load("right")


def test_crash_barrier_line_load_positions(one_footpath_manager):
    left = one_footpath_manager.crash_barrier_load("left")
    right = one_footpath_manager.crash_barrier_load("right")

    assert left.start.x == pytest.approx(2.025)
    assert right.start.x == pytest.approx(11.175)
    assert left.end.z == pytest.approx(30.0)
    assert right.end.z == pytest.approx(30.0)


def test_median_line_load_is_at_component_center(one_footpath_manager):
    load = one_footpath_manager.median_line_load()

    assert load.start.x == pytest.approx(6.6)
    assert load.end.x == pytest.approx(6.6)
    assert load.end.z == pytest.approx(30.0)


def test_railing_line_load_position(one_footpath_manager):
    load = one_footpath_manager.railing_load("left")

    assert load.start.x == pytest.approx(0.15)
    assert load.end.x == pytest.approx(0.15)
    assert load.end.z == pytest.approx(30.0)


import pytest


@pytest.mark.parametrize("clearance", [-1, -0.5, 5.7, 6.0, 10])
def test_overlay_load_rejects_invalid_clearance(clearance):
    manager = create_default_load_placement(
        span=30,
        carriageway_width=7.5,
        crash_barrier_width=0.45,
        no_of_footpaths=1,
        footpath_width=1.5,
        railing_width=0.3,
        median_width=1.2,
    )

    with pytest.raises(ValueError):
        manager.overlay_load(clearance)


@pytest.mark.parametrize("clearance", [True, float("nan"), float("inf")])
def test_overlay_load_rejects_non_finite_or_boolean_clearance(clearance):
    manager = create_default_load_placement(
        span=30,
        carriageway_width=7.5,
        crash_barrier_width=0.45,
        no_of_footpaths=1,
        footpath_width=1.5,
        railing_width=0.3,
        median_width=1.2,
    )

    with pytest.raises(ValueError):
        manager.overlay_load(clearance)


@pytest.mark.parametrize("invalid_side", ["middle", "centre", "LEFT", "", None])
def test_railing_load_rejects_invalid_side(
    one_footpath_manager, invalid_side
):
    from osdagbridge.core.bridge_types.plate_girder.bridge_geometry import (
        RailingLoad,
    )

    load = RailingLoad(
        one_footpath_manager.bridge,
        offset_from_edge=0.15,
        side=invalid_side,
    )

    with pytest.raises(ValueError, match="side must be 'left' or 'right'"):
        load.to_global()


@pytest.mark.parametrize("invalid_side", ["middle", "centre", "RIGHT", "", None])
def test_median_load_rejects_invalid_side(
    one_footpath_manager, invalid_side
):
    from osdagbridge.core.bridge_types.plate_girder.bridge_geometry import (
        MedianLoad,
    )

    load = MedianLoad(
        one_footpath_manager.bridge,
        offset_from_edge=6.6,
        side=invalid_side,
    )

    with pytest.raises(ValueError, match="side must be 'left' or 'right'"):
        load.to_global()
