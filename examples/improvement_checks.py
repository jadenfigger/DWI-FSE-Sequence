"""Spatial-support, diffusion, and scanner-limit checks for selected candidates."""
import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import matplotlib
matplotlib.use('Agg')
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dwfse import epg,pathways,simulate


def main():
    records=[]
    for name in ['base','varying','combined','linear_crushers','centered_linear']:
        folder=Path('runs')/f'improve_screen_{name}_b1000_ph90'
        seq=epg.quiet(epg.mr0.Sequence.import_file,str(folder/'seq.seq'))
        for size,d in [(.5,0),(1,0),(2,0),(1,1)]:
            args=SimpleNamespace(voxel_mm=[.2,.2,size],T1=1.5,T2=.08,T2dash=.03,D=d,b0=0,b1=.8)
            ms=epg.quiet(pathways.with_mrzero_closure,seq,epg.make_phantom(args))
            for m in ms:
                records.append(dict(variant=name,voxel_z_mm=size,D_MRzero=d,echo=m.echo,
                    primary=abs(m.primary),total=abs(m.total),unwanted_fraction=m.other_l1_fraction,
                    closure_relative_error=m.closure_relative_error))
        original=simulate.read_seq(str(folder/'seq.seq'))
        maxg=maxslew=energy=0.
        for ib in original.block_events:
            block=original.get_block(ib)
            for ax in 'xyz':
                pts=simulate.grad_pts(getattr(block,'g'+ax))
                if pts is not None:
                    ts,gs=pts
                    maxg=max(maxg,float(np.max(abs(gs))))
                    slopes=np.divide(np.diff(gs),np.diff(ts),out=np.zeros(len(ts)-1),where=np.diff(ts)>0)
                    maxslew=max(maxslew,float(np.max(abs(slopes))))
            if block.rf is not None:
                energy+=float(np.sum(abs(block.rf.signal)**2)*original.rf_raster_time)
        hardware=dict(max_grad_mT_per_m=maxg/42.577478e6*1000,
                      max_slew_T_per_m_per_s=maxslew/42.577478e6,
                      rf_energy_Hz2_s=energy,RF_energy_is_not_SAR=True,
                      duration_s=original.duration()[0],timing_pass=original.check_timing()[0])
        (folder/'limits.json').write_text(json.dumps(hardware,indent=2))
        print(name,hardware,flush=True)
    with Path('runs/improve_model_checks.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)


if __name__=='__main__':main()
