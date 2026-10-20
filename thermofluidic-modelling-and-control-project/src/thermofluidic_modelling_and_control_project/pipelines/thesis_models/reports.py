"""Scientific tables from actual executions; unavailable tables have no fake rows."""

import hashlib
import importlib.metadata
import json
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd

SECTIONS = {
    "01": "Caracterización de la planta, los materiales y la carga de café",
    "02": "Desempeño metrológico y operativo de la plataforma de sensado",
    "03": "Caracterización experimental y meteorológica del secado",
    "04": "Caracterización de actuadores y distribución del flujo",
    "05": "Verificación y resultados del modelo CFD tridimensional",
    "06": "Verificación y resultados del modelo bidimensional",
    "07": "Identificación y resultados de la red térmica reducida",
    "08": "Validación experimental de los modelos físicos",
    "09": "Desempeño predictivo de los modelos basados en datos",
    "10": "Efecto del enriquecimiento físico--basado en datos",
    "12": "Comparación integrada y alcance de los resultados",
}
EXPECTED = {
    "01": ["geometria", "materiales", "carga_cafe"],
    "02": ["inventario_sensores", "calibracion", "operacion_adquisicion"],
    "03": ["episodios", "condiciones_termohigrometricas", "meteorologia_radiacion", "secado_observado"],
    "04": ["actuadores_modos", "caudal_punto_operacion", "distribucion_uniformidad"],
    "05": ["discretizacion_convergencia", "refinamiento_cantidades", "campos_balances"],
    "06": ["benchmark_cavidad", "acoplamiento_radiativo"],
    "07": ["parametros_identificados", "transitorios_red", "proyeccion_y_reduccion", "inventario_y_cierres"],
    "08": ["validacion_por_variable", "equivalencia_criterios", "cobertura_validacion"],
    "09": ["modelos_configuracion", "errores_predictivos", "incertidumbre_costo", "pinn_fisica_y_entrenamiento"],
    "10": ["fuentes_y_ponderaciones", "ablaciones", "mejora_y_detencion"],
    "12": ["comparacion_integrada", "alcance_limitaciones"],
}
MISSING = {
    "materiales": "material, density, Cp, k, thickness, optical bands, uncertainty and sources",
    "carga_cafe": "lot, processing, dry coffee mass, gravimetry, bed area/thickness",
    "calibracion": "independent calibrated reference, dates, uncertainty and compatible sensor pairs",
    "meteorologia_radiacion": "ambient T/RH/p, irradiance, wind, position/time and instrument metadata",
    "secado_observado": "product gravimetry, dry mass, sample withdrawals and measurement dates",
    "caudal_punto_operacion": "normal velocities, represented areas, pressure, air state and active fan power",
    "refinamiento_cantidades": "three compatible CFD grids and steps with converged plant quantities",
    "proyeccion_y_reduccion": "compatible CFD and network plant cases and thermodynamic projection",
    "validacion_por_variable": "independent physical observations, parameters, boundaries and observation operators",
    "equivalencia_criterios": "prior physical margins, independent episodes and residual dependence/uncertainty",
    "cobertura_validacion": "physical independent campaign, lots, regimes and metrological metadata",
    "fuentes_y_ponderaciones": "physical trajectories mapped to common task and development-only generator fitting",
    "ablaciones": "independent measured targets and compatible baseline/enriched runs",
    "mejora_y_detencion": "paired baseline/enriched predictions, development stopping criteria and numerical verification",
}


