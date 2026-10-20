"""Direct temporal predictors: persistence, tree, XGBoost and LightGBM."""

import hashlib
import importlib.metadata
import json
import platform
import time

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeRegressor
from xgboost import XGBRegressor

from ..measurement_results.nodes import VALUES

CAT = ["SURFACE", "NODE_ID", "SENSOR_POSITION"]


def build_causal_targets(data, config):
    """Exact timestamp joins within operational segments; no row-shift horizons."""
    source = data.loc[data.INCLUDED_SUMMARIES].copy()
    source = source.loc[~source[[f"INVALID_{v}" for v in VALUES]].any(axis=1)]
    keys = ["POSITION_ID", "SEGMENT_ID", "TIMESTAMP"]
    if source.duplicated(keys).any():
        raise ValueError("Ambiguous causal target keys")
    seconds = source.TIMESTAMP.dt.as_unit("s").astype("int64")
    origins = source.loc[seconds.mod(config["origin_stride_seconds"]).eq(0)].copy()
    for lag in config["history_seconds"]:
        previous = source[keys + VALUES].copy()
        previous["TIMESTAMP"] += pd.Timedelta(seconds=lag)
        previous = previous.rename(columns={v: f"{v}_lag_{lag}" for v in VALUES})
        origins = origins.merge(previous, on=keys, how="left", validate="one_to_one")
    origins["hour_sin"] = np.sin(2 * np.pi * (origins.TIMESTAMP.dt.hour + origins.TIMESTAMP.dt.minute / 60) / 24)
    origins["hour_cos"] = np.cos(2 * np.pi * (origins.TIMESTAMP.dt.hour + origins.TIMESTAMP.dt.minute / 60) / 24)
    rows = []
    for horizon in config["horizons_seconds"]:
        future = source[keys + VALUES].copy()
        future["TIMESTAMP"] -= pd.Timedelta(seconds=horizon)
        future = future.rename(columns={v: f"target_{v}" for v in VALUES})
        paired = origins.merge(future, on=keys, how="inner", validate="one_to_one")
        paired["horizon_seconds"] = horizon
        paired["target_timestamp"] = paired.TIMESTAMP + pd.Timedelta(seconds=horizon)
        paired["support_start"] = paired.TIMESTAMP - pd.Timedelta(seconds=max(config["history_seconds"]))
        paired["support_end"] = paired.target_timestamp
        rows.append(paired)
    result = pd.concat(rows, ignore_index=True)
    features = VALUES + [f"{v}_lag_{lag}" for lag in config["history_seconds"] for v in VALUES] + ["X", "Y", "hour_sin", "hour_cos"]
    result = result.dropna(subset=features + [f"target_{v}" for v in VALUES])
    if result.empty:
        raise ValueError("No complete causal windows for configured histories/horizons")
    result["episode_id"] = "operational_segment_" + result.SEGMENT_ID.astype(str)
    result["configuration_id"] = config["configuration_id"]
    # Whole timestamps stay together. These are temporal blocks, not physical lots.
    times = np.sort(data.TIMESTAMP.dropna().unique())
    boundary = pd.Timestamp(times[int(len(times) * config["development_fraction"])])
    purge = pd.Timedelta(seconds=max(config["history_seconds"]) + max(config["horizons_seconds"]))
    result["split_id"] = "purged"
    result.loc[result.TIMESTAMP.lt(boundary - purge) & result.support_end.lt(boundary), "split_id"] = "development"
    result.loc[result.support_start.ge(boundary), "split_id"] = "test"
    result["split_boundary"] = boundary
    result["source_kind"] = config["source_kind"]
    if config["episode_column"]:
        raise ValueError("Whole-episode assignment must be supplied before enabling episode-aware production splits")
    return result


def make_estimator(name, parameters, seed):
    if name == "tree":
        return DecisionTreeRegressor(random_state=seed, **parameters)
    if name == "xgboost":
        return XGBRegressor(objective="reg:squarederror", tree_method="hist", n_jobs=2, random_state=seed, **parameters)
    if name == "lightgbm":
        return LGBMRegressor(n_jobs=2, random_state=seed, verbosity=-1, deterministic=True, force_col_wise=True, **parameters)
    raise ValueError(name)


