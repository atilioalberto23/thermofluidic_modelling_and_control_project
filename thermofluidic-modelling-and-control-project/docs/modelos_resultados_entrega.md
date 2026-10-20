# Modelos y resultados locales: ejecución del 5 de octubre de 2026

Esta entrega amplía `resultados_kedro.md`: añade los productores de modelos,
entrenamiento, comparación y exportación científica exigidos en la instrucción
actualizada. Se leyeron `../instrucciones_codex_resultados_kedro.md`,
`../ch4_methodology (1).tex` y `../ch2_theoretical_framework(1).tex`.
Los catálogos usan archivos locales; no se requiere S3.

## Procedencia y alcance

El Parquet disponible tiene 466 560 filas, 36 posiciones, tres días y pasos de
20 s. Fue generado mediante el generador sintético del repositorio durante la
ejecución anterior; **no es una campaña experimental**, aunque se utilice el
alias de entrada de mediciones. SHA256:
`f2a65744deec8953d7bf8e06e95914e3c951d28407e831f78a6bb1cd75d37999`.
No se encontró un archivo original de mediciones físicas ni propiedades y
condiciones de contorno suficientes para identificar la planta.

Los nombres de columnas térmicas no certifican Celsius: el entrenamiento ML
conserva la escala nativa sin convertirla en kelvin. Red, PINN y OpenFOAM usan
kelvin explícitamente en casos numéricos independientes. RH, W y M permanecen
como cantidades diferentes. Los casos de software no constituyen validación
experimental de Coffee Solutions. Control permanece aplazado.

## Implementación y correspondencia matemática

Código en `src/thermofluidic_modelling_and_control_project/pipelines/thesis_models/`:

| Archivo / función | Modelo o contrato implementado |
| --- | --- |
| `learning.build_causal_targets` | Unión por tiempos exactos para historial y objetivos futuros; identidad/segmento, máscaras y purga temporal |
| `learning.train_temporal_models` | Persistencia, árbol de decisión, XGBoost y LightGBM reales; búsqueda interna rolling origin; transformador ajustado dentro de entrenamiento y persistido |
| `thermal.thermal_rhs` | Seis estados Tc,Tb,Tp,Ta,W,M; capacidades, convección/contacto, solar, radiosidad, GAB y cinética Arrhenius; mismo flujo de evaporación en agua y energía |
| `thermal.simulate_network` | Inventario general de aire seco y salida compatible; alternativa constante; integración Radau y balances integrales de agua/aire/energía |
| `thermal.identify_parameters` | Mínimos cuadrados acotados, operadores de observación, escalas y diagnóstico de rango/condicionamiento |
| `cavity.solve_cavity` | Corriente–vorticidad–temperatura; Poisson DST, condición de Thom, advección donor cell, difusión centrada y estabilidad explícita |
| `cavity.refinement_estimate` | Diagnóstico de refinamiento; rechaza conclusiones de orden/GCI ante secuencias no monótonas |
| `pinn.ConditionalPINN` / `residuals` | Flujo condicional con estado inicial exacto; diferenciación respecto de segundos y seis residuales usando el mismo RHS físico |
| `pinn.train_conditional_pinn` | Supervisión por máscaras, colocación física, selección por observaciones de validación, checkpoint y evaluación reservada |
| `enrichment.fit_discrepancy_model` | Corrección de discrepancia observable con predicciones físicas fuera del ajuste y selección interna |
| `enrichment.train_enriched_model` | Entrenamiento con pesos equilibrados por fuente y trayectoria; rechazo de generadores ajustados en prueba |
| `openfoam.create_openfoam_case` | Caso Foundation 12 multicomponentFluid: continuidad, momento, entalpía, aire/H2O, gravedad y transporte térmico |
| `openfoam.run_openfoam_cases` / `extract_openfoam_outputs` | blockMesh, checkMesh, solver WSL; logs reales y extracción T,p,Y,W,RH por celda |
| `comparison` | Soporte común, métricas temporales por sensor y agregado, bootstrap emparejado por bloques con sensibilidad de longitud |
| `reports` | Tablas locales Parquet/CSV/LaTeX, capítulo 01–10 y 12, figuras y manifiestos |

El catálogo `conf/base/catalog_thesis.yml` conecta todos los productores y
artefactos. `conf/base/parameters_thesis_models.yml` externaliza parámetros,
semillas, horizontes, tolerancias, presupuestos y procedencia. El entorno exacto
está en `docs/requirements-results-lock.txt`.

## Ejecuciones efectuadas

Se ejecutaron las ramas siguientes, además de la preparación descriptiva:

