from thermofluidic_modelling_and_control_project.pipelines import synthetic_data, measurement_results
from thermofluidic_modelling_and_control_project.pipelines.measurement_results import model_comparison
from thermofluidic_modelling_and_control_project.pipelines.thesis_models import pipeline as thesis


def register_pipelines():
    synthetic_pipeline = synthetic_data.create_pipeline()
    results_pipeline = measurement_results.create_pipeline()
    integrated = (results_pipeline + thesis.data_pipeline() + thesis.learning_pipeline() + thesis.thermal_pipeline() + thesis.verification_pipeline() + thesis.cavity_pipeline() + thesis.pinn_pipeline() + thesis.comparison_pipeline() + thesis.enrichment_pipeline() + thesis.openfoam_pipeline() + thesis.openfoam_execution_pipeline() + thesis.results_pipeline())

    return {
        "__default__": results_pipeline,
        "synthetic_data": synthetic_pipeline,
        "measurement_results": results_pipeline,
        "synthetic_results": synthetic_pipeline + results_pipeline,
        "model_comparison": model_comparison.create_pipeline(),
        "thesis_data": results_pipeline + thesis.data_pipeline(),
        "data_driven": thesis.data_pipeline() + thesis.learning_pipeline(),
        "thermal_network": thesis.thermal_pipeline(),
        "physics_verification": thesis.verification_pipeline(),
        "cavity_2d": thesis.cavity_pipeline(),
        "physics_informed": thesis.pinn_pipeline(),
        "thesis_comparison": thesis.comparison_pipeline(),
        "enrichment": thesis.enrichment_pipeline(),
        "cfd_openfoam": thesis.openfoam_pipeline(),
        "cfd_execute": thesis.openfoam_execution_pipeline(),
        "thesis_results": thesis.results_pipeline(),
        "thesis_models": integrated,
    }
