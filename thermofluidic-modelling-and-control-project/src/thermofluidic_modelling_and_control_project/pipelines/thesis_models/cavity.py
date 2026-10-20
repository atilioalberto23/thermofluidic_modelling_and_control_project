"""2D streamfunction-vorticity-temperature solver; met:cavidad.

Second-order diffusion and Poisson; donor-cell advection (first order).
Thom no-slip wall vorticity. Explicit diffusion/advection stability bound.
"""

import time

import numpy as np
import pandas as pd
from scipy.fft import dstn, idstn


def poisson_streamfunction(omega, dx):
    n = omega.shape[0] - 2
    wave = np.arange(1, n + 1)
    eigen = (2 * np.cos(np.pi * wave / (n + 1)) - 2) / dx**2
    transformed = dstn(-omega[1:-1, 1:-1], type=1, norm="ortho")
    psi = np.zeros_like(omega)
    psi[1:-1, 1:-1] = idstn(transformed / (eigen[:, None] + eigen[None, :]), type=1, norm="ortho")
    return psi


def laplacian(field, dx):
    return (field[2:, 1:-1] + field[:-2, 1:-1] + field[1:-1, 2:] + field[1:-1, :-2] - 4 * field[1:-1, 1:-1]) / dx**2


def advective_derivative(field, u, v, dx):
    center = field[1:-1, 1:-1]
    horizontal = np.where(u >= 0, center - field[:-2, 1:-1], field[2:, 1:-1] - center) / dx
    vertical = np.where(v >= 0, center - field[1:-1, :-2], field[1:-1, 2:] - center) / dx
    return u * horizontal + v * vertical


def square_view_factors():
    adjacent = 1 - 1 / np.sqrt(2)
    opposite = np.sqrt(2) - 1
    # left, right, bottom, top; equal lengths, closure and reciprocity.
    return np.array([[0, opposite, adjacent, adjacent], [opposite, 0, adjacent, adjacent], [adjacent, adjacent, 0, opposite], [adjacent, adjacent, opposite, 0]])


def wall_radiation(theta, config):
    mean_theta = np.array([theta[0, :].mean(), theta[-1, :].mean(), theta[:, 0].mean(), theta[:, -1].mean()])
    absolute = config["cold_temperature_k"] + config["delta_temperature_k"] * mean_theta
    factors = square_view_factors()
    epsilon = np.asarray(config["emissivities"])
    matrix = np.eye(4) - (1 - epsilon)[:, None] * factors
    radiosity = np.linalg.solve(matrix, epsilon * 5.670374419e-8 * absolute**4)
    return radiosity - factors @ radiosity


