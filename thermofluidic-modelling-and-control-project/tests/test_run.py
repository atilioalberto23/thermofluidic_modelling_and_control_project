"""
This module contains example tests for a Kedro project.
Tests should be placed in ``src/tests``, in modules that mirror your
project's structure, and in files named test_*.py.
"""
from pathlib import Path
import shutil
import yaml

from kedro.framework.session import KedroSession
from kedro.framework.startup import bootstrap_project

# The tests below are here for the demonstration purpose
# and should be replaced with the ones testing the project
# functionality

class TestKedroRun:
    def test_kedro_run(self, tmp_path, monkeypatch):
        """Run the full graph with a small synthetic fixture, in isolation."""
        project = Path.cwd()
        shutil.copy(project / "pyproject.toml", tmp_path / "pyproject.toml")
        shutil.copytree(project / "conf", tmp_path / "conf")
        shutil.copytree(project / "src", tmp_path / "src")
        parameters_path = tmp_path / "conf/base/parameters.yml"
        parameters = yaml.safe_load(parameters_path.read_text(encoding="utf-8"))
        parameters["synthetic_data"]["timing"]["simulation_days"] = 0.001
        parameters_path.write_text(yaml.safe_dump(parameters), encoding="utf-8")
        results_path = tmp_path / "conf/base/parameters_measurement_results.yml"
        parameters = yaml.safe_load(results_path.read_text(encoding="utf-8"))
        parameters["measurement_results"]["methodology_path"] = str(project.parent / "ch4_methodology (1).tex")
        parameters["measurement_results"]["execution_label"] = "synthetic software fixture"
        results_path.write_text(yaml.safe_dump(parameters), encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        bootstrap_project(tmp_path)
        with KedroSession.create(project_path=tmp_path) as session:
            assert session.run(pipeline_name="synthetic_results") is not None
        assert (tmp_path / "data/08_reporting/measurement_results/audit.json").exists()
        assert len(list((tmp_path / "data/08_reporting/measurement_results/figures").glob("*.png"))) == 12