| Pipeline | Evidencia y resultado |
| --- | --- |
| `data_driven` | 12 artefactos algoritmo/horizonte, nueve con estimadores entrenados y tres marcadores de persistencia; 828 576 predicciones entre validación interna y bloque final; unos 31.6 s |
| `physics_verification` | Red de seis estados, comparación inventario general/constante, refinamiento de integración y recuperación de un coeficiente conocido |
| `thermal_network` | Contrato de entrada evaluado; ejecución de planta pendiente de campos físicos, detallados en `plant_network_status` |
| `cavity_2d` | Ra=10³ y 10⁴, Pr=.71, mallas 17/33/65, tres factores temporales y variante radiativa; once corridas convergieron según criterio configurado; unos 10.8 s |
| `physics_informed` | PINN condicional de seis estados, 300 épocas sobre referencias numéricas independientes; condición inicial exacta; evaluación numérica reservada, unos 6 s |
| `thesis_comparison` | Métricas y bootstrap exploratorio de 200 remuestreos, bloques 6/12/24 orígenes; la primera implementación completa tardó unos 226 s, después se eliminó un filtrado repetido |
| `enrichment` | Adaptador evaluado: faltan predicciones físicas OOF compatibles; funciones de peso y protección contra fuga comprobadas en pruebas |
| `cfd_openfoam,cfd_execute` | OpenFOAM Foundation 12 en Ubuntu WSL, cámara vacía 0.1 m, 64 celdas, 0.05 s, paso .001 s; mesh OK, solver terminó; unos 17.8 s |
| `thesis_results` | Exportación ejecutada desde datasets existentes; manifiestos por tabla, fuentes/versiones/parámetros, capítulo y figuras |

OpenFOAM: run/case `7447aeda307eaea132e0` / `air_vapor_7447aeda307eaea132e0`.
Los logs permanecen en `data/07_model_output/openfoam/<case>/log.*`.
El solver de presión alcanzó repetidamente su límite de iteraciones:
**terminar el proceso no certifica convergencia numérica ni validación**.
Se corrigieron saltos CRLF del script WSL, orden de inicialización de bashrc,
extracción de ejecuciones fallidas y tipos de identidad en la exportación.

Para 1200 s, RMSE en bloque final del archivo sintético:

| Modelo | DS temperatura, escala nativa | DHT temperatura, escala nativa | RH, puntos porcentuales |
| --- | ---: | ---: | ---: |
| Persistencia | 0.375805 | 0.400944 | 1.852344 |
| Árbol | 0.286190 | 0.303265 | 1.172541 |
| XGBoost | 0.176456 | 0.201382 | 1.062235 |
| LightGBM | 0.175835 | 0.202021 | 1.064741 |

Estas cifras comparan predicciones directas de observables en un soporte común.
No son comparación de los seis estados físicos ni equivalencia experimental.
No se fijaron márgenes de aceptación después de observar errores.

## Dónde están los modelos y salidas

- `data/06_models/data_driven/`: `.pkl` por algoritmo/horizonte, con codificador,
  lista de entradas y estimadores por variable; `run.json`.
- `data/06_models/pinn_verification/`: checkpoint y configuración del PINN numérico.
- `data/07_model_output/thesis/`: ventanas, predicciones, búsqueda, costos,
  métricas, intervalos y estados de disponibilidad de planta.
- `data/07_model_output/network_verification/`: estados, flujos, balances,
  identificación numérica y metadata.
- `data/07_model_output/cavity_2d/`: campos, historias y metadata de las corridas.
- `data/08_reporting/thesis_results/`: `structured/`, `csv/`, `figures/`,
  `tex/tables/`, `tex/resultados_tablas.tex`, `tex/resultados_documento.tex`,
  `results_manifest.*`, `model_execution_manifest.*`, `execution_provenance.json`.

Las tablas ausentes no tienen filas inventadas ni referencias LaTeX colgantes.
La verificación de sintaxis de referencias puede ejecutarse localmente; la
compilación PDF requiere instalar o proporcionar un motor LaTeX disponible.
Las tablas completas conservan columnas de trazabilidad: algunas necesitan una
selección editorial de columnas para la versión impresa.

## Comandos reproducibles

Desde la raíz Kedro, con el entorno ya instalado:

```powershell
$env:KEDRO_DISABLE_TELEMETRY = '1'
$env:MPLCONFIGDIR = Join-Path (Get-Location) '.mplconfig'
../.venv/Scripts/python.exe -m kedro run --pipelines=thesis_data
../.venv/Scripts/python.exe -m kedro run --pipelines=data_driven
../.venv/Scripts/python.exe -m kedro run --pipelines=physics_verification,cavity_2d,physics_informed,thermal_network,enrichment
../.venv/Scripts/python.exe -m kedro run --pipelines=thesis_comparison
../.venv/Scripts/python.exe -m kedro run --pipelines=cfd_openfoam,cfd_execute --params=openfoam.execute=true
../.venv/Scripts/python.exe -m kedro run --pipelines=thesis_results
$env:PYTHONPATH = 'src'
../.venv/Scripts/python.exe -m pytest -q
```

