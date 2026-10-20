"""Auditable local measurement processing, without modifying original rows."""

import hashlib
import importlib.metadata
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KEYS = ["SURFACE", "NODE_ID", "SENSOR_POSITION"]
VALUES = ["DS_TEMPERATURE", "DHT_TEMPERATURE", "DHT_HUMIDITY"]
LAGS = ["DS_TEMP_ANT", "DHT_TEMP_ANT", "DHT_HUMIDITY_ANT"]


def prepare_measurements(raw, config):
    """Keep duplicates visible; exclude ambiguous times only from summaries."""
    if config["source_class"] not in {"synthetic", "physical", "mixed", "unknown"}:
        raise ValueError("Explicit synthetic/physical/mixed/unknown source class required")
    if config["nominal_seconds"] <= 0 or config["max_gap_seconds"] <= 0:
        raise ValueError("Positive nominal interval and gap threshold required")
    required = KEYS + ["X", "Y", "TIMESTAMP", "MSR_PRD_ID"] + VALUES
    missing = sorted(set(required) - set(raw.columns))
    if missing or raw.empty:
        raise ValueError(f"Empty data or missing columns: {missing}")
    data = raw.copy().reset_index(drop=True)
    data["SOURCE_ROW"] = np.arange(len(data))
    data["TIMESTAMP"] = pd.to_datetime(data.TIMESTAMP, format="ISO8601", errors="coerce")
    data["INVALID_TIME"] = data.TIMESTAMP.isna()
    encoded = pd.to_datetime(data.MSR_PRD_ID.astype(str), format="%Y%m%d%H%M%S", errors="coerce")
    data["TIME_ID_MISMATCH"] = encoded.ne(data.TIMESTAMP) | encoded.isna()
    for column in VALUES + ["X", "Y"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    # Typed tuple hashes avoid merging nulls with real textual identifiers.
    data["SENSOR_ID"] = pd.util.hash_pandas_object(data[KEYS], index=False).astype(str)
    data["POSITION_ID"] = pd.util.hash_pandas_object(data[KEYS + ["X", "Y"]], index=False).astype(str)
    positions = data.groupby("SENSOR_ID").POSITION_ID.transform("nunique")
    data["IDENTITY_CONFLICT"] = positions.gt(1)
    data["MISSING_IDENTITY"] = data[["SURFACE", "SENSOR_POSITION", "X", "Y"]].isna().any(axis=1)
    data["MISSING_IDENTITY"] |= ~np.isfinite(data[["X", "Y"]]).all(axis=1)
    data["MISSING_IDENTITY"] |= data.NODE_ID.isna() & data.SURFACE.ne("BACK_WALL")
    original_columns = list(raw.columns)
    data["EXACT_DUPLICATE"] = raw.reset_index(drop=True).duplicated(keep=False)
    data["DUPLICATE_TIME"] = data.duplicated(["POSITION_ID", "TIMESTAMP"], keep=False)
    variants = data.groupby(["POSITION_ID", "TIMESTAMP"], dropna=False)[VALUES].transform("nunique", dropna=False)
    data["CONFLICTING_DUPLICATE"] = data.DUPLICATE_TIME & variants.gt(1).any(axis=1)
    for column in VALUES:
        data[f"INVALID_{column}"] = ~np.isfinite(data[column])
    data["INVALID_DHT_HUMIDITY"] |= ~data.DHT_HUMIDITY.between(0, 100)
    limits = config.get("temperature_limits")
    if limits is not None:
        for column in VALUES[:2]:
            data[f"INVALID_{column}"] |= ~data[column].between(*limits)
    episode = config.get("episode_column")
    if episode and episode not in data:
        raise ValueError(f"Episode column missing: {episode}")
    groups = ["SENSOR_ID"]
    data = data.sort_values(groups + ["TIMESTAMP", "SOURCE_ROW"], kind="stable")
    grouped = data.groupby(groups, dropna=False)
    dt = grouped.TIMESTAMP.diff().dt.total_seconds()
    previous_position = grouped.POSITION_ID.shift()
    boundary = dt.isna() | dt.le(0) | dt.gt(config["max_gap_seconds"])
    boundary |= data.POSITION_ID.ne(previous_position)
    boundary |= data.DUPLICATE_TIME | grouped.DUPLICATE_TIME.shift().fillna(False).astype(bool)
    boundary |= data.INVALID_TIME | data.MISSING_IDENTITY
    if episode:
        boundary |= data[episode].ne(grouped[episode].shift())
    data["SEGMENT_ID"] = boundary.groupby(data.SENSOR_ID).cumsum().astype(int)
    data["DT_SECONDS"] = dt
    data["CONTINUOUS"] = ~boundary
    data["NOMINAL_INTERVAL"] = dt.sub(config["nominal_seconds"]).abs().le(config["interval_tolerance_seconds"])
    segments = data.groupby(["SENSOR_ID", "SEGMENT_ID"], dropna=False)
    data["TIMESTAMP_ANT"] = segments.TIMESTAMP.shift()
    for value, lag in zip(VALUES, LAGS):
        if lag in original_columns:
            data[f"ORIGINAL_{lag}"] = data[lag]
        data[lag] = segments[value].shift()
        if lag in original_columns:
            original = pd.to_numeric(data[f"ORIGINAL_{lag}"], errors="coerce")
            data[f"CHANGED_{lag}"] = ~(np.isclose(original, data[lag], equal_nan=True))
    data["SOURCE_CLASS"] = config["source_class"]
    data["PROCESSING_CLASS"] = "source values preserved; lags reconstructed; no calibration or interpolation"
    data["VALIDATION_CLASS"] = "synthetic_processing" if config["source_class"] == "synthetic" else "descriptive_only"
    data["INCLUDED_SUMMARIES"] = ~(data.INVALID_TIME | data.DUPLICATE_TIME | data.MISSING_IDENTITY)
    return data.reset_index(drop=True)


def audit_measurements(raw, data, config, generation_config):
    path = Path(config["input_path"])
    file_info = {"path": str(path), "exists": path.exists(), "storage": "local", "s3_comparison": "not applicable: local storage requested"}
    if path.exists():
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        stat = path.stat()
        file_info.update(bytes=stat.st_size, sha256=digest.hexdigest(), modified_utc=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat())
    flags = [c for c in data if c.startswith(("INVALID_", "CHANGED_"))] + ["TIME_ID_MISMATCH", "IDENTITY_CONFLICT", "MISSING_IDENTITY", "EXACT_DUPLICATE", "DUPLICATE_TIME", "CONFLICTING_DUPLICATE"]
    methodology = Path(config["methodology_path"])
    methodology_info = {"path": str(methodology), "exists": methodology.exists()}
    if methodology.exists():
        methodology_info["sha256"] = hashlib.sha256(methodology.read_bytes()).hexdigest()
    pending = ["Physical independent measurements, calibration and installed DHT11 variant datasheet", "Coordinate units/reference, temperature units and observed timestamp timezone confirmation (methodology prescribes UTC)", "Experimental episodes, device serials, firmware, reception time and relocation validity", "CFD/network/ML/controller predictions and versioned observation operators with compatible independent references", "Air pressure, provenance and joint temperature/RH/pressure uncertainty for psychrometrics", "Coffee moisture, flow, energy and control signals absent", "Physical equivalence margins, residual dependence/block lengths and enough independent episodes", "Chronological whole-episode final split and frozen models; no predictive windows produced by this descriptive pipeline"]
    if not methodology.exists():
        pending.insert(0, "Methodology file unavailable; wider methodological contrast pending")
    report = {
        "source": file_info, "source_class": config["source_class"],
        "interpretation": f"Descriptive {config['source_class']} processing; no hardware accuracy or experimental validation claim",
        "methodology": methodology_info,
        "generation_configuration": generation_config,
        "generation_configuration_status": "Current configuration only, not proof of historical input generation; consult execution log and exact input hash",
        "processing_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": sys.version,
        "rows": len(raw), "schema": {c: str(t) for c, t in raw.dtypes.items()},
        "index": str(raw.index.dtype), "sensors": int(data.SENSOR_ID.nunique()),
        "positions": int(data.POSITION_ID.nunique()),
        "time_start": str(data.TIMESTAMP.min()), "time_end": str(data.TIMESTAMP.max()),
        "flags": {c: int(data[c].sum()) for c in flags},
        "ranges": {c: {"min": float(data[c].replace([np.inf, -np.inf], np.nan).min()), "max": float(data[c].replace([np.inf, -np.inf], np.nan).max()), "missing": int(data[c].isna().sum())} for c in VALUES},
        "interval_seconds": data.DT_SECONDS.describe().to_dict(),
        "policy": "Original rows preserved. All duplicate sensor-position timestamps excluded from summaries; invalid values masked per variable. Position changes, episode changes and long gaps reset history. Segments are not experimental batches. No interpolation.",
        "configuration": config, "pending_requirements": pending,
        "summary_weighting": "Sample-weighted hourly descriptive means, not predictive features. Spatial uniform observed-point weights, population SD. Coverage denominator is nominal slots within each position span, not scheduled uptime.",
        "executed_utc": datetime.now(timezone.utc).isoformat(),
        "versions": {p: importlib.metadata.version(p) for p in ["kedro", "kedro-datasets", "pandas", "numpy", "matplotlib", "pyarrow"]},
    }
    # Strict JSON: absent finite statistics become null rather than nonstandard NaN.
    return json.loads(json.dumps(report), parse_constant=lambda _: None)


def summarize_measurements(data, config):
    eligible = data[data.INCLUDED_SUMMARIES].copy()
    for value in VALUES:
        eligible.loc[eligible[f"INVALID_{value}"], value] = np.nan
    eligible["PERIOD"] = eligible.TIMESTAMP.dt.floor(config["summary_frequency"])
    temporal = eligible.groupby(["POSITION_ID", "SURFACE", "PERIOD"], dropna=False)[VALUES].agg(["count", "mean", "std", "min", "max"])
    temporal.columns = ["_".join(c) for c in temporal.columns]
    temporal = temporal.reset_index()
    coverage = data.groupby("POSITION_ID").agg(SENSOR_ID=("SENSOR_ID", "first"), SURFACE=("SURFACE", "first"), NODE_ID=("NODE_ID", "first"), SENSOR_POSITION=("SENSOR_POSITION", "first"), X=("X", "first"), Y=("Y", "first"), start=("TIMESTAMP", "min"), end=("TIMESTAMP", "max"), rows=("SOURCE_ROW", "count"), included=("INCLUDED_SUMMARIES", "sum"), identity_conflict=("IDENTITY_CONFLICT", "max"))
    coverage["nominal_slots_in_span"] = ((coverage.end - coverage.start).dt.total_seconds() / config["nominal_seconds"]).floordiv(1) + 1
    for value in VALUES:
        counts = eligible.groupby("POSITION_ID")[value].count()
        coverage[f"{value}_valid"] = counts.reindex(coverage.index, fill_value=0)
        coverage[f"{value}_coverage"] = coverage[f"{value}_valid"] / coverage.nominal_slots_in_span
    spatial = eligible.groupby(["SURFACE", "TIMESTAMP"], dropna=False)[VALUES].agg(["count", "mean", "std", "min", "max"])
    for value in VALUES:
        spatial[(value, "std")] = eligible.groupby(["SURFACE", "TIMESTAMP"], dropna=False)[value].std(ddof=0)
        spatial[(value, "amplitude")] = spatial[(value, "max")] - spatial[(value, "min")]
    spatial.columns = ["_".join(c) for c in spatial.columns]
    spatial = spatial.reset_index()
    spatial["weighting"] = "uniform observed sensors; population standard deviation; not area/volume average"
    eligible["DS_MINUS_DHT"] = eligible.DS_TEMPERATURE - eligible.DHT_TEMPERATURE
    concordance = eligible.groupby("POSITION_ID").DS_MINUS_DHT.agg(["count", "mean", "std", "min", "max"]).reset_index()
    concordance["interpretation"] = f"instrument agreement only; {config['source_class']}; not calibration accuracy"
    return temporal, coverage.reset_index(), spatial, concordance


def psychrometrics(data, config):
    """Opt-in Magnus saturation over liquid water; pressure must be explicit."""
    settings = config["psychrometrics"]
    out = data[["SOURCE_ROW", "POSITION_ID", "TIMESTAMP"]].copy()
    out["W_KG_PER_KG_DRY_AIR"] = np.nan
    out["status"] = "omitted: explicit compatible Celsius temperature and pressure with provenance required"
    pressure = settings.get("pressure_pa")
    if pressure is None or config.get("temperature_unit") != "degC" or not settings.get("pressure_provenance") or not settings.get("temperature_compatible"):
        return out
    if not np.isfinite(pressure) or pressure <= 0 or settings.get("pressure_uncertainty_pa") is None or settings["pressure_uncertainty_pa"] < 0:
        raise ValueError("Positive pressure and explicit uncertainty required")
    temperature = data.DHT_TEMPERATURE
    rh = data.DHT_HUMIDITY / 100.0
    vapor = rh * 610.94 * np.exp(17.625 * temperature / (temperature + 243.04))
    valid = data.INCLUDED_SUMMARIES & ~data.INVALID_DHT_TEMPERATURE & ~data.INVALID_DHT_HUMIDITY & temperature.between(0, 50) & vapor.lt(pressure)
    out.loc[valid, "W_KG_PER_KG_DRY_AIR"] = 0.62198 * vapor[valid] / (pressure - vapor[valid])
    out.loc[valid, "status"] = "Magnus liquid water 0..50 degC; pressure " + str(settings["pressure_provenance"])
    out["pressure_pa"] = pressure
    out["pressure_uncertainty_pa"] = settings["pressure_uncertainty_pa"]
    out["Y_VAPOR_MASS_FRACTION"] = out.W_KG_PER_KG_DRY_AIR / (1 + out.W_KG_PER_KG_DRY_AIR)
    out["uncertainty_status"] = "Not propagated: joint T/RH/p uncertainties and covariances required; pressure uncertainty is metadata only"
    return out


def create_figures(data, temporal, coverage, concordance, config):
    label = f"{config['source_class']} | {data.TIMESTAMP.min()} to {data.TIMESTAMP.max()}"
    unit = config.get("temperature_unit") or "unit unconfirmed"
    figures = {}
    for value in VALUES:
        fig, ax = plt.subplots(figsize=(10, 4))
        for surface, rows in temporal.groupby("SURFACE"):
            series = rows.groupby("PERIOD")[f"{value}_mean"].mean()
            ax.plot(pd.to_datetime(series.index), series.values, label=surface)
        ax.set(title=label, ylabel=f"{value} ({'%' if value == 'DHT_HUMIDITY' else unit})", xlabel="Time (timezone unconfirmed)")
        ax.legend(); fig.tight_layout()
        figures[value.lower() + ".png"] = fig
        surfaces = temporal.SURFACE.nunique()
        fig, axes = plt.subplots(max(1, surfaces), 1, figsize=(10, max(4, 3 * surfaces)), sharex=True, squeeze=False)
        axes = axes.ravel()
        identities = coverage.set_index("POSITION_ID")
        for ax_sensor, (surface, rows) in zip(axes, temporal.groupby("SURFACE")):
            for position, values in rows.groupby("POSITION_ID"):
                identity = identities.loc[position]
                sensor_label = f"{identity.NODE_ID if pd.notna(identity.NODE_ID) else 'BACK'} {identity.SENSOR_POSITION}"
                ax_sensor.plot(pd.to_datetime(values.PERIOD), values[f"{value}_mean"], linewidth=0.6, alpha=0.7, label=sensor_label)
            ax_sensor.set(title=surface, ylabel=f"{value} ({'%' if value == 'DHT_HUMIDITY' else unit})")
            ax_sensor.legend(ncol=4, fontsize=6)
        axes[-1].set_xlabel("Observation time; each line is a sensor position (coverage table)")
        fig.suptitle(label)
        fig.tight_layout()
        figures[value.lower() + "_sensors.png"] = fig
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(np.arange(len(coverage)), coverage.DHT_HUMIDITY_coverage)
    ax.set(title=label, xlabel="Sensor position index (coverage table)", ylabel="Valid humidity / nominal slots in position span")
    fig.tight_layout(); figures["coverage.png"] = fig
    fig, ax = plt.subplots(figsize=(10, 4))
    rates = [float(data[f"INVALID_{v}"].mean()) for v in VALUES]
    ax.bar(VALUES, rates); ax.set(title=label, ylabel="Invalid or missing fraction")
    fig.tight_layout(); figures["missing.png"] = fig
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.errorbar(np.arange(len(concordance)), concordance["mean"], yerr=concordance["std"].fillna(0), fmt="o")
    ax.set(title=label + " | agreement, not calibration", xlabel="Position index (concordance table)", ylabel=f"DS minus DHT ({unit}); mean +/- sample SD")
    fig.tight_layout(); figures["agreement.png"] = fig
    for surface, rows in data.groupby("SURFACE"):
        valid = rows[rows.INCLUDED_SUMMARIES & ~rows.INVALID_DS_TEMPERATURE]
        means = valid.groupby(["X", "Y"]).DS_TEMPERATURE.mean().reset_index()
        fig, ax = plt.subplots(figsize=(6, 4))
        points = ax.scatter(means.X, means.Y, c=means.DS_TEMPERATURE)
        fig.colorbar(points, ax=ax, label=f"Mean DS ({unit})")
        ax.set(title=f"{surface} | {label}", xlabel="Wall X (unit unconfirmed)", ylabel="Wall Y (unit unconfirmed)")
        fig.tight_layout(); figures[f"wall_{surface.lower()}.png"] = fig
    plt.close("all")
    return figures
