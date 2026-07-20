from kedro.pipeline import Pipeline, node, pipeline

from pipelines.synthetic_data.synthetic_solar_dryer.geometry import create_empty_synthetic_dataset
from pipelines.synthetic_data.synthetic_solar_dryer.geometry import generate_sensor_geometry
from pipelines.synthetic_data.synthetic_solar_dryer.timing import generate_measurement_times


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=generate_sensor_geometry,
                inputs="params:synthetic_data",
                outputs="sensor_geometry",
                name="generate_sensor_geometry",
                tags=[
                    "synthetic_data",
                    "synthetic_geometry",
                ],
            ),
            node(
                func=generate_measurement_times,
                inputs="params:synthetic_data.timing",
                outputs="measurement_times",
                name="generate_measurement_times",
                tags=[
                    "synthetic_data",
                    "synthetic_timing",
                ],
            ),
            node(
                func=create_empty_synthetic_dataset,
                inputs=None,
                outputs="synthetic_dataset",
                name="create_empty_synthetic_dataset_node",
                tags=["synthetic_data", "generation"],
            ),

        ]
    )