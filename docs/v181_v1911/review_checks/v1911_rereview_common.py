"""Shared helpers for the independent final v1.911 review (read-only analysis)."""
import sys, hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from dwfse.ppl.run import map_events
from dwfse.ppl.ledger import build_ledger, adc_middle_times, dac_us_to_cyc_m
from examples.v19_validate_events import COST_MODELS
SC=ROOT/'scanner'
V7D=ROOT/'docs/v181_v1911/baseline_v7'
SEQ={'v7':(V7D/'FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl',V7D/'FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppr'),
     'v1911':(SC/'FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl',SC/'FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppr')}
EXPECT_SHA={'v7':'6a0d222b6c8689fbdee5f4ae412c4d5df0bea10a7da99a309fabf5dfab04d828',
            'v1911':'716478bb357ba1479e6cc8fcc18c1085e44b3c78ecf1bdf32bb561b171838682'}
IMG={'no_disacq':0,'nav_on':0,'no_views':128}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(seq,model,imaging,shots=None,overrides=None,**kw):
    ppl,ppr=SEQ[seq]
    ov=dict(IMG) if imaging else {}
    if overrides: ov.update(overrides)
    ns=shots or (3 if imaging else 8)
    return map_events(ppl,ppr,max_shots=ns,overrides=ov,rf_latency_us=3,**COST_MODELS[model],**kw)
def lobes(G,t0,t1,eps=1e-8):
    out=[];cur=None
    for a,b,v in zip(G.t[:-1],G.t[1:],G.v):
        if b<=t0 or a>=t1 or b<=a: continue
        a=max(a,t0);b=min(b,t1)
        if abs(v)>eps:
            if cur and abs(a-cur[1])<1e-6:
                cur[1]=b;cur[2]+=v*(b-a);cur[3]=max(cur[3],abs(v)) if True else 0
            else:
                if cur: out.append(tuple(cur))
                cur=[a,b,v*(b-a),abs(v)]
        else:
            if cur: out.append(tuple(cur));cur=None
    if cur: out.append(tuple(cur))
    return out
