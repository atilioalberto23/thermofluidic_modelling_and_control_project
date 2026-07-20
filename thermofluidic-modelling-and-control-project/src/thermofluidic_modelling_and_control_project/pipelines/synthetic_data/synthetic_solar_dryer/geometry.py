import pandas as pd


import math
import pandas as pd


def calculate_sensor_position(
    node_x,
    node_y,
    direction,
    cable_length,
    angle_deg,
):

    angle_rad = math.radians(angle_deg)

    dx = cable_length * math.cos(angle_rad)
    dy = cable_length * math.sin(angle_rad)

    movements = {

        "NO": (-dx, dy),
        "NE": (dx, dy),
        "SO": (-dx, -dy),
        "SE": (dx, -dy),

    }

    move_x, move_y = movements[direction]

    return (
        round(node_x + move_x, 4),
        round(node_y + move_y, 4),
    )

def generate_wall_sensor_geometry(
    surface_name,
    cable_length,
    angle_deg,
):

    nodes = {

        "N1": (0.925, 0.32),
        "N2": (0.925, 1.58),
        "N3": (4.625, 0.32),
        "N4": (4.625, 1.58),

    }


    angle = math.radians(angle_deg)

    dx = cable_length * math.cos(angle)
    dy = cable_length * math.sin(angle)


    directions = {

        "SO": (-dx, -dy),
        "SE": (dx, -dy),
        "NO": (-dx, dy),
        "NE": (dx, dy),

    }


    rows=[]


    for node_id,(nx,ny) in nodes.items():

        for position,(ox,oy) in directions.items():

            rows.append(
                {
                    "SURFACE":surface_name,
                    "NODE_ID":node_id,
                    "SENSOR_POSITION":position,
                    "X":nx+ox,
                    "Y":ny+oy,
                }
            )


    df=pd.DataFrame(rows)


    # referencia global de la pared
    #df["X"]=df["X_RAW"]-df["X_RAW"].min()
    #df["Y"]=df["Y_RAW"]-df["Y_RAW"].min()


    return df[
        [
            "SURFACE",
            "NODE_ID",
            "SENSOR_POSITION",
            "X",
            "Y",
        ]
    ]


def generate_back_wall_geometry():

    points = [

        ("SO",0,0),
        ("SE",1.12,0),
        ("NO",0,2.05),
        ("NE",1.12,2.05),

    ]


    rows=[]


    for pos,x,y in points:

        rows.append({

            "SURFACE":"BACK_WALL",
            "NODE_ID":None,
            "SENSOR_POSITION":pos,
            "X":x,
            "Y":y,

        })


    return pd.DataFrame(rows)


def generate_sensor_geometry(parameters):

    cable_length = (
        parameters["geometry"]["cable_length"]
    )

    angle_deg = (
        parameters["geometry"]["cable_angle_deg"]
    )


    left_geometry = generate_wall_sensor_geometry(
        surface_name="LEFT_WALL",
        cable_length=cable_length,
        angle_deg=angle_deg,
    )


    right_geometry = generate_wall_sensor_geometry(
        surface_name="RIGHT_WALL",
        cable_length=cable_length,
        angle_deg=angle_deg,
    )


    back_geometry = generate_back_wall_geometry()


    geometry = pd.concat(
        [
            left_geometry,
            right_geometry,
            back_geometry,
        ],
        ignore_index=True,
    )


    return geometry






















#####################

COLUMNS = [
    "SURFACE",
    "X",
    "Y",
    "DS_TEMPERATURE",
    "DHT_TEMPERATURE",
    "DHT_HUMIDITY",
    "MSR_PRD_ID",
    "TIMESTAMP",
    "DS_TEMP_ANT",
    "DHT_TEMP_ANT",
    "DHT_HUMIDITY_ANT",
]


def create_empty_synthetic_dataset() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)







