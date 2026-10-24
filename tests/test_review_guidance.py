import sys
from pathlib import Path

import flowkit as fk
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from apply_review_guidance import clip_right, make_revision, pixel_to_data, state_hash


def test_pixel_calibration_inverts_y_and_extrapolates_outside_axes():
    calibration = {
        "x_pixels": [100, 200],
        "x_values": [0, 1],
        "y_pixels": [300, 100],
        "y_values": [0, 1],
    }
    np.testing.assert_allclose(
        pixel_to_data([[150, 200], [90, 80]], calibration), [[0.5, 0.5], [-0.1, 1.1]]
    )


def test_clipped_polygon_matches_independent_half_plane_predicate():
    square = [[0, 0], [1, 0], [1, 1], [0, 1]]
    vertices = clip_right(square, 0.23, 0.43)
    points = np.random.default_rng(7).uniform(-0.1, 1.1, (2000, 2))
    import pandas as pd

    gate = fk.gates.PolygonGate(
        "clipped", [fk.Dimension("x"), fk.Dimension("y")], vertices
    )
    actual = gate.apply(pd.DataFrame(points, columns=["x", "y"]))
    expected = (
        (points[:, 0] >= 0.23 + 0.43 * points[:, 1])
        & (points[:, 0] > 0)
        & (points[:, 0] < 1)
        & (points[:, 1] > 0)
        & (points[:, 1] < 1)
    )
    np.testing.assert_array_equal(actual, expected)


def test_degenerate_calibration_and_empty_intersection_fail():
    with pytest.raises(ValueError, match="Degenerate"):
        pixel_to_data(
            [[1, 1]],
            {
                "x_pixels": [0, 0],
                "x_values": [0, 1],
                "y_pixels": [0, 1],
                "y_values": [0, 1],
            },
        )
    with pytest.raises(ValueError, match="entire"):
        clip_right([[0, 0], [1, 0], [1, 1], [0, 1]], 2, 0)


def test_revision_preserves_source_downstream_geometry_and_processing():
    original = fk.GatingStrategy()
    square = [[0, 0], [1, 0], [1, 1], [0, 1]]
    original.add_gate(
        fk.gates.PolygonGate(
            "No Debris", [fk.Dimension("FSC-A"), fk.Dimension("SSC-A")], square
        ),
        ("root",),
    )
    original.add_gate(
        fk.gates.PolygonGate(
            "Singlets", [fk.Dimension("FSC-A"), fk.Dimension("FSC-H")], square
        ),
        ("root", "No Debris"),
    )
    original.add_gate(
        fk.gates.RectangleGate("Live", [fk.Dimension("viability", range_max=0.7)]),
        ("root", "No Debris", "Singlets"),
    )
    original.add_gate(
        fk.gates.RectangleGate("CAR", [fk.Dimension("CAR", range_min=0.5)]),
        ("root", "No Debris", "Singlets", "Live"),
    )
    calibration = {
        "x_pixels": [0, 10],
        "x_values": [0, 1],
        "y_pixels": [10, 0],
        "y_values": [0, 1],
    }
    config = {
        "first_gate": {**calibration, "line_pixels": [[2, 10], [8, 0]]},
        "second_gate": {
            **calibration,
            "polygon_pixels": [[3, 7], [7, 3], [8, 4], [4, 8]],
        },
    }
    fingerprints = {
        n: state_hash(original.get_gate(n, p)) for n, p in original.get_gate_ids()
    }
    revised, geometry = make_revision(original, "fixture", config)
    assert geometry["intercept"] == pytest.approx(0.2)
    assert geometry["slope_x_per_y"] == pytest.approx(0.6)
    for name, path in original.get_gate_ids():
        assert state_hash(original.get_gate(name, path)) == fingerprints[name]
        if name in ["Live", "CAR"]:
            assert state_hash(revised.get_gate(name, path)) == fingerprints[name]
        else:
            assert state_hash(revised.get_gate(name, path)) != fingerprints[name]
