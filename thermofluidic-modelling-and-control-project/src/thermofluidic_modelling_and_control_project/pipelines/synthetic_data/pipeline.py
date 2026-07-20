from kedro.pipeline import Pipeline, node, pipeline

from .geometry import create_empty_synthetic_dataset
from .geometry import generate_sensor_geometry


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
                func=create_empty_synthetic_dataset,
                inputs=None,
                outputs="synthetic_dataset",
                name="create_empty_synthetic_dataset_node",
                tags=["synthetic_data", "generation"],
            ),

        ]
    )