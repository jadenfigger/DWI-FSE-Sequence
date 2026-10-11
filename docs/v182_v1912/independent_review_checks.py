"""One-pass independent final-byte probes; read-only for sequence inputs."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events
from dwfse.ppl.ledger import build_ledger
from examples import validate_v182_v1912 as gate

DOC = Path(__file__).parent
cases = []
for version, label, esp in [('1.82', 'v182', 11), ('1.912', 'v1912', 10)]:
    for name, model in gate.MODELS.items():
        source = ROOT / 'scanner' / f'FSE_dwi_CPMG_non_CPMG_twoTE-{version}.ppl'
        ppr = DOC / 'test_pprs' / f'{label}_nav2_3slices.ppr'
        # Minimum ESP at 25-us dwell, three slices, every recorded shot.
        if not ppr.exists():
            ppr = DOC / 'test_pprs' / f'{label}_manual_x0.8_slice_0mm.ppr'
        overrides = {'sample_period': 250, 'esp': esp, 'nav_on': 2,
                     'no_views': 153, 'no_disacq': 0, 'no_slices': 3,
                     'batch_slices': 3, 'fov_slice_off': [-1120, 0, 1120],
                     'r_angle_var': [0]*3, 'p_angle_var': [0]*3,
                     's_angle_var': [0]*3, 'slice_mm_10': 0, 'PE_order': 1}
        it = map_events(source, ppr, overrides=overrides, max_shots=6,
                        rf_latency_us=3, **model)
        ledger = build_ledger(it, 1)
        hazard = gate.hazard_summary(it, ledger)
        nav = gate.navigator_pe_audit(it)
        row = {'label': label, 'model': name, 'ppl_sha': hashlib.sha256(source.read_bytes()).hexdigest(),
               'rf': len(gate.rf_all(it)), 'adc': len(it.adc),
               'hazards': hazard, 'ledger_issues': ledger['issues'], 'nav': nav,
               'echo': gate.echo_metrics(it), 'prints': [s for _,s in it.out],
               'vars': {k: it.vars[k].value for k in ['tr_min','tacq','phase_correction'] if k in it.vars}}
        cases.append(row)
        print(label, name, 'RF',row['rf'],'ADC',row['adc'], hazard, flush=True)
result = {'cases': cases}
(DOC / 'independent_events.json').write_text(json.dumps(result, indent=2, default=gate.json_default))
