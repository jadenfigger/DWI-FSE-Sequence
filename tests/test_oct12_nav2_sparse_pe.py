"""Regression checks for the recovered v1.83 nav-mode-2 scan N PE geometry."""
import sys
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parents[1] / "docs" / "data"
sys.path.insert(0, str(DATA))

from oct12_nav_common import N_LINES, nav2_imaging_rows, ns  # noqa: E402


def test_scan_n_maps_seven_echoes_into_original_eight_echo_table():
    acquired = nav2_imaging_rows()
    planned = ns["pe_rows"](128, 8, 1).reshape(16, 8)
    expected = planned[:, :7].ravel()

    assert N_LINES == 128
    assert acquired.shape == (112,)
    np.testing.assert_array_equal(acquired, expected)
    assert len(np.unique(acquired)) == 112
    np.testing.assert_array_equal(np.setdiff1d(np.arange(128), acquired), np.r_[0:8, 120:128])


def test_compact_112_row_order_matches_sparse_grid_up_to_common_row_origin():
    actual = nav2_imaging_rows()
    compact = ns["pe_rows"](112, 7, 1)
    np.testing.assert_array_equal(actual - 8, compact)
    assert actual.min() == 8
    assert actual.max() == 119
