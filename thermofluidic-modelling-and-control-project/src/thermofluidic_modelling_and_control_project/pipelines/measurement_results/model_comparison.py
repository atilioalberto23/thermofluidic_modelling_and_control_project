"""Opt-in aligned comparison, per met:metricas; never infer independence."""

import numpy as np
import pandas as pd
from kedro.pipeline import node, pipeline


def validate_window_supports(windows):
    """Reject shared history/target support across chronological partitions.

    Each interval is closed, from earliest historical input to latest target.
    Trajectory IDs must group dependent sensors and episodes of the same case.
    """
    required = {"trajectory_id", "partition", "support_start", "support_end"}
    if not required.issubset(windows.columns):
        raise ValueError(f"Required window columns: {sorted(required)}")
    data = windows.copy()
    for column in ["support_start", "support_end"]:
        data[column] = pd.to_datetime(data[column], format="ISO8601", errors="raise")
    if data[list(required)].isna().any().any() or (data.support_end < data.support_start).any():
        raise ValueError("Missing or reversed window support")
    for _, trajectory in data.groupby("trajectory_id"):
        intervals = trajectory.groupby("partition").agg(start=("support_start", "min"), end=("support_end", "max")).sort_values("start")
        if (intervals.start.iloc[1:].reset_index(drop=True) <= intervals.end.iloc[:-1].reset_index(drop=True)).any():
            raise ValueError("History/target supports overlap across partitions")
    return {"status": "nonoverlapping supports", "windows": len(data)}


def compare_models(predictions, references, config):
    """Exact observation-time join; explicit duration weights; no fitted shifts."""
    if not config["enabled"]:
        raise ValueError("Model comparison is disabled until compatible inputs exist")
    keys = ["variable", "position_id", "episode", "regime", "timestamp"]
    ref_required = set(keys + ["reference", "unit", "observation_operator", "duration_seconds", "source_class", "independent", "used_for_development", "reference_provenance"])
    pred_required = set(keys + ["prediction", "model", "horizon_seconds", "origin_timestamp", "unit", "observation_operator", "source_class"])
    for frame, required in [(predictions, pred_required), (references, ref_required)]:
        if not required.issubset(frame.columns) or frame.empty:
            raise ValueError(f"Missing compatible comparison data: {sorted(required - set(frame.columns))}")
        if frame[list(required - {"prediction", "reference"})].isna().any().any():
            raise ValueError("Missing comparison identity, unit or provenance")
    pred, ref = predictions.copy(), references.copy()
    for frame in [pred, ref]:
        frame["timestamp"] = pd.to_datetime(frame.timestamp, format="ISO8601", errors="raise")
    pred["origin_timestamp"] = pd.to_datetime(pred.origin_timestamp, format="ISO8601", errors="raise")
    if not ref.independent.eq(True).all() or not ref.used_for_development.eq(False).all():
        raise ValueError("Reference must be independent and unused for development")
    if not ref.source_class.isin(["physical", "synthetic"]).all() or not pred.source_class.isin(["physical", "synthetic"]).all():
        raise ValueError("Unknown provenance prevents model comparison")
    if ref.duplicated(keys).any() or pred.duplicated(keys + ["model", "horizon_seconds"]).any():
        raise ValueError("Ambiguous duplicate comparison keys")
    if not np.isfinite(ref.duration_seconds).all() or ref.duration_seconds.le(0).any():
        raise ValueError("Explicit positive finite duration weights required")
    if not np.isfinite(pred.horizon_seconds).all() or pred.horizon_seconds.lt(0).any():
        raise ValueError("Nonnegative finite horizons required")
    actual_horizon = (pred.timestamp - pred.origin_timestamp).dt.total_seconds()
    if not np.isclose(actual_horizon, pred.horizon_seconds).all():
        raise ValueError("Prediction origin, target time and horizon disagree")
    paired = pred.merge(ref, on=keys, how="left", suffixes=("_pred", "_ref"), validate="many_to_one", indicator=True)
    matched = paired._merge.eq("both")
    if (matched & (paired.unit_pred.ne(paired.unit_ref) | paired.observation_operator_pred.ne(paired.observation_operator_ref))).any():
        raise ValueError("Incompatible units or observation operators")
    # Common quality mask for all models at each requested horizon.
    paired["pair_valid"] = matched & np.isfinite(paired.prediction) & np.isfinite(paired.reference)
    shared_keys = keys + ["horizon_seconds"]
    models_per_horizon = paired.groupby("horizon_seconds").model.nunique()
    model_counts = paired.groupby(shared_keys, dropna=False).model.transform("nunique")
    paired["common_valid"] = paired.groupby(shared_keys, dropna=False).pair_valid.transform("all") & model_counts.eq(paired.horizon_seconds.map(models_per_horizon))
    group_keys = ["model", "variable", "position_id", "episode", "regime", "horizon_seconds"]
    output = []
    for identity, rows in paired.groupby(group_keys, dropna=False):
        valid = rows.common_valid
        usable = rows[valid]
        record = dict(zip(group_keys, identity))
        record.update(expected=len(rows), matched=int(rows._merge.eq("both").sum()), valid=len(usable), coverage=len(usable) / len(rows), unit=rows.unit_pred.iloc[0], weighting="reference duration within episode; no pooled domination by long episodes", inference="not performed: independent episodes/block dependence and physical margins required")
        record.update(MAE=np.nan, RMSE=np.nan, MBE=np.nan, P95_ABSOLUTE_ERROR=np.nan, classification="insufficient_reference")
        if len(usable):
            error = usable.prediction.to_numpy() - usable.reference.to_numpy()
            weights = usable.duration_seconds.to_numpy()
            weights = weights / weights.sum()
            absolute = np.abs(error)
            ordered = np.argsort(absolute)
            percentile = absolute[ordered][np.searchsorted(weights[ordered].cumsum(), 0.95)]
            record.update(MAE=float(np.sum(weights * absolute)), RMSE=float(np.sqrt(np.sum(weights * error**2))), MBE=float(np.sum(weights * error)), P95_ABSOLUTE_ERROR=float(percentile))
            record["classification"] = "synthetic_comparison" if usable.source_class_pred.eq("synthetic").any() or usable.source_class_ref.eq("synthetic").any() else "independent_physical_reference_comparison"
        output.append(record)
    return pd.DataFrame(output)


def create_pipeline(**kwargs):
    return pipeline([node(compare_models, ["model_predictions", "model_references", "params:model_comparison"], "model_metrics", name="compare_models")])
