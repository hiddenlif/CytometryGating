"""Apply the user's pictured debris/singlet guidance as a source-bound variant."""

import copy
import hashlib
import json
import pickle

import flowkit as fk
import matplotlib.pyplot as plt
import numpy as np
from build_scatter_report import (
    ASSETS,
    annotate_bounds,
    density_scatter,
    dimension_label,
    workspace_plot,
    write_csv,
)
from matplotlib.path import Path as PolygonPath
from validate_existing_data import (
    ROOT,
    assert_membership,
    sample_from_events,
    verify_source,
)


def pixel_to_data(points, calibration):
    values = np.asarray(points, dtype=float).copy()
    for column, axis in enumerate(["x", "y"]):
        pixels = calibration[f"{axis}_pixels"]
        coordinates = calibration[f"{axis}_values"]
        if pixels[0] == pixels[1]:
            raise ValueError("Degenerate image axis calibration")
        values[:, column] = coordinates[0] + (values[:, column] - pixels[0]) * (
            coordinates[1] - coordinates[0]
        ) / (pixels[1] - pixels[0])
    return values


def clip_right(polygon, intercept, slope):
    """Intersect a polygon with x >= intercept + slope*y."""
    result = []
    previous = np.asarray(polygon[-1], dtype=float)
    prior = previous[0] - intercept - slope * previous[1]
    for current in np.asarray(polygon, dtype=float):
        value = current[0] - intercept - slope * current[1]
        if (value >= 0) != (prior >= 0):
            result.append(
                (previous + prior / (prior - value) * (current - previous)).tolist()
            )
        if value >= 0:
            result.append(current.tolist())
        previous, prior = current, value
    if len(result) < 3:
        raise ValueError("Guidance excludes the entire author polygon")
    return result


def state_hash(value):
    return hashlib.sha256(pickle.dumps(value, protocol=5)).hexdigest()


def make_revision(original, sample_id, configuration):
    line = pixel_to_data(
        configuration["first_gate"]["line_pixels"], configuration["first_gate"]
    )
    if line[0, 1] == line[1, 1]:
        raise ValueError("The drawn line cannot define x as a function of y")
    slope = (line[1, 0] - line[0, 0]) / (line[1, 1] - line[0, 1])
    intercept = line[0, 0] - slope * line[0, 1]
    singlets = pixel_to_data(
        configuration["second_gate"]["polygon_pixels"], configuration["second_gate"]
    ).tolist()
    revised = fk.GatingStrategy()
    for name, matrix in original.comp_matrices.items():
        revised.add_comp_matrix(name, copy.deepcopy(matrix))
    for name, transform in original.transformations.items():
        revised.add_transform(name, copy.deepcopy(transform))
    for name, path in original.get_gate_ids():
        gate = copy.deepcopy(original.get_gate(name, path, sample_id=sample_id))
        if name == "No Debris":
            gate.vertices = clip_right(gate.vertices, intercept, slope)
        elif name == "Singlets":
            gate.vertices = singlets
        revised.add_gate(gate, path)
    if state_hash(original.comp_matrices) != state_hash(revised.comp_matrices):
        raise ValueError("Revision changed compensation")
    if state_hash(original.transformations) != state_hash(revised.transformations):
        raise ValueError("Revision changed transformations")
    for name, path in original.get_gate_ids():
        if name in ["No Debris", "Singlets"]:
            continue
        if state_hash(original.get_gate(name, path, sample_id=sample_id)) != state_hash(
            revised.get_gate(name, path)
        ):
            raise ValueError("Revision changed downstream gate geometry")
    return revised, {
        "intercept": intercept,
        "slope_x_per_y": slope,
        "line_data_points": line.tolist(),
        "singlet_vertices": singlets,
        "keep": "x >= intercept + slope_x_per_y*y inside original No Debris polygon",
    }


