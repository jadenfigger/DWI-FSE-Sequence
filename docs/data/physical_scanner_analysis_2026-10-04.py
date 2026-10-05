"""Read-only analysis of October 4 MRDs; outputs stay under docs.

Run from the repository root: python docs/data/physical_scanner_analysis_2026-10-04.py
Uses only function definitions from the supplied recon script (never its driver).
"""
from pathlib import Path
import ast, sys, re, json, hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import nibabel as nib
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scanner/recon'))
from get_mrd_3d4 import get_mrd_3d4
source = (ROOT / 'scanner/recon/bare_bones_recon_fse.py').read_text()
tree = ast.parse(source)
ns = dict(np=np, re=re)
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)], type_ignores=[]), '<recon-functions>', 'exec'), ns)
OUT = ROOT / 'docs/figures/physical_scanner_2026-10-04'
OUT.mkdir(parents=True, exist_ok=True)
names = ['test0','test1','test2','test3','test4','test5','test6','increasing','increasing-alternating','test7','test8','test9']
scans = {}
def blocks(text):
    text = re.sub(r'[\r\n]+', '\n', text)
    result = {}
    for m in re.finditer(r'^:(\w+)[ \t]*([^\n]*(?:\n[^:\n][^\n]*)*)', text, re.M):
        key, val = m.groups()
        if key in ('VAR','VAR_ARRAY'):
            key += ':' + val.split(',')[0]
        result[key] = ' '.join(val.split())
    return result
summary = dict(scans={}, pairs={}, context='User reports a water phantom with a surface coil on a 9.4 T MR Solutions small-animal scanner; transmit configuration and temperature unspecified.', source_sha256=hashlib.sha256((ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.7.ppl').read_bytes()).hexdigest())
for name in names:
    folder = next(p for p in (ROOT/'experiments').iterdir() if p.is_dir() and p.name.endswith('_'+name))
    mrd = next(folder.glob('*.MRD'))
    raw, dims, par = get_mrd_3d4(mrd)
    binary = mrd.read_bytes()
    header = binary[binary.find(b':PPL'):].decode('latin1')
    side = next(folder.glob('*.ppr')).read_bytes().decode('latin1')
    bh, bs = blocks(header), blocks(side)
    var = lambda key, default=0: ns['ppr_var'](header,key,default)
    L = int(var('views_per_seg', re.search(r':VIEWS_PER_SEGMENT\s+\w+,\s*(\d+)',header).group(1)))
    nav = int(var('nav_on')); N = dims[4] - nav*L
    rows = ns['pe_rows'](N,L,int(var('PE_order')))
    assert len(np.unique(rows)) == N and rows.min() == 0 and rows.max() == N-1
    b = ns['ppr_array'](header,'acq_b')[:dims[0]]
    if len(b)==0: b = ns['ppr_array'](header,'b_steps_array')[:dims[0]]
    data = raw[:,0,0,0,:,:]
    images = {}; navs=[]; phase=[]; vols=[]
    for e, k in enumerate(data):
        sorted_k = np.zeros((N,dims[5]), dtype=np.complex64)
        sorted_k[rows] = k[nav*L:]
        ims={}
        for mode, apply_phase in [('off',False),('deramp_mag',False),('deramp',True),('flatten',True)]:
            kk=sorted_k.copy()
            if nav and mode!='off':
                amp, ph, lines = ns['nav_envelope'](k,L)
                corr=ns['nav_correction'](amp,ph,np.arange(N)%L,rows,N,'deramp' if mode.startswith('deramp') else 'flatten',apply_phase,.01,int(var('PE_order')))
                kk[rows] *= corr[:,None]
            ims[mode] = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kk)))
        images[e]=ims
        if nav:
            amp, ph, lines = ns['nav_envelope'](k,L)
            norms=np.linalg.norm(lines,axis=1)
            # Shape consistency after removing each echo's best complex scalar.
            ref=lines[0]
            coef=(lines@ref.conj())/np.vdot(ref,ref).real
            residual=np.linalg.norm(lines-coef[:,None]*ref,axis=1)/norms
            profile=ns['nav_profile_spread'](lines)
            navs.append(dict(norm=norms.tolist(),relative_amp=amp.tolist(),phase_deg=np.degrees(ph).tolist(),best_scalar_phase_deg=np.degrees(np.angle(coef)).tolist(),shape_residual=residual.tolist(),profile_spread=None if profile is None else profile.tolist(),peak_sample=np.argmax(np.abs(lines),axis=1).tolist()))
        vols.append(dict(b=float(b[e]),max_off=float(np.abs(ims['off']).max()),max_deramp=float(np.abs(ims['deramp']).max()),outside_energy={}))
    nifti=list(folder.glob('*.nii.gz'))
    match=None
    if nifti:
        vol=nib.load(nifti[0]).get_fdata()
        expected=np.stack([np.abs(images[e]['deramp']) for e in range(dims[0])],axis=-1).T
        expected=np.stack([np.abs(images[e]['deramp']).T for e in range(dims[0])],axis=-1)[:,:,None,:]
        match={mode:float(np.linalg.norm(vol-np.stack([np.abs(images[e][mode]).T for e in range(dims[0])],axis=-1)[:,:,None,:])/np.linalg.norm(vol)) for mode in images[0]}
    meta={key:bh.get(key) for key in bh if key.startswith('_') or key.endswith('Delay') or key in ('PerformanceCounterFrequency','AcquisitionStartTime','OBSERVE_FREQUENCY')}
    summary['scans'][name]=dict(folder=str(folder.relative_to(ROOT)),mrd_sha256=hashlib.sha256(binary).hexdigest(),ppr_sha256=hashlib.sha256(next(folder.glob('*.ppr')).read_bytes()).hexdigest(),dims=dims,etl=L,nav=nav,N=N,b=b.tolist(),embedded_sidecar_differences={key:[bs[key],bh.get(key)] for key in bs if bs[key]!=bh.get(key)},metadata=meta,nifti_relative_errors=match,volumes=vols,navigators=navs)
    if nav:
        for e, rec in enumerate(navs):
            lines=data[e,:L]
            edge=np.r_[0:12,116:128]; mid=np.r_[16:48,80:112]
            power=np.abs(lines)**2
            # Approximate noise power, excluding central primary and edge transient.
            noise=float(np.median(power[:,mid])/np.log(2))
            rec['approx_noise_complex_power']=noise
            rec['edge_excess_l2']=(np.sqrt(np.maximum(power[:,edge].sum(1)-len(edge)*noise,0))).tolist()
            rec['centre_excess_l2']=(np.sqrt(np.maximum(power[:,56:73].sum(1)-17*noise,0))).tolist()
            rec['edge_power_fraction']=(power[:,edge].sum(1)/power.sum(1)).tolist()
    scans[name]=dict(folder=folder,raw=data,header=header,images=images,b=b,rows=rows,L=L,nav=nav,N=N)
    print(name, 'dims',dims,'b',b,'header differences',list(summary['scans'][name]['embedded_sidecar_differences']), 'NIfTI',match)
    if nav: print('nav relative amps',np.round(np.array([x['relative_amp'] for x in navs]),3))

