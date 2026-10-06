"""Reproduce Oct 5 image/raw measurements; original data are read only.

Run: python docs/data/physical_scanner_analysis_2026-10-05.py
Add/rebuild only k-space outputs: append --kspace-only (keeps image figures intact).
Uses current supplied reconstruction function definitions without its file-writing driver.
PE5 single echo uses sequential rows as in archived PPL; v1.8 playback remains unverified.
"""
from pathlib import Path
import ast, re, sys, json, csv, hashlib, io
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import ndimage, signal
import nibabel as nib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scanner/recon'))
from get_mrd_3d4 import get_mrd_3d4
SRC = ROOT/'scanner/recon/bare_bones_recon_fse.py'
ns = dict(np=np, re=re)
tree=ast.parse(SRC.read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),str(SRC),'exec'),ns)
OUT=ROOT/'docs/figures/physical_scanner_2026-10-05'
OUT.mkdir(parents=True,exist_ok=True)
NAMES=['test0','test1','test1b','test1c','test1d','test1e','test1f','test1g','test2','test2b','test2c','test2d','test3','test3b','test4','test4b','test5','test6','test7','testa']

def save_figure(fig,path,**kwargs):
    # Render completely before opening the destination. A standard binary write
    # also avoids PIL's read/write file mode on existing Windows workspace files.
    output=io.BytesIO()
    fig.savefig(output,format='png',**kwargs)
    path.write_bytes(output.getvalue())

def load_scans():
    scans={}
    for name in NAMES:
        folder=next(p for p in (ROOT/'experiments').glob('FSE-DWI_10-05-2026_*') if p.name.endswith('_'+name))
        mrd=next(folder.glob('*.MRD')); binary=mrd.read_bytes()
        header=binary[binary.find(b':PPL'):].decode('latin1')
        raw,dims,params=get_mrd_3d4(mrd)
        var=lambda key,default=0: ns['ppr_var'](header,key,default)
        L=int(var('views_per_seg',params.get('views_per_seg',8)))
        nav=int(var('nav_on')); N=dims[4]-nav*L; pe=int(var('PE_order'))
        if N<=0 or N%L: raise ValueError((name,dims,L,N))
        rows=np.arange(N) if pe==5 and L==1 else ns['pe_rows'](N,L,pe)
        assert len(np.unique(rows))==N and rows.min()==0 and rows.max()==N-1
        b=ns['ppr_array'](header,'acq_b')[:dims[0]]
        if not len(b): b=ns['ppr_array'](header,'b_steps_array')[:dims[0]]
        data=raw[:,0,0,0]
        images={}; navigators=[]
        for e,k in enumerate(data):
            ims={}
            for mode in ('off','deramp_mag','deramp'):
                kk=np.zeros((N,dims[5]),complex); kk[rows]=k[nav*L:]
                if nav and mode!='off':
                    amp,ph,lines=ns['nav_envelope'](k,L)
                    corr=ns['nav_correction'](amp,ph,np.arange(N)%L,rows,N,'deramp',mode=='deramp',.01,pe)
                    kk[rows]*=corr[:,None]
                ims[mode]=np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kk)))
            images[e]=ims
            if nav:
                lines=k[:L]; norms=np.linalg.norm(lines,axis=1)
                amp,ph,_=ns['nav_envelope'](k,L)
                coef=(lines@lines[0].conj())/np.vdot(lines[0],lines[0]).real
                residual=np.linalg.norm(lines-coef[:,None]*lines[0],axis=1)/norms
                power=np.abs(lines)**2
                edge=np.r_[0:12,116:128]; mid=np.r_[16:48,80:112]
                noise=float(np.median(power[:,mid])/np.log(2))
                navigators.append(dict(norm=norms.tolist(),ratio=amp.tolist(),phase_deg=np.degrees(ph).tolist(),shape_residual=residual.tolist(),peak_sample=np.argmax(np.abs(lines),axis=1).tolist(),noise_power=noise,edge_excess=np.sqrt(np.maximum(power[:,edge].sum(1)-len(edge)*noise,0)).tolist(),centre_excess=np.sqrt(np.maximum(power[:,56:73].sum(1)-17*noise,0)).tolist(),edge_power_fraction=(power[:,edge].sum(1)/power.sum(1)).tolist()))
        paths=list(folder.glob('*.nii.gz')); errors={}
        if paths:
            vol=nib.load(paths[0]).get_fdata()
            for mode in ('off','deramp_mag','deramp'):
                expected=np.stack([np.abs(images[e][mode]).T for e in images],axis=-1)[:,:,None,:]
                errors[mode]=float(np.linalg.norm(vol-expected)/np.linalg.norm(vol))
        scans[name]=dict(folder=folder,raw=data,header=header,images=images,b=b,L=L,nav=nav,N=N,pe=pe,rows=rows,dims=dims,navigators=navigators,nifti_errors=errors,mrd_sha256=hashlib.sha256(binary).hexdigest())
    return scans

