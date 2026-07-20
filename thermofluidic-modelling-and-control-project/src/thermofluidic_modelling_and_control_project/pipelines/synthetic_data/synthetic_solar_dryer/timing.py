import pandas as pd


def generate_measurement_times(parameters):

    #parameters = parameters["timing"]

    days = parameters["simulation_days"]

    interval = parameters["sampling_seconds"]


    start = pd.Timestamp(
        "2026-01-01 00:00:00"
    )


    end = start + pd.Timedelta(
        days=days
    )


    timestamps = pd.date_range(
        start=start,
        end=end,
        freq=f"{interval}s",
        inclusive="left",
    )


    df = pd.DataFrame(
        {
            "TIMESTAMP": timestamps
        }
    )


    df["MSR_PRD_ID"] = (
        df["TIMESTAMP"]
        .dt.strftime("%Y%m%d%H%M%S")
    )


    return df