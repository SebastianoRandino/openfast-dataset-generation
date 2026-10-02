"""Synthetic decoding and analytical checks; never execute OpenFAST."""

import importlib.util
import struct
from pathlib import Path

import numpy as np
import pytest

MODULE = Path(__file__).resolve().parents[1] / "analysis/structural_comparison/analyze.py"
spec = importlib.util.spec_from_file_location("structural_analysis", MODULE)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


@pytest.mark.parametrize("fid", [1, 2, 3, 4])
def test_outb_decodes_known_physical_values_and_times(tmp_path, fid):
    length = 12 if fid == 4 else 10
    blob = struct.pack("<h", fid)
    if fid == 4:
        blob += struct.pack("<h", length)
    blob += struct.pack("<ii", 2, 3)
    blob += struct.pack("<dd", 100, 0) if fid == 1 else struct.pack("<dd", 0, 0.01)
    if fid != 3:
        blob += struct.pack("<ff", 2, 4) + struct.pack("<ff", 10, -8)
    blob += struct.pack("<i", 4) + b"test"
    for item in ["Time", "A", "B", "(s)", "(N)", "(N-m)"]:
        blob += item.encode().ljust(length)
    if fid == 1:
        blob += struct.pack("<iii", 0, 1, 2)
    expected = np.array([[1, 2], [3, 4], [5, 6]], dtype=float)
    blob += (
        expected.astype("<f8").tobytes()
        if fid == 3
        else (expected * [2, 4] + [10, -8]).astype("<i2").tobytes()
    )
    path = tmp_path / "test.outb"
    path.write_bytes(blob)
    record = analysis.read_outb(path)
    np.testing.assert_allclose(record[0], [0, 0.01, 0.02])
    np.testing.assert_allclose(record[3], expected)
    np.testing.assert_allclose(analysis.extract(record, "A", "N", 0.001), expected[:, 0] / 1000)
    with pytest.raises(ValueError, match="expected"):
        analysis.extract(record, "A", "kN", 1)
    path.write_bytes(blob[:-1])
    with pytest.raises(ValueError, match="payload"):
        analysis.read_outb(path)


def test_statistics_and_near_zero_reference():
    row = analysis.compare(np.array([-1.0, 1.0]), np.array([0.0, 2.0]))
    assert row["ed_mean"] == 0
    assert row["ed_std"] == 1
    assert row["ed_rms"] == 1
    assert row["absolute_mean_difference"] == 1
    assert np.isnan(row["relative_mean_difference_pct"])
    assert row["relative_std_difference_pct"] == 0
    assert row["bd_peak_to_peak"] == 2
    constant = analysis.compare(np.ones(10), np.ones(10) * 2)
    assert constant["relative_mean_difference_pct"] == 100
    assert np.isnan(constant["relative_std_difference_pct"])


def test_welch_sinusoid_peak_and_integrated_variance():
    n = 8192
    fs = 100
    frequency = 80 * fs / n
    signal = 3 * np.sin(2 * np.pi * frequency * np.arange(30001) / fs) + 42
    f, p = analysis.welch(signal)
    assert f[np.argmax(p)] == frequency
    assert np.sum(p) * (fs / n) == pytest.approx(4.5, rel=1e-10)
    assert analysis.welch(2 * signal)[1].sum() == pytest.approx(4 * p.sum())


def test_mapping_allowlist_and_load_conversion():
    mapping = analysis.channel_map()
    assert len(mapping) == 41
    assert len({m["channel"] for m in mapping}) == 41
    root = next(m for m in mapping if m["channel"] == "RootMyb1")
    assert root["bd"] == "B1RootMyr"
    assert root["bd_unit"] == "N-m"
    assert root["unit"] == "kN-m"
    assert root["bd_factor"] == 0.001
