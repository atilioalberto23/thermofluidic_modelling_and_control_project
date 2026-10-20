# Pipeline local de resultados

La ampliación con LightGBM, XGBoost, red térmica, cavidad, PINN, OpenFOAM y
tablas científicas está documentada en [modelos_resultados_entrega.md](modelos_resultados_entrega.md).
Ese informe identifica las ejecuciones actuales y los requisitos pendientes.

Implementación basada en `../instrucciones_codex_resultados_kedro.md` y
`../ch4_methodology (1).tex`. Se revisó también el marco teórico disponible.
La instrucción del investigador de almacenar localmente prevalece sobre la
arquitectura AWS descrita en la metodología. Ningún dataset del catálogo utiliza
S3 ni necesita credenciales AWS.

## Ejecución

Desde la raíz Kedro, `thermofluidic-modelling-and-control-project`, en PowerShell:

```powershell
$env:KEDRO_DISABLE_TELEMETRY = '1'
$env:MPLCONFIGDIR = Join-Path (Get-Location) '.mplconfig'
../.venv/Scripts/python.exe -m kedro run --pipelines=measurement_results
$env:PYTHONPATH = 'src'
../.venv/Scripts/python.exe -m pytest -q
```

`kedro run` ejecuta también `measurement_results`: lee el Parquet local sin
regenerarlo. Si no existe entrada, ejecutar explícitamente:

```powershell
../.venv/Scripts/python.exe -m kedro run --pipelines=synthetic_results
```

Este último comando genera datos artificiales y luego los analiza. **Sobrescribe
los datasets del generador sintético**; no se utiliza para datos físicos reservados.
La semilla `synthetic_data.random_seed: 20260101` controla dos flujos distintos
de ruido para DHT temperatura y humedad. Los antecedentes defectuosos del
generador existente se conservan como evidencia de entrada; el pipeline de
resultados los corrige en un dataset nuevo.

El entorno de verificación contiene Python 3.14.8, Kedro 1.5.0,
kedro-datasets 9.6.0, pandas 3.0.6, NumPy 2.5.3, Matplotlib 3.11.2 y
PyArrow 25.0.1. `requirements-results-lock.txt` registra el entorno utilizado
para estos pipelines y pruebas; no incluye las herramientas opcionales de
notebooks, Spark o visualización Kedro. Puede reproducirse en otro entorno
Python 3.14 con `python -m pip install -r docs/requirements-results-lock.txt`.

## Salidas

Todas las rutas siguientes son relativas a la raíz Kedro y se exportan por el catálogo.

| Dataset | Ruta | Contenido |
|---|---|---|
| `synthetic_final_data` | `data/03_primary/synthetic_final_data.parquet` | Entrada original local |
| `measurement_derived` | `data/04_feature/measurement_results/derived.parquet` | Identidad, coordenadas, calidad, segmentos, antecedentes originales/recalculados y diferencias |
| `measurement_audit` | `data/08_reporting/measurement_results/audit.json` | Procedencia, esquema, SHA-256, tamaño, fecha, intervalos, reglas, configuración, versiones y pendientes |
| `measurement_temporal` | `data/08_reporting/measurement_results/temporal.csv` | Estadísticos horarios por posición y superficie; conteo válido por variable |
| `measurement_coverage` | `data/08_reporting/measurement_results/coverage.csv` | Correspondencia identidad/posición/coordenadas y cobertura por variable |
| `measurement_spatial` | `data/08_reporting/measurement_results/spatial.csv` | Dispersión y amplitud entre puntos simultáneos por pared |
| `measurement_concordance` | `data/08_reporting/measurement_results/concordance.csv` | Diferencia simultánea DS menos DHT por posición |
| `measurement_psychrometrics` | `data/04_feature/measurement_results/psychrometrics.parquet` | W y estado de omisión o cálculo condicionado |
| `measurement_figures` | `data/08_reporting/measurement_results/figures/*.png` | Series por superficie y sensor, cobertura, faltantes, concordancia y mapas observados por pared |

El repositorio ignora `data/**`: las salidas están disponibles localmente pero no
se incorporan a Git. El informe de entrega versionable es este documento.

## Reglas y correspondencia metodológica

- `met:instrumentacion` y arquitectura de datos: se auditan identidad, formato,
  duplicados, valores no finitos, RH fuera de 0..100 % y límites térmicos solo si
  se configuran. No se inventa una ficha DHT11 ni una calibración.
- La clave nominal es `SURFACE, NODE_ID, SENSOR_POSITION`; `NODE_ID` nulo es
  admisible para `BACK_WALL`. Las coordenadas completan `POSITION_ID`.
  Una clave con varias coordenadas queda marcada como conflicto y sus
  posiciones se mantienen separadas. Los hashes de identidad son identificadores
  operacionales, no sustituyen un número de serie físico.
