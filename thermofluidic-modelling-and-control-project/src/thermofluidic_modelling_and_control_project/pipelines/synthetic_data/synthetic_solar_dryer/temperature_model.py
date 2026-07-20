import numpy as np
import pandas as pd


SURFACE_EFFECT = {

    "LEFT_WALL": 0,

    "RIGHT_WALL": 2,

    "BACK_WALL": -1,

}


def generate_ds_temperature(df, parameters):

    data = df.copy()

    data["TIMESTAMP"] = pd.to_datetime(
        data["TIMESTAMP"]
    )


    base_temperature = (
        parameters["temperature"]["base"]
    )


    amplitude = (
        parameters["temperature"]["daily_amplitude"]
    )


    hour = (
        data["TIMESTAMP"]
        .dt.hour
        +
        data["TIMESTAMP"]
        .dt.minute / 60
    )


    daily_cycle = (
        np.sin(
            2*np.pi*(hour-6)/24
        )
    )


    data["DS_TEMPERATURE"] = (
        base_temperature
        +
        amplitude*daily_cycle
        +
        data["SURFACE"].map(
            SURFACE_EFFECT
        )
        +
        0.4*data["Y"]
        +
        np.random.normal(
            0,
            0.15,
            len(data)
        )
    )


    return data