def encoder_for(features):
    numeric = [c for c in features if c not in CAT]
    return ColumnTransformer([("numeric", "passthrough", numeric), ("categories", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT)])


def train_temporal_models(windows, config):
    numeric = VALUES + [f"{v}_lag_{lag}" for lag in config["history_seconds"] for v in VALUES] + ["X", "Y", "hour_sin", "hour_cos"]
    features = numeric + CAT
    run_id = hashlib.sha256((json.dumps(config, sort_keys=True) + str(pd.util.hash_pandas_object(windows, index=False).sum())).encode()).hexdigest()[:16]
    bundles, searches, predictions, costs, partitions = {}, [], [], [], []
    development = windows[windows.split_id.eq("development")].copy()
    development[CAT] = development[CAT].fillna("<NULL>")
    final = windows[windows.split_id.eq("test")].copy()
    final[CAT] = final[CAT].fillna("<NULL>")
    if development.empty or final.empty:
        raise ValueError("Development and purged final test must both contain windows")
    dev_times = np.sort(development.TIMESTAMP.unique())
    purge_seconds = max(config["history_seconds"]) + max(config["horizons_seconds"])
    for horizon in config["horizons_seconds"]:
        dev = development[development.horizon_seconds.eq(horizon)]
        test = final[final.horizon_seconds.eq(horizon)]
        folds = []
        edges = config["rolling_origins"] + [1.0]
        for fold, fraction in enumerate(edges[:-1]):
            boundary = pd.Timestamp(dev_times[min(len(dev_times) - 1, int(fraction * len(dev_times)))])
            end = pd.Timestamp(dev_times[-1]) + pd.Timedelta(seconds=1) if edges[fold + 1] == 1 else pd.Timestamp(dev_times[int(edges[fold + 1] * len(dev_times))])
            train = dev[dev.TIMESTAMP.lt(boundary - pd.Timedelta(seconds=purge_seconds))]
            valid = dev[dev.support_start.ge(boundary) & dev.TIMESTAMP.lt(end)]
            if train.empty or valid.empty:
                raise ValueError("Rolling-origin fold empty after purge")
            if train.support_end.max() >= valid.support_start.min():
                raise ValueError("Overlapping historical/target supports")
            folds.append((train, valid))
            partitions.append({"horizon_seconds": horizon, "fold": fold, "train_end": str(train.support_end.max()), "validation_start": str(valid.support_start.min()), "N_train": len(train), "N_validation": len(valid), "purge_seconds": purge_seconds})
        for name in config["models"]:
            if name == "persistence":
                selected = {}
            else:
                candidate_scores = []
                for candidate, parameters in enumerate(config["search"][name]):
                    fold_scores = []
                    for fold, (train, valid) in enumerate(folds):
                        encoder = encoder_for(features)
                        tx = encoder.fit_transform(train[features])
                        vx = encoder.transform(valid[features])
                        errors = []
                        for value in VALUES:
                            estimator = make_estimator(name, parameters, config["seed"])
                            estimator.fit(tx, train[f"target_{value}"])
                            prediction = estimator.predict(vx)
                            scale = max(float(train[f"target_{value}"].std()), 1e-6)
                            errors.append(float(np.sqrt(np.mean((prediction - valid[f"target_{value}"].to_numpy())**2)) / scale))
                        score = float(np.mean(errors))
                        fold_scores.append(score)
                        searches.append({"run_id": run_id, "model": name, "horizon_seconds": horizon, "candidate": candidate, "fold": fold, "parameters": json.dumps(parameters, sort_keys=True), "standardized_RMSE": score})
                    candidate_scores.append(float(np.mean(fold_scores)))
                selected = config["search"][name][int(np.argmin(candidate_scores))]
            # Validation outputs are reproduced with each fold's own transforms.
            evaluations = [(f"validation_{i}", train, valid) for i, (train, valid) in enumerate(folds)] + [("test", dev, test)]
            for split, train, evaluate in evaluations:
                started = time.perf_counter()
                encoder = None if name == "persistence" else encoder_for(features)
                tx = None if encoder is None else encoder.fit_transform(train[features])
                vx = None if encoder is None else encoder.transform(evaluate[features])
                trained = {}
                for value in VALUES:
                    estimator = None
                    if name == "persistence":
                        values = evaluate[value].to_numpy()
                    else:
                        estimator = make_estimator(name, selected, config["seed"])
                        estimator.fit(tx, train[f"target_{value}"])
                        values = estimator.predict(vx)
                        trained[value] = estimator
                    frame = evaluate[["POSITION_ID", "episode_id", "configuration_id", "TIMESTAMP", "target_timestamp", "horizon_seconds", "source_kind"]].copy()
                    frame = frame.rename(columns={"POSITION_ID": "sensor_id", "TIMESTAMP": "forecast_origin"})
                    frame["model_id"] = name
                    frame["model_version"] = importlib.metadata.version({"tree": "scikit-learn", "xgboost": "xgboost", "lightgbm": "lightgbm", "persistence": "pandas"}[name])
                    frame["run_id"] = run_id
                    frame["split_id"] = "test" if split == "test" else "validation"
                    frame["fold_id"] = split
                    frame["task_id"] = "direct_sensor_forecast"
                    frame["variable"] = value
                    frame["unit"] = "percentage_points" if value == "DHT_HUMIDITY" else config["temperature_unit"]
                    frame["y_true"] = evaluate[f"target_{value}"].to_numpy()
                    frame["y_pred"] = values
                    frame["quality_flag"] = "common_valid_causal_window"
                    frame["observation_operator_id"] = "sensor_channel_direct_v1"
                    frame["information_mode"] = "history_only_direct_forecast"
                    predictions.append(frame)
                training_seconds = time.perf_counter() - started
                if split == "test":
                    if dev.support_end.max() >= test.support_start.min():
                        raise ValueError("Final test shares history or targets with development")
                    artifact = {"encoder": encoder, "estimators": trained, "features": features, "parameters": selected, "seed": config["seed"], "history_seconds": config["history_seconds"], "horizon_seconds": horizon, "run_id": run_id, "source_kind": config["source_kind"], "train_support_end": str(dev.support_end.max()), "test_support_start": str(test.support_start.min())}
                    bundles[f"{name}_{horizon}s.pkl"] = artifact
                    latency = []
                    for _ in range(config["latency_repetitions"] + 1):
                        start = time.perf_counter()
                        if encoder is not None:
                            single = encoder.transform(evaluate[features].iloc[[0]])
                            for estimator in trained.values():
                                estimator.predict(single)
                        else:
                            evaluate[VALUES].iloc[0].to_numpy()
                        latency.append(time.perf_counter() - start)
                    costs.append({"run_id": run_id, "model_id": name, "horizon_seconds": horizon, "selected_parameters": json.dumps(selected), "training_seconds_including_batch_prediction": training_seconds, "N_train": len(dev), "N_test": len(test), "latency_median_seconds": float(np.median(latency[1:])), "latency_p95_seconds": float(np.quantile(latency[1:], .95)), "latency_p99_seconds": float(np.quantile(latency[1:], .99)), "latency_batch_size": 1, "latency_repetitions": config["latency_repetitions"], "hardware": platform.platform(), "processor": platform.processor(), "source_kind": config["source_kind"], "strategy": "direct", "history_seconds": json.dumps(config["history_seconds"]), "temperature_unit": config["temperature_unit"]})
    bundles["run.json"] = {"run_id": run_id, "configuration": config, "split_rule": "chronological blocks, not independent experimental episodes", "partitions": partitions, "no_future_exogenous_inputs": True}
    return bundles, pd.concat(predictions, ignore_index=True), pd.DataFrame(searches), pd.DataFrame(costs)
