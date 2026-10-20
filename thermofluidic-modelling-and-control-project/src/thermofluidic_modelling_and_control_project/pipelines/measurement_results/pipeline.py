from kedro.pipeline import node, pipeline

from .nodes import audit_measurements, create_figures, prepare_measurements, psychrometrics, summarize_measurements


def create_pipeline(**kwargs):
    return pipeline([
        node(prepare_measurements, ["synthetic_final_data", "params:measurement_results"], "measurement_derived", name="prepare_measurements"),
        node(audit_measurements, ["synthetic_final_data", "measurement_derived", "params:measurement_results", "params:synthetic_data"], "measurement_audit", name="audit_measurements"),
        node(summarize_measurements, ["measurement_derived", "params:measurement_results"], ["measurement_temporal", "measurement_coverage", "measurement_spatial", "measurement_concordance"], name="summarize_measurements"),
        node(psychrometrics, ["measurement_derived", "params:measurement_results"], "measurement_psychrometrics", name="psychrometrics"),
        node(create_figures, ["measurement_derived", "measurement_temporal", "measurement_coverage", "measurement_concordance", "params:measurement_results"], "measurement_figures", name="measurement_figures"),
    ])
