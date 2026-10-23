"""Validate GatingML before publishing an export; preserve exact gate semantics."""
import io
from pathlib import Path

import flowkit as fk
import numpy as np


def export_verified_gatingml(strategy, destination, sample=None, sample_id=None):
    buffer = io.BytesIO()
    fk.export_gatingml(strategy, buffer, sample_id=sample_id)
    payload = buffer.getvalue()
    reloaded = fk.parse_gating_xml(io.BytesIO(payload))
    if sample is not None:
        before = strategy.gate_sample(sample)
        after = reloaded.gate_sample(sample)
        if set(strategy.get_gate_ids()) != set(reloaded.get_gate_ids()):
            raise ValueError('GatingML changed gate identities or hierarchy')
        for name, path in strategy.get_gate_ids():
            if not np.array_equal(before.get_gate_membership(name, path), after.get_gate_membership(name, path)):
                raise ValueError('GatingML changed event membership')
    Path(destination).write_bytes(payload)