def build_section_tables(data, coverage, concordance, temporal, spatial, metrics, costs, intervals, cavity, refinement, network_bundle, network_comparison, plant_status, pinn_metrics, pinn_history, enrichment_status, foam_runs, foam_fields, audit, config):
    tables = {}
    source = audit["source_class"]
    tables["tab_s02_inventario_sensores"] = coverage.copy()
    tables["tab_s02_operacion_adquisicion"] = coverage.copy()
    intervals_by_sensor = data.groupby("POSITION_ID").DT_SECONDS.agg(["median", "max", "count"]).reset_index()
    coverage = coverage.copy()
    coverage["POSITION_ID"] = coverage["POSITION_ID"].astype(str)
    intervals_by_sensor["POSITION_ID"] = intervals_by_sensor["POSITION_ID"].astype(str)
    tables["tab_s02_operacion_adquisicion"] = coverage.merge(intervals_by_sensor, on="POSITION_ID", validate="one_to_one")
    tables["tab_s02_concordancia_ds_dht"] = concordance.copy()
    tables["tab_s03_condiciones_termohigrometricas"] = temporal.copy()
    tables["tab_s03_episodios"] = data.groupby("SEGMENT_ID").agg(start=("TIMESTAMP", "min"), end=("TIMESTAMP", "max"), rows=("SOURCE_ROW", "count")).reset_index()
    tables["tab_s03_episodios"]["definition"] = "operational temporal block, not documented experimental lot"
    tables["tab_s04_distribucion_uniformidad"] = spatial.groupby("SURFACE").agg(DS_sigma_mean=("DS_TEMPERATURE_std", "mean"), DS_amplitude_max=("DS_TEMPERATURE_amplitude", "max"), RH_sigma_mean=("DHT_HUMIDITY_std", "mean"), RH_amplitude_max=("DHT_HUMIDITY_amplitude", "max")).reset_index()
    tables["tab_s04_distribucion_uniformidad"]["weighting"] = "uniform observed sensors; no area/mass weights"
    tables["tab_s09_modelos_configuracion"] = costs[["model_id", "horizon_seconds", "selected_parameters", "N_train", "N_test", "history_seconds", "strategy", "source_kind", "run_id"]].copy()
    tables["tab_s09_errores_predictivos"] = metrics.copy()
    tables["tab_s09_incertidumbre_costo"] = costs.copy()
    tables["tab_s09_intervalos_emparejados"] = intervals.copy()
    tables["tab_s09_pinn_fisica_y_entrenamiento"] = pinn_metrics.copy()
    tables["tab_s06_benchmark_cavidad"] = cavity.loc[~cavity.radiation].copy()
    tables["tab_s06_acoplamiento_radiativo"] = cavity.loc[cavity.radiation].copy()
    tables["tab_s06_refinamiento"] = refinement.copy()
    # These network tables explicitly describe the numerical fixture execution.
    tables["tab_s07_parametros_identificados"] = network_bundle["parameter_recovery.csv"].copy()
    state_summary = network_bundle["states.parquet"].drop(columns="seconds").agg(["min", "max", "mean"]).T.reset_index(names="state")
    state_summary["source_kind"] = "synthetic_software_fixture"
    tables["tab_s07_transitorios_red"] = state_summary
    tables["tab_s07_inventario_y_cierres"] = network_comparison.copy()
    balances = network_bundle["balances.parquet"].drop(columns="seconds").abs().max().reset_index()
    balances.columns = ["quantity", "maximum_absolute_value"]
    balances["source_kind"] = "synthetic_software_fixture"
    tables["tab_s07_balances_verificacion"] = balances
    if not foam_runs.empty and foam_runs.status.eq("executed").any():
        tables["tab_s05_discretizacion_convergencia"] = foam_runs.loc[foam_runs.status.eq("executed")].copy()
    if not foam_fields.empty:
        tables["tab_s05_campos_balances"] = foam_fields.groupby(["case_id", "run_id", "seconds"]).agg(T_mean_K=("T_K", "mean"), T_max_K=("T_K", "max"), W_mean_kg_kg=("W_kg_kg", "mean"), Y_mean=("Y", "mean"), RH_mean_fraction=("RH_fraction", "mean")).reset_index()
        tables["tab_s05_campos_balances"]["interpretation"] = "empty 3D numerical fixture; full boundary energy flux and plant balances not yet contrasted"
    geometry = []
    for surface, properties in config["synthetic_data"]["geometry"]["surfaces"].items():
        geometry.append({"component": surface, "width": properties["width"], "height": properties["height"], "area_in_coordinate_units_squared": properties["width"] * properties["height"], "source": "repository synthetic generator geometry, not a new measured plant survey", "unit": "coordinate unit unconfirmed"})
    tables["tab_s01_geometria"] = pd.DataFrame(geometry)
    # Plate values are supplied explicitly in the methodology; no inferred airflow.
    tables["tab_s04_actuadores_modos"] = pd.DataFrame(config["nameplate"])
    tables["tab_s04_actuadores_modos"]["voltage_V"] = tables["tab_s04_actuadores_modos"]["voltage_V"].astype(str)
    integrated = metrics.loc[metrics.fold_id.eq("test")].copy()
    integrated["information_mode"] = "history only, direct forecasting"
    integrated["balance_scope"] = "observables only; not full-state water/energy conservation"
    integrated["spatial_scope"] = "individual measured sensor positions"
    tables["tab_s12_comparacion_integrada"] = integrated
    limitations = [{"approach": "ML", "evidence": "trained and final-block scored on existing local generated input", "source_kind": source, "limitation": config["learning"]["source_discrepancy"]}, {"approach": "network", "evidence": "six-state numerical fixture and single known-coefficient recovery", "source_kind": "numerical_verification", "limitation": plant_status.missing_fields.iloc[0] if "missing_fields" in plant_status else "plant parameters/boundaries require independent validation"}, {"approach": "cavity", "evidence": "stationary solutions, three spatial grids and three temporal factors", "source_kind": "numerical_verification", "limitation": "spatial refinement not assumed monotone; primary benchmark numerical table pending"}, {"approach": "PINN", "evidence": "conditional six-state training and held-out numerical references", "source_kind": "numerical_verification", "limitation": "experimental initial states, observation masks and physical coefficients unavailable"}, {"approach": "hybrid", "evidence": "discrepancy and source/trajectory-weighted enrichment code", "source_kind": "not_executed_on_plant", "limitation": enrichment_status.missing_fields.iloc[0] if "missing_fields" in enrichment_status else "see explicit execution"}, {"approach": "CFD", "evidence": "Foundation 12 multicomponent case and retained mesh/solver logs", "source_kind": "numerical_verification", "limitation": "global plant geometry, real openings, boundary time series, coffee coupling and compatible sensors pending"}]
    tables["tab_s12_alcance_limitaciones"] = pd.DataFrame(limitations)
    for name, frame in tables.items():
        if "source_kind" not in frame:
            frame["source_kind"] = "numerical_verification" if name.startswith(("tab_s05", "tab_s06", "tab_s07")) else source
    return tables