# Inspect every saved image and k-space PNG in chronological contact sheets.
for group in range(2):
    fig,axs=plt.subplots(6,6,figsize=(16,16),layout='constrained')
    for j,name in enumerate(names[group*6:(group+1)*6]):
        sc=scans[name]
        for col in range(6):
            exp=col//2
            ax=axs[j,col]
            if exp<len(sc['b']):
                kind='reconstructed_image' if col%2==0 else 'reordered_log_kspace'
                p=sc['folder']/f'{kind}_exp_{exp+1}_slice_1.png'
                if p.exists():
                    ax.imshow(Image.open(p))
                elif col%2==0:
                    ax.imshow(np.abs(sc['images'][exp]['deramp']), cmap='gray')
                else:
                    kk=np.zeros((sc['N'],128),complex);kk[sc['rows']]=sc['raw'][exp][sc['nav']*sc['L']:]
                    ax.imshow(np.log1p(np.abs(kk)),cmap='gray')
                ax.set_title(f'{name} | b={sc["b"][exp]:g} | {"image" if col%2==0 else "k-space"}',fontsize=9)
            ax.axis('off')
    fig.savefig(OUT/f'saved_scan_contact_{group+1}.png',dpi=115)
    plt.close(fig)

# Raw unencoded navigator amplitudes, independently of reconstruction.
fig,axs=plt.subplots(2,5,figsize=(16,6),layout='constrained')
nav_names=[n for n in names if scans[n]['nav']]
for ax,name in zip(axs.flat,nav_names):
    sc=scans[name]
    for e,navrec in enumerate(summary['scans'][name]['navigators']):
        ax.plot(np.arange(1,sc['L']+1),navrec['relative_amp'],'.-',label=f'b={sc["b"][e]:g}')
    ax.axhline(1,c='gray',lw=.5); ax.set_title(name); ax.set_xlabel('Echo'); ax.set_ylabel('L2 amplitude / echo 1'); ax.legend(fontsize=8);ax.grid(alpha=.2)
fig.suptitle('Raw ky=0 navigator: rebounds and parity structure precede reconstruction')
fig.savefig(OUT/'raw_navigator_envelopes.png',dpi=150);plt.close(fig)