También está registrado `thesis_models`, que integra las ramas. Para ejecutar
OpenFOAM en esa corrida debe habilitarse `openfoam.execute=true`; con false
construye casos y marca explícitamente no ejecutado. No se ejecutó el comando
integrado completo: se ejecutaron las ramas anteriores por separado.
`kedro run` por defecto conserva la preparación descriptiva, sin regenerar datos.

## Requisitos pendientes y límites de implementación

Los JSON físicos son opcionales para permitir ramas independientes, pero un
archivo presente e inválido produce error. No deben rellenarse con números de
software para representar la planta.

| Entrada local | Campos necesarios |
| --- | --- |
| Archivo experimental original | Ruta/identidad, unidades y timezone, episodios/lotes, instrumentación, calibraciones y referencia independiente |
| `data/01_raw/physics/network_case.json` | `parameters` físicos con procedencia; `boundaries` con segundos,T ambiente,W ambiente,p,irradiancia,caudal,T cielo; seis estados iniciales; operadores, observaciones independientes e identification_fit_partition=development si se identifican parámetros |
| `data/01_raw/physics/pinn_case.json` | `parameters`, `samples` train/validation/test con seconds,initial,boundary,target,mask; normalization,normalization_fit_partition,physical_parameters_fit_partition; supports sin solapamiento; provenance,task_id y estados no observados con priors documentados |
| `data/01_raw/physics/cfd_case.json` | Vértices/global geometry, celdas, aperturas reales, campos de frontera con unidades y tiempos, propiedades de especies, régimen/transporte, estados iniciales, transformaciones de sensores y `fvModels` conservativo si hay café |
| `data/01_raw/physics/enrichment_case.json` | train/validation/test causal; `physical_prediction` fuera del ajuste, `base_out_of_fit`; features/target/operador; trayectorias numerical con trajectory_id y generator_fit_partition=development |
| Calibración y caracterización | Materiales/espesores/propiedades, masa seca y gravimetría, geometría medida, radiación/meteorología, caudal/perfiles/áreas y potencia activa del ventilador |

Además de los datos, quedan extensiones de código/verificación para alcanzar
todo el alcance científico de la instrucción:

- Red: integración actual a presión constante y en segmentos sin eventos;
  completar reinitialización por retiro de muestras/inventario y reversión;
  perfiles/correlación de identificabilidad multiparamétrica. El contraste
  Radau–BDF y el refinamiento temporal sí se ejecutaron sobre el caso numérico.
- CFD: el adaptador acepta un `fvModels` conservativo suministrado, pero no
  implementa por sí solo un modelo dinámico de café acoplado; faltan generación
  y verificación de ese acoplamiento, tres mallas/pasos, balances de frontera,
  muestreo geométrico y reducción termodinámica compatibles con la planta.
- Cavidad: faltan cifras de la tabla de referencia primaria de de Vahl Davis;
  no se atribuyen errores de benchmark ni GCI a la secuencia no monótona;
  Ra=10⁵ y 10⁶ quedan para presupuesto y refinamiento adicionales.
- PINN: faltan contraste experimental, priors iniciales no observados y pruebas
  de restricciones físicas completas fuera de los casos numéricos usados.
- ML: el camino actual utiliza bloques operativos cronológicos; la asignación
  íntegra por lotes/episodios documentados requiere conectar esa metadata y
  ampliar su adaptador. No se interpreta SEGMENT_ID como lote experimental.
- Híbridos: faltan generadores físicos ajustados dentro de folds, predicciones
  OOF y ablaciones sobre las mismas observaciones físicas independientes.
- Inferencia: el bootstrap es exploratorio; no se declaró estacionariedad ni
  equivalencia. Hacen falta episodios independientes y márgenes previos.
- Exportación: PDF no compilado en este entorno; queda validación con el motor
  y preámbulo de la tesis, además de selección editorial de tablas anchas.

Pruebas ejecutadas: 15 pasaron en el conjunto completo y una prueba adicional
de exportación pasó después. Las 24 referencias LaTeX existentes apuntan a
archivos presentes; el manifiesto contiene 24 tablas ready y 14 missing_input.
Las pruebas incluyen identidad/antecedentes, psicrometría,
comparación compatible, pipeline aislado, exactitud de objetivos futuros,
purga, Poisson, RHS NumPy/Torch, condición inicial PINN, seis gradientes,
reciprocidad, asignación solar y protección contra fuga en enriquecimiento.
Estos controles verifican software; no sustituyen los contrastes físicos
pendientes listados arriba.
