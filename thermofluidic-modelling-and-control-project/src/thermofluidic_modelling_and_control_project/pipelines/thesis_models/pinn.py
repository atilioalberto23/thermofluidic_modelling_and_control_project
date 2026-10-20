"""Conditional six-state PINN, met:flujo_pinn/residual_pinn/perdida_pinn."""

from io import BytesIO
import time

import numpy as np
import pandas as pd
import torch
from torch import nn

from .thermal import STATES, thermal_rhs


class ConditionalPINN(nn.Module):
    def __init__(self, config):
        super().__init__()
        torch.manual_seed(config["seed"])
        sizes = [13] + config["hidden_layers"] + [6]
        layers = []
        for i in range(len(sizes) - 1):
            layers.append(nn.Linear(sizes[i], sizes[i + 1]))
            if i < len(sizes) - 2:
                layers.append(nn.Tanh())
        self.network = nn.Sequential(*layers).double()
        # Small initial increments stay inside the physical collocation domain.
        nn.init.zeros_(self.network[-1].weight)
        nn.init.zeros_(self.network[-1].bias)
        self.duration = config["segment_seconds"]
        self.register_buffer("state_center", torch.tensor(config["state_center"], dtype=torch.float64))
        self.register_buffer("state_scale", torch.tensor(config["state_scale"], dtype=torch.float64))
        self.register_buffer("boundary_center", torch.tensor(config["boundary_center"], dtype=torch.float64))
        self.register_buffer("boundary_scale", torch.tensor(config["boundary_scale"], dtype=torch.float64))

    def forward(self, seconds, initial, boundary):
        normalized = seconds / self.duration
        inputs = torch.cat([normalized, (initial - self.state_center) / self.state_scale, (boundary - self.boundary_center) / self.boundary_scale], dim=1)
        return initial + normalized * self.network(inputs) * self.state_scale


def residuals(model, seconds, initial, boundary, physical_parameters, create_graph=True):
    seconds = seconds.clone().detach().requires_grad_(True)
    predicted = model(seconds, initial, boundary)
    derivative = torch.cat([torch.autograd.grad(predicted[:, q].sum(), seconds, create_graph=create_graph, retain_graph=True)[0] for q in range(6)], dim=1)
    physics = thermal_rhs(predicted, boundary, physical_parameters, xp=torch)
    return predicted, derivative - physics


def train_conditional_pinn(samples, parameters, config):
    """Only explicitly supplied observed targets are supervised via a mask.

    Numerical assistance is identified separately in each supplied sample.
    Input arrays: initial (N,6), boundary (N,6), target (N,6), mask (N,6).
    Splits are supplied by the causal upstream producer, never random rows.
    """
    torch.set_num_threads(2)
    model = ConditionalPINN(config)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"])
    generator = np.random.default_rng(config["seed"])
    train = samples["train"]
    valid = samples["validation"]
    def tensors(sample):
        return [torch.as_tensor(sample[key], dtype=torch.float64) for key in ["seconds", "initial", "boundary", "target", "mask"]]
    ts, tx, tb, ty, mask = tensors(train)
    vs, vx, vb, vy, vm = tensors(valid)
    best, best_state, stale = np.inf, None, 0
    history = []
    start = time.perf_counter()
    for epoch in range(config["epochs"]):
        optimizer.zero_grad()
        # Conditional state/forcing samples stay coupled; only local time varies.
        collocation_seconds = torch.tensor(generator.uniform(0, config["segment_seconds"], (len(tx), 1)), dtype=torch.float64)
        predicted = model(ts, tx, tb)
        _, residual = residuals(model, collocation_seconds, tx, tb, parameters)
        data_loss = (((predicted - ty) / model.state_scale)**2 * mask).sum() / mask.sum().clamp(min=1)
        physics_loss = ((residual / (model.state_scale / model.duration))**2).mean()
        positivity = torch.relu(-predicted[:, 4:]).square().mean()
        # Domain restriction; no monotonic-M constraint (rehumectation is allowed).
        loss = config["lambda_data"] * data_loss + config["lambda_physics"] * physics_loss + config["lambda_restriction"] * positivity
        if not torch.isfinite(loss):
            raise RuntimeError("PINN loss nonfinite; inspect physical domain and scaling")
        loss.backward()
        gradient_norm = float(nn.utils.clip_grad_norm_(model.parameters(), config["max_gradient_norm"]))
        optimizer.step()
        with torch.no_grad():
            val_loss = ((((model(vs, vx, vb) - vy) / model.state_scale)**2 * vm).sum() / vm.sum().clamp(min=1)).item()
        history.append({"epoch": epoch, "data_loss": data_loss.item(), "physics_loss": physics_loss.item(), "restriction_loss": positivity.item(), "validation_data_loss": val_loss, "gradient_norm": gradient_norm, "training_source_kind": train["source_kind"]})
        if val_loss < best:
            best = val_loss
            best_state = {key: value.detach().clone() for key, value in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        if stale >= config["patience"]:
            break
    model.load_state_dict(best_state)
    held = samples["test"]
    hs, hx, hb, hy, hm = tensors(held)
    predicted, residual = residuals(model, hs, hx, hb, parameters, create_graph=False)
    initial_error = float(torch.max(torch.abs(model(torch.zeros_like(hs), hx, hb) - hx)).detach())
    output = pd.DataFrame(predicted.detach().numpy(), columns=STATES)
    metrics = []
    for q, name in enumerate(STATES):
        errors = (predicted[:, q] - hy[:, q]).detach().numpy()
        selected = hm[:, q].bool().numpy()
        metrics.append({"state": name, "RMSE_on_supplied_reference": float(np.sqrt(np.mean(errors[selected]**2))) if selected.any() else np.nan, "N_supervised": int(selected.sum()), "RMS_physical_residual_per_second": float(torch.sqrt(torch.mean(residual[:, q]**2)).detach()), "initial_condition_error": initial_error, "source_kind": held["source_kind"], "interpretation": "reference type controls evidence; numerical supervision is not experimental validation"})
    buffer = BytesIO()
    torch.save({"state_dict": model.state_dict(), "configuration": config, "physical_parameters": parameters, "input_sources": {k: s["source_kind"] for k, s in samples.items()}, "seconds_training": time.perf_counter() - start}, buffer)
    return {"conditional_pinn.pt": buffer.getvalue(), "configuration.json": config}, pd.DataFrame(history), output, pd.DataFrame(metrics)
