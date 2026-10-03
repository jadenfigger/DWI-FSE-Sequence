"""Archive compact measurements and regenerate the report's scientific figures.

Run after the experiments: python examples/summarize_improvement.py
Reads raw per-run JSON so independent subset sweeps cannot erase evidence.
"""
import csv
import hashlib
import importlib.metadata
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

OUT=Path('docs/data')
FIG=Path('docs/figures')


def table(path, rows):
    if not rows:
        raise ValueError(f'No records for {path}')
    with path.open('w', newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def main():
    OUT.mkdir(parents=True,exist_ok=True);FIG.mkdir(parents=True,exist_ok=True)
    source_paths=[Path('scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.6.'+ext) for ext in ['ppl','ppr']]
    provenance=dict(source_sha256={p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
        package_versions={name:importlib.metadata.version(name) for name in
                          ['numpy','scipy','matplotlib','pypulseq','torch','MRzeroCore']},
        experiment_design='docs/ppl_experiment_log.md',
        measurement_definitions='docs/ppl_improvement_report.md',
        raw_run_settings='runs/improve_*/overrides.json and sim_settings.json',
        baseline_source_preserved=True)
    (OUT/'improvement_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    bloch=[];pdg=[]
    for path in sorted(Path('runs').glob('improve_*_b*_ph*/metrics.json')):
        rows=json.loads(path.read_text());meta=rows[0]
        for row in rows:
            row['run']=row['run'].replace('\\','/')
        bloch+=rows
        for file in sorted(path.parent.glob('pathways_b1*_D0.json')):
            b1=float(re.fullmatch(r'pathways_b1([^_]+)_D0.json',file.name).group(1))
            for m in json.loads(file.read_text()):
                pdg.append(dict(group=meta['group'],variant=meta['variant'],b=meta['b'],phase=meta['phase'],
                    b1=b1,echo=m['echo'],primary=m['primary']['magnitude'],total=m['total']['magnitude'],
                    other=m['other_coherent_sum']['magnitude'],unwanted_fraction=m['other_l1_fraction'],
                    cancellation=m['net_over_l1_cancellation_ratio'],
                    other_phase_deg=m['other_relative_to_primary_phase_deg'],
                    closure_relative_error=m['closure_relative_error'],run=meta['run'].replace('\\','/')))
    screen=[r for r in bloch if r['group']=='screen']
    robust=[r for r in bloch if r['group']=='robust']
    sensitivity=[r for r in bloch if r['group'].startswith('sensitivity')]
    table(OUT/'improvement_screen.csv',screen)
    table(OUT/'improvement_robustness.csv',[r for r in robust if r['echo'] in (1,8)])
    table(OUT/'improvement_sensitivity.csv',[r for r in sensitivity if r['echo'] in (1,8)])
    table(OUT/'improvement_pathways.csv',pdg)
    table(OUT/'improvement_model_checks.csv',list(csv.DictReader(open('runs/improve_model_checks.csv'))))
    table(OUT/'improvement_steady8.csv',[r for r in bloch if r['group']=='steady8'])
    memory=json.loads(Path('runs/improve_pe_memory.json').read_text())
    memory.pop('shared_order');memory.pop('isolated_order')
    (OUT/'improvement_pe_memory.json').write_text(json.dumps(memory,indent=2)+'\n')
    summary={}
    baselines={(r['b'],r['phase'],r['b1'],r['b0'],r['echo']):r['center'] for r in robust if r['variant']=='base'}
    for name in sorted({r['variant'] for r in robust}):
        r8=[r for r in robust if r['variant']==name and r['echo']==8]
        if len(r8)!=48:
            raise ValueError(f'{name}: expected 48 robustness conditions, found {len(r8)}')
        a=np.asarray([r['center'] for r in r8])
        ratios=[r['center']/baselines[(r['b'],r['phase'],r['b1'],r['b0'],r['echo'])]
                for r in robust if r['variant']==name and r['echo']==1]
        summary[name]=dict(conditions=len(a),e8_min=float(a.min()),e8_median=float(np.median(a)),
                           e8_max=float(a.max()),e1_ratio_min=min(ratios),e1_ratio_max=max(ratios))
    closed=[float(r['closure_relative_error']) for r in pdg if r['closure_relative_error'] is not None]
    summary['validation']=dict(max_screen_closure_relative_error=max(closed),
        bloch_conditions=len(bloch)//8,screen_conditions=len(screen)//8,
        robustness_conditions=len(robust)//8)
    (OUT/'improvement_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    labels={'base':'Original','linear_crushers':'Linear crushers','centered_linear':'Linear + centred',
            'varying':'Stronger varying crushers','combined':'Stronger + centred','phase_xy':'XY RF phase'}
    colors={'base':'#555555','linear_crushers':'#1f77b4','centered_linear':'#239653','varying':'#b36a16',
            'combined':'#8f5ba6','phase_xy':'#bc4545'}
    selected=['base','linear_crushers','centered_linear','varying']
    fig,axs=plt.subplots(1,3,figsize=(13,4))
    for name in selected:
        rs=sorted([r for r in pdg if r['group']=='screen' and r['variant']==name and r['phase']==90 and r['b1']==.8],key=lambda r:r['echo'])
        if len(rs)!=8:raise ValueError(f'Missing screen PDG: {name}')
        e=[r['echo'] for r in rs]
        axs[0].plot(e,[100*r['unwanted_fraction'] for r in rs],'o-',color=colors[name],label=labels[name])
        axs[1].plot(e,[r['primary'] for r in rs],'o-',color=colors[name],label=labels[name])
        bs=sorted([r for r in screen if r['variant']==name and r['phase']==90],key=lambda r:r['echo'])
        axs[2].plot(e,[r['center'] for r in bs],'o-',color=colors[name],label=labels[name])
    for ax in axs:ax.set_xlabel('Echo number');ax.set_xticks([1,2,4,6,8]);ax.grid(alpha=.2)
    axs[0].set_ylabel('Other-path amplitude share (%)');axs[0].set_ylim(0,100)
    axs[1].set_ylabel('Primary amplitude (instantaneous RF)')
    axs[2].set_ylabel('Total amplitude (finite RF Bloch)')
    axs[0].legend(fontsize=8)
    fig.suptitle('One-factor mechanism comparison: B1=.8, phase error=90°, b=1000, ETL=8\nPDG box: 0.2 × 0.2 × 1 mm; Bloch: 4096 static spins across 2 mm z support')
    fig.tight_layout();fig.savefig(FIG/'improvement_mechanism.png',dpi=160);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,4.5))
    for name in ['base','linear_crushers','centered_linear','varying','phase_xy']:
        x=[.7,.8,1,1.2];med=[];lo=[];hi=[]
        for b1 in x:
            a=[r['center'] for r in robust if r['variant']==name and r['echo']==8 and r['b1']==b1]
            med.append(np.median(a));lo.append(min(a));hi.append(max(a))
        axs[0].plot(x,med,'o-',label=labels[name],color=colors[name]);axs[0].fill_between(x,lo,hi,color=colors[name],alpha=.07)
        rs=sorted([r for r in pdg if r['group']=='robust' and r['variant']==name and r['phase']==90 and r['b']==1000 and r['echo']==8],key=lambda r:r['b1'])
        if rs:axs[1].plot([r['b1'] for r in rs],[r['unwanted_fraction']*100 for r in rs],'o-',color=colors[name],label=labels[name])
    axs[0].set_ylabel('Echo 8 total amplitude (Bloch)');axs[0].set_title('Median and full range across 12 conditions per B1')
    axs[0].legend(fontsize=8)
    axs[1].set_ylabel('Echo 8 other-path amplitude share (%)');axs[1].set_title('PDG: phase error=90°, b=1000, B0=0');axs[1].set_ylim(0,100)
    for ax in axs:ax.set_xlabel('B1 scale');ax.set_xticks([.7,.8,1,1.2]);ax.grid(alpha=.2)
    fig.suptitle('Robustness: b=0/1000, B0=0/100 Hz, phase=0/45/90°\n10,000 static spins per Bloch condition; RF-shape sensitivity assessed separately')
    fig.tight_layout();fig.savefig(FIG/'improvement_robustness.png',dpi=160);plt.close(fig)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
