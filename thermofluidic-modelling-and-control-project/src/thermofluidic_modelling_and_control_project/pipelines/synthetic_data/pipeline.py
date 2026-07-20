from kedro.pipeline import Pipeline, node, pipeline



from thermofluidic_modelling_and_control_project.pipelines.synthetic_data.synthetic_solar_dryer.geometry import (
    generate_sensor_geometry
)

from thermofluidic_modelling_and_control_project.pipelines.synthetic_data.synthetic_solar_dryer.timing import (
    generate_measurement_times
)

from thermofluidic_modelling_and_control_project.pipelines.synthetic_data.synthetic_solar_dryer.measurement_grid import (
    create_measurement_grid,
    add_previous_measurements
)

from thermofluidic_modelling_and_control_project.pipelines.synthetic_data.synthetic_solar_dryer.temperature_model import (
    generate_ds_temperature
)

from thermofluidic_modelling_and_control_project.pipelines.synthetic_data.synthetic_solar_dryer.dht_model import (
    generate_dht_temperature
)

from thermofluidic_modelling_and_control_project.pipelines.synthetic_data.synthetic_solar_dryer.dht_model import (
    generate_dht_humidity
)


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
                func=create_measurement_grid,
                inputs=[
                    "sensor_geometry",
                    "measurement_times",
                ],
                outputs="synthetic_measurement_grid",
                name="create_measurement_grid",
                tags=["synthetic_data", "synthetic_grid"],
            ),
            node(
                func=generate_ds_temperature,
                inputs=[
                    "synthetic_measurement_grid",
                    "params:synthetic_data",
                ],
                outputs="synthetic_temperature_data",
                name="generate_ds_temperature",
                tags=["synthetic_data", "synthetic_temperature"],
            ),
            node(
                func=generate_dht_temperature,
                inputs=[
                    "synthetic_temperature_data",
                    "params:synthetic_data",
                ],
                outputs="synthetic_dht_temperature_data",
                name="generate_dht_temperature",
                tags=["synthetic_data", "synthetic_dht_temperature"],
            ),
            node(
                func=generate_dht_humidity,
                inputs=[
                    "synthetic_dht_temperature_data",
                    "params:synthetic_data",
                ],
                outputs="synthetic_humidity_data",
                name="generate_dht_humidity",
                tags=["synthetic_data", "synthetic_humidity_data"],
            ),
            node(
                func=add_previous_measurements,
                inputs="synthetic_humidity_data",
                outputs="synthetic_final_data",
                name="add_previous_measurements",
                tags=["synthetic_data", "synthetic_final_data"],
            ),
        ]
    )