def montage(scans,names,file,title,mode='deramp'):
    fig,axs=plt.subplots(len(names),3,figsize=(10,2.6*len(names)),layout='constrained')
    vmax=[max(np.abs(scans[n]['images'][e][mode]).max() for n in names) for e in range(3)]
    for j,n in enumerate(names):
        for e in range(3):
            im=np.abs(scans[n]['images'][e][mode]); ax=axs[j,e]
            artist=ax.imshow(im,cmap='gray',vmin=0,vmax=vmax[e],origin='upper')
            ax.set_title(f'{n}, b={scans[n]["b"][e]:g}; PE{scans[n]["pe"]}',fontsize=10)
            ax.axis('off')
    for e in range(3): fig.colorbar(axs[0,e].images[0],ax=axs[:,e].tolist(),shrink=.4,label='Image magnitude (acquisition units)')
    gain_note='\nCAUTION: test0 RX gain 180; others 30. Brightness is not gain-normalized.' if 'test0' in names else ''
    fig.suptitle(title+'\nFull 35 mm FOV; single centered slice; shared linear scale within each b column'+gain_note)
    save_figure(fig,OUT/file,dpi=130);plt.close(fig)

def main():
    scans=load_scans()
    if '--kspace-only' in sys.argv:
        path=ROOT/'docs/data/physical_scanner_analysis_2026-10-05.json'
        summary=json.loads(path.read_text())
        kspace_comparisons(scans,summary)
        path.write_text(json.dumps(summary,indent=2))
        print('K-space comparisons and measurements generated for all 20 scans')
        return
    for i in range(4): montage(scans,NAMES[i*5:(i+1)*5],f'all_scans_{i+1}.png','Oct 5 consistent deramp + navigator phase reconstruction')
    for n,s in scans.items(): print(n,s['dims'],'NIfTI',s['nifti_errors'])
    # Reconstructed images are regenerated from the MRDs, avoiding a large duplicate archive.
    summary=dict(reconstruction_sha256=hashlib.sha256(SRC.read_bytes()).hexdigest(),scans={n:{k:s[k] for k in ('dims','L','nav','N','pe','navigators','nifti_errors','mrd_sha256')} for n,s in scans.items()})
    summary['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SRC,ROOT/'scanner/recon/get_mrd_3d4.py',ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.7.ppl',ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.3.ppl',ROOT/'scanner/m3040_15.pph']}
    measurements(scans,summary)
    kspace_comparisons(scans,summary)
    (ROOT/'docs/data/physical_scanner_analysis_2026-10-05.json').write_text(json.dumps(summary,indent=2))

def measurements(scans,summary):
    yy,xx=np.indices((128,128)); radius=np.hypot(xx-56,yy-77)
    interior=radius<=34; rim=(radius>=41)&(radius<=48)
    background=(yy<24)&((xx<16)|(xx>=112))
    masks=dict(interior=interior,rim=rim,background=background)
    np.savez_compressed(ROOT/'docs/data/oct05_roi_masks.npz',**masks)
    summary['roi']=dict(center_xy=[56,77],interior_radius_px=34,rim_radii_px=[41,48],background='y<24 and (x<16 or x>=112)',counts={k:int(v.sum()) for k,v in masks.items()},selection='Fixed after visual inspection of all b1000 images; excludes outer boundary from interior and reserves distant top corners as empirical background. No scan-specific threshold used for measurement.')
    rows=[]; centroid=[]
    for name,s in scans.items():
        base=np.abs(s['images'][1]['deramp'])
        labels,num=ndimage.label(base>.35*base.max()); sizes=np.bincount(labels.ravel());sizes[0]=0
        region=labels==sizes.argmax(); cy,cx=ndimage.center_of_mass(region)
        centroid.append(dict(scan=name,x=float(cx),y=float(cy),area_px=int(region.sum())))
        for mode in ('off','deramp_mag','deramp'):
            means=[]
            for e,b in enumerate(s['b']):
                im=np.abs(s['images'][e][mode]); smooth=ndimage.gaussian_filter(im,2)
                mu=float(im[interior].mean()); means.append(mu)
                row=dict(scan=name,mode=mode,b=float(b),interior_mean=mu,interior_median=float(np.median(im[interior])),rim_mean=float(im[rim].mean()),rim_p95=float(np.percentile(im[rim],95)),background_mean=float(im[background].mean()),background_rms=float(np.sqrt(np.mean(im[background]**2))),interior_highpass_rms=float(np.sqrt(np.mean((im-smooth)[interior]**2))),interior_highpass_over_mean=float(np.sqrt(np.mean((im-smooth)[interior]**2))/mu),roi_ratio_to_b0=0.)
                row['roi_ratio_to_b0']=mu/means[0]
                rows.append(row)
    summary['alignment']=centroid; summary['measurements']=rows
    with (ROOT/'docs/data/oct05_image_measurements.csv').open('w',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with (ROOT/'docs/data/oct05_alignment.csv').open('w',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=list(centroid[0]));w.writeheader();w.writerows(centroid)
    fig,axs=plt.subplots(1,3,figsize=(12,4),layout='constrained')
    for ax,n in zip(axs,['test1','test1e','test7']):
        ax.imshow(np.abs(scans[n]['images'][1]['deramp']),cmap='gray')
        for mask,color,label in [(interior,'cyan','interior'),(rim,'orange','rim'),(background,'lime','background reference')]:
            ax.contour(mask,levels=[.5],colors=[color],linewidths=.8)
            ax.plot([],[],c=color,label=label)
        ax.set_title(n+' b1000; fixed coordinates');ax.legend(fontsize=7);ax.set_xlabel('Read sample / image x');ax.set_ylabel('Phase / image y')
    fig.suptitle('ROI placement verified against all scans; no registration or cropping')
    save_figure(fig,OUT/'roi_placement.png',dpi=150);plt.close(fig)
    groups=[(['test1','test1e','test2','test2b','test3','test3b'],'polarity_comparison.png','Polarity pairs: constant, increasing, increasing + alternating'),(['test1b','test1c','test1d','test1e'],'duration_amplitude.png','Constant crushers: sign, amplitude and duration controls'),(['test1e','test2b','test3b','test5','test6','test7'],'negative_schedules.png','Negative-baseline schedule comparisons'),(['test4','test4b','test5'],'decreasing_comparison.png','Decreasing schedules: unequal baselines / first duration')]
    for names,file,title in groups: montage(scans,names,file,title)
    montage(scans,['test1e','test1f','test1g','test2b','test2c','test2d'],'pe_groups_shared_scale.png','Phase-order controls: constant group above, increasing group below')
    selected=['test1','test1e','test2','test2b','test3','test3b','test4','test5','test6','test7']
    fig,axs=plt.subplots(2,3,figsize=(14,8),layout='constrained')
    for n in selected:
        rec=[r for r in rows if r['scan']==n and r['mode']=='deramp']
        axs[0,0].plot([0,1000,6000],[r['interior_mean'] for r in rec],'.-',label=n)
        axs[0,1].plot([0,1000,6000],[r['roi_ratio_to_b0'] for r in rec],'.-',label=n)
        nav=scans[n]['navigators']
        axs[0,2].plot([0,1000,6000],[r['norm'][0]/nav[0]['norm'][0] for r in nav],'.-',label=n)
        axs[1,0].plot(np.arange(1,9),nav[1]['ratio'],'.-',label=n)
        axs[1,1].plot(np.arange(1,9),nav[2]['edge_excess'],'.-',label=n)
        axs[1,2].plot(np.arange(1,9),nav[2]['centre_excess'],'.-',label=n)
    titles=['Absolute fixed-interior signal','Normalized fixed-interior signal','First raw navigator norm / b0','b1000 raw navigator / E1','b6000 ADC-edge excess','b6000 ADC-center excess']
    labels=['Image acquisition units','Mean signal / b0','L2 norm / b0','L2 norm / E1','Approx. excess L2 units','Approx. excess L2 units']
    for i,ax in enumerate(axs.flat):
        ax.set_title(titles[i]);ax.set_ylabel(labels[i]);ax.set_xlabel('Requested b (s/mm²)' if i<3 else 'Echo');ax.grid(alpha=.2)
        if i in (0,1,2): ax.set_yscale('log')
    axs[0,0].legend(fontsize=7,ncol=2)
    fig.suptitle('Absolute signal, attenuation, and raw contamination answer different questions\nHigh-b magnitude ratios include noise bias; raw excess uses an approximate background power estimate')
    save_figure(fig,OUT/'signal_and_raw_metrics.png',dpi=150);plt.close(fig)
    names=['test1','test1e','test2','test2b','test3b','test6','test7','test5']
    fig,axs=plt.subplots(2,4,figsize=(14,6),layout='constrained')
    vmax=max(np.abs(scans[n]['raw'][2,:8]).max() for n in names)
    for ax,n in zip(axs.flat,names):
        im=ax.imshow(np.abs(scans[n]['raw'][2,:8]),aspect='auto',cmap='magma',vmin=0,vmax=vmax,extent=[0,6.4,8.5,.5])
        ax.axvline(3.2,c='cyan',ls='--',lw=.8);ax.set_title(n+' b6000');ax.set_xlabel('ADC time (ms)');ax.set_ylabel('Navigator echo')
    fig.colorbar(im,ax=axs.ravel().tolist(),shrink=.7,label='Raw magnitude (same scale throughout)')
    fig.suptitle('High-b residuals localize near ADC edges, separate from the intended centered echo')
    save_figure(fig,OUT/'raw_high_b_location.png',dpi=150);plt.close(fig)
    fig,axs=plt.subplots(2,3,figsize=(13,7),layout='constrained')
    for c,(a,b) in enumerate([('test1','test1e'),('test2b','test3b'),('test6','test7')]):
        for n in (a,b):
            im=np.abs(scans[n]['images'][1]['deramp'])
            axs[0,c].plot(np.arange(128),im[65:90].mean(0),label=n)
        axs[0,c].set_title(a+' vs '+b+' b1000');axs[0,c].set_xlabel('Readout image pixel');axs[0,c].set_ylabel('Mean profile y65:89');axs[0,c].legend();axs[0,c].grid(alpha=.2)
        diff=np.abs(scans[b]['images'][2]['deramp'])-np.abs(scans[a]['images'][2]['deramp'])
        lim=max(abs(diff.min()),abs(diff.max())); artist=axs[1,c].imshow(diff,cmap='coolwarm',vmin=-lim,vmax=lim)
        axs[1,c].set_title(b+' − '+a+' b6000');axs[1,c].axis('off');fig.colorbar(artist,ax=axs[1,c],shrink=.75,label='Magnitude difference units')
    fig.suptitle('Profiles retain absolute intensity; signed magnitude differences use fixed coordinates')
    save_figure(fig,OUT/'profiles_and_differences.png',dpi=150);plt.close(fig)
    # Reconstruction ablation at fixed raw data and shared per-b scales.
    names=['test1e','test3b','test7'];fig,axs=plt.subplots(3,3,figsize=(10,9),layout='constrained')
    vmax=max(np.abs(scans[n]['images'][1][m]).max() for n in names for m in ('off','deramp_mag','deramp'))
    for j,n in enumerate(names):
        for c,m in enumerate(('off','deramp_mag','deramp')):
            axs[j,c].imshow(np.abs(scans[n]['images'][1][m]),cmap='gray',vmin=0,vmax=vmax);axs[j,c].set_title(n+' b1000 '+m);axs[j,c].axis('off')
    fig.suptitle('Raw-data-fixed correction check; one common intensity scale')
    save_figure(fig,OUT/'reconstruction_ablation.png',dpi=150);plt.close(fig)

def sorted_kspace(sc,volume,mode='off'):
    """Centered row table applied directly to imaging ADC samples; no image FFT.

    The read axis remains sample index, with sample 64 the intended echo center.
    The ky assignment has the same conditional v1.7 mapping as image reconstruction.
    """
    raw=sc['raw'][volume]; rows=sc['rows']; N=sc['N']; L=sc['L']
    out=np.zeros((N,raw.shape[1]),complex);out[rows]=raw[sc['nav']*L:]
    if sc['nav'] and mode!='off':
        amp,phase,_=ns['nav_envelope'](raw,L)
        corr=ns['nav_correction'](amp,phase,np.arange(N)%L,rows,N,'deramp',mode=='deramp',.01,sc['pe'])
        out[rows]*=corr[:,None]
    expected=sc['images'][volume][mode]
    replay=np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(out)))
    assert np.allclose(replay,expected,rtol=1e-10,atol=1e-12)
    if mode=='off':assert np.isclose(np.sum(abs(out)**2),np.sum(abs(raw[sc['nav']*L:].astype(np.complex128))**2),rtol=1e-12)
    return out

