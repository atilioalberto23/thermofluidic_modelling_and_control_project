"""Synthetic software fixtures, never experimental evidence."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest
import yaml

from thermofluidic_modelling_and_control_project.pipelines.measurement_results.nodes import prepare_measurements, psychrometrics, summarize_measurements


@pytest.fixture
def config():
    with open("conf/base/parameters_measurement_results.yml", encoding="utf-8") as stream:
        return yaml.safe_load(stream)["measurement_results"]


@pytest.fixture
def measurements():
    times = pd.to_datetime(["2026-01-01 00:00:00", "2026-01-01 00:00:20", "2026-01-01 00:02:00", "2026-01-01 00:02:20"])
    return pd.DataFrame({"SURFACE": "BACK_WALL", "NODE_ID": None, "SENSOR_POSITION": "SO", "X": 0.1, "Y": 0.2, "TIMESTAMP": times, "MSR_PRD_ID": times.strftime("%Y%m%d%H%M%S"), "DS_TEMPERATURE": [25., 26., 27., 28.], "DHT_TEMPERATURE": 25., "DHT_HUMIDITY": 50., "DS_TEMP_ANT": np.nan})


def test_null_node_gap_and_source_preserved(measurements, config):
    original = measurements.copy(deep=True)
    result = prepare_measurements(measurements, config)
    assert result.DS_TEMP_ANT.iloc[1] == 25
    assert np.isnan(result.DS_TEMP_ANT.iloc[2])
    assert result.DS_TEMP_ANT.iloc[3] == 27
    assert result.ORIGINAL_DS_TEMP_ANT.isna().all()
    assert result.VALIDATION_CLASS.eq("synthetic_processing").all()
    pd.testing.assert_frame_equal(original, measurements)


def test_sensor_position_and_episode_boundaries(measurements, config):
    measurements["episode"] = ["A", "B", "B", "B"]
    measurements.loc[3, "X"] = 0.5
    config["episode_column"] = "episode"
    result = prepare_measurements(measurements, config)
    assert result.DS_TEMP_ANT.isna().all()
    assert result.IDENTITY_CONFLICT.all()
    other = measurements.copy()
    other["NODE_ID"] = "N1"
    other["DS_TEMPERATURE"] += 100
    merged = prepare_measurements(pd.concat([measurements, other]), config)
    assert merged.groupby("SENSOR_ID").head(1).DS_TEMP_ANT.isna().all()


def test_duplicates_invalid_values_and_coverage(measurements, config):
    duplicate = measurements.iloc[[1]].copy()
    duplicate["DS_TEMPERATURE"] = 90
    measurements.loc[3, "DHT_HUMIDITY"] = 101
    result = prepare_measurements(pd.concat([measurements, duplicate]), config)
    assert result.CONFLICTING_DUPLICATE.sum() == 2
    assert result.INVALID_DHT_HUMIDITY.sum() == 1
    assert not result[result.DUPLICATE_TIME].INCLUDED_SUMMARIES.any()
    _, coverage, _, concordance = summarize_measurements(result, config)
    assert coverage.DHT_HUMIDITY_valid.sum() == 2
    assert concordance["count"].sum() == 3


def test_psychrometrics_requires_explicit_inputs(measurements, config):
    data = prepare_measurements(measurements, config)
    assert psychrometrics(data, config).W_KG_PER_KG_DRY_AIR.isna().all()
    configured = deepcopy(config)
    configured["temperature_unit"] = "degC"
    configured["psychrometrics"] = {"pressure_pa": 101325, "pressure_provenance": "synthetic assumed fixture", "pressure_uncertainty_pa": 1000, "temperature_compatible": True}
    result = psychrometrics(data, configured)
    assert result.W_KG_PER_KG_DRY_AIR.iloc[0] == pytest.approx(0.00986, abs=0.0001)
    configured["psychrometrics"]["pressure_pa"] = -1
    with pytest.raises(ValueError):
        psychrometrics(data, configured)


def test_unknown_source_never_experimental(measurements, config):
    config["source_class"] = "unknown"
    result = prepare_measurements(measurements, config)
    assert result.VALIDATION_CLASS.eq("descriptive_only").all()
