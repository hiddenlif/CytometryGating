import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
spec = importlib.util.spec_from_file_location('validate_existing', Path(__file__).parents[1] / 'scripts/validate_existing_data.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def test_matching_counts_do_not_hide_wrong_event_membership():
    with pytest.raises(ValueError, match='membership mismatches'):
        validator.assert_membership(np.array([True, False]), np.array([False, True]), np.ones(2, dtype=bool))


def test_child_cannot_escape_parent_even_with_identical_replays():
    child = np.array([True, True])
    with pytest.raises(ValueError, match='escapes'):
        validator.assert_membership(child, child, np.array([True, False]))


def test_numeric_membership_is_not_silently_cast_to_boolean():
    with pytest.raises(ValueError, match='boolean'):
        validator.assert_membership(np.array([0, 2]), np.array([False, True]), np.ones(2, dtype=bool))


def test_event_count_mismatch_is_rejected():
    with pytest.raises(ValueError, match='counts differ'):
        validator.assert_membership(np.ones(2, dtype=bool), np.ones(3, dtype=bool), np.ones(2, dtype=bool))


def test_duplicate_filenames_cannot_silently_select_a_different_sample():
    with pytest.raises(ValueError, match='Ambiguous'):
        validator.exact_index([{'filename': 'sample.fcs', 'path': 'first'}, {'filename': 'sample.fcs', 'path': 'second'}])


def test_permuted_counts_require_restored_event_order():
    original = np.array([True, False, True])
    permutation = np.array([1, 0, 2])
    validator.assert_membership(original[permutation], original[permutation], np.ones(3, dtype=bool))
    with pytest.raises(ValueError, match='membership mismatches'):
        validator.assert_membership(original, original[permutation], np.ones(3, dtype=bool))
