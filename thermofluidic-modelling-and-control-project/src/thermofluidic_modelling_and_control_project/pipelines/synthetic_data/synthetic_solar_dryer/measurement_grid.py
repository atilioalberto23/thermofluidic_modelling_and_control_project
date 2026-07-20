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

def add_previous_measurements(df):

    data = df.copy()


    sensor_keys = [
        "SURFACE",
        "NODE_ID",
        "SENSOR_POSITION",
    ]


    data = data.sort_values(
        sensor_keys + ["TIMESTAMP"]
    )


    data[
        "DS_TEMP_ANT"
    ] = (
        data
        .groupby(sensor_keys)
        ["DS_TEMPERATURE"]
        .shift(1)
    )


    data[
        "DHT_TEMP_ANT"
    ] = (
        data
        .groupby(sensor_keys)
        ["DHT_TEMPERATURE"]
        .shift(1)
    )


    data[
        "DHT_HUMIDITY_ANT"
    ] = (
        data
        .groupby(sensor_keys)
        ["DHT_HUMIDITY"]
        .shift(1)
    )


    return data