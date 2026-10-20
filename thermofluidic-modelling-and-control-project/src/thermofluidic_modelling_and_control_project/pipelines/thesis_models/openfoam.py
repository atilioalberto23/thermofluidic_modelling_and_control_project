"""Foundation 12 multicomponentFluid: local cases and controlled WSL runner.

Case dictionaries remain catalog-managed. Plant configuration is never inferred
from wall-local X/Y or from fan nameplate electrical power.
"""

import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time

import numpy as np
import pandas as pd

from .thermal import relative_humidity


def header(name, kind="dictionary"):
    return f'FoamFile {{ version 2.0; format ascii; class {kind}; object {name}; }}\n'


def field(name, kind, dimensions, initial, boundaries):
    return header(name, kind) + f"dimensions {dimensions};\ninternalField uniform {initial};\nboundaryField\n{{\n" + "\n".join(f"{patch} {{ {description} }}" for patch, description in boundaries.items()) + "\n}\n"


def create_openfoam_case(case, runtime):
    required = ["geometry", "initial", "patches", "species_properties", "transport_model", "sensor_map", "geometry_provenance", "boundary_provenance", "source_kind", "evaporation_model"]
    missing = [key for key in required if key not in case]
    if missing:
        raise ValueError(f"Missing CFD fields: {missing}")
    if runtime["version"] != "Foundation-12":
        raise ValueError("These dictionaries target the verified Foundation 12 distribution")
    geometry, initial = case["geometry"], case["initial"]
    identity_runtime = {k: v for k, v in runtime.items() if k not in {"execute", "case_directory", "timeout_seconds"}}
    digest = hashlib.sha256(json.dumps({"case": case, "runtime": identity_runtime}, sort_keys=True).encode()).hexdigest()[:20]
    case_id = "air_vapor_" + digest
    vertices = "\n".join("(" + " ".join(map(str, vertex)) + ")" for vertex in geometry["vertices"])
    cells = " ".join(map(str, geometry["cells"]))
    mesh_patches = []
    for patch, settings in case["patches"].items():
        faces = " ".join("(" + " ".join(map(str, face)) + ")" for face in settings["faces"])
        mesh_patches.append(f"{patch} {{ type {settings['mesh_type']}; faces ({faces}); }}")
    mesh = header("blockMeshDict") + f"convertToMeters 1;\nvertices ({vertices});\nblocks (hex (0 1 2 3 4 5 6 7) ({cells}) simpleGrading (1 1 1));\nedges ();\nboundary ({' '.join(mesh_patches)});\nmergePatchPairs ();\n"
    bundle = {f"{case_id}/system/blockMeshDict": mesh}
    for name, kind, dimensions, value in [("U", "volVectorField", "[0 1 -1 0 0 0 0]", "(" + " ".join(map(str, initial["velocity_m_s"])) + ")"), ("p", "volScalarField", "[1 -1 -2 0 0 0 0]", initial["pressure_pa"]), ("T", "volScalarField", "[0 0 0 1 0 0 0]", initial["temperature_k"]), ("H2O", "volScalarField", "[0 0 0 0 0 0 0]", initial["vapor_mass_fraction"]), ("air", "volScalarField", "[0 0 0 0 0 0 0]", 1 - initial["vapor_mass_fraction"])]:
        conditions = {patch: settings["fields"][name] for patch, settings in case["patches"].items()}
        bundle[f"{case_id}/0/{name}"] = field(name, kind, dimensions, value, conditions)
    bundle[f"{case_id}/constant/physicalProperties"] = header("physicalProperties") + 'thermoType { type heRhoThermo; mixture multicomponentMixture; transport const; thermo hConst; energy sensibleEnthalpy; equationOfState perfectGas; specie specie; }\nspecies (air H2O);\ndefaultSpecie air;\n' + case["species_properties"]
    bundle[f"{case_id}/constant/momentumTransport"] = header("momentumTransport") + "simulationType laminar;\n"
    bundle[f"{case_id}/constant/thermophysicalTransport"] = header("thermophysicalTransport") + "simulationType laminar;\nlaminar { model unityLewisFourier; }\n"
    bundle[f"{case_id}/constant/g"] = header("g", "uniformDimensionedVectorField") + "dimensions [0 1 -2 0 0 0 0]; value (0 0 -9.81);\n"
    bundle[f"{case_id}/system/controlDict"] = header("controlDict") + f"application foamRun; solver multicomponentFluid; startFrom startTime; startTime 0; stopAt endTime; endTime {case['end_seconds']}; deltaT {case['dt_seconds']}; writeControl timeStep; writeInterval {case['write_steps']}; writeFormat ascii; writePrecision 12; writeCompression off; timePrecision 10; runTimeModifiable false; adjustTimeStep false;\n"
    bundle[f"{case_id}/system/fvSchemes"] = header("fvSchemes") + "ddtSchemes { default Euler; } gradSchemes { default Gauss linear; } divSchemes { default none; div(phi,U) Gauss upwind; div(phid,p) Gauss upwind; div(phi,K) Gauss upwind; div(phi,Yi_h) Gauss upwind; div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear; } laplacianSchemes { default Gauss linear corrected; } interpolationSchemes { default linear; } snGradSchemes { default corrected; }\n"
    bundle[f"{case_id}/system/fvSolution"] = header("fvSolution") + 'solvers { "rho.*" { solver diagonal; } "p.*" { solver GAMG; smoother DICGaussSeidel; tolerance 1e-9; relTol 0; } "(U|h|Yi|air|H2O).*" { solver PBiCGStab; preconditioner DILU; tolerance 1e-10; relTol 0; } } PIMPLE { nOuterCorrectors 2; nCorrectors 2; nNonOrthogonalCorrectors 0; momentumPredictor yes; } relaxationFactors { equations { ".*" 1; } }\n'
    if case.get("fvModels"):
        bundle[f"{case_id}/constant/fvModels"] = header("fvModels") + case["fvModels"]
    if case["evaporation_model"] not in ["none_empty_chamber", "supplied_conservative_fvModel"]:
        raise ValueError("Coffee evaporation requires a supplied coupled mass/species/energy fvModel; never assume passive source")
    if case["evaporation_model"] == "supplied_conservative_fvModel" and not case.get("fvModels"):
        raise ValueError("Coupled fvModel dictionary missing")
    # Reversing openings must supply inletOutlet species/temperature conditions.
    bundle[f"{case_id}/manifest.json"] = {"run_id": digest, "case_id": case_id, "configuration": case, "runtime": runtime, "equations": "compressible continuity, momentum, mixture sensible enthalpy and air/H2O species; gravity; no reactions", "limitations": "laminar; unity Lewis diffusion; not justified for plant until regime/transport parameters supplied"}
    bundle[f"{case_id}/Allrun"] = "#!/usr/bin/env bash\nsource " + shlex.quote(runtime["installation"] + "/etc/bashrc") + "\nset -eo pipefail\ncd -- \"$(dirname -- \"$0\")\"\nblockMesh > log.blockMesh 2>&1\ncheckMesh > log.checkMesh 2>&1\nfoamRun > log.foamRun 2>&1\n"
    return bundle, case_id


