"""Common tasks, duration weights and paired exploratory block uncertainty."""

import numpy as np
import pandas as pd


def compute_prediction_metrics(predictions, config):
    identity = ["model_id", "variable", "sensor_id", "target_timestamp", "horizon_seconds", "fold_id"]
    if predictions.duplicated(identity).any():
        raise ValueError("Predictions multiply comparison keys")
    reference_keys = [k for k in identity if k != "model_id"]
    if predictions.groupby(reference_keys).y_true.nunique().gt(1).any():
        raise ValueError("Models do not share identical references")
    models = predictions.model_id.nunique()
    counts = predictions.groupby(reference_keys).model_id.transform("nunique")
    finite = np.isfinite(predictions.y_pred) & np.isfinite(predictions.y_true)
    valid = finite.groupby([predictions[k] for k in reference_keys]).transform("all") & counts.eq(models)
    paired = predictions.loc[valid].copy()
    paired["error"] = paired.y_pred - paired.y_true
    rows = []
    group = ["model_id", "variable", "horizon_seconds", "fold_id", "sensor_id", "episode_id", "unit", "source_kind"]
    expected_counts = predictions.groupby(group, sort=False).size()
    for key, records in paired.groupby(group, sort=False):
        records = records.sort_values("target_timestamp")
        differences = records.target_timestamp.diff().dt.total_seconds()
        nominal = float(differences.dropna().median()) if differences.notna().any() else 1.
        weights = differences.fillna(nominal).clip(upper=nominal).to_numpy()
        weights = weights / weights.sum()
        error = records.error.to_numpy()
        absolute = np.abs(error)
        order = np.argsort(absolute)
        percentile = absolute[order][np.searchsorted(weights[order].cumsum(), .95)]
        output = dict(zip(group, key))
        output.update(N=len(records), MBE=float(np.sum(weights * error)), MAE=float(np.sum(weights * absolute)), RMSE=float(np.sqrt(np.sum(weights * error**2))), P95_ABS=float(percentile), matched_coverage=len(records) / int(expected_counts.loc[key]), weighting="duration within observed origin cadence; no bridging gaps", evidence="synthetic processing" if key[-1] == "synthetic" else "reserved observations; campaign independence must be documented")
        rows.append(output)
    sensor_metrics = pd.DataFrame(rows)
    summary = []
    for identity, records in sensor_metrics.groupby(["model_id", "variable", "horizon_seconds", "fold_id", "unit", "source_kind"]):
        record = dict(zip(["model_id", "variable", "horizon_seconds", "fold_id", "unit", "source_kind"], identity))
        record.update(N=int(records.N.sum()), sensors=len(records), MBE=float(records.MBE.mean()), MAE=float(records.MAE.mean()), RMSE=float(np.sqrt(np.mean(records.RMSE**2))), coverage=float(records.matched_coverage.mean()), weighting="equal sensors/segments; duration within each sensor", represented_balances="not represented by observable-only predictor")
        summary.append(record)
    return sensor_metrics, pd.DataFrame(summary)


def paired_block_intervals(predictions, config):
    test = predictions[predictions.split_id.eq("test")].copy()
    test["squared_error"] = (test.y_pred - test.y_true)**2
    generator = np.random.default_rng(config["bootstrap_seed"])
    records = []
    for (variable, horizon), rows in test.groupby(["variable", "horizon_seconds"]):
        errors = rows.groupby(["forecast_origin", "model_id"]).squared_error.mean().unstack("model_id").dropna()
        if "persistence" not in errors or len(errors) < 4:
            continue
        values = errors.to_numpy()
        baseline = errors.columns.get_loc("persistence")
        origin_count = len(errors)
        for block in config["block_length_sensitivity"]:
            if block >= origin_count:
                continue
            bootstrap = []
            for _ in range(config["bootstrap_repetitions"]):
                starts = generator.integers(0, origin_count - block + 1, int(np.ceil(origin_count / block)))
                indices = np.concatenate([np.arange(i, i + block) for i in starts])[:origin_count]
                rms = np.sqrt(values[indices].mean(axis=0))
                bootstrap.append(rms[baseline] - rms)
            intervals = np.quantile(bootstrap, [.025, .975], axis=0)
            rms = np.sqrt(values.mean(axis=0))
            for column, model in enumerate(errors.columns):
                series = errors[model]
                records.append({"model_id": model, "reference_model": "persistence", "variable": variable, "horizon_seconds": horizon, "improvement_RMSE": rms[baseline] - rms[column], "lower_95": intervals[0, column], "upper_95": intervals[1, column], "block_origins": block, "origins": origin_count, "bootstrap_repetitions": config["bootstrap_repetitions"], "squared_residual_autocorrelation_lag1": series.autocorr(1), "squared_residual_first_half_mean": series.iloc[:origin_count // 2].mean(), "squared_residual_second_half_mean": series.iloc[origin_count // 2:].mean(), "stationarity_status": "not established; intervals exploratory with block-length sensitivity", "uncertainty_kind": "paired temporal block resampling; not instrumental or numerical uncertainty", "equivalence": "not evaluated: prior physical margins and independent episodes absent"})
    return pd.DataFrame(records)
