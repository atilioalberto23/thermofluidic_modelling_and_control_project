"""Export contracts: no dangling LaTeX inputs, figures and exact parameters."""
import pandas as pd
from thermofluidic_modelling_and_control_project.pipelines.thesis_models.reports import render_results


def test_export_has_only_existing_inputs_and_missing_requirements():
    costs = pd.DataFrame([{'run_id':'fixture-run', 'model_id':'persistence', 'horizon_seconds':20}])
    tables = {'tab_s01_geometria': pd.DataFrame([{'component':'wall_1', 'width':1., 'source_kind':'synthetic'}])}
    audit = {'source':{'sha256':'fixture-hash'}, 'source_class':'synthetic'}
    output = render_results(tables, costs, audit, {'seed':7})
    chapter = output['tex/resultados_tablas.tex']
    inputs = [line[len('\\input{'):-1] for line in chapter.splitlines() if line.startswith('\\input{')]
    assert inputs == ['tables/tab_s01_geometria.tex']
    assert all('tex/'+item in output for item in inputs)
    manifest = output['results_manifest.csv']
    assert manifest.loc[manifest.table_id.eq('tab_s01_geometria'), 'status'].iloc[0] == 'ready'
    missing = manifest.loc[manifest.table_id.eq('tab_s01_materiales')].iloc[0]
    assert missing.status == 'missing_input' and 'density' in missing.reason
    assert output['execution_provenance.json']['parameters'] == {'seed':7}
    assert 'tab_s11_' not in chapter
