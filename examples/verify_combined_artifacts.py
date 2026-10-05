"""Check study artifact integrity, timing readback and tensor validity.

This is packaging/sequence verification, not an acquired-signal closure audit.
Run after all experiments: python examples/verify_combined_artifacts.py
"""
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse import simulate


def main():
    data = ROOT / 'docs/data'
    counts = {'finite': 0, 'exact': 0, 'echoes': 0}
    maximum_group_error = 0.
    for name, model in [('finite.json', 'finite'), ('pathways.json', 'exact')]:
        for path in (ROOT / 'runs/combined_factor_study/cases').glob('*/' + name):
            rows = json.loads(path.read_text())
            assert len(rows) == rows[0]['etl'], path
            assert [r['echo'] for r in rows] == list(range(1, len(rows)+1)), path
            assert all(np.isfinite(r['total_abs']) for r in rows), path
            if model == 'exact':
                assert rows[0]['etl'] <= 8, path
                maximum_group_error = max(maximum_group_error, *(r['group_closure_abs'] for r in rows))
            counts[model] += 1
            counts['echoes'] += len(rows)
    assert maximum_group_error < 1e-12
    sequences = 0
    tensors = 0
    minimum_eigenvalue = float('inf')
    for folder in (ROOT / 'runs/combined_factor_study/sequences').glob('*'):
        if not (folder / 'seq.seq').exists():
            continue
        seq = simulate.read_seq(str(folder / 'seq.seq'))
        assert seq.check_timing()[0], folder
        settings = json.loads((folder / 'settings.json').read_text())
        assert settings['overrides']['scanner_version'] == '1.6'
        assert settings['overrides']['sim_train_crusher_scales'][0] == 1
        hardware = json.loads((folder / 'hardware.json').read_text())
        assert hardware['crusher_amplitudes_DAC'][0] == 2754, folder
        assert abs(hardware['TE_ms'] - 36.025) < 1e-5, folder
        assert abs(hardware['ESP_ms'] - 16) < 1e-5, folder
        assert abs(hardware['TR_s'] - 2) < 1e-8, folder
        payload = json.loads((folder / 'btensor.json').read_text())
        for echo in payload['echoes']:
            if echo['convention'] != 'sample':
                continue
            matrix = np.asarray(echo['B_s_mm2'])
            assert np.allclose(matrix, matrix.T, atol=1e-10), folder
            eigenvalue = float(np.linalg.eigvalsh(matrix).min())
            assert eigenvalue >= -1e-8, (folder, eigenvalue)
            minimum_eigenvalue = min(minimum_eigenvalue, eigenvalue)
            assert abs(np.trace(matrix) - echo['trace_s_mm2']) < 1e-9
            tensors += 1
        sequences += 1
    with (data / 'combined_summary_screen_tests.csv').open(newline='', encoding='utf-8') as stream:
        screen_tests = list(csv.DictReader(stream))
    assert len(screen_tests) == 41, len(screen_tests)
    errors = json.loads((data / 'combined_factor_errors.json').read_text())
    assert all(e['status'] == 'resolved_infrastructure' for e in errors)
    missing_links = []
    for path in [ROOT / 'docs/combined_factor_investigation.md',
                 ROOT / 'docs/research/combined_factor_execution.md']:
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            destination = (path.parent / target.split('#')[0]).resolve()
            if ('://' not in target and destination != (data / 'combined_verification.json').resolve()
                    and not destination.exists()):
                missing_links.append(str(path) + ': ' + target)
    assert not missing_links, missing_links
    prior = json.loads((data / 'combined_prior_reproduction.json').read_text())
    assert prior['passed'] and all(prior['prior_provenance_matches'].values())
    phantom = json.loads((data / 'combined_phantom_audit.json').read_text())
    assert phantom['image_sampling_qualified'] is False
    result = dict(counts=counts, generated_sequences_readback_timing_passed=sequences,
                  primary_tensor_samples=tensors, minimum_tensor_eigenvalue_s_mm2=minimum_eigenvalue,
                  arithmetic_component_sum_max_absolute=maximum_group_error,
                  component_sum_is_not_independent_signal_closure=True,
                  screened_configurations_with_complete_table=len(screen_tests),
                  missing_report_links=missing_links,
                  prior_reproduction_passed=True,
                  resolved_infrastructure_events=len(errors),
                  phantom_image_sampling_qualified=False,
                  regression_suite_last_observed_passes=31,
                  regression_suite_not_rerun_by_inventory=True,
                  environment=dict(python=platform.python_version(), platform=platform.platform(),
                      packages={p:importlib.metadata.version(p) for p in
                                ['numpy','scipy','matplotlib','pypulseq','MRzeroCore','torch']}),
                  final_current_scanner17_sha256=hashlib.sha256(
                      (ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.7.ppl').read_bytes()).hexdigest())
    (data / 'combined_verification.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
