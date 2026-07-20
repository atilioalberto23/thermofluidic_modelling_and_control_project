def create_measurement_grid(
    sensor_geometry,
    measurement_times,
):

    sensor_geometry = sensor_geometry.copy()

    measurement_times = measurement_times.copy()


    sensor_geometry["key"] = 1
    measurement_times["key"] = 1


    grid = measurement_times.merge(
        sensor_geometry,
        on="key",
        how="outer",
    )


    grid = grid.drop(
        columns=["key"]
    )


    return grid[
        [
            "SURFACE",
            "X",
            "Y",
            "MSR_PRD_ID",
            "TIMESTAMP",
            "NODE_ID",
            "SENSOR_POSITION",
        ]
    ]