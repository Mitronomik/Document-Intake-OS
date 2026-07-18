from __future__ import annotations

from spikes.windows_encryption.performance_probe import measure_aes_gcm, measure_standard_sqlite


def test_performance_samples_are_bounded_and_non_thresholded() -> None:
    sqlite_samples = measure_standard_sqlite()
    assert sqlite_samples
    assert all(sample.sample_count == 3 for sample in sqlite_samples)
    aes_samples = measure_aes_gcm()
    assert all(sample.sample_count == 3 for sample in aes_samples)
