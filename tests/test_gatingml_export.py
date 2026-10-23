import importlib.util
from pathlib import Path

import flowkit as fk
import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('gatingml_export', Path(__file__).parents[1] / 'scripts/gatingml_export.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def test_supported_gate_roundtrip_preserves_boundary_membership(tmp_path):
    sample = fk.Sample(np.array([[0.], [1.], [2.]]), sample_id='boundary', channel_labels=['FSC-A'], preprocess=False)
    strategy = fk.GatingStrategy()
    strategy.add_gate(fk.gates.RectangleGate('positive', [fk.Dimension('FSC-A', range_min=1.)]), ('root',))
    path = tmp_path / 'gates.xml'
    exporter.export_verified_gatingml(strategy, path, sample)
    result = fk.parse_gating_xml(path).gate_sample(sample)
    np.testing.assert_array_equal(result.get_gate_membership('positive'), [False, True, True])


def test_unsupported_flowjo_transform_cannot_publish_or_overwrite_export(tmp_path):
    strategy = fk.GatingStrategy()
    strategy.add_transform('flowjo_biex', fk.transforms.WSPBiexTransform())
    strategy.add_gate(fk.gates.RectangleGate('positive', [fk.Dimension('APC-A', transformation_ref='flowjo_biex', range_min=1.)]), ('root',))
    path = tmp_path / 'gates.xml'
    path.write_bytes(b'previous verified artifact')
    with pytest.raises(ValueError, match='neither GatingML'):
        exporter.export_verified_gatingml(strategy, path)
    assert path.read_bytes() == b'previous verified artifact'