def render_results(tables, costs, audit, config):
    bundle, manifest, executions = {}, [], []
    code_files = sorted(Path(__file__).parent.glob("*.py"))
    code_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in code_files}
    versions = {name: importlib.metadata.version(name) for name in ["kedro", "numpy", "pandas", "scipy", "scikit-learn", "xgboost", "lightgbm", "torch"]}
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()
    bundle["execution_provenance.json"] = {"parameters": config, "parameters_sha256": config_hash, "implementation_sha256": code_hashes, "versions": versions, "measurement_audit": audit}
    expected = {f"tab_s{s}_{suffix}" for s, suffixes in EXPECTED.items() for suffix in suffixes}
    for name in sorted(expected | set(tables)):
        section = name[5:7]
        frame = tables.get(name)
        record = {"section_id": section, "section_title": SECTIONS[section], "table_id": name, "node_name": "build_section_tables", "source_input_sha256": audit["source"].get("sha256"), "source_kind": audit["source_class"], "rows": 0, "status": "missing_input", "reason": MISSING.get(name[8:], "required compatible producer/input not executed"), "structured_path": None, "csv_path": None, "latex_path": None}
        if frame is not None and not frame.empty:
            csv_path, parquet_path, tex_path = f"csv/{name}.csv", f"structured/{name}.parquet", f"tex/tables/{name}.tex"
            bundle[csv_path], bundle[parquet_path] = frame, frame
            caption = SECTIONS[section] + ": " + name[8:].replace("_", " ")
            latex = frame.to_latex(index=False, escape=True, longtable=True, na_rep="--", float_format=lambda value: f"{value:.5g}", caption=caption, label="tab:res_" + name[4:])
            note = "% Generated from executed datasets. Source/weighting/split preserved in CSV and structured table. Numerical fixtures are not experimental validation.\n"
            bundle[tex_path] = note + "\\begingroup\n\\scriptsize\n" + latex + "\\endgroup\n"
            record.update(rows=len(frame), status="ready", reason=None, structured_path=parquet_path, csv_path=csv_path, latex_path=tex_path, source_kind=";".join(frame.source_kind.dropna().astype(str).unique()) if "source_kind" in frame else audit["source_class"])
        record["parameters_sha256"] = config_hash
        record["input_catalog_keys"] = json.dumps({"05": ["openfoam_runs", "openfoam_fields"], "06": ["cavity_summary", "cavity_refinement"], "07": ["network_verification_artifacts", "network_verification_comparison"], "09": ["thesis_prediction_metrics", "temporal_costs", "thesis_paired_intervals", "pinn_verification_metrics"]}.get(section, ["measurement_derived", "measurement_audit", "parameters"]))
        record["units"] = json.dumps(frame.unit.dropna().astype(str).unique().tolist()) if frame is not None and "unit" in frame else "see column suffixes and execution_provenance.json; source temperature scale remains unconfirmed"
        record["weighting"] = ";".join(frame.weighting.dropna().astype(str).unique()) if frame is not None and "weighting" in frame else "see table and producer contract"
        record["split"] = json.dumps(frame.fold_id.dropna().astype(str).unique().tolist()) if frame is not None and "fold_id" in frame else "not_applicable_or_numerical_verification"
        record["run_ids"] = json.dumps(frame.run_id.dropna().astype(str).unique().tolist()) if frame is not None and "run_id" in frame else json.dumps(costs.run_id.unique().tolist()) if section == "09" else "see producer bundle run.json and configuration hashes"
        manifest.append(record)
    chapter = ["\\chapter{Resultados}\n\\label{ch:resultados}\n", "% Sources and pending requirements: results_manifest.csv and model_execution_manifest.csv.\n"]
    for section, title in SECTIONS.items():
        chapter.append("\\section{" + title + "}\n")
        for row in manifest:
            if row["section_id"] == section and row["status"] == "ready":
                chapter.append("\\input{tables/" + row["table_id"] + ".tex}\n")
    bundle["tex/resultados_tablas.tex"] = "\n".join(chapter)
    bundle["tex/resultados_documento.tex"] = "\\documentclass{report}\n\\usepackage[T1]{fontenc}\n\\usepackage[utf8]{inputenc}\n\\usepackage{booktabs,longtable,array}\n\\usepackage[a4paper,landscape,margin=1cm]{geometry}\n\\begin{document}\n\\input{resultados_tablas.tex}\n\\end{document}\n"
    bundle["results_manifest.csv"] = pd.DataFrame(manifest)
    bundle["results_manifest.parquet"] = pd.DataFrame(manifest)
    for row in costs.to_dict("records"):
        executions.append({**row, "pipeline": "data_driven", "implementation_status": "implemented", "execution_status": "executed", "task_id": "direct_sensor_forecast", "equations": "eq:prediccion_arbol; eq:gradient_boosting; eq:objetivo_xgboost", "models_path": "data/06_models/data_driven", "predictions_path": "data/07_model_output/thesis/temporal_predictions.parquet", "test_interpretation": "chronological purged final block; current source synthetic, not experimental campaign"})
    for model, table, path in [
        ("network_verification", "tab_s07_transitorios_red", "data/07_model_output/network_verification"),
        ("cavity_2d", "tab_s06_benchmark_cavidad", "data/07_model_output/cavity_2d"),
        ("conditional_pinn_verification", "tab_s09_pinn_fisica_y_entrenamiento", "data/06_models/pinn_verification"),
        ("openfoam_verification", "tab_s05_discretizacion_convergencia", "data/07_model_output/openfoam"),
    ]:
        frame = tables.get(table)
        executions.append({"model_id": model, "pipeline": model, "implementation_status": "implemented", "execution_status": "executed" if frame is not None and not frame.empty else "not_executed", "source_kind": "numerical_verification", "models_path": path, "evidence_table": table, "test_interpretation": "software numerical verification; independent plant validation pending"})
    for model, input_path in [("plant_network", "network_case.json"), ("plant_conditional_pinn", "pinn_case.json"), ("hybrid_enrichment", "enrichment_case.json"), ("plant_cfd", "cfd_case.json")]:
        executions.append({"model_id": model, "implementation_status": "adapter_implemented", "execution_status": "plant_not_validated", "required_input": "data/01_raw/physics/" + input_path, "test_interpretation": "inspect producer status; plant inputs and independent observations required"})
    bundle["model_execution_manifest.csv"] = pd.DataFrame(executions)
    bundle["model_execution_manifest.parquet"] = pd.DataFrame(executions)
    # Scientific plots derived exclusively from executed output tables.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures = []
    def save_figure(fig, name, source_table):
        buffer = BytesIO()
        fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
        plt.close(fig)
        bundle[f"figures/{name}.png"] = buffer.getvalue()
        figures.append({"figure_id": name, "path": f"figures/{name}.png", "source_table": source_table, "scope": "current local synthetic input or numerical verification; not experimental validation"})
    frame = tables.get("tab_s09_errores_predictivos")
    if frame is not None:
        final = frame.loc[frame.fold_id.eq("test")]
        variables = final.variable.unique()
        fig, axes = plt.subplots(1, len(variables), figsize=(14, 4), squeeze=False)
        for ax, variable in zip(axes[0], variables):
            for model, group in final.loc[final.variable.eq(variable)].groupby("model_id"):
                group = group.sort_values("horizon_seconds")
                ax.plot(group.horizon_seconds, group.RMSE, "o-", label=model)
            ax.set(title=str(variable), xlabel="Horizonte (s)", ylabel="RMSE, unidad nativa")
            ax.grid(alpha=.25)
        axes[0][-1].legend()
        fig.suptitle("Bloque final local: fuente sintética")
        save_figure(fig, "errores_por_horizonte", "tab_s09_errores_predictivos")
    frame = tables.get("tab_s06_benchmark_cavidad")
    if frame is not None:
        fig, ax = plt.subplots()
        for ra, group in frame.groupby("Ra"):
            grid_column = "grid_points"
            nu_column = "Nu_hot" if "Nu_hot" in group else "Nu_hot_mean"
            if grid_column in group and nu_column in group:
                ax.plot(group[grid_column], group[nu_column], "o", label=f"Ra={ra:g}")
        ax.set(xlabel="Puntos por lado", ylabel="Nu pared caliente", title="Cavidad: refinamiento numérico")
        if ax.lines:
            ax.legend()
            save_figure(fig, "refinamiento_cavidad", "tab_s06_benchmark_cavidad")
        else:
            plt.close(fig)
    bundle["figure_manifest.csv"] = pd.DataFrame(figures)
    bundle["README.txt"] = "Compile from this bundle's tex directory: pdflatex resultados_documento.tex. Integrate resultados_tablas.tex with tables/ alongside it. No section 11 (control). All absent tables are listed only in results_manifest; no dangling input references. Wide tables may require editorial column selection for the final thesis layout.\n"
    return bundle
