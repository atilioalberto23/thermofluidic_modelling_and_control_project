"""Six-state enthalpy/water network, met:red and met:conservacion.

All temperatures are kelvin; one shared evaporation flux couples three balances.
The same algebra supports NumPy integration and Torch differentiation.
"""

from copy import deepcopy
import time

import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid, solve_ivp
from scipy.optimize import least_squares

STATES = ["Tc_K", "Tb_K", "Tp_K", "Ta_K", "W_kg_kg", "M_kg_kg"]
BOUNDARIES = ["T_ambient_K", "W_ambient_kg_kg", "pressure_pa", "irradiance_w_m2", "mda_in_kg_s", "T_sky_K"]
REQUIRED = ["Cc_j_k", "Cb_j_k", "dry_coffee_mass_kg", "coffee_cp_j_kg_k", "volume_air_m3", "Hca_w_k", "Hba_w_k", "Hpa_w_k", "Gce_w_k", "Gbe_w_k", "Gbp_w_k", "solar_effective_areas_m2", "incident_area_m2", "radiation_areas_m2", "emissivities", "view_factors", "gab_Mm", "gab_C", "gab_K", "kinetic_k0_s", "kinetic_Ea_j_mol", "parameter_provenance"]


def saturation_pressure(temperature, xp=np):
    celsius = temperature - 273.15
    return 610.94 * xp.exp(17.625 * celsius / (celsius + 243.04))


def humidity_ratio(temperature, rh_fraction, pressure, xp=np):
    vapor = rh_fraction * saturation_pressure(temperature, xp)
    return 0.62198 * vapor / (pressure - vapor)


def relative_humidity(temperature, ratio, pressure, xp=np):
    return pressure * ratio / (0.62198 + ratio) / saturation_pressure(temperature, xp)


def validate_parameters(parameters):
    missing = [key for key in REQUIRED if parameters.get(key) is None]
    if missing:
        raise ValueError(f"Missing physical network fields: {missing}")
    for key in ["Cc_j_k", "Cb_j_k", "dry_coffee_mass_kg", "coffee_cp_j_kg_k", "volume_air_m3", "gab_Mm", "gab_C", "gab_K"]:
        if parameters[key] <= 0:
            raise ValueError(f"Positive physical property required: {key}")
    for key in ["Hca_w_k", "Hba_w_k", "Hpa_w_k", "Gce_w_k", "Gbe_w_k", "Gbp_w_k", "kinetic_k0_s", "kinetic_Ea_j_mol"]:
        if parameters[key] < 0:
            raise ValueError(f"Nonnegative transfer coefficient required: {key}")
    areas = np.asarray(parameters["radiation_areas_m2"], dtype=float)
    factors = np.asarray(parameters["view_factors"], dtype=float)
    eps = np.asarray(parameters["emissivities"], dtype=float)
    if factors.shape != (4, 4) or areas.shape != (4,) or eps.shape != (4,):
        raise ValueError("Radiation requires cover/base/product/environment surfaces")
    if np.any(areas <= 0) or np.any(eps <= 0) or np.any(eps > 1) or np.any(factors < 0) or not np.allclose(factors.sum(axis=1), 1):
        raise ValueError("Invalid radiosity areas, emissivities or view-factor closure")
    if not np.allclose(areas[:, None] * factors, areas[None, :] * factors.T):
        raise ValueError("View-factor reciprocity violated")
    if sum(parameters["solar_effective_areas_m2"]) > parameters["incident_area_m2"] or min(parameters["solar_effective_areas_m2"]) < 0:
        raise ValueError("Solar power allocated more than once or negative")


