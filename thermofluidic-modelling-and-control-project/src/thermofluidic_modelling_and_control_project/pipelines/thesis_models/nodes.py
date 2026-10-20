"""Kedro orchestration for producers; missing plant inputs are field-specific."""

from copy import deepcopy
import hashlib
import json

import numpy as np
import pandas as pd

from .cavity import refinement_estimate, solve_cavity
from .learning import build_causal_targets, train_temporal_models
from .pinn import train_conditional_pinn
from .thermal import BOUNDARIES, REQUIRED, STATES, humidity_ratio, identify_parameters, simulate_network, thermal_rhs, verification_parameters


def run_thermal_verification(config):
    parameters = verification_parameters()
    times = np.arange(0, config["fixture_duration_seconds"] + 1, config["fixture_output_step_seconds"])
    boundary = np.array([298.15, float(humidity_ratio(298.15, .4, 101325)), 101325., 200., .01, 298.15])
    boundaries = pd.DataFrame(np.tile(boundary, (len(times), 1)), columns=BOUNDARIES)
    boundaries["seconds"] = times
    initial = np.array([298.15] * 4 + [boundary[1], .1])
    states, flows, balances, metadata = simulate_network(parameters, boundaries, initial, config["solver"])
    constant = deepcopy(parameters)
    constant["inventory"] = "constant"
    constant["constant_mda_kg"] = 101325 * 5 / (287.055 * initial[3] * (1 + initial[4] / .62198))
    simplified, _, simple_balances, simple_metadata = simulate_network(constant, boundaries, initial, config["solver"])
    comparison = pd.DataFrame({"state": STATES, "max_absolute_general_minus_constant": np.max(np.abs(states[STATES].to_numpy() - simplified[STATES].to_numpy()), axis=0), "source_kind": "synthetic_software_fixture"})
    refined_solver = deepcopy(config["solver"])
    refined_solver["rtol"] /= 10
    refined_solver["max_step_seconds"] /= 2
    refined, _, _, _ = simulate_network(parameters, boundaries, initial, refined_solver)
    comparison["max_absolute_integrator_refinement"] = np.max(np.abs(states[STATES].to_numpy() - refined[STATES].to_numpy()), axis=0)
    bdf_solver = deepcopy(refined_solver)
    bdf_solver["method"] = "BDF"
    bdf, _, _, bdf_metadata = simulate_network(parameters, boundaries, initial, bdf_solver)
    comparison["max_absolute_Radau_minus_BDF"] = np.max(np.abs(states[STATES].to_numpy() - bdf[STATES].to_numpy()), axis=0)
    # One known coefficient from numerical reference, explicitly not plant fitting.
    guess = deepcopy(parameters)
    guess["Gce_w_k"] = 4.
    observed = pd.DataFrame({"Tc": states.Tc_K})
    fit, diagnostic = identify_parameters(guess, boundaries, initial, observed, [{"state": "Tc_K", "variable": "Tc", "unit": "K", "scale": 1.}], {"names": ["Gce_w_k"], "lower": [.1], "upper": [20.], "max_nfev": 15}, config["solver"])
    fit["source_kind"] = "synthetic_parameter_recovery_fixture"
    metadata["identification_diagnostics"] = diagnostic
    metadata["BDF_comparison"] = bdf_metadata
    bundle = {"states.parquet": states, "flows.parquet": flows, "balances.parquet": balances, "constant_states.parquet": simplified, "constant_balances.parquet": simple_balances, "comparison.csv": comparison, "parameter_recovery.csv": fit, "run.json": metadata, "constant_run.json": simple_metadata}
    return bundle, comparison


def run_plant_network(case, config):
    if case is None:
        missing = REQUIRED + ["boundary_times_seconds"] + BOUNDARIES + ["initial_state_six_components", "observation_operators", "independent_reference", "episode_id", "parameter_sources"]
        return {"manifest.json": {"implementation": "six-state RHS, radiosity, GAB, Radau, identification and integral balances implemented", "execution": "missing_input", "missing_fields": missing}}, pd.DataFrame([{"model_id": "thermal_network", "status": "missing_input", "missing_fields": json.dumps(missing)}])
    parameters = case["parameters"]
    boundaries = pd.DataFrame(case["boundaries"])
    initial = case["initial_state"]
    bundle = {}
    if case.get("identification"):
        if case.get("identification_fit_partition") != "development":
            raise ValueError("Physical identification must be restricted to development; reserved references cannot fit parameters")
        fitting = case["identification"]
        references = pd.DataFrame(case["identification_observations"])
        table, diagnostic = identify_parameters(parameters, boundaries, initial, references, case["operators"], fitting, config["solver"])
        parameters = {**parameters, **dict(zip(table.parameter, table.value))}
        bundle["parameters.csv"] = table
        bundle["identification.json"] = diagnostic
    states, flows, balances, metadata = simulate_network(parameters, boundaries, initial, config["solver"])
    metadata.update(episode_id=case["episode_id"], operator_provenance=case["operators"], information_mode=case["information_mode"])
    bundle.update({"states.parquet": states, "flows.parquet": flows, "balances.parquet": balances, "run.json": metadata})
    return bundle, pd.DataFrame([{"model_id": "thermal_network", "status": "executed", "source_kind": "synthetic", "episode_id": case["episode_id"], "compute_seconds": metadata["seconds_compute"]}])


