"""Plot logical DAC waveforms for an imaging shot of the saved v1.7 test3 PPR."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from dwfse.generate import build_sequence


def main():
    ppr = ROOT/'experiments/FSE-DWI_10-04-2026_v17_test3/FSE-DWI_10-04-2026_v17_test3.ppr'
    seq,c,d,log = build_sequence(ppr=ppr,reduced=True,overrides={
        'sim_reduced_rows':[1]})
    assert seq.check_timing()[0]
    assert not log[0]['nav'] and d.diff_grad[1] > 1
    train = log[0]['train']
    centre90 = train.c90
    ms = lambda tick: (tick-centre90)/10000
    fig,axes=plt.subplots(3,1,figsize=(15,8),sharex=True,layout='constrained')
    for ax,key,name,colour in zip(axes,('s','r','p'),
            ('Slice S','Read R','Phase P'),('#7b3f9a','#16708d','#bd5a24')):
        ax.axhline(0,color='#bcc4ce',lw=.8)
        for segment in train.g[key]:
            ax.plot([ms(t) for t,_ in segment],[v for _,v in segment],color=colour,lw=1.4)
        for k,rf in enumerate(train.rf):
            ax.axvline(ms(rf['start']+rf['dur']/2),color='#323b45',lw=.7,ls='--')
            if key=='s':
                ax.text(ms(rf['start']+rf['dur']/2),1.02,
                    '90' if k==0 else f'RF {k}',transform=ax.get_xaxis_transform(),
                    ha='center',fontsize=8)
        for ac in train.adc:
            ax.axvspan(ms(ac['start']),ms(ac['start']+ac['n']*ac['dwell']),
                       color='#79b698',alpha=.15,lw=0)
        ax.set_ylabel(f'{name}\nDAC')
        ax.grid(axis='y',alpha=.15)
    axes[-1].set_xlabel('Time from excitation RF centre (ms)')
    axes[-1].set_xlim(-2,ms(train.t_end)+1)
    fig.suptitle(f'v1.7 test3: requested b={c.acq_b[1]}, TE={c.te} ms, ESP={c.esp} ms\n'
        'Logical gradient model: dashed lines = RF centres; green shading = ADC windows',fontsize=13)
    folder=ROOT/'docs/figures'
    folder.mkdir(exist_ok=True)
    for suffix in ('png','svg'):
        fig.savefig(folder/f'gradient_reference_v17.{suffix}',dpi=160)
    print(folder/'gradient_reference_v17.png')


if __name__=='__main__':
    main()
