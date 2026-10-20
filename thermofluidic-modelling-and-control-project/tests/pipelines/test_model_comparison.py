"""Synthetic interface fixtures; no production model predictions available."""

import pandas as pd
import pytest

from thermofluidic_modelling_and_control_project.pipelines.measurement_results.model_comparison import compare_models, validate_window_supports


def test_duration_weighted_metrics_and_provenance_gate():
    common = {"variable": "T", "position_id": "P", "episode": "fixture", "regime": "fixture", "timestamp": pd.to_datetime(["2026-01-01 00:00:20", "2026-01-01 00:00:40"]), "unit": "degC", "observation_operator": "point_v1", "source_class": "synthetic"}
    references = pd.DataFrame({**common, "reference": [20., 20.], "duration_seconds": [10., 30.], "independent": True, "used_for_development": False, "reference_provenance": "synthetic fixture only"})
    predictions = pd.DataFrame({**common, "prediction": [21., 23.], "model": "fixture", "horizon_seconds": 20., "origin_timestamp": pd.to_datetime(["2026-01-01 00:00:00", "2026-01-01 00:00:20"])})
    result = compare_models(predictions, references, {"enabled": True})
    assert result.MAE.iloc[0] == 2.5
    assert result.RMSE.iloc[0] == pytest.approx(7**0.5)
    assert result.classification.iloc[0] == "synthetic_comparison"
    for column, value in [("unit", "K"), ("independent", False), ("source_class", "unknown")]:
        invalid = references.copy()
        invalid[column] = value
        with pytest.raises(ValueError):
            compare_models(predictions, invalid, {"enabled": True})
    with pytest.raises(ValueError):
        compare_models(predictions, references, {"enabled": False})


def test_window_supports_reject_shared_history_and_targets():
    windows = pd.DataFrame({"trajectory_id": "synthetic_fixture", "partition": ["train", "validation"], "support_start": ["2026-01-01", "2026-01-02"], "support_end": ["2026-01-02", "2026-01-03"]})
    with pytest.raises(ValueError):
        validate_window_supports(windows)
    windows.loc[1, "support_start"] = "2026-01-02 00:00:01"
    assert validate_window_supports(windows)["windows"] == 2