def sensor_global_positions(sensor_map, frame):
    output = []
    for row in frame.itertuples():
        transform = sensor_map[row.SURFACE]
        global_point = np.asarray(transform["origin_m"]) + row.X * np.asarray(transform["axis_x"]) + row.Y * np.asarray(transform["axis_y"])
        output.append(global_point)
    return np.array(output)


def windows_to_wsl(path):
    resolved = Path(path).resolve()
    return "/mnt/" + resolved.drive[0].lower() + "/" + resolved.as_posix().split(":/", 1)[1]


def run_openfoam_cases(runtime):
    """Processes write only explicit catalog case directory; logs retained."""
    root = Path(runtime["case_directory"]).resolve()
    if not root.is_relative_to(Path.cwd().resolve()):
        raise ValueError("Case directory must remain inside Kedro workspace")
    rows = []
    names = json.loads((root / "inventory.json").read_text(encoding="utf-8"))
    active_cases = {Path(name).parts[0] for name in names if name.endswith("/manifest.json")}
    for manifest_path in root.glob("*/manifest.json"):
        if manifest_path.parent.name not in active_cases:
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        case = manifest_path.parent
        start = time.perf_counter()
        command = ["wsl", "-d", runtime["distribution"], "--", "bash", windows_to_wsl(case / "Allrun")]
        if not runtime["execute"]:
            rows.append({"run_id": manifest["run_id"], "case_id": manifest["case_id"], "status": "built_not_executed", "command": json.dumps(command), "reason": "runtime execute=false; use registered cfd_execute after case construction"})
            continue
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=runtime["timeout_seconds"], check=False)
            code, error = result.returncode, result.stdout + result.stderr
        except subprocess.TimeoutExpired as exc:
            code, error = -1, f"timeout: {exc}"
        (case / "log.orchestrator").write_text(error, encoding="utf-8")
        rows.append({"run_id": manifest["run_id"], "case_id": manifest["case_id"], "status": "executed" if code == 0 else "failed", "exit_code": code, "compute_seconds": time.perf_counter() - start, "command": json.dumps(command), "solver": runtime["version"], "source_kind": manifest["configuration"]["source_kind"], "log": str(case / "log.foamRun"), "error": error})
    return pd.DataFrame(rows)


