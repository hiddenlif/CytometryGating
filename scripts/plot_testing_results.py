"""Create review figures from the saved offline testing reports."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "reports/local/testing"
    report = json.loads((output / "validation.json").read_text())
    cases = [c for w in report["workspaces"] for c in w["cases"]]
    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(cases))
    for level in range(4):
        values = [c["gates"][level]["percent_of_all_events"] for c in cases]
        ax.bar(
            x + (level - 1.5) * 0.2,
            values,
            width=0.2,
            label=["Scatter parent", "Singlets", "Live", "CAR"][level],
        )
    ax.set_xticks(
        x, [c["sample"].removesuffix(".fcs") for c in cases], rotation=25, ha="right"
    )
    ax.set_ylabel("Events retained (% of all input events)")
    ax.set_ylim(0, 105)
    ax.set_title(
        "Author gate replay: CAR-NK development files\nFixed author gates in FlowKit; biological accuracy and FlowJo agreement untested"
    )
    ax.legend(ncols=4, loc="upper center")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(output / "author-gate-retention.png", dpi=160)
    plt.close(fig)
    batch = json.loads((output / "opencyto/validation.json").read_text())
    gates = [c["gate"] for c in batch["cases"] if c["status"] == "passed"]
    selected = [100 * g["selected_count"] / g["event_count"] for g in gates]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.scatter([g["event_count"] for g in gates], selected, s=30, alpha=0.7)
    ax.set_xscale("log")
    ax.set_xlabel("Input events per file (log scale)")
    ax.set_ylabel("Events above fitted FSC-A threshold (%)")
    ax.set_title(
        f"{len(gates)} per-file openCyto fits: engineering scatter gate\nNo biological population identity assigned"
    )
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output / "opencyto-fit-review.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
