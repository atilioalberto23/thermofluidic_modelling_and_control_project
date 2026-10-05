# Estructura de `synthetic_final_data`

Cada fila representa una medición sintética de un sensor en un instante determinado. El conjunto contiene 13 columnas de datos.

Tipos verificados en los metadatos de `thermofluidic-modelling-and-control-project/data/03_primary/synthetic_final_data.parquet`.

| Columna | Tipo | Descripción |
|---|---|---|
| `SURFACE` | Texto | Pared: `LEFT_WALL`, `RIGHT_WALL` o `BACK_WALL`. |
| `X` | `float64` | Coordenada horizontal del sensor. |
| `Y` | `float64` | Coordenada vertical del sensor. |
| `MSR_PRD_ID` | `int64` | Identificador del instante, con formato `AAAAMMDDHHMMSS`. |
| `TIMESTAMP` | `datetime64[us]` | Fecha y hora de la medición. |
| `NODE_ID` | Texto | Nodo: `N1` a `N4`; nulo para la pared posterior. |
| `SENSOR_POSITION` | Texto | Posición: `SO`, `SE`, `NO` o `NE`. |
| `DS_TEMPERATURE` | `float64` | Temperatura sintética del sensor DS. |
| `DHT_TEMPERATURE` | `float64` | Temperatura sintética del sensor DHT. |
| `DHT_HUMIDITY` | `float64` | Humedad relativa sintética, entre 0 y 100 %. |
| `DS_TEMP_ANT` | `float64` | Temperatura DS de la medición anterior. |
| `DHT_TEMP_ANT` | `float64` | Temperatura DHT de la medición anterior. |
| `DHT_HUMIDITY_ANT` | `float64` | Humedad DHT de la medición anterior. |

## Mediciones anteriores

Las columnas `_ANT` se calculan agrupando por `SURFACE`, `NODE_ID` y `SENSOR_POSITION`, ordenando por `TIMESTAMP` y aplicando `shift(1)`.

- La primera medición de cada sensor no tiene valor anterior y queda nula.
- En la implementación actual, `groupby` excluye los grupos con `NODE_ID` nulo. Por ello, las columnas `_ANT` de `BACK_WALL` quedan nulas en todas sus mediciones.

## Índice y almacenamiento

El Parquet guarda además el índice de pandas como `__index_level_0__`, de tipo `int64`. Este campo no es una variable de medición ni forma parte de las 13 columnas de datos.

El catálogo de Kedro configura `synthetic_final_data` como `pandas.ParquetDataset`, con destino `s3://thermofluidic-modelling-and-control-project/synthetic_data/synthetic_dataset.parquet`. Los tipos documentados corresponden al archivo local inspeccionado.