- Se conservan todas las filas, incluidos duplicados exactos y conflictivos.
  Todos los registros con tiempo duplicado en una posición se excluyen de los
  resúmenes, evitando escoger arbitrariamente una lectura. Cada variable
  inválida se enmascara en su análisis sin borrar el resto de la fila.
- Se ordena establemente antes del cálculo y se conservan los grupos nulos.
  El primer registro, un hueco mayor de 60 s, un cambio de posición/episodio
  o un tiempo duplicado corta antecedentes. `DT_SECONDS` informa el intervalo
  real aunque se corte el antecedente. `CONTINUOUS` significa pertenencia al
  mismo segmento operativo; `NOMINAL_INTERVAL` verifica separadamente los 20 s.
  `SEGMENT_ID` no es un lote experimental ni una réplica independiente.
- Las medias horarias son descriptivas, ponderadas por observación, y no se
  ofrecen como características causales de un predictor. La entrada ejecutada
  tiene muestreo regular. En una serie irregular se debe construir y verificar
  la agregación integral causal de `met:agregacion_causal` antes de usarla para
  predicción; el pipeline actual no genera ventanas predictivas.
- La cobertura divide observaciones válidas entre oportunidades nominales
  dentro del intervalo observado de cada posición. No estima disponibilidad
  fuera de ese intervalo, tiempos de encendido ni cobertura volumétrica.
  Una cadencia superior a la nominal puede producir una razón mayor de uno;
  no se oculta mediante truncamiento.
- `met:dispersion_espacial`: los puntos observados llevan pesos uniformes y
  desviación poblacional (`ddof=0`); amplitud y desviación mantienen las unidades
  originales. No se calcula coeficiente de variación en Celsius ni se interpreta
  el resultado como promedio de área, masa o volumen.
- DS menos DHT es concordancia, con desviación descriptiva muestral.
  No constituye exactitud de hardware. Los mapas muestran solo puntos de pared;
  no se interpolan ni se convierten X/Y en coordenadas globales 3D.
- El documento prescribe UTC para almacenamiento, pero los tiempos sintéticos
  disponibles no tienen zona. No se localizan automáticamente: confirmar el
  significado de la entrada antes de convertir a UTC/Panamá.
- `met:conversion_humedad`: RH se divide entre cien y se usa temperatura DHT.
  W se omite si faltan Celsius explícitos, compatibilidad térmica, presión positiva,
  procedencia o incertidumbre de presión. La opción implementada utiliza Magnus
  sobre agua líquida, `p_ws = 610.94 exp(17.625 T/(T+243.04))` Pa,
  exclusivamente entre 0 y 50 °C; `W = 0.62198 p_v/(p-p_v)` y `Y=W/(1+W)`.
  Esta correlación debe homologarse con las futuras implementaciones CFD/red/control.
  La incertidumbre de presión se conserva como metadato; no es una propagación
  de la incertidumbre de W. Para ello faltan incertidumbres y covarianzas conjuntas
  de T, RH y p. No se confunde W ni RH con humedad del café M.

## Interfaz opcional de contraste de modelos

`model_comparison` no pertenece al pipeline por defecto y
`model_comparison.enabled` permanece en `false`. No hay predicciones de
producción ni referencias independientes disponibles para ejecutarlo.

Entradas locales Parquet:

| Dataset | Ruta |
|---|---|
| `model_predictions` | `data/07_model_output/model_predictions.parquet` |
| `model_references` | `data/05_model_input/model_references.parquet` |

Ambas tablas necesitan `variable, position_id, episode, regime, timestamp, unit,
observation_operator, source_class`. `timestamp` es la hora objetivo observada,
con convenciones temporales iguales; `observation_operator` identifica un operador
versionado compatible según `met:operadores`. No se acepta unidad incompatible
ni desplazamiento de tiempo ajustado para mejorar correlación.

Las predicciones agregan `prediction, model, horizon_seconds, origin_timestamp`.
La diferencia entre origen y objetivo debe coincidir con el horizonte.
Las referencias agregan `reference, duration_seconds, independent,
used_for_development, reference_provenance`. Las duraciones deben ser positivas
y representar el soporte temporal puntuado; no deben atravesar huecos ni episodios.
`independent` y `used_for_development` son booleanos. El expediente debe respaldar
`independent=true` y `used_for_development=false`; el software no demuestra
independencia por sí mismo. Origen desconocido y claves duplicadas se rechazan.