def thermal_rhs(state, boundary, parameters, xp=np, return_flows=False):
    """Fixed p,V formulation; outlet determined by dry-air continuity."""
    p = parameters
    torch_mode = xp.__name__ == "torch"
    constant = (lambda a: state.new_tensor(a)) if torch_mode else (lambda a: np.asarray(a))
    stack = (lambda a: xp.stack(a, dim=-1)) if torch_mode else (lambda a: xp.stack(a, axis=-1))
    tc, tb, tp, ta, ratio, moisture = [state[..., i] for i in range(6)]
    ambient, w_in, pressure, solar, m_in, sky = [boundary[..., i] for i in range(6)]
    temperatures = stack([tc, tb, tp, sky])
    factors = constant(p["view_factors"])
    emissivity = constant(p["emissivities"])
    matrix = constant(np.eye(4)) - (1 - emissivity)[..., None] * factors
    emitted = emissivity * 5.670374419e-8 * temperatures**4
    radiosity = xp.linalg.solve(matrix, emitted[..., None])[..., 0]
    # Matrix row j receives radiation from each surface i.
    irradiation = radiosity @ factors.T
    q_r = constant(p["radiation_areas_m2"]) * (radiosity - irradiation)
    phi_p = relative_humidity(tp, ratio, pressure, xp)
    equilibrium = p["gab_Mm"] * p["gab_C"] * p["gab_K"] * phi_p / ((1 - p["gab_K"] * phi_p) * (1 - p["gab_K"] * phi_p + p["gab_C"] * p["gab_K"] * phi_p))
    rate = p["kinetic_k0_s"] * xp.exp(-p["kinetic_Ea_j_mol"] / (8.314462618 * tp))
    d_m = -rate * (moisture - equilibrium)
    evaporation = -p["dry_coffee_mass_kg"] * d_m
    latent = 2501000 + (1860 - 4180) * (tp - 273.15)
    q_ca = p["Hca_w_k"] * (tc - ta)
    q_ba = p["Hba_w_k"] * (tb - ta)
    q_pa = p["Hpa_w_k"] * (tp - ta)
    q_bp = p["Gbp_w_k"] * (tb - tp)
    solar_powers = solar[..., None] * constant(p["solar_effective_areas_m2"])
    external_cover = p["Gce_w_k"] * (tc - ambient)
    external_base = p["Gbe_w_k"] * (tb - ambient)
    d_tc = (solar_powers[..., 0] - q_ca - external_cover - q_r[..., 0]) / p["Cc_j_k"]
    d_tb = (solar_powers[..., 1] - q_ba - q_bp - external_base - q_r[..., 1]) / p["Cb_j_k"]
    capacity_product = p["dry_coffee_mass_kg"] * (p["coffee_cp_j_kg_k"] + moisture * 4180)
    d_tp = (solar_powers[..., 2] - q_pa + q_bp - q_r[..., 2] - latent * evaporation) / capacity_product
    m_da_general = pressure * p["volume_air_m3"] / (287.055 * ta * (1 + ratio / 0.62198))
    m_da = m_da_general if p.get("inventory", "general") == "general" else ta * 0 + p["constant_mda_kg"]
    d_w = (m_in * (w_in - ratio) + evaporation) / m_da
    d_ta = (q_ca + q_ba + q_pa + m_in * (1006 + w_in * 1860) * (ambient - ta) + evaporation * 1860 * (tp - ta)) / (m_da * (1006 + ratio * 1860))
    d_mda = -m_da * (d_ta / ta + d_w / (0.62198 + ratio)) if p.get("inventory", "general") == "general" else ta * 0
    m_out = m_in - d_mda
    rhs = stack([d_tc, d_tb, d_tp, d_ta, d_w, d_m])
    if not return_flows:
        return rhs
    h_air = 1006 * (ta - 273.15) + ratio * (2501000 + 1860 * (ta - 273.15))
    h_in = 1006 * (ambient - 273.15) + w_in * (2501000 + 1860 * (ambient - 273.15))
    vapor_water = m_da * ratio
    product_energy = p["dry_coffee_mass_kg"] * (p["coffee_cp_j_kg_k"] + moisture * 4180) * (tp - 273.15)
    energy = p["Cc_j_k"] * (tc - 273.15) + p["Cb_j_k"] * (tb - 273.15) + product_energy + m_da * h_air
    flows = {"mda_kg": m_da, "mda_in_kg_s": m_in, "mda_out_kg_s": m_out, "evaporation_kg_s": evaporation, "dry_air_external_kg_s": d_mda, "water_external_kg_s": m_in * w_in - m_out * ratio, "energy_external_w": solar_powers.sum(dim=-1) - external_cover - external_base - q_r[..., :3].sum(dim=-1) + m_in * h_in - m_out * h_air if torch_mode else solar_powers.sum(axis=-1) - external_cover - external_base - q_r[..., :3].sum(axis=-1) + m_in * h_in - m_out * h_air, "water_inventory_kg": p["dry_coffee_mass_kg"] * moisture + vapor_water, "energy_inventory_j": energy, "RH_air_fraction": relative_humidity(ta, ratio, pressure, xp), "RH_product_fraction": phi_p, "Q_cover_air_w": q_ca, "Q_base_air_w": q_ba, "Q_product_air_w": q_pa, "Q_base_product_w": q_bp}
    return rhs, flows


