from kedro.pipeline import node, pipeline

from .nodes import build_causal_targets, train_temporal_models, run_thermal_verification, run_plant_network, run_cavity_study, run_pinn_verification, run_plant_pinn
from .comparison import compute_prediction_metrics, paired_block_intervals
from .enrichment import run_enrichment
from .openfoam import build_cases, run_openfoam_cases, extract_openfoam_outputs
from .reports import build_section_tables, render_results


def data_pipeline():
    return pipeline([node(build_causal_targets, ["measurement_derived", "params:learning"], "learning_windows", name="build_causal_targets")])


def learning_pipeline():
    return pipeline([node(train_temporal_models, ["learning_windows", "params:learning"], ["trained_temporal_models", "temporal_predictions", "temporal_search", "temporal_costs"], name="train_tree_xgboost_lightgbm_persistence")])


def thermal_pipeline():
    return pipeline([node(run_plant_network, ["plant_network_inputs", "params:thermal_network"], ["plant_network_artifacts", "plant_network_status"], name="simulate_and_identify_plant_network")])


def verification_pipeline():
    return pipeline([node(run_thermal_verification, "params:thermal_network", ["network_verification_artifacts", "network_verification_comparison"], name="verify_six_state_network")])


def cavity_pipeline():
    return pipeline([node(run_cavity_study, "params:cavity", ["cavity_artifacts", "cavity_summary", "cavity_refinement"], name="solve_streamfunction_vorticity_refinement")])


def pinn_pipeline():
    return pipeline([
        node(run_pinn_verification, ["params:pinn", "params:thermal_network"], ["pinn_checkpoint", "pinn_loss_history", "pinn_verification_predictions", "pinn_verification_metrics"], name="train_conditional_pinn_numerical_verification"),
        node(run_plant_pinn, ["plant_pinn_inputs", "params:pinn"], ["plant_pinn_artifacts", "plant_pinn_status"], name="train_conditional_pinn_with_observed_masks"),
    ])


def comparison_pipeline():
    return pipeline([
        node(compute_prediction_metrics, ["temporal_predictions", "params:thesis_comparison"], ["thesis_sensor_metrics", "thesis_prediction_metrics"], name="compute_common_prediction_metrics"),
        node(paired_block_intervals, ["temporal_predictions", "params:thesis_comparison"], "thesis_paired_intervals", name="compute_paired_block_intervals"),
    ])


def enrichment_pipeline():
    return pipeline([node(run_enrichment, ["enrichment_inputs", "params:enrichment"], ["enrichment_artifacts", "enrichment_status"], name="fit_discrepancy_and_enriched_models")])


def openfoam_pipeline():
    return pipeline([node(build_cases, ["plant_cfd_inputs", "params:openfoam"], "openfoam_cases", name="build_foundation12_multicomponent_cases")])


def openfoam_execution_pipeline():
    return pipeline([
        node(run_openfoam_cases, "params:openfoam", "openfoam_runs", name="run_mesh_check_and_multicomponent_solver"),
        node(extract_openfoam_outputs, ["params:openfoam", "openfoam_runs"], "openfoam_fields", name="extract_openfoam_thermal_and_vapor_fields"),
    ])


def results_pipeline():
    return pipeline([
        node(build_section_tables, ["measurement_derived", "measurement_coverage", "measurement_concordance", "measurement_temporal", "measurement_spatial", "thesis_prediction_metrics", "temporal_costs", "thesis_paired_intervals", "cavity_summary", "cavity_refinement", "network_verification_artifacts", "network_verification_comparison", "plant_network_status", "pinn_verification_metrics", "pinn_loss_history", "enrichment_status", "openfoam_runs", "openfoam_fields", "measurement_audit", "parameters"], "section_tables", name="build_scientific_section_tables"),
        node(render_results, ["section_tables", "temporal_costs", "measurement_audit", "parameters"], "thesis_results_bundle", name="export_structured_csv_latex_and_manifests"),
    ])
