"""Timing/hardware event checks for the additive v1.911 candidate."""
from pathlib import Path
import json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from timing_investigation import audit,MODELS
from dwfse.ppl.run import map_events,sha256
from dwfse.ppl.ledger import build_ledger,adc_middle_times,list_starts,list_duration_us
from dwfse.ppl.events import PWC

PPL=ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl'
PPR=PPL.with_suffix('.ppr')
OUT=Path(__file__).parent

def waveform_checks(model,overrides=None):
 it=map_events(PPL,PPR,max_shots=2,rf_latency_us=3,overrides=overrides or {},**model)
 led=build_ledger(it,2)
 rfs=[r for r in led['rf'] if r['frame']=='v19_imaging180']
 # RF-selection gradient is intended during RF. Added fused secondary lobes
 # must have finished before RF and must start after RF, in the physical frame.
 lat=it.vars['rfdelay'].value
 spans=list_starts(it,led,'v19_l_im')
 fused=[]
 for t,a in spans:
  fused.extend([(t+lat,t+1728+lat),(t+3448+lat,t+5176+lat)])
 fused.extend((t+lat,t+1100+lat) for t,a in list_starts(it,led,'v1911_l_end'))
 overlap=lambda a,b,c,d:max(0,min(b,d)-max(a,c))
 rf_overlap=[overlap(a,b,r['t_go'],r['t_go']+r['duration_us']) for a,b in fused for r in rfs]
 adc_overlap=[overlap(a,b,q['t_init'],q['t_complete']) for a,b in fused for q in led['adc']]
 adc_clear=[]
 for q in led['adc']:
  future=[a-q['t_complete'] for a,b in fused if a>=q['t_complete']]
  adc_clear.append(min(future,default=None))
 return dict(fused_RF_overlap_max_us=max(rf_overlap,default=0),
  fused_full_ADC_overlap_max_us=max(adc_overlap,default=0),
  next_fused_start_after_ADC_complete_us=adc_clear,
  gradients={a:dict(peak_DAC=float(max(abs(w.v))),slew_DAC_per_us=float(max(abs(np.diff(w.v)/np.diff(w.t[:-1])))) if len(w.v)>1 else 0) for a,w in led['G'].items()},
  gated_RF_samples=[r['gated_samples'] for r in led['rf']],
  min_timer_slack_us=min((t-u)/10 for _,t,u in it.window_use),
  matrix_use_issues=led['issues'])

def main():
 report=dict(ppl_sha256=sha256(PPL),ppr_sha256=sha256(PPR),baseline={},sweep={},waveforms={},image_shots={})
 for m,cfg in MODELS.items():
  report['baseline'][m]=audit(PPL,PPR,cfg)
  report['waveforms'][m]=waveform_checks(cfg)
  image=dict(no_disacq=0,nav_on=0)
  report['image_shots'][m]=dict(audit=audit(PPL,PPR,cfg,image),waveforms=waveform_checks(cfg,image))
 for esp in range(10,16):
  report['sweep'][esp]=audit(PPL,PPR,MODELS['manual_x0.8'],dict(esp=esp))
 multi=dict(no_disacq=0,nav_on=0,no_views=16,no_experiments=1,no_diff_acq=3,
            acq_b=[100,1000,6000]+[0]*61,acq_x=[1000,0,0]+[0]*61,
            acq_y=[0,1000,0]+[0]*61,acq_z=[0,0,1000]+[0]*61)
 it=map_events(PPL,PPR,overrides=multi,max_shots=6,rf_latency_us=3,**MODELS['manual_x0.8'])
 shots=[]
 for si in range(1,7):
  led=build_ledger(it,si)
  shots.append(dict(shot=si,rf=len(led['rf']),adc=len(led['adc']),
    rows=sorted(set(p['vars']['diff_acq_cnt'] for p in led['rf'])),
    PEmax_DAC=float(max(abs(led['G']['P'].v))),matrix_issues=led['issues']))
 report['multirow']=dict(overrides=multi,shots=shots,flags=it.flags)
 (OUT/'timing_candidate_audit.json').write_text(json.dumps(report,indent=2)+'\n')
 for m,v in report['baseline'].items():
  print(m,len(v['rf_centres_us']),v['adc_esp_us'][:1],len(v['overruns']),len(v['ignored_lists']),report['waveforms'][m]['fused_full_ADC_overlap_max_us'])

if __name__=='__main__':main()
