"""Descriptive requested-b attenuation; no calibrated diffusivity or pathway fit.

Run after physical_scanner_analysis_2026-10-07.py. Reads originals only.
The first navigator is unencoded and precedes image reconstruction/correction.
An offset fit to an L2 norm is phenomenological: coherent components need not
add as positive scalars, and noise creates a positive norm floor.
"""
from pathlib import Path
import importlib.util
import json
import csv
import numpy as np
from scipy.optimize import least_squares
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('oct07', HERE/'physical_scanner_analysis_2026-10-07.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def main():
    scans = analysis.load_scans()
    results = []
    for name, s in scans.items():
        b = np.asarray(s['b'])
        norms = np.array([x['norm'][0] for x in s['navigators']])
        y = norms / norms[0]
        # Low-b region is prospectively common to every family, above its floor.
        low = b <= 1000
        fit = least_squares(lambda p: np.exp(-p[0]*b[low])-y[low], [.002], bounds=(0,.01))
        dlow = float(fit.x[0])
        rec = dict(scan=name, b=b.tolist(), first_navigator_norm=norms.tolist(),
                   ratio_to_b0=y.tolist(), low_b_limit=1000,
                   low_b_anchored_mono_slope_mm2_s=dlow,
                   low_b_rms_ratio_residual=float(np.sqrt(np.mean(fit.fun**2))),
                   b6000_measured_ratio=float(y[b==6000][0]),
                   b6000_low_b_mono_extrapolation=float(np.exp(-6000*dlow)),
                   mrd_sha256=s['mrd_sha256'])
        if len(b)==7:
            mono = least_squares(lambda p: np.exp(-p[0]*b)-y, [.002], bounds=(0,.01))
            offset = least_squares(lambda p: (1-p[1])*np.exp(-p[0]*b)+p[1]-y,
                                   [.002,.05], bounds=([0,0],[.01,.5]),
                                   xtol=1e-12,ftol=1e-12,gtol=1e-12)
            rec.update(full_mono_slope_mm2_s=float(mono.x[0]),
                       full_mono_rms_ratio_residual=float(np.sqrt(np.mean(mono.fun**2))),
                       offset_slope_mm2_s=float(offset.x[0]),
                       offset_fraction=float(offset.x[1]),
                       offset_rms_ratio_residual=float(np.sqrt(np.mean(offset.fun**2))))
        results.append(rec)
    payload=dict(method='Unweighted bounded least squares of normalized first-navigator L2. Anchored mono y=exp(-D*b); offset y=(1-f)*exp(-D*b)+f. Low-b fits use b<=1000; full fits only seven-value scans. Slopes use requested b, not verified effective b. No uncertainty estimate, physical component assignment, or noise-floor subtraction.', scans=results)
    (HERE/'oct07_attenuation_fits.json').write_text(json.dumps(payload,indent=2))
    fields=[k for r in results for k in r if k not in ('b','first_navigator_norm','ratio_to_b0')]
    fields=list(dict.fromkeys(fields))
    with (HERE/'oct07_attenuation_fits.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        w.writerows({k:v for k,v in r.items() if k in fields} for r in results)
    fig,axs=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    colors={'test1b':'black','test2c':'tab:blue','test3c':'tab:orange','test3d':'tab:red'}
    for r in results:
        if r['scan'] not in colors:continue
        b=np.array(r['b']);y=np.array(r['ratio_to_b0']);color=colors[r['scan']]
        for ax in axs[0]:ax.plot(b,y,'o-',color=color,label=r['scan'])
        grid=np.linspace(0,6000,300)
        axs[0,1].plot(grid,np.exp(-r['low_b_anchored_mono_slope_mm2_s']*grid),'--',color=color,alpha=.6)
        axs[1,0].plot(b,np.log(np.maximum(y,1e-12))+r['low_b_anchored_mono_slope_mm2_s']*b,'o-',color=color,label=r['scan'])
        axs[1,1].plot(b,y,'o',color=color,label=r['scan'])
        axs[1,1].plot(grid,(1-r['offset_fraction'])*np.exp(-r['offset_slope_mm2_s']*grid)+r['offset_fraction'],color=color)
    axs[0,0].set_title('Measured uncorrected first-navigator attenuation')
    axs[0,1].set_title('Dashed: extrapolation from b <= 1000')
    axs[0,1].set_yscale('log');axs[0,1].set_ylim(1e-6,1.2)
    axs[1,0].set_title('Log departure from low-b monoexponential')
    axs[1,1].set_title('Descriptive exponential + constant fit')
    for ax in axs.flat:
        ax.set_xlabel('Requested b (s/mm²)');ax.grid(alpha=.2);ax.legend(fontsize=8)
    axs[0,0].set_ylabel('E1 L2 / b0');axs[0,1].set_ylabel('E1 L2 / b0')
    axs[1,0].set_ylabel('ln(measured / extrapolated)');axs[1,1].set_ylabel('E1 L2 / b0')
    fig.suptitle('Seven-b ETL16 scans: v192 retains a large high-b component\nL2 includes noise; offset is a descriptive plateau, not a physical compartment estimate')
    analysis.OUT.mkdir(parents=True,exist_ok=True)
    analysis.save_figure(fig,analysis.OUT/'attenuation_and_plateau.png')
    for r in results:
        print(r['scan'],'low-b slope',round(r['low_b_anchored_mono_slope_mm2_s'],7),'high-b',round(r['b6000_measured_ratio'],6), 'offset',round(r.get('offset_fraction',0),6))


if __name__=='__main__':
    main()