La alineación es exacta por tiempo, variable, posición, episodio y régimen.
Se aplica una máscara válida común entre modelos del mismo horizonte.
Según `met:errores`, se calcula MAE, RMSE, MBE con error predicción menos referencia,
pesos por duración y cuantil ponderado 95 % del error absoluto. Se informa cobertura
por variable, sensor, episodio, régimen y horizonte. No se mezcla indiscriminadamente
un episodio largo con uno corto ni se calcula inferencia por número de registros.

Para habilitarlo, suministrar ambas entradas compatibles y configurar `enabled: true`:

```powershell
../.venv/Scripts/python.exe -m kedro run --pipelines=model_comparison
```

La salida es `data/08_reporting/measurement_results/model_metrics.csv`.
Cualquier fuente sintética mantiene la clasificación `synthetic_comparison`.
El contraste con referencia física independiente no demuestra conservación,
equivalencia ni utilidad en control.

`validate_window_supports` permite verificar una tabla
`trajectory_id, partition, support_start, support_end`: cada soporte cerrado
incluye toda historia y todos los objetivos de una muestra. Rechaza solapamientos
entre particiones de una trayectoria. Los sensores dependientes deben compartir
trayectoria. Esta comprobación no crea una partición ni garantiza que el modelo
o el preprocesamiento estén congelados. Según `met:particion`, la separación final
debe ser cronológica por episodios completos; la fracción aproximada 50/50 no
autoriza dividir arbitrariamente los tres días sintéticos en campañas independientes.
La purga conservadora requiere historia + horizonte en fronteras dentro de una serie.

## Ejecución verificada el 5 de octubre de 2026

La entrada local no estaba presente al comenzar. Se ejecutó el generador del
proyecto con semilla fija y se procesó su salida completa: **datos artificiales
del generador**, además de los fixtures pequeños de las pruebas.

- 466.560 filas, 36 sensores/posiciones; 1 de enero de 2026 00:00:00 a
  3 de enero de 2026 23:59:40, sin zona horaria asignada.
- Intervalos reales de 20 s; sin duplicados, conflicto de coordenadas,
  valores no finitos ni RH fuera de 0..100 % en este conjunto generado.
- 51.836 antecedentes recuperados en `BACK_WALL` **por variable**;
  el primer antecedente de cada sensor permanece nulo.
- 2.592 filas de resumen horario, 38.880 filas espaciales simultáneas,
  36 filas de cobertura y 36 de concordancia.
- Diferencia media descriptiva DS menos DHT: aproximadamente 1,49992 en la
  escala térmica de entrada, compatible con el desplazamiento programado de
  1,5. Esto verifica procesamiento, no desempeño metrológico.
- 12 figuras PNG exportadas: tres series por superficie, tres paneles de sensores,
  cobertura, faltantes, concordancia y tres mapas de pared.
- `pytest -q`: 8 pruebas aprobadas, incluyendo ejecución del pipeline Kedro.
  Los tests de comparación de modelos utilizan exclusivamente fixtures sintéticos.
- Entrada: 26.771.697 bytes, SHA-256
  `f2a65744deec8953d7bf8e06e95914e3c951d28407e831f78a6bb1cd75d37999`.
  El manifiesto JSON registra el hash de la metodología y las fechas reales.

## Requisitos pendientes

1. Mediciones físicas reservadas, lote/episodio, número de serie, firmware,
   estado de comunicación, hora de observación/recepción y posición vigente.
2. Confirmación de unidades y zona de los datos, correspondencia local/global
   de coordenadas, inventario y ficha de la variante DHT11, calibraciones e incertidumbre.
3. Presión compatible, su procedencia, temperatura DHT confirmada y presupuesto
   conjunto de incertidumbre para W. El cálculo de producción se omitió.
4. Predicciones CFD/cavidad/red/aprendizaje y referencias independientes con
   operadores versionados, episodios, posiciones, unidades, tiempo y horizonte.
5. Partición cronológica por episodios y campañas independientes, modelos y
   transformaciones congelados, márgenes físicos previos y análisis de dependencia
   de residuos para bootstrap por bloques/lotes y equivalencia. No se ha ejecutado
   inferencia ni TOST con los datos disponibles.
6. Para conservación, secado y control: humedad gravimétrica y masa del café,
   muestreo/retirada, caudales, irradiancia, presión, propiedades e inventarios,
   curvas de actuadores, potencia activa, señales de mando y escenarios comunes.
   La tabla actual no sustenta resultados de evaporación, balances ni control.

La metodología sí está disponible y se ha incorporado; lo pendiente es ejecutar
sus contrastes con las entradas y evidencia física correspondientes.