class ResultView:
    def __init__(self, sample, strategy, results):
        self.sample, self.strategy, self.results = sample, strategy, results

    def get_sample(self, sample_id):
        return self.sample

    def get_gating_strategy(self, sample_id):
        return self.strategy

    def get_gate_membership(self, sample_id, name, path):
        return self.results.get_gate_membership(name, path)


def comparison_plot(sample, original, baseline, revised, results, output):
    fig, axes = plt.subplots(2, 2, figsize=(13, 10), sharex="row", sharey="row")
    for row, (name, path) in enumerate(original.get_gate_ids()[:2]):
        for column, (strategy, result, title, color) in enumerate(
            [
                (original, baseline, "Original author gate", "#e83e8c"),
                (revised, results, "User-guided revision", "#ed8a00"),
            ]
        ):
            ax = axes[row, column]
            gate = strategy.get_gate(name, path, sample_id=sample.id)
            coords = strategy._preprocess_sample_events(sample, gate)
            parent = (
                np.ones(sample.event_count, dtype=bool)
                if path == ("root",)
                else result.get_gate_membership(path[-1], path[:-1])
            )
            member = result.get_gate_membership(name, path)
            density_scatter(
                ax,
                coords[gate.dimensions[0].id].to_numpy()[parent],
                coords[gate.dimensions[1].id].to_numpy()[parent],
            )
            annotate_bounds(ax, gate, color=color)
            ax.set_xlabel(dimension_label(gate.dimensions[0], strategy))
            ax.set_ylabel(dimension_label(gate.dimensions[1], strategy))
            ax.set_title(
                f"{title}: {name}\n{member.sum():,} / {parent.sum():,} ({100 * member.sum() / parent.sum():.2f}%)",
                fontsize=12,
            )
    fig.suptitle(
        f"{sample.id}\nUser-drawn guidance, digitized approximately; every parent event shown",
        fontsize=14,
    )
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))
    fig.savefig(output, dpi=145)
    plt.close(fig)