def kspace_montage(scans,names,file,title,mode='off'):
    """Same additive 1-unit offset and scale per b across each comparison."""
    fig,axs=plt.subplots(len(names),3,figsize=(11,2.6*len(names)),layout='constrained')
    kk={n:[sorted_kspace(scans[n],v,mode) for v in range(3)] for n in names}
    vmax=[max(np.log10(1+abs(kk[n][v])).max() for n in names) for v in range(3)]
    for j,n in enumerate(names):
        for v in range(3):
            ax=axs[j,v]
            ax.imshow(np.log10(1+abs(kk[n][v])),cmap='magma',vmin=0,vmax=vmax[v],origin='upper',extent=[-.5,127.5,63.5,-64.5],interpolation='nearest')
            ax.set_title(f'{n}, b={scans[n]["b"][v]:g}; PE{scans[n]["pe"]}',fontsize=9)
            ax.set_xticks([0,64,127]);ax.set_yticks([-64,0,63]);ax.set_xlabel('Readout sample index');ax.set_ylabel('ky row relative to center')
    for v in range(3):fig.colorbar(axs[0,v].images[0],ax=axs[:,v].tolist(),shrink=.5,label='log10(1 + |K| / 1 acquisition unit)')
    gain='\nCAUTION: test0 RX180; all other scans RX30. No gain normalization.' if 'test0' in names else ''
    fig.suptitle(title+'\nNavigator excluded; '+mode+' correction; shared scale within each b column'+gain)
    save_figure(fig,OUT/file,dpi=130);plt.close(fig)