def read_scalar_field(path, cells):
    text = path.read_text(encoding="utf-8")
    uniform = re.search(r"internalField\s+uniform\s+([-+\deE.]+)\s*;", text)
    if uniform:
        return np.full(cells, float(uniform.group(1)))
    values = re.search(r"internalField\s+nonuniform\s+List<scalar>\s+\d+\s*\((.*?)\)\s*;", text, re.S)
    if not values:
        raise ValueError(f"Unsupported scalar field format: {path}")
    return np.fromstring(values.group(1), sep=" ")


def extract_openfoam_outputs(runtime, runs=None):
    output = []
    for manifest_path in Path(runtime["case_directory"]).glob("*/manifest.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        case = manifest_path.parent
        if runs is not None and not ((runs.case_id == manifest["case_id"]) & runs.status.eq("executed")).any():
            continue
        shape = manifest["configuration"]["geometry"]["cells"]
        cells = int(np.prod(shape))
        for directory in case.iterdir():
            try:
                seconds = float(directory.name)
            except ValueError:
                continue
            if not all((directory / f).exists() for f in ["T", "p", "H2O"]):
                continue
            temperature = read_scalar_field(directory / "T", cells)
            pressure = read_scalar_field(directory / "p", cells)
            vapor = read_scalar_field(directory / "H2O", cells)
            ratio = vapor / (1 - vapor)
            rh = relative_humidity(temperature, ratio, pressure)
            # Cell ordering is retained; geometry-aware observation sampling is separate.
            frame = pd.DataFrame({"cell_index": np.arange(cells), "seconds": seconds, "T_K": temperature, "p_Pa": pressure, "Y": vapor, "W_kg_kg": ratio, "RH_fraction": rh})
            frame["case_id"] = manifest["case_id"]
            frame["run_id"] = manifest["run_id"]
            output.append(frame)
    return pd.concat(output, ignore_index=True) if output else pd.DataFrame(columns=["case_id", "run_id", "seconds", "T_K", "Y", "RH_fraction"])


def verification_case():
    """Explicit empty 3D chamber fixture, not the Coffee Solutions plant."""
    field_conditions = {"U": "type fixedValue; value uniform (0 0 0);", "p": "type fixedFluxPressure; value uniform 101325;", "T": "type fixedValue; value uniform 300;", "H2O": "type zeroGradient;", "air": "type zeroGradient;"}
    faces = {"left": [0, 4, 7, 3], "right": [1, 2, 6, 5], "front": [0, 1, 5, 4], "back": [3, 7, 6, 2], "bottom": [0, 3, 2, 1], "top": [4, 5, 6, 7]}
    patches = {name: {"mesh_type": "wall", "faces": [vertices], "fields": dict(field_conditions)} for name, vertices in faces.items()}
    patches["left"]["fields"]["T"] = "type fixedValue; value uniform 310;"
    species = "air { specie { molWeight 28.9596; } thermodynamics { Cp 1006; hf 0; } transport { mu 1.85e-5; Pr 0.71; } }\nH2O { specie { molWeight 18.0153; } thermodynamics { Cp 1860; hf 2501000; } transport { mu 1.0e-5; Pr 0.71; } }\n"
    return {"geometry": {"vertices": [[0,0,0], [.1,0,0], [.1,.1,0], [0,.1,0], [0,0,.1], [.1,0,.1], [.1,.1,.1], [0,.1,.1]], "cells": [4,4,4]}, "initial": {"temperature_k": 300., "pressure_pa": 101325., "velocity_m_s": [0.,0.,0.], "vapor_mass_fraction": .005}, "patches": patches, "species_properties": species, "transport_model": "laminar unity Lewis numerical fixture", "sensor_map": {}, "geometry_provenance": "0.1m cube software fixture", "boundary_provenance": "explicit thermal walls and sealed vapor fixture", "source_kind": "numerical_software_fixture", "evaporation_model": "none_empty_chamber", "end_seconds": .05, "dt_seconds": .001, "write_steps": 10}


def build_cases(plant, runtime):
    bundle, fixture_id = create_openfoam_case(verification_case(), runtime)
    if plant is not None:
        plant_bundle, _ = create_openfoam_case(plant, runtime)
        bundle.update(plant_bundle)
    bundle["plant_status.json"] = {"status": "case_built" if plant is not None else "missing_input", "missing_fields": [] if plant else ["global geometry and real openings", "sensor wall transformations and role", "time-aligned thermal/pressure/velocity/vapor boundary conditions", "properties and regimes", "coffee evaporation and conservative coupled fvModel", "numerical acceptance tolerances"]}
    return bundle
