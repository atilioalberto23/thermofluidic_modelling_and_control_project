from thermofluidic_modelling_and_control_project.pipelines import synthetic_data, measurement_results


def register_pipelines():
    synthetic_pipeline = synthetic_data.create_pipeline()
    results_pipeline = measurement_results.create_pipeline()

    return {
        "__default__": synthetic_pipeline + results_pipeline,
        "synthetic_data": synthetic_pipeline,
        "measurement_results": results_pipeline,
    }
