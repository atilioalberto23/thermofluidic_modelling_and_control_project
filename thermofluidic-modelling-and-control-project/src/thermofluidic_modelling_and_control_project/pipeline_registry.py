from thermofluidic_modelling_and_control_project.pipelines import synthetic_data


def register_pipelines():
    synthetic_pipeline = synthetic_data.create_pipeline()

    return {
        "__default__": synthetic_pipeline,
        "synthetic_data": synthetic_pipeline,
    }