for a,b in [('test2','test9'),('test0','test1'),('test3','test4'),('test4','test6'),('test7','test8'),('increasing','increasing-alternating')]:
    sa,sb=scans[a],scans[b]
    ph={}
    keys=set(blocks(sa['header']))|set(blocks(sb['header']))
    for k in keys:
        av=blocks(sa['header']).get(k);bv=blocks(sb['header']).get(k)
        if av!=bv: ph[k]=[av,bv]
    metrics=[]
    if sa['raw'].shape==sb['raw'].shape:
        for e in range(sa['raw'].shape[0]):
            x,y=sa['raw'][e],sb['raw'][e]
            coef=np.vdot(x,y)/np.vdot(x,x)
            metrics.append(dict(norm_ratio=float(np.linalg.norm(y)/np.linalg.norm(x)),complex_correlation=float(abs(np.vdot(x,y))/np.linalg.norm(x)/np.linalg.norm(y)),complex_residual_after_scalar=float(np.linalg.norm(y-coef*x)/np.linalg.norm(y)),scalar_phase_deg=float(np.degrees(np.angle(coef))),image_correlation=float(np.corrcoef(np.abs(sa['images'][e]['deramp']).ravel(),np.abs(sb['images'][e]['deramp']).ravel())[0,1])))
    summary['pairs'][f'{a}_vs_{b}']=dict(embedded_differences=ph,metrics=metrics)

fig,axs=plt.subplots(3,4,figsize=(12,9),layout='constrained')
for e in range(3):
    for col,(name,mode) in enumerate([('test2','off'),('test2','deramp'),('test9','off'),('test9','deramp')]):
        im=np.abs(scans[name]['images'][e][mode]); ax=axs[e,col]
        vmax=max(np.abs(scans[n]['images'][e][m]).max() for n,m in [('test2','off'),('test2','deramp'),('test9','off'),('test9','deramp')])
        ax.imshow(im,cmap='gray',vmin=0,vmax=vmax);ax.set_title(f'{name}, {mode}, b={scans[name]["b"][e]:g}',fontsize=10);ax.axis('off')
fig.suptitle('Same PPR repeat; each b row uses one common intensity scale')
fig.savefig(OUT/'repeat_and_reconstruction.png',dpi=160);plt.close(fig)

# Hold raw data fixed while changing navigator correction; also show parity phase.
fig,axs=plt.subplots(3,4,figsize=(12,9),layout='constrained')
for j,name in enumerate(['test3','test4','test6']):
    sc=scans[name]; e=1
    vmax=max(np.abs(sc['images'][e][m]).max() for m in ('off','deramp_mag','deramp'))
    for c,mode in enumerate(['off','deramp_mag','deramp']):
        axs[j,c].imshow(np.abs(sc['images'][e][mode]),cmap='gray',vmin=0,vmax=vmax)
        axs[j,c].set_title(f'{name}, b1000: {mode}',fontsize=10);axs[j,c].axis('off')
    rec=summary['scans'][name]['navigators'][e]
    ax=axs[j,3]; ax.plot(np.arange(1,sc['L']+1),rec['phase_deg'],'o-',label='sum-based phase')
    ax.plot(np.arange(1,sc['L']+1),rec['best_scalar_phase_deg'],'s--',label='profile correlation phase')
    ax.set_xlabel('Echo');ax.set_ylabel('Degrees relative to echo 1');ax.legend(fontsize=8);ax.grid(alpha=.2)
fig.suptitle('One MRD per row: phase correction concentrates signal and changes morphology')
fig.savefig(OUT/'navigator_correction_ablation.png',dpi=150);plt.close(fig)

fig,axs=plt.subplots(2,4,figsize=(13,6),layout='constrained')
for c,name in enumerate(['test3','test4','test6','test8']):
    sc=scans[name]
    for j,e in enumerate([1,2]):
        lines=sc['raw'][e,:sc['L']]; amp=np.abs(lines)
        im=axs[j,c].imshow(amp,aspect='auto',cmap='magma',extent=[-.025,6.375,8.5,.5])
        axs[j,c].axvline(3.2,color='cyan',lw=1,ls='--');axs[j,c].set_title(f'{name}, b={sc["b"][e]:g}',fontsize=10)
        axs[j,c].set_xlabel('Time from first ADC sample (ms)');axs[j,c].set_ylabel('Navigator echo');fig.colorbar(im,ax=axs[j,c],shrink=.7)
axs[1,0].annotate('off-center burst',xy=(.15,2),xytext=(2,4),color='white',arrowprops=dict(arrowstyle='->',color='white'))
fig.suptitle('Raw ADC magnitude: b1000 echoes centered; b6000 excess near ADC edges')
fig.savefig(OUT/'raw_adc_location.png',dpi=160);plt.close(fig)
summary_path=ROOT/'docs/data/physical_scanner_analysis_2026-10-04.json'
summary_path.write_text(json.dumps(summary,indent=2))
print('Pairs:', json.dumps(summary['pairs'],indent=2))