def solve_cavity(config):
    n, rayleigh, prandtl = config["grid_points"], config["Ra"], config["Pr"]
    dx = 1 / (n - 1)
    theta = np.tile(np.linspace(1, 0, n)[:, None], (1, n))
    omega = np.zeros((n, n))
    psi = np.zeros_like(omega)
    u, v = np.zeros_like(omega), np.zeros_like(omega)
    t, step = 0., 0
    history = []
    converged = False
    start = time.perf_counter()
    while t < config["max_dimensionless_time"] and step < config["max_steps"]:
        psi = poisson_streamfunction(omega, dx)
        # Thom formula: no slip, psi=0 at all walls (omega is not zero).
        omega[0, 1:-1] = -2 * psi[1, 1:-1] / dx**2
        omega[-1, 1:-1] = -2 * psi[-2, 1:-1] / dx**2
        omega[1:-1, 0] = -2 * psi[1:-1, 1] / dx**2
        omega[1:-1, -1] = -2 * psi[1:-1, -2] / dx**2
        u[1:-1, 1:-1] = (psi[1:-1, 2:] - psi[1:-1, :-2]) / (2 * dx)
        v[1:-1, 1:-1] = -(psi[2:, 1:-1] - psi[:-2, 1:-1]) / (2 * dx)
        speed = np.max(np.abs(u) + np.abs(v))
        dt = config["time_factor"] * min(dx**2 / (4 * max(1., prandtl)), dx / max(speed, 1e-12))
        dt = min(dt, config["max_dimensionless_time"] - t)
        ui, vi = u[1:-1, 1:-1], v[1:-1, 1:-1]
        d_theta = laplacian(theta, dx) - advective_derivative(theta, ui, vi, dx)
        gradient_x = (theta[2:, 1:-1] - theta[:-2, 1:-1]) / (2 * dx)
        d_omega = prandtl * laplacian(omega, dx) - advective_derivative(omega, ui, vi, dx) + rayleigh * prandtl * gradient_x
        theta[1:-1, 1:-1] += dt * d_theta
        omega[1:-1, 1:-1] += dt * d_omega
        if config.get("radiation"):
            radiative = wall_radiation(theta, config)
            scale = config["length_m"] / (config["conductivity_w_m_k"] * config["delta_temperature_k"])
            # External insulation: inward conductive supply equals outgoing radiation.
            theta[1:-1, 0] = theta[1:-1, 1] - dx * scale * radiative[2]
            theta[1:-1, -1] = theta[1:-1, -2] - dx * scale * radiative[3]
        else:
            theta[1:-1, 0] = (4 * theta[1:-1, 1] - theta[1:-1, 2]) / 3
            theta[1:-1, -1] = (4 * theta[1:-1, -2] - theta[1:-1, -3]) / 3
        theta[0, :] = 1
        theta[-1, :] = 0
        t += dt
        step += 1
        if not np.isfinite(theta).all() or not np.isfinite(omega).all():
            raise RuntimeError("Cavity diverged; reduce timestep/refine discretization")
        if step % 200 == 0:
            residual = max(float(np.max(np.abs(d_theta))), float(np.max(np.abs(d_omega))) / max(1., rayleigh))
            history.append({"step": step, "dimensionless_time": t, "dt": dt, "scaled_stationary_residual": residual})
            if t >= config["minimum_dimensionless_time"] and residual < config["stationary_tolerance"]:
                converged = True
                break
    derivative_hot = (-3 * theta[0, :] + 4 * theta[1, :] - theta[2, :]) / (2 * dx)
    derivative_cold = (3 * theta[-1, :] - 4 * theta[-2, :] + theta[-3, :]) / (2 * dx)
    hot = float(np.trapezoid(-derivative_hot, dx=dx))
    cold = float(np.trapezoid(-derivative_cold, dx=dx))
    mesh_x, mesh_y = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n), indexing="ij")
    fields = pd.DataFrame({"x_dimensionless": mesh_x.ravel(), "y_dimensionless": mesh_y.ravel(), "theta": theta.ravel(), "psi": psi.ravel(), "omega": omega.ravel(), "u_alpha_over_L": u.ravel(), "v_alpha_over_L": v.ravel()})
    u_index, v_index = np.unravel_index(np.argmax(np.abs(u)), u.shape), np.unravel_index(np.argmax(np.abs(v)), v.shape)
    summary = {"Ra": rayleigh, "Pr": prandtl, "grid_points": n, "h": dx, "Nu_hot": hot, "Nu_cold": cold, "heat_balance_difference": hot - cold, "u_extreme": float(u[u_index]), "u_x": u_index[0] * dx, "u_y": u_index[1] * dx, "v_extreme": float(v[v_index]), "v_x": v_index[0] * dx, "v_y": v_index[1] * dx, "steps": step, "dimensionless_time": t, "converged": converged, "compute_seconds": time.perf_counter() - start, "radiation": bool(config.get("radiation")), "source_kind": "numerical_verification", "advection_order": 1, "poisson": "DST exact discrete solve", "stationary_residual": history[-1]["scaled_stationary_residual"] if history else np.nan}
    return fields, pd.DataFrame(history), summary


def refinement_estimate(coarse, middle, fine, r=2., safety=1.25):
    differences = [middle - fine, coarse - middle]
    if differences[0] * differences[1] <= 0 or min(map(abs, differences)) < 1e-12:
        return {"status": "inconclusive: oscillatory or nearly zero differences"}
    order = np.log(abs(differences[1] / differences[0])) / np.log(r)
    if order <= 0:
        return {"status": "inconclusive: not decreasing under refinement"}
    return {"status": "monotone estimate; asymptotic regime still requires examination", "observed_order": float(order), "extrapolated": float(fine + (fine - middle) / (r**order - 1)), "GCI_absolute": float(safety * abs(fine - middle) / (r**order - 1))}
