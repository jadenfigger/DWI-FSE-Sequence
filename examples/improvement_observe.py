"""Bloch-only diagnostic: observe free-precession blocks outside imaging ADCs.

This observation sequence adds ideal zero-dead-time ADC events for analysis;
it is not a proposed scanner sequence. RF and gradients are unchanged.
"""
import copy
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pypulseq as pp
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dwfse import simulate, view


def observe(original, dwell=100e-6):
    system=copy.deepcopy(original.system)
    system.adc_dead_time=0
    seq=pp.Sequence(system)
    for ib in original.block_events:
        blk=original.get_block(ib)
        dur=original.block_durations[ib]
        ev=[getattr(blk,k) for k in ('rf','gx','gy','gz') if getattr(blk,k) is not None]
        # Ignore the long TR recovery fill and pre-excitation preparation delay.
        if blk.rf is None and dwell<=dur<.1:
            n=int(np.floor(dur/dwell))
            ev.append(pp.make_adc(n,dwell=dwell,system=system))
        ev.append(pp.make_delay(dur))
        seq.add_block(*ev)
    return seq


def main():
    names=sys.argv[1:] or ['base','varying','phase_xy']
    fig,axs=plt.subplots(len(names),1,figsize=(10,2.4*len(names)),sharex=True)
    for ax,name in zip(np.atleast_1d(axs),names):
        folder=Path('runs')/f'improve_screen_{name}_b1000_ph90'
        original=simulate.read_seq(str(folder/'seq.seq'))
        seq=observe(original)
        r=simulate.simulate(seq,b1=.8,n=20000)
        rfs,adcs,_=view.events(original,view.select_blocks(original))
        t0=rfs[0]['t'];t=(r['t_adc']-t0)*1e3
        edges=np.cumsum(np.r_[0,r['adc_sizes']])
        for start,end in zip(edges[:-1],edges[1:]):
            ax.plot(t[start:end],abs(r['signal'][start:end]),lw=.8,color='C0')
        for rf in rfs[1:]:ax.axvline((rf['t']-t0)*1e3,c='.7',lw=.7)
        for adc in adcs:ax.axvspan((adc['t']-t0)*1e3-3.2,(adc['t']-t0)*1e3+3.2,color='C1',alpha=.15)
        ax.set_ylabel('|mean Mxy|');ax.set_title(name,loc='left');ax.set_xlim(0,160)
        np.savez_compressed(folder/'observation.npz',time_ms=t,signal=r['signal'])
    axs[-1].set_xlabel('Time after excitation centre (ms); shading = original ADC windows')
    fig.suptitle('Observe gaps as well as acquired echoes: B1=.8, phase error=90°, b=1000\nFinite RF Bloch, 20,000 static spins; vertical lines = refocusing RF')
    fig.tight_layout()
    out=Path('docs/figures/improvement_observation.png');out.parent.mkdir(exist_ok=True)
    fig.savefig(out,dpi=150)


if __name__=='__main__':main()