def main():
    config_path = ROOT / "data/gating-reviews/nk-her2-v1.json"
    config = json.loads(config_path.read_text())
    if (
        hashlib.sha256((ROOT / config["annotation_source"]).read_bytes()).hexdigest()
        != config["annotation_sha256"]
    ):
        raise ValueError("Annotation source image changed")
    manifest = json.loads((ROOT / "data/manifests/public-files.json").read_text())
    source = next(
        r
        for r in manifest["files"]
        if r["dataset"] == "car-nk-knockin" and r["filename"] == config["sample_id"]
    )
    wsp = next(
        r
        for r in manifest["files"]
        if r["dataset"] == "car-nk-knockin" and r["filename"] == config["workspace"]
    )
    sample = fk.Sample(
        str(verify_source(source)), sample_id=config["sample_id"], preprocess=False
    )
    workspace = fk.Workspace(
        str(verify_source(wsp)), fcs_samples=[sample], load_missing_file_data=True
    )
    original = workspace.get_gating_strategy(sample.id)
    baseline = original.gate_sample(sample)
    revised, geometry = make_revision(original, sample.id, config)
    results = revised.gate_sample(sample)
    order = np.random.default_rng(20261018).permutation(sample.event_count)
    permuted = revised.gate_sample(sample_from_events(sample, order))
    subset_indices = order[: sample.event_count // 2]
    subset = revised.gate_sample(sample_from_events(sample, subset_indices))
    records = []
    memberships = {}
    for name, path in revised.get_gate_ids():
        before = baseline.get_gate_membership(name, path)
        after = results.get_gate_membership(name, path)
        parent = (
            np.ones(sample.event_count, dtype=bool)
            if path == ("root",)
            else results.get_gate_membership(path[-1], path[:-1])
        )
        old_parent = (
            np.ones(sample.event_count, dtype=bool)
            if path == ("root",)
            else baseline.get_gate_membership(path[-1], path[:-1])
        )
        assert_membership(
            after, permuted.get_gate_membership(name, path)[np.argsort(order)], parent
        )
        assert_membership(
            after[subset_indices],
            subset.get_gate_membership(name, path),
            parent[subset_indices],
        )
        if name == "No Debris":
            coords = original._preprocess_sample_events(
                sample, original.get_gate(name, path, sample_id=sample.id)
            )
            predicate = (
                coords["FSC-A"].to_numpy()
                >= geometry["intercept"]
                + geometry["slope_x_per_y"] * coords["SSC-A"].to_numpy()
            ) & before
        elif name == "Singlets":
            coords = revised._preprocess_sample_events(
                sample, revised.get_gate(name, path)
            )
            predicate = (
                PolygonPath(geometry["singlet_vertices"]).contains_points(
                    coords[["FSC-A", "FSC-H"]].to_numpy()
                )
                & parent
            )
        else:
            coords = original._preprocess_sample_events(
                sample, original.get_gate(name, path, sample_id=sample.id)
            )
            predicate = (
                np.asarray(
                    original.get_gate(name, path, sample_id=sample.id).apply(coords),
                    dtype=bool,
                )
                & parent
            )
        assert_membership(after, predicate, parent)
        count, denominator = int(after.sum()), int(parent.sum())
        if not np.isclose(
            results.get_gate_relative_percent(name, path),
            100 * count / denominator,
            rtol=0,
            atol=1e-10,
        ):
            raise ValueError("Revised denominator mismatch")
        records.append(
            {
                "gate": name,
                "original_count": int(before.sum()),
                "original_parent_count": int(old_parent.sum()),
                "original_percent_of_parent": 100 * before.sum() / old_parent.sum(),
                "revised_count": count,
                "revised_parent_count": denominator,
                "revised_percent_of_parent": 100 * count / denominator,
                "excluded_vs_original": int(np.count_nonzero(before & ~after)),
                "included_vs_original": int(np.count_nonzero(after & ~before)),
            }
        )
        memberships[name] = after
    directory = ASSETS / "reviews/nk-her2-v1"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "configuration.json").write_bytes(config_path.read_bytes())
    plotted = workspace_plot(
        ResultView(sample, revised, results),
        sample.id,
        directory / "revised-hierarchy.png",
        heading="User-guided revision v1",
        original_strategy=original,
    )
    comparison_plot(
        sample, original, baseline, revised, results, directory / "before-after.png"
    )
    local = ROOT / "reports/local/testing/reviews/nk-her2-v1"
    local.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(local / "memberships.npz", **memberships)
    report = {
        "id": config["id"],
        "sample": sample.id,
        "workspace": wsp["filename"],
        "events": sample.event_count,
        "source_checksum": source["checksum"],
        "source_checksum_algorithm": source["checksum_algorithm"],
        "workspace_checksum": wsp["checksum"],
        "configuration": str(config_path.relative_to(ROOT)),
        "configuration_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "annotation_sha256": config["annotation_sha256"],
        "coordinate_status": config["coordinate_status"],
        "scope": config["scope"],
        "geometry": geometry,
        "gates": records,
        "plot_geometry": plotted,
        "checks": {
            "analytic_first_gate": "passed",
            "independent_singlet_polygon": "passed",
            "unchanged_live_car_geometry": "passed",
            "compensation_and_transforms_unchanged": "passed",
            "event_permutation": "passed",
            "event_subset": "passed",
            "nested_membership_and_denominators": "passed",
            "figure_geometry": "passed",
        },
        "interpretation": "User-guided manual development revision. This is not an automatic fit, exact vector transcription, or independent biological accuracy validation.",
    }
    report["figure_sha256"] = {
        n: hashlib.sha256((directory / n).read_bytes()).hexdigest()
        for n in ["revised-hierarchy.png", "before-after.png", "user-guidance.png"]
    }
    (directory / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    write_csv(directory / "gate-comparison.csv", records, list(records[0]))
    print(
        json.dumps(
            {"sample": sample.id, "gates": records, "checks": report["checks"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