def run_cavity_study(config):
    summaries, bundles, refinement = [], {}, []
    for ra in config["Ra"]:
        numerical = []
        for n in config["grids"]:
            case = {**config, "Ra": ra, "grid_points": n, "time_factor": config["time_factors"][0], "radiation": False}
            fields, history, summary = solve_cavity(case)
            summaries.append(summary)
            numerical.append(summary)
            bundles[f"Ra{ra}_N{n}/fields.parquet"] = fields
            bundles[f"Ra{ra}_N{n}/history.csv"] = history
        estimate = refinement_estimate(*[s["Nu_hot"] for s in numerical])
        refinement.append({"Ra": ra, "refinement": "spatial", **estimate, "all_converged": all(s["converged"] for s in numerical)})
        # Temporal study on the middle grid; same physical quantity and solver.
        temporal = [numerical[1]]
        for factor in config["time_factors"][1:]:
            case = {**config, "Ra": ra, "grid_points": config["grids"][1], "time_factor": factor, "radiation": False}
            fields, history, summary = solve_cavity(case)
            summaries.append(summary)
            temporal.append(summary)
            bundles[f"Ra{ra}_dtfactor{factor}/history.csv"] = history
        refinement.append({"Ra": ra, "refinement": "temporal", **refinement_estimate(*[s["Nu_hot"] for s in temporal]), "all_converged": all(s["converged"] for s in temporal)})
    radiation_case = {**config, **config["radiation_fixture"], "Ra": config["Ra"][0], "grid_points": config["grids"][1], "time_factor": config["time_factors"][0], "radiation": True}
    fields, history, radiative = solve_cavity(radiation_case)
    summaries.append(radiative)
    bundles["radiation_fixture/fields.parquet"] = fields
    bundles["radiation_fixture/history.csv"] = history
    table = pd.DataFrame(summaries)
    table["reference_status"] = "primary benchmark numeric table required; no unverified copied numbers"
    if config["benchmark_reference"]:
        table["Nu_reference"] = table.Ra.astype(str).map(config["benchmark_reference"])
        table["Nu_error"] = table.Nu_hot - table.Nu_reference
    bundles["refinement.csv"] = pd.DataFrame(refinement)
    bundles["configuration.json"] = config
    return bundles, table, pd.DataFrame(refinement)


def run_pinn_verification(config, network_config):
    parameters = verification_parameters()
    generator = np.random.default_rng(config["seed"])
    samples = {}
    for partition, count in [("train", 64), ("validation", 24), ("test", 24)]:
        initial, boundaries, targets = [], [], []
        for _ in range(count):
            temperatures = generator.uniform(297., 303., 4)
            ratio = float(humidity_ratio(temperatures[3], generator.uniform(.3, .5), 101325))
            state = np.r_[temperatures, ratio, generator.uniform(.06, .14)]
            boundary = np.array([298.15, float(humidity_ratio(298.15, .4, 101325)), 101325., generator.uniform(0, 250), .01, 298.15])
            records = pd.DataFrame([boundary, boundary], columns=BOUNDARIES)
            records["seconds"] = [0., config["segment_seconds"]]
            trajectory, _, _, _ = simulate_network(parameters, records, state, network_config["solver"])
            initial.append(state); boundaries.append(boundary); targets.append(trajectory[STATES].iloc[-1].to_numpy())
        samples[partition] = {"initial": np.array(initial), "boundary": np.array(boundaries), "target": np.array(targets), "seconds": np.full((count, 1), config["segment_seconds"]), "mask": np.ones((count, 6)), "source_kind": "numerical_software_fixture_not_experimental"}
    return train_conditional_pinn(samples, parameters, config)


def run_plant_pinn(case, config):
    if case is None:
        missing = ["identified/fixed positive physical network parameters with provenance", "causal six-state initial estimates and uncertainty", "compatible boundary segments and pressure", "observed variable masks/operators", "development-only normalizations", "nonoverlapping train/validation/test supports"]
        return {"manifest.json": {"implementation": "conditional six-state autograd PINN", "execution": "missing_input", "missing_fields": missing}}, pd.DataFrame([{"model_id": "conditional_pinn_plant", "status": "missing_input", "missing_fields": json.dumps(missing)}])
    if case["normalization_fit_partition"] != "development" or case["physical_parameters_fit_partition"] != "development":
        raise ValueError("PINN normalization or physical parameters leak reserved data")
    for left, right in [("train", "validation"), ("validation", "test")]:
        previous = pd.to_datetime(case["samples"][left]["support_end"])
        following = pd.to_datetime(case["samples"][right]["support_start"])
        if previous.max() >= following.min():
            raise ValueError("PINN history/targets cross partitions")
    checkpoints, history, predictions, metrics = train_conditional_pinn(case["samples"], case["parameters"], {**config, **case["normalization"]})
    checkpoints.update({"loss_history.parquet": history, "predictions.parquet": predictions, "metrics.parquet": metrics, "provenance.json": case["provenance"]})
    return checkpoints, pd.DataFrame([{"model_id": "conditional_pinn_plant", "status": "executed", "source_kind": case["samples"]["test"]["source_kind"], "task_id": case["task_id"]}])
