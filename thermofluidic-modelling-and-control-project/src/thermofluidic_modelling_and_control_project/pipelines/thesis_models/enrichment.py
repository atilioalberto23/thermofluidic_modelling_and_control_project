"""Nested discrepancy correction and source-balanced physical enrichment."""

import json

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeRegressor


def fit_discrepancy_model(train, validation, test, features, target, config):
    """Base predictions must be OOF in development, and frozen in final test."""
    for frame in [train, validation, test]:
        if not frame["base_out_of_fit"].eq(True).all():
            raise ValueError("Discrepancy requires out-of-fit physical predictions")
    candidates, scores = [], []
    for depth in config["depths"]:
        model = DecisionTreeRegressor(max_depth=depth, min_samples_leaf=config["min_samples_leaf"], random_state=config["seed"])
        model.fit(train[features], train[target] - train["physical_prediction"])
        predicted = validation.physical_prediction + model.predict(validation[features])
        scores.append(float(np.mean((predicted - validation[target])**2)))
        candidates.append(model)
    best = candidates[int(np.argmin(scores))]
    # Select on validation, then refit with out-of-fit development residuals.
    development = pd.concat([train, validation], ignore_index=True)
    best.fit(development[features], development[target] - development.physical_prediction)
    predicted = test.physical_prediction + best.predict(test[features])
    output = test.copy()
    output["hybrid_prediction"] = predicted
    return best, output, {"validation_scores": scores, "selected_depth": best.max_depth, "state_balance_interpretation": "observable discrepancy only; full-state conservation not represented"}


def train_enriched_model(experimental, numerical, features, target, estimator, source_weight):
    """Numerical rows require trajectories and a generator trained on development."""
    if numerical.generator_fit_partition.ne("development").any() or numerical.trajectory_id.isna().any():
        raise ValueError("Numerical generator leaks final data or lacks trajectory provenance")
    real_weights = np.full(len(experimental), 1 / len(experimental))
    trajectory_count = numerical.trajectory_id.nunique()
    simulated_weights = source_weight / (trajectory_count * numerical.groupby("trajectory_id").trajectory_id.transform("size").to_numpy())
    combined = pd.concat([experimental, numerical], ignore_index=True)
    weights = np.r_[real_weights, simulated_weights]
    estimator.fit(combined[features], combined[target], sample_weight=weights)
    return estimator, {"real_total_weight": float(real_weights.sum()), "numerical_total_weight": float(simulated_weights.sum()), "numerical_trajectories": trajectory_count, "operator": "must be supplied and verified upstream"}


def run_enrichment(case, config):
    if case is None:
        fields = ["OOF physical predictions on development", "compatible observation_operator_id", "causal features and chronological partitions", "numerical trajectories with generator_id/run_id", "generator fitting provenance limited to development", "source weight and physical domain"]
        return {"manifest.json": {"implementation": "nested discrepancy and trajectory/source-balanced enrichment implemented", "execution": "missing_input", "fields": fields}}, pd.DataFrame([{"model_id": "hybrid_enrichment", "status": "missing_input", "missing_fields": json.dumps(fields)}])
    train, valid, test = [pd.DataFrame(case[k]) for k in ["train", "validation", "test"]]
    if pd.to_datetime(train.support_end).max() >= pd.to_datetime(valid.support_start).min() or pd.to_datetime(valid.support_end).max() >= pd.to_datetime(test.support_start).min():
        raise ValueError("Hybrid supports overlap partitions")
    model, predictions, diagnostics = fit_discrepancy_model(train, valid, test, case["features"], case["target"], config)
    baseline = DecisionTreeRegressor(max_depth=model.max_depth, min_samples_leaf=config["min_samples_leaf"], random_state=config["seed"])
    development = pd.concat([train, valid])
    baseline.fit(development[case["features"]], development[case["target"]])
    predictions["experimental_only_prediction"] = baseline.predict(test[case["features"]])
    bundle = {"discrepancy.pkl": model, "predictions.parquet": predictions, "diagnostics.json": diagnostics}
    if case.get("numerical"):
        enriched = DecisionTreeRegressor(max_depth=model.max_depth, min_samples_leaf=config["min_samples_leaf"], random_state=config["seed"])
        enriched, weights = train_enriched_model(development, pd.DataFrame(case["numerical"]), case["features"], case["target"], enriched, config["source_weight"])
        predictions["enriched_prediction"] = enriched.predict(test[case["features"]])
        bundle["enriched.pkl"] = enriched
        bundle["source_weights.json"] = weights
    errors = []
    for name in [c for c in predictions if c.endswith("prediction")]:
        residual = predictions[name] - predictions[case["target"]]
        errors.append({"model_id": name, "status": "executed", "RMSE": float(np.sqrt(np.mean(residual**2))), "MAE": float(np.mean(np.abs(residual))), "MBE": float(residual.mean()), "source_kind": case["source_kind"], "task_id": case["task_id"]})
    return bundle, pd.DataFrame(errors)
