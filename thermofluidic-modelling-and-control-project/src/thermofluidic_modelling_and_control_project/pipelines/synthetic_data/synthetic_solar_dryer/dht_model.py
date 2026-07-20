import numpy as np


def generate_dht_temperature(
    df,
    parameters
):

    data = df.copy()


    offset = (
        parameters["dht"]["temperature_offset"]
    )


    noise = (
        parameters["dht"]["temperature_noise"]
    )


    data["DHT_TEMPERATURE"] = (
        data["DS_TEMPERATURE"]
        +
        offset
        +
        np.random.normal(
            0,
            noise,
            len(data)
        )
    )


    return data


import numpy as np


def generate_dht_humidity(
    df,
    parameters
):

    data = df.copy()


    base = (
        parameters["humidity"]["base"]
    )


    amplitude = (
        parameters["humidity"]["daily_amplitude"]
    )


    temp_factor = (
        parameters["humidity"]["temperature_factor"]
    )


    noise = (
        parameters["humidity"]["noise"]
    )


    hour = (
        data["TIMESTAMP"]
        .dt.hour
        +
        data["TIMESTAMP"]
        .dt.minute / 60
    )


    # Máxima humedad durante la madrugada
    daily_cycle = (
        np.cos(
            2*np.pi*(hour)/24
        )
    )


    humidity = (
        base
        +
        amplitude*daily_cycle
        -
        temp_factor *
        (
            data["DHT_TEMPERATURE"] - 35
        )
        +
        np.random.normal(
            0,
            noise,
            len(data)
        )
    )


    data["DHT_HUMIDITY"] = (
        humidity
        .clip(
            lower=0,
            upper=100
        )
    )


    return data