def simulate_network(parameters, boundaries, initial_state, solver):
    validate_parameters(parameters)
    data = boundaries.sort_values("seconds")
    if data.seconds.duplicated().any() or data.seconds.min() != 0:
        raise ValueError("Boundary times must be unique and start at zero")
    if data[BOUNDARIES].isna().any().any() or data.pressure_pa.nunique() != 1:
        raise ValueError("Complete constant-pressure boundary data required; variable p needs V dp/dt extension")
    if data.mda_in_kg_s.lt(0).any():
        raise ValueError("Flow reversal requires a new inlet composition configuration")
    times = data.seconds.to_numpy(dtype=float)
    def boundary(t):
        return np.array([np.interp(t, times, data[name]) for name in BOUNDARIES])
    start = time.perf_counter()
    solution = solve_ivp(lambda t, x: thermal_rhs(x, boundary(t), parameters), (times[0], times[-1]), initial_state, t_eval=times, method=solver["method"], rtol=solver["rtol"], atol=solver["atol"], max_step=solver["max_step_seconds"])
    if not solution.success:
        raise RuntimeError(solution.message)
    states = pd.DataFrame(solution.y.T, columns=STATES)
    states["seconds"] = times
    _, flows = thermal_rhs(solution.y.T, data[BOUNDARIES].to_numpy(), parameters, return_flows=True)
    fluxes = pd.DataFrame(flows)
    if states[STATES[:4]].le(0).any().any() or states[STATES[4:]].lt(0).any().any() or fluxes.RH_air_fraction.gt(1).any() or fluxes.RH_product_fraction.gt(1).any() or fluxes.mda_out_kg_s.lt(0).any():
        raise ValueError("Network leaves noncondensing/nonreversing physical domain; no clipping performed")
    fluxes["seconds"] = times
    residuals = {}
    for name, inventory, external, reference in [("dry_air", "mda_kg", "dry_air_external_kg_s", solver["mass_reference_kg"]), ("water", "water_inventory_kg", "water_external_kg_s", solver["mass_reference_kg"]), ("energy", "energy_inventory_j", "energy_external_w", solver["energy_reference_j"])]:
        delta = fluxes[inventory] - fluxes[inventory].iloc[0]
        integrated = cumulative_trapezoid(fluxes[external], times, initial=0)
        throughput = cumulative_trapezoid(np.abs(fluxes[external]), times, initial=0)
        residuals[f"R_{name}"] = delta - integrated
        residuals[f"eta_{name}"] = np.abs(delta - integrated) / np.maximum.reduce([np.abs(delta), throughput, np.full(len(times), reference)])
    balance = pd.DataFrame(residuals)
    balance["seconds"] = times
    metadata = {"method": solver["method"], "nfev": solution.nfev, "seconds_compute": time.perf_counter() - start, "source_kind": "synthetic", "interpretation": "numerical trajectory, not independent experimental validation", "inventory": parameters.get("inventory", "general"), "boundary_interpolation": "piecewise linear supplied boundary records", "events": "only event-free segments; split/reinitialize explicit inventory-changing events", "parameters": parameters}
    return states, fluxes, balance, metadata


def project_observations(states, pressure, operator):
    if operator["state"] not in STATES:
        raise ValueError("A documented observation-state mapping is required")
    if operator["variable"] == "RH":
        return 100 * relative_humidity(states.Ta_K.to_numpy(), states.W_kg_kg.to_numpy(), pressure)
    values = states[operator["state"]].to_numpy()
    return values - 273.15 if operator["unit"] == "degC" else values


def identify_parameters(parameters, boundaries, initial_state, observed, operators, fitting, solver):
    """Bounded fitting; singular-value diagnostics are not independent CIs."""
    names = fitting["names"]
    def residual(vector):
        candidate = deepcopy(parameters)
        candidate.update(dict(zip(names, vector)))
        states, _, _, _ = simulate_network(candidate, boundaries, initial_state, solver)
        errors = [(project_observations(states, boundaries.pressure_pa.to_numpy(), op) - observed[op["variable"]].to_numpy()) / op["scale"] for op in operators]
        if fitting.get("prior_scale"):
            errors.append((vector - np.asarray(fitting["prior_mean"])) / fitting["prior_scale"])
        return np.concatenate(errors)
    solution = least_squares(residual, [parameters[n] for n in names], bounds=(fitting["lower"], fitting["upper"]), x_scale="jac", max_nfev=fitting["max_nfev"])
    singular = np.linalg.svd(solution.jac, compute_uv=False)
    rank = int(np.linalg.matrix_rank(solution.jac))
    table = pd.DataFrame({"parameter": names, "value": solution.x, "lower": fitting["lower"], "upper": fitting["upper"], "jacobian_rank": rank, "parameters_count": len(names), "condition_number": np.inf if singular[-1] == 0 else singular[0] / singular[-1], "status": "conditional fitted parameter" if rank == len(names) else "rank deficient; not individually identified", "uncertainty": "independent interval unavailable; temporal dependence not inferred from row count"})
    return table, {"success": bool(solution.success), "cost": float(solution.cost), "singular_values": singular.tolist(), "nfev": solution.nfev}


def verification_parameters():
    """Explicit software fixture; no parameter represents Coffee Solutions."""
    return {"Cc_j_k": 10000., "Cb_j_k": 30000., "dry_coffee_mass_kg": 2., "coffee_cp_j_kg_k": 1500., "volume_air_m3": 5., "Hca_w_k": 10., "Hba_w_k": 8., "Hpa_w_k": 3., "Gce_w_k": 5., "Gbe_w_k": 2., "Gbp_w_k": 1., "solar_effective_areas_m2": [0.2, 0.3, 0.1], "incident_area_m2": 1., "radiation_areas_m2": [1., 1., 1., 1.], "emissivities": [.8, .8, .8, 1.], "view_factors": [[0., 1/3, 1/3, 1/3], [1/3, 0., 1/3, 1/3], [1/3, 1/3, 0., 1/3], [1/3, 1/3, 1/3, 0.]], "gab_Mm": .05, "gab_C": 5., "gab_K": .8, "kinetic_k0_s": .0001, "kinetic_Ea_j_mol": 0., "parameter_provenance": "synthetic software verification fixture; not plant estimates", "inventory": "general"}
