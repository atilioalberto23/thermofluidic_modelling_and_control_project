"""Numerical invariants and leakage checks, independent of production outputs."""
import numpy as np
import pandas as pd
import pytest
import torch

from thermofluidic_modelling_and_control_project.pipelines.thesis_models.thermal import (
    thermal_rhs, verification_parameters, validate_parameters, BOUNDARIES,
)
from thermofluidic_modelling_and_control_project.pipelines.thesis_models.cavity import poisson_streamfunction, laplacian
from thermofluidic_modelling_and_control_project.pipelines.thesis_models.pinn import ConditionalPINN, residuals
from thermofluidic_modelling_and_control_project.pipelines.thesis_models.learning import build_causal_targets
from thermofluidic_modelling_and_control_project.pipelines.thesis_models.enrichment import train_enriched_model, fit_discrepancy_model
from sklearn.tree import DecisionTreeRegressor


def test_shared_numpy_torch_rhs_and_evaporation():
    p = verification_parameters()
    state = np.array([[305., 303., 302., 300., .008, .15]])
    boundary = np.array([[298., .007, 101325., 200., .01, 298.]])
    expected, flows = thermal_rhs(state, boundary, p, return_flows=True)
    actual = thermal_rhs(torch.tensor(state), torch.tensor(boundary), p, xp=torch)
    np.testing.assert_allclose(actual.numpy(), expected, rtol=1e-12, atol=1e-12)
    assert expected[0, 5] < 0
    # Rehumidification is a physical possibility, not silently clipped.
    state[0, 5] = 0
    assert thermal_rhs(state, boundary, p)[0, 5] > 0


def test_reciprocity_and_solar_allocation_rejected():
    p = verification_parameters()
    p['radiation_areas_m2'][0] = 2
    with pytest.raises(ValueError, match='reciprocity'):
        validate_parameters(p)
    p = verification_parameters()
    p['solar_effective_areas_m2'] = [1, 1, 1]
    with pytest.raises(ValueError, match='Solar'):
        validate_parameters(p)


def test_poisson_sign_and_no_slip_boundary():
    n = 17
    x = np.linspace(0, 1, n)
    exact = np.sin(np.pi * x[:, None]) * np.sin(np.pi * x[None, :])
    omega = np.zeros_like(exact)
    omega[1:-1, 1:-1] = -laplacian(exact, 1 / (n - 1))
    computed = poisson_streamfunction(omega, 1 / (n - 1))
    np.testing.assert_allclose(computed, exact, atol=2e-15)


def test_pinn_exact_initial_and_six_differentiable_residuals():
    config = dict(seed=7, hidden_layers=[8], segment_seconds=20, state_center=[300]*4+[.01,.1], state_scale=[10]*4+[.01,.1], boundary_center=[300,.01,101325,100,.01,300], boundary_scale=[10,.01,10000,100,.01,10])
    model = ConditionalPINN(config)
    initial = torch.tensor([[300.]*4+[.008,.1]], dtype=torch.float64)
    boundary = torch.tensor([[298.,.007,101325.,200.,.01,298.]], dtype=torch.float64)
    assert torch.equal(model(torch.zeros((1,1), dtype=torch.float64), initial, boundary), initial)
    _, residual = residuals(model, torch.ones((1,1), dtype=torch.float64), initial, boundary, verification_parameters())
    assert residual.shape == (1,6) and torch.isfinite(residual).all()
    residual.square().sum().backward()
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in model.parameters())


def test_exact_future_timestamp_and_purged_supports():
    times = pd.date_range('2026-01-01', periods=240, freq='20s')
    frame = pd.DataFrame(dict(TIMESTAMP=times, POSITION_ID='a', SEGMENT_ID=1, INCLUDED_SUMMARIES=True, DS_TEMPERATURE=np.arange(240.), DHT_TEMPERATURE=np.arange(240.), DHT_HUMIDITY=50., X=0., Y=0., SURFACE='wall', NODE_ID=1, SENSOR_POSITION=1))
    for name in ['DS_TEMPERATURE','DHT_TEMPERATURE','DHT_HUMIDITY']:
        frame['INVALID_'+name] = False
    cfg = dict(origin_stride_seconds=20, history_seconds=[20,60], horizons_seconds=[20,120], development_fraction=.5, configuration_id='fixture', source_kind='synthetic', episode_column=None)
    result = build_causal_targets(frame, cfg)
    np.testing.assert_allclose(result.target_DS_TEMPERATURE - result.DS_TEMPERATURE, result.horizon_seconds / 20)
    dev, test = [result.loc[result.split_id.eq(s)] for s in ['development','test']]
    assert dev.support_end.max() < test.support_start.min()
    # Deleting a timestamp must remove its target, not shift to the next row.
    hole = times[160]
    missing = build_causal_targets(frame.loc[frame.TIMESTAMP.ne(hole)], cfg)
    assert not missing.target_timestamp.eq(hole).any()


def test_enrichment_balances_sources_and_rejects_leaked_generator():
    measured = pd.DataFrame({'x':[0.,1.], 'y':[0.,1.]})
    numerical = pd.DataFrame({'x':[0.,1.,2.,3.], 'y':[0.,1.,2.,3.], 'trajectory_id':['a','b','b','b'], 'generator_fit_partition':'development'})
    _, metadata = train_enriched_model(measured, numerical, ['x'], 'y', DecisionTreeRegressor(), .5)
    assert metadata['real_total_weight'] == 1
    assert metadata['numerical_total_weight'] == pytest.approx(.5)
    numerical.loc[0,'generator_fit_partition'] = 'test'
    with pytest.raises(ValueError, match='leaks'):
        train_enriched_model(measured, numerical, ['x'], 'y', DecisionTreeRegressor(), .5)


def test_discrepancy_requires_out_of_fit_base():
    frame = pd.DataFrame({'x':[0.,1.], 'y':[1.,2.], 'physical_prediction':[0.,0.], 'base_out_of_fit':False})
    with pytest.raises(ValueError, match='out-of-fit'):
        fit_discrepancy_model(frame,frame,frame,['x'],'y',dict(depths=[2], min_samples_leaf=1,seed=1))
