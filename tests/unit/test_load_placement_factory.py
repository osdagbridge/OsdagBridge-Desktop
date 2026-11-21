import pytest

from osdagbridge.core.bridge_types.plate_girder import bridge_geometry as bg


def create_layout(no_of_footpaths):
    return bg.CrossSectionLayout(
        carriageway_width=7.5,
        crash_barrier_width=0.45,
        railing_width=0.30,
        footpath_width=1.50,
        median_width=1.20,
        no_of_footpaths=no_of_footpaths,
    )


@pytest.mark.parametrize(
    ("footpaths", "expected_width"),
    [
        (0, 9.60),
        (1, 11.40),
        (2, 13.20),
    ],
)
def test_default_factory_builds_valid_manager(footpaths, expected_width):
    manager = bg.create_default_load_placement(
        span=33.5,
        carriageway_width=7.5,
        crash_barrier_width=0.45,
        no_of_footpaths=footpaths,
        footpath_width=1.50,
        railing_width=0.30,
        median_width=1.20,
    )

    assert isinstance(manager, bg.LoadPlacementManager)
    assert manager.bridge.span == pytest.approx(33.5)
    assert manager.bridge.width == pytest.approx(expected_width)
    assert manager.layout.total_width == pytest.approx(expected_width)


def test_manager_generates_deck_geometry():
    layout = create_layout(2)
    bridge = bg.BridgeGeometry(span=33.5, width=layout.total_width)
    manager = bg.LoadPlacementManager(bridge, layout)

    deck = manager.deck_load()

    assert deck.p1 == bg.Point(0.0, 0.0)
    assert deck.p2 == bg.Point(13.2, 0.0)
    assert deck.p3 == bg.Point(13.2, 33.5)
    assert deck.p4 == bg.Point(0.0, 33.5)


def test_manager_generates_left_and_right_footpaths():
    layout = create_layout(2)
    bridge = bg.BridgeGeometry(span=33.5, width=layout.total_width)
    manager = bg.LoadPlacementManager(bridge, layout)

    left = manager.footpath_load("left")
    right = manager.footpath_load("right")

    assert left.p1.x == pytest.approx(0.30)
    assert left.p2.x == pytest.approx(1.80)

    assert right.p1.x == pytest.approx(11.40)
    assert right.p2.x == pytest.approx(12.90)


def test_single_footpath_layout_has_no_right_footpath():
    layout = create_layout(1)
    bridge = bg.BridgeGeometry(span=33.5, width=layout.total_width)
    manager = bg.LoadPlacementManager(bridge, layout)

    assert layout.has_component("footpath_left")
    assert not layout.has_component("footpath_right")

    with pytest.raises(KeyError):
        manager.footpath_load("right")


def test_from_layout_creates_manager():
    layout = create_layout(2)

    manager = bg.from_layout(layout=layout, span=33.5)

    assert isinstance(manager, bg.LoadPlacementManager)
    assert manager.bridge.span == pytest.approx(33.5)
    assert manager.bridge.width == pytest.approx(layout.total_width)

@pytest.mark.parametrize(
    "footpaths",
    [-1, 3, 1.5, True],
)
def test_layout_rejects_invalid_footpath_count(footpaths):
    with pytest.raises(
        ValueError,
        match="no_of_footpaths must be 0, 1, or 2",
    ):
        create_layout(footpaths)