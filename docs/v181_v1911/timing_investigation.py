"""Additive baseline timing audit; does not edit scanner sources."""
from pathlib import Path
import json, sys, zipfile
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events, sha256
from dwfse.ppl.ledger import build_ledger, adc_middle_times, list_starts, list_duration_us
from dwfse.ppl.events import gradient_pwc

OUT = Path(__file__).parent
Z = ROOT/'docs/v19/compiler_compatibility/v19_method_only_v7.zip'
with zipfile.ZipFile(Z) as z:
    for suffix in ('.ppl', '.ppr'):
        name = next(n for n in z.namelist() if n.endswith('1.91'+suffix))
        (OUT/('timing_baseline_v191_v7'+suffix)).write_bytes(z.read(name))
MODELS = {
 'flat_0us':dict(stmt_cost_us=0),
 'flat_0.5us':dict(stmt_cost_us=.5),
 'flat_1us':dict(stmt_cost_us=1),
 'flat_2us':dict(stmt_cost_us=2),
 'manual_x0.8':dict(expr_costs=True,expr_scale=.8),
 'manual_x0.9':dict(expr_costs=True,expr_scale=.9),
 'manual_x1.0':dict(expr_costs=True,expr_scale=1),
 'manual_x0.8_plus_0.5us_stmt':dict(expr_costs=True,expr_scale=.8,stmt_cost_us=.5),
}
SOURCES = {
 'v18': (ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl', ROOT/'experiments/FSE-DWI_10-05-2026_v18_test1e/FSE-DWI_10-05-2026_v18_test1.ppr'),
 'v191_v7': (OUT/'timing_baseline_v191_v7.ppl', OUT/'timing_baseline_v191_v7.ppr'),
}
def audit(ppl,ppr,model,overrides=None,latency=3):
 it=map_events(ppl,ppr,overrides=overrides or {},max_shots=2,rf_latency_us=latency,**model)
 led=build_ledger(it,1)
 rf=led['rf']; adc=[t for _,t in adc_middle_times(it,led)]
 t0=rf[0]['t_center'] if rf else 0
 im=[p for p in rf if p['frame']=='v19_imaging180'] if 'v19_t0' in it.vars else rf[1:]
 c=[p['t_center'] for p in im]
 v=lambda n:it.vars[n].value if n in it.vars else None
 out=dict(rf_centres_us=[p['t_center']-t0 for p in rf],adc_centres_us=[t-t0 for t in adc],
  rf_esp_us=np.diff(c).tolist(),adc_esp_us=np.diff(adc).tolist(),
  rf_to_adc_us=[a-r for a,r in zip(adc,c)],
  adc_midpoint_residual_us=[adc[k]-(c[k]+c[k+1])/2 for k in range(min(len(adc),len(c)-1))],
  overruns=[f for f in it.flags if f['kind']=='timer_overrun'],ignored_lists=[f for f in it.flags if 'ignored' in f['msg']],
  matrix_issues=led['issues'],
  outputs=[o for o in it.out if 'error' in o[1].lower() or 'V19' in o[1]],
  min_window_slack_us=min(((target-used)/10 for _,target,used in it.window_use),default=None),
  tight_windows=[dict(source=str(s),target_ticks=t,used_ticks=u,slack_us=(t-u)/10) for s,t,u in it.window_use if t-u<100],
  values={n:v(n) for n in ['rfdelay','tramp','tdp','tcrush','diff_tcrush','v19_f_im','v19_comp_flat','v19_t0','v19_first_wait','v19_gap_ir','v19_post_a','v19_post_b','v19_read_len','v19_b_im','crusher_max_dac','crusher_slew_dac_100us','v19_d_dac','crusher_saved_train','crusher_saved_first']})
 if rf:
  out['gradient_list_spans_us']={n:[dict(axis=ax,start_us=t-t0,end_us=t+list_duration_us(it,n)-t0) for t,ax in list_starts(it,led,n)] for n in ['v19_l_im','slice_list_rp','read_list','phase_list'] if n in it.vars}
 return out

def main():
 report={'assumptions':{'RF_pipeline_latency_us':3,'gradient_physical_shift':'rfdelay must be added to command G times, excluded from command list spans','timing':'source interpreter, not console verified'},'source_hashes':{k:[sha256(p) for p in pair] for k,pair in SOURCES.items()},'baseline':{},'esp_sweep':{}}
 for name,(ppl,ppr) in SOURCES.items():
  report['baseline'][name]={}
  for model,cfg in MODELS.items():
   print(name,model,flush=True)
   report['baseline'][name][model]=audit(ppl,ppr,cfg)
  report['esp_sweep'][name]={}
  for esp in range(10,15):
   print(name,'ESP',esp,flush=True)
   try:report['esp_sweep'][name][esp]=audit(ppl,ppr,MODELS['manual_x0.8'],dict(esp=esp))
   except Exception as e:report['esp_sweep'][name][esp]={'exception':str(e)}
 (OUT/'timing_baseline_audit.json').write_text(json.dumps(report,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n')

if __name__=='__main__':main()