def kspace_comparisons(scans,summary):
    records=[]
    for n,sc in scans.items():
        for v,b in enumerate(sc['b']):
            for mode in ('off','deramp'):
                k=sorted_kspace(sc,v,mode);power=abs(k)**2;total=float(power.sum())
                edge=float(power[:,np.r_[0:12,116:128]].sum())
                center=float(power[:,56:73].sum())
                records.append(dict(scan=n,b=float(b),mode=mode,total_power=total,total_l2=float(np.sqrt(total)),readout_edge_power_fraction=edge/total,readout_center_power_fraction=center/total,central_ky_band_power_fraction=float(power[56:72].sum()/total),all_ky_edge_sample_l2=float(np.sqrt(edge))))
    with (ROOT/'docs/data/oct05_kspace_measurements.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    summary['kspace']=dict(method='Imaging-only complex ADC samples reordered to the same centered ky rows used for images. No FFT of magnitude images. Off and deramp modes; all raw imaging energy conserved on row permutation.',display='log10(1+|K| / 1 acquisition unit); shared offset and limits within each b column; no per-scan normalization',windows=dict(readout_edge_samples='0:11,116:127',readout_center_samples='56:72',central_ky_rows='56:71 (ky -8:7)'),limitations='Positive noise power retained, not noise-subtracted. Fractions describe distribution rather than SNR. ky map conditional on predecessor implementation; readout index not calibrated physical kx.',measurements=records)
    for i in range(4):kspace_montage(scans,NAMES[i*5:(i+1)*5],f'kspace_all_scans_{i+1}.png','Oct 5 imaging k-space before navigator correction')
    groups=[(['test1','test1e','test2','test2b','test3','test3b'],'kspace_polarity.png','Equal-area polarity and alternation comparisons'),(['test1e','test2b','test3b','test5','test6','test7'],'kspace_negative_schedules.png','Negative-baseline schedules and custom sign pair'),(['test1b','test1c','test1d','test1e'],'kspace_duration_amplitude.png','Constant duration, amplitude and polarity controls'),(['test4','test4b','test5'],'kspace_decreasing.png','Decreasing protocols; unequal area and first duration'),(['test1e','test1f','test1g','test2b','test2c','test2d'],'kspace_pe_groups.png','Phase-order controls: constant above, increasing below')]
    for names,file,title in groups:kspace_montage(scans,names,file,title)
    # Fixed raw data, identical per-b scales: corrected phase leaves |K| unchanged;
    # any displayed magnitude change is due to the deramp amplitude factor.
    names=['test1e','test3b','test7'];fig,axs=plt.subplots(3,3,figsize=(11,9),layout='constrained')
    vmax=max(np.log10(1+abs(sorted_kspace(scans[n],1,m))).max() for n in names for m in ('off','deramp_mag','deramp'))
    for j,n in enumerate(names):
        for c,m in enumerate(('off','deramp_mag','deramp')):
            k=sorted_kspace(scans[n],1,m);axs[j,c].imshow(np.log10(1+abs(k)),cmap='magma',vmin=0,vmax=vmax,origin='upper',extent=[-.5,127.5,63.5,-64.5])
            axs[j,c].set_title(f'{n} b1000: {m}');axs[j,c].set_xlabel('Readout sample index');axs[j,c].set_ylabel('ky row relative to center')
        assert np.allclose(abs(sorted_kspace(scans[n],1,'deramp_mag')),abs(sorted_kspace(scans[n],1,'deramp')),rtol=2e-7)
    fig.colorbar(axs[0,0].images[0],ax=axs.ravel().tolist(),shrink=.6,label='log10(1 + |K| / 1 acquisition unit)')
    fig.suptitle('K-space correction check at fixed raw data and one common scale\nNavigator phase correction affects phase, not the displayed magnitude')
    save_figure(fig,OUT/'kspace_correction_ablation.png',dpi=150);plt.close(fig)
    fig,axs=plt.subplots(2,3,figsize=(14,7),layout='constrained')
    for c,(names,title) in enumerate([(['test1','test1e','test6','test7'],'High-b sign controls'),(['test1e','test1f','test1g'],'b1000 constant PE group'),(['test2b','test2c','test2d'],'b1000 increasing PE group')]):
        v=2 if c==0 else 1
        for n in names:
            k=sorted_kspace(scans[n],v);p=abs(k)**2
            axs[0,c].plot(np.arange(128),np.sqrt(p.sum(0)),label=n)
            axs[1,c].plot(np.arange(128)-64,np.sqrt(p.sum(1)),label=n)
        axs[0,c].set_title(title);axs[0,c].set_xlabel('Readout sample index');axs[1,c].set_xlabel('ky row relative to center')
        for ax in axs[:,c]:ax.set_yscale('log');ax.set_ylabel('Imaging-data L2 (acquisition units)');ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.suptitle('Uncorrected imaging k-space profiles: absolute norms, no normalization or noise subtraction\nReadout profile sums power over ky; ky profile sums power over readout')
    save_figure(fig,OUT/'kspace_profiles.png',dpi=150);plt.close(fig)

if __name__=='__main__': main()
