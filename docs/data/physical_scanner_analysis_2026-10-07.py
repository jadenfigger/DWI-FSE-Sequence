"""Reproduce Oct 7 scan comparisons, reading original acquisitions without modification.

Run: python docs/data/physical_scanner_analysis_2026-10-07.py
The shared reconstruction function definitions are loaded without its executable driver.
Primary comparison images use uncorrected complex k-space; navigator corrections are
explicit ablations because the new RF trains need not have the old navigator model.
"""
from pathlib import Path
import ast, re, sys, json, csv, hashlib, io
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import ndimage
import nibabel as nib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scanner/recon'))
from get_mrd_3d4 import get_mrd_3d4
SRC=ROOT/'scanner/recon/bare_bones_recon_fse.py'
ns=dict(np=np,re=re)
tree=ast.parse(SRC.read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),str(SRC),'exec'),ns)
OUT=ROOT/'docs/figures/physical_scanner_2026-10-07'
DATA=ROOT/'docs/data'
NAMES=['test0','test1','test1b','test2','test2b','test2c','test3','test3b','test3c','test3d']
MODES=('off','deramp_mag','deramp')
LABELS={'off':'No correction','deramp_mag':'Amplitude only','deramp':'Amplitude + phase'}

def save_figure(fig,path):
    out=io.BytesIO();fig.savefig(out,format='png',dpi=150);path.write_bytes(out.getvalue());plt.close(fig)

def load_scans():
    scans={}
    for name in NAMES:
        folder=next(p for p in (ROOT/'experiments').glob('FSE-DWI_10-07-2026_*') if p.name.endswith('_'+name))
        mrd=next(folder.glob('*.MRD'));binary=mrd.read_bytes();header=binary[binary.find(b':PPL'):].decode('latin1')
        gains={key:float(re.search(rf'^:_{field}\s+(-?[\d.]+)',header,re.M).group(1)) for key,field in [('rx','ObserveReceiverGain'),('tx','ObserveTransmitGain'),('decouple','DecoupleTransmitGain')]}
        assert gains['rx']==30 and gains['tx']==-195,('Figure gain captions need updating',name,gains)
        raw,dims,params=get_mrd_3d4(mrd)
        assert dims[1:4]==[1,1,1],(name,dims)
        var=lambda key,default=0: ns['ppr_var'](header,key,default)
        L=int(var('views_per_seg',params['views_per_seg']));nav=int(var('nav_on'));N=dims[4]-nav*L;pe=int(var('PE_order'))
        rows=ns['pe_rows'](N,L,pe)
        assert len(np.unique(rows))==N and rows.min()==0 and rows.max()==N-1
        b=ns['ppr_array'](header,'acq_b')[:dims[0]]
        assert len(b)==dims[0],(name,b,dims)
        data=raw[:,0,0,0];images={};navigators=[];corrections={}
        for e,k in enumerate(data):
            ims={};corrs={};amp,ph,lines=ns['nav_envelope'](k,L)
            for mode in MODES:
                corr=np.ones(N,dtype=complex) if mode=='off' else ns['nav_correction'](amp,ph,np.arange(N)%L,rows,N,'deramp',mode=='deramp',.01,pe)
                kk=np.zeros((N,dims[5]),complex);kk[rows]=k[nav*L:]*corr[:,None]
                ims[mode]=np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kk)))
                corrs[mode]=corr
            images[e]=ims;corrections[e]=corrs
            norms=np.linalg.norm(lines,axis=1);coef=(lines@lines[0].conj())/np.vdot(lines[0],lines[0]).real
            residual=np.linalg.norm(lines-coef[:,None]*lines[0],axis=1)/norms
            power=abs(lines)**2;dc=lines.sum(1)
            center=np.arange(56,73);edge=np.r_[0:12,116:128];noise_window=np.r_[16:48,80:112]
            noise=float(np.median(power[:,noise_window])/np.log(2))
            projection=np.fft.fftshift(np.fft.ifft(np.fft.ifftshift(lines,axes=1),axis=1),axes=1)
            refmag=abs(projection[0]);support=refmag>.25*refmag.max()
            shape_mag=np.linalg.norm(abs(projection)-np.linalg.norm(projection,axis=1)[:,None]/np.linalg.norm(projection[0])*refmag,axis=1)/norms*np.sqrt(dims[5])
            pixphase=np.angle(projection[:,support]*projection[0,support].conj())
            pixweight=abs(projection[:,support]*projection[0,support].conj())
            coherence=abs((pixweight*np.exp(1j*pixphase)).sum(1))/pixweight.sum(1)
            navigators.append(dict(norm=norms.tolist(),ratio=amp.tolist(),phase_deg=np.degrees(ph).tolist(),inner_product_phase_deg=np.degrees(np.angle(coef)).tolist(),shape_residual=residual.tolist(),magnitude_projection_shape_residual=shape_mag.tolist(),projection_phase_coherence=coherence.tolist(),dc_coherence=(abs(dc)/(np.sqrt(dims[5])*norms)).tolist(),peak_sample=np.argmax(abs(lines),axis=1).tolist(),noise_power_approx=noise,edge_excess=np.sqrt(np.maximum(power[:,edge].sum(1)-len(edge)*noise,0)).tolist(),centre_excess=np.sqrt(np.maximum(power[:,center].sum(1)-len(center)*noise,0)).tolist(),edge_power_fraction=(power[:,edge].sum(1)/power.sum(1)).tolist(),centre_power_fraction=(power[:,center].sum(1)/power.sum(1)).tolist(),amplitude_correction_min=float(abs(corrs['deramp_mag']).min()),amplitude_correction_max=float(abs(corrs['deramp_mag']).max())))
        paths=list(folder.glob('*.nii.gz'));errors={};niftimeta=None
        if paths:
            nii=nib.load(paths[0]);vol=nii.get_fdata();niftimeta=dict(shape=list(vol.shape),affine=nii.affine.tolist(),zooms=[float(z) for z in nii.header.get_zooms()])
            for mode in MODES:
                expected=np.stack([abs(images[e][mode]).T for e in images],axis=-1)[:,:,None,:]
                assert expected.shape==vol.shape
                errors[mode]=float(np.linalg.norm(vol-expected)/np.linalg.norm(vol))
        values={key:var(key) for key in ('crush_amp','diff_crush_amp','crusher_schedule','crusher_step_pct','esp','te','tr','v19_on','v19_cycles','v19_comp_flat','v19_tip_pml','v19_slab_pml','v19_spoil_cpmm','v19_spoil_dac')}
        scans[name]=dict(folder=folder,raw=data,header=header,images=images,b=b,L=L,nav=nav,N=N,pe=pe,rows=rows,dims=dims,navigators=navigators,nifti_errors=errors,nifti=niftimeta,parameters=values,gains=gains,mrd_sha256=hashlib.sha256(binary).hexdigest(),corrections=corrections)
    return scans

def bindex(s,b):
    match=np.flatnonzero(s['b']==b)
    return int(match[0]) if len(match) else None

def sorted_kspace(s,e,mode='off'):
    k=np.zeros((s['N'],s['dims'][5]),complex);k[s['rows']]=s['raw'][e,s['nav']*s['L']:]*s['corrections'][e][mode][:,None]
    assert np.allclose(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(k))),s['images'][e][mode])
    if mode=='off':assert np.isclose((abs(k)**2).sum(),(abs(s['raw'][e,s['L']:].astype(complex))**2).sum(),rtol=1e-12)
    return k

def montage(scans,names,file,title,mode='off',kspace=False,bs=(0,1000,6000),scale_names=None):
    OUT.mkdir(parents=True,exist_ok=True)
    fig,axs=plt.subplots(len(names),len(bs),figsize=(3.6*len(bs),2.55*len(names)),squeeze=False,layout='constrained')
    vals=lambda n,e: np.log10(1+abs(sorted_kspace(scans[n],e,mode))) if kspace else abs(scans[n]['images'][e][mode])
    vmax=[max(vals(n,bindex(scans[n],b)).max() for n in (scale_names or names) if bindex(scans[n],b) is not None) for b in bs]
    for j,n in enumerate(names):
        for c,b in enumerate(bs):
            e=bindex(scans[n],b);ax=axs[j,c]
            if e is None:ax.axis('off');continue
            artist=ax.imshow(vals(n,e),cmap='magma' if kspace else 'gray',vmin=0,vmax=vmax[c],origin='upper',interpolation='nearest')
            ax.set_title(f'{n} ({scans[n]["folder"].name.split("_")[-2]}, ETL{scans[n]["L"]}), b{b:g}',fontsize=9)
            if kspace:ax.set_xlabel('ADC sample');ax.set_ylabel('Centered ky row');ax.set_xticks([0,64,127]);ax.set_yticks([0,64,127],labels=['-64','0','63'])
            else:ax.axis('off')
    for c,b in enumerate(bs):
        artists=[ax.images[0] for ax in axs[:,c] if len(ax.images)]
        fig.colorbar(artists[0],ax=axs[:,c].tolist(),shrink=.4,label='log10(1 + |K| / 1 unit)' if kspace else 'Magnitude (acquisition units)')
    fig.suptitle(title+'\n'+LABELS[mode]+'; shared scale within each requested-b column; all RX30 / TX−195'+ ('\nImaging ADC samples reordered directly; navigator excluded; no image FFT' if kspace else '\nFull 35 mm FOV; no registration or per-scan brightness normalization'))
    save_figure(fig,OUT/file)

def roi_masks():
    yy,xx=np.indices((128,128));radius=np.hypot(xx-61,yy-71)
    return dict(interior=radius<=34,rim=(radius>=41)&(radius<=47),background=(yy<20)&((xx<16)|(xx>=112)))

def write_csv(name,records):
    with (DATA/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)

def measurements(scans,summary):
    masks=roi_masks();interior=masks['interior'];rim=masks['rim'];background=masks['background']
    np.savez_compressed(DATA/'oct07_roi_masks.npz',**masks)
    summary['roi']=dict(center_xy=[61,71],interior_radius_px=34,rim_radii_px=[41,47],background='y<20 and (x<16 or x>=112)',counts={k:int(m.sum()) for k,m in masks.items()},selection='Fixed across scans/modes/b after all uncorrected b0/b1000 images were inspected. No registration. Different coordinates from Oct5; object center changed. Interior excludes boundary; background is empirical artifact/noise reference, not a calibrated noise-only scan.')
    image_records=[];k_records=[];alignment=[];correction_records=[]
    for n,s in scans.items():
        base=abs(s['images'][bindex(s,1000)]['off']);labels,num=ndimage.label(base>.45*base.max());sizes=np.bincount(labels.ravel());sizes[0]=0;region=labels==sizes.argmax();cy,cx=ndimage.center_of_mass(region)
        alignment.append(dict(scan=n,x=float(cx),y=float(cy),area_px=int(region.sum()),equivalent_radius_px=float(np.sqrt(region.sum()/np.pi))))
        for e,b in enumerate(s['b']):
            off=abs(s['images'][e]['off'])
            for mode in MODES:
                im=abs(s['images'][e][mode]);smooth=ndimage.gaussian_filter(im,2);mu=float(im[interior].mean());hp=float(np.sqrt(np.mean((im-smooth)[interior]**2)));bgpower=float(np.mean(im[background]**2));power=float(np.mean(im[interior]**2))
                image_records.append(dict(scan=n,mode=mode,b=float(b),interior_mean=mu,interior_median=float(np.median(im[interior])),interior_rms=float(np.sqrt(power)),interior_excess_rms_approx=float(np.sqrt(max(power-bgpower,0))),rim_mean=float(im[rim].mean()),rim_p95=float(np.percentile(im[rim],95)),background_mean=float(im[background].mean()),background_rms=float(np.sqrt(bgpower)),interior_to_background_mean=mu/float(im[background].mean()),interior_highpass_rms=hp,interior_highpass_over_mean=hp/mu,interior_cv=float(im[interior].std()/mu),interior_smooth_cv=float(smooth[interior].std()/smooth[interior].mean()),roi_ratio_to_b0=mu/float(abs(s['images'][0][mode])[interior].mean())))
                correction_records.append(dict(scan=n,b=float(b),mode=mode,magnitude_relative_l2=float(np.linalg.norm(im-off)/np.linalg.norm(off)),interior_mean_change_pct=100*(mu/float(off[interior].mean())-1),background_rms_change_pct=100*(np.sqrt(bgpower)/np.sqrt(np.mean(off[background]**2))-1)))
                k=sorted_kspace(s,e,mode);p=abs(k)**2;total=float(p.sum());edge=float(p[:,np.r_[0:12,116:128]].sum());center=float(p[:,56:73].sum())
                k_records.append(dict(scan=n,b=float(b),mode=mode,total_power=total,total_l2=float(np.sqrt(total)),readout_edge_power_fraction=edge/total,readout_center_power_fraction=center/total,central_ky_band_power_fraction=float(p[56:72].sum()/total),all_ky_edge_sample_l2=float(np.sqrt(edge)),all_ky_center_sample_l2=float(np.sqrt(center))))
    summary['alignment']=alignment;summary['measurements']=image_records;summary['correction_ablation']=correction_records
    summary['kspace']=dict(method='Complex imaging ADC samples reordered directly to centered ky table; excludes first navigator train. Checks conserve raw energy and reproduce complex image exactly. No FFT of magnitude images.',display='log10(1+|K| / 1 acquisition unit), same additive offset and per-b scale across comparisons.',windows=dict(readout_edge_samples='0:11 and116:127',readout_center_samples='56:72',central_ky_rows='56:71'),limitations='Power contains positive noise contribution. Windows describe signal location; lower edge fraction alone does not establish diffusion accuracy. ADC sample index is not calibrated physical kx.',measurements=k_records)
    summary['navigator_limits']='Navigator scalar complex fit compares each full ADC line with echo1 after best complex coefficient; high residual indicates shape changes that a single amplitude/phase cannot remove. DC phase uses a complex sum and can be unstable when spatial cancellation suppresses that sum. Phase coherence calculated over first-echo projection support (>|25% peak|). The approximate edge/center excess assumes off-center ADC windows estimate noise; not a calibrated SNR.'
    summary['repeat_comparison']=[]
    for mode in MODES:
        for e,b in enumerate(scans['test3c']['b']):
            a=abs(scans['test3c']['images'][e][mode]);z=abs(scans['test3d']['images'][e][mode]);sel=interior
            summary['repeat_comparison'].append(dict(mode=mode,b=float(b),interior_mean_change_pct=100*(z[sel].mean()/a[sel].mean()-1),interior_relative_difference_rms=float(np.sqrt(np.mean((z[sel]-a[sel])**2))/a[sel].mean()),interior_pixel_correlation=float(np.corrcoef(a[sel],z[sel])[0,1])))
    for file,records in [('oct07_image_measurements.csv',image_records),('oct07_kspace_measurements.csv',k_records),('oct07_alignment.csv',alignment),('oct07_correction_ablation.csv',correction_records)]:write_csv(file,records)
    fig,axs=plt.subplots(2,5,figsize=(15,6.5),layout='constrained')
    for ax,n in zip(axs.flat,NAMES):
        ax.imshow(abs(scans[n]['images'][bindex(scans[n],1000)]['off']),cmap='gray')
        for key,color in [('interior','cyan'),('rim','orange'),('background','lime')]:ax.contour(masks[key],levels=[.5],colors=[color],linewidths=.7)
        ax.set_title(n+' b1000');ax.axis('off')
    fig.suptitle('Fixed ROI coordinates verified across all ten scans; no registration\nCyan interior r≤34; orange rim r41–47; green empirical background; center (61,71)')
    save_figure(fig,OUT/'roi_placement.png')

def figures(scans):
    groups=[(NAMES[:5],'all_scans_1.png','Oct 7 baseline and v1.91 scans'),(NAMES[5:],'all_scans_2.png','Oct 7 seven-b v1.91 and v1.92 scans'),(['test1','test2','test3'],'new_methods_etl8.png','ETL8 method comparison; same baseline crusher settings'),(['test1b','test2c','test3c'],'new_methods_etl16.png','ETL16 seven-b method comparison'),(['test0','test1'],'crusher_amplitude.png','Controlled baseline train-crusher amplitude comparison'),(['test2','test2b','test2c'],'v191_comparison.png','v1.91 train-length and b-sampling comparisons'),(['test3','test3b','test3c','test3d'],'v192_comparison.png','v1.92 train-length, b-sampling and repeated protocol')]
    for names,file,title in groups:
        shared=NAMES if file.startswith('all_scans') else names
        montage(scans,names,file,title,scale_names=shared)
        montage(scans,names,'kspace_'+file,title+' raw k-space',kspace=True,scale_names=shared)
    for n in ('test1b','test2c','test3c','test3d'):
        montage(scans,[n],n+'_seven_b.png',n+' full attenuation series',bs=scans[n]['b'])
    montage(scans,['test1b','test2c','test3c','test3d'],'seven_b_comparison.png','All seven-b acquisitions; shared per-b absolute scales',bs=scans['test1b']['b'])
    # Uncorrected navigator line heatmaps show whether high-b signal is centered or edge-localized.
    fig,axs=plt.subplots(2,5,figsize=(16,6.5),layout='constrained');vmax=max(abs(s['raw'][bindex(s,6000),:s['L']]).max() for s in scans.values())
    for ax,n in zip(axs.flat,NAMES):
        s=scans[n];e=bindex(s,6000);im=ax.imshow(abs(s['raw'][e,:s['L']]),aspect='auto',cmap='magma',vmin=0,vmax=vmax,extent=[0,6.4,s['L']+.5,.5]);ax.axvline(3.2,c='cyan',ls='--',lw=.7);ax.set_title(n+' b6000');ax.set_xlabel('ADC time (ms)');ax.set_ylabel('Navigator echo')
    fig.colorbar(im,ax=axs.ravel().tolist(),shrink=.6,label='Raw magnitude (acquisition units)');fig.suptitle('b6000 raw navigators: one shared absolute scale\nCentered v1.92 signal is present before reconstruction; dashed line is intended echo center')
    save_figure(fig,OUT/'raw_high_b_location.png')
    # Selected methods x b, with raw projected navigator shapes and ADC/ky power profiles.
    names=['test1b','test2c','test3c'];bs=[0,1000,6000]
    fig,axs=plt.subplots(3,3,figsize=(13,10),layout='constrained')
    for c,b in enumerate(bs):
        for n in names:
            s=scans[n];e=bindex(s,b);k=sorted_kspace(s,e);p=abs(k)**2
            axs[0,c].plot(np.arange(128),np.sqrt(p.sum(0)),label=n)
            axs[1,c].plot(np.arange(128)-64,np.sqrt(p.sum(1)),label=n)
            nav=s['navigators'][e];axs[2,c].plot(np.arange(1,s['L']+1),nav['ratio'],'.-',label=n)
        axs[0,c].set_title('b'+str(b));axs[0,c].set_xlabel('ADC sample');axs[1,c].set_xlabel('ky row relative to center');axs[2,c].set_xlabel('Navigator echo')
        for ax in axs[:2,c]:ax.set_yscale('log');ax.set_ylabel('Imaging L2 (raw units)');ax.grid(alpha=.2)
        axs[2,c].set_ylabel('Navigator L2 / first echo');axs[2,c].grid(alpha=.2)
    axs[0,0].legend();fig.suptitle('Raw complex data profiles: ADC location, ky distribution and echo envelope\nAbsolute imaging norms; navigator envelope alone is normalized within each b')
    save_figure(fig,OUT/'kspace_profiles.png')
    fig,axs=plt.subplots(3,3,figsize=(13,10),layout='constrained')
    for c,b in enumerate(bs):
        for n in names:
            s=scans[n];e=bindex(s,b);nav=s['navigators'][e];echo=np.arange(1,s['L']+1)
            axs[0,c].plot(echo,nav['phase_deg'],'.-',label=n)
            axs[1,c].plot(echo,nav['shape_residual'],'.-',label=n)
            axs[2,c].plot(echo,nav['projection_phase_coherence'],'.-',label=n)
        axs[0,c].set_title('b'+str(b));axs[0,c].set_ylabel('Navigator DC phase (degrees)');axs[1,c].set_ylabel('Best scalar-fit residual / line L2');axs[2,c].set_ylabel('Projection phase coherence')
        for ax in axs[:,c]:ax.set_xlabel('Echo');ax.grid(alpha=.2)
        axs[2,c].set_ylim(0,1.05)
    axs[0,0].legend();fig.suptitle('Does one complex navigator coefficient describe the whole echo?\nResidual 0 / coherence 1 support a scalar correction; high-b noise can lower coherence')
    save_figure(fig,OUT/'navigator_model_diagnostics.png')
    fig,axs=plt.subplots(3,3,figsize=(13,10),layout='constrained')
    for r,n in enumerate(names):
        s=scans[n]
        for c,b in enumerate(bs):
            e=bindex(s,b);nav=s['raw'][e,:s['L']];proj=abs(np.fft.fftshift(np.fft.ifft(np.fft.ifftshift(nav,axes=1),axis=1),axes=1))
            for j in (0,1,3,7,15):axs[r,c].plot(np.arange(128),proj[j],label='E'+str(j+1))
            axs[r,c].set_title(n+' b'+str(b));axs[r,c].set_xlabel('Readout spatial pixel');axs[r,c].set_ylabel('Projection magnitude units');axs[r,c].grid(alpha=.2)
    axs[0,0].legend();fig.suptitle('Raw navigator spatial projections (1D complex inverse FFT)\nChanges in width/shape across echoes cannot be represented by global scalar amplitude alone')
    save_figure(fig,OUT/'navigator_projections.png')
    for b in bs:
        fig,axs=plt.subplots(3,3,figsize=(11,9.5),layout='constrained');vmax=max(abs(scans[n]['images'][bindex(scans[n],b)][m]).max() for n in names for m in MODES)
        for r,n in enumerate(names):
            e=bindex(scans[n],b)
            for c,m in enumerate(MODES):axs[r,c].imshow(abs(scans[n]['images'][e][m]),cmap='gray',vmin=0,vmax=vmax);axs[r,c].set_title(n+': '+LABELS[m],fontsize=9);axs[r,c].axis('off')
        fig.colorbar(axs[0,0].images[0],ax=axs.ravel().tolist(),shrink=.6,label='Image magnitude units');fig.suptitle('b'+str(b)+' correction ablation: fixed raw acquisition, one common scale\nSaved NIfTI uses amplitude + phase; primary method comparisons use no correction')
        save_figure(fig,OUT/f'reconstruction_ablation_b{b}.png')
    # Quantitative image attenuation and noise/texture controls, without claiming ADC.
    masks=roi_masks();fig,axs=plt.subplots(2,3,figsize=(14,8),layout='constrained')
    for n in NAMES:
        s=scans[n];ims=[abs(s['images'][e]['off']) for e in range(len(s['b']))];mu=np.array([im[masks['interior']].mean() for im in ims]);bg=np.array([np.sqrt(np.mean(im[masks['background']]**2)) for im in ims]);hp=np.array([np.sqrt(np.mean((im-ndimage.gaussian_filter(im,2))[masks['interior']]**2))/m for im,m in zip(ims,mu)]);nav=np.array([r['norm'][0] for r in s['navigators']])
        for ax,y in zip(axs.flat,[mu,mu/mu[0],nav/nav[0],bg,mu/np.array([im[masks['background']].mean() for im in ims]),hp]):ax.plot(s['b'],y,'.-',label=n)
    titles=['Absolute fixed-interior mean','Fixed-interior mean / b0','First raw navigator L2 / b0','Remote background RMS','Interior / background mean','Interior high-pass RMS / mean']
    for i,ax in enumerate(axs.flat):ax.set_title(titles[i]);ax.set_xlabel('Requested b (s/mm²)');ax.grid(alpha=.2);ax.set_yscale('log' if i<4 else 'linear')
    axs[0,0].legend(ncol=2,fontsize=8);fig.suptitle('Uncorrected image and raw attenuation metrics answer different questions\nMagnitude ratios at low signal include noise bias; background ratio is empirical contrast, not calibrated SNR')
    save_figure(fig,OUT/'signal_and_raw_metrics.png')
    fig,axs=plt.subplots(2,3,figsize=(13,8),layout='constrained');mask=masks['interior'];lim=max(abs(abs(scans['test3d']['images'][bindex(scans['test3d'],b)]['off'])-abs(scans['test3c']['images'][bindex(scans['test3c'],b)]['off'])).max() for b in bs)
    for c,b in enumerate(bs):
        a=abs(scans['test3c']['images'][bindex(scans['test3c'],b)]['off']);z=abs(scans['test3d']['images'][bindex(scans['test3d'],b)]['off']);axs[0,c].plot(a[60:82].mean(0),label='test3c');axs[0,c].plot(z[60:82].mean(0),label='test3d');axs[0,c].set_title('b'+str(b)+' fixed-y profile');axs[0,c].set_xlabel('Readout pixel');axs[0,c].legend();axs[0,c].grid(alpha=.2);im=axs[1,c].imshow(z-a,cmap='coolwarm',vmin=-lim,vmax=lim);axs[1,c].axis('off');axs[1,c].set_title('test3d − test3c')
    fig.colorbar(im,ax=axs[1].tolist(),shrink=.65,label='Magnitude difference units');fig.suptitle('Identical stored-protocol repeat: absolute profiles and signed differences\nNo image registration; repeated residual signal does not establish its intended coherence pathway')
    save_figure(fig,OUT/'v192_repeatability.png')

def main():
    scans=load_scans()
    if '--preview' in sys.argv:
        montage(scans,NAMES,'preview_roi.png','Oct 7 all scans',mode='off');return
    summary=dict(reconstruction_sha256=hashlib.sha256(SRC.read_bytes()).hexdigest(),analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),loader_sha256=hashlib.sha256((ROOT/'scanner/recon/get_mrd_3d4.py').read_bytes()).hexdigest(),scans={n:{k:s[k] for k in ('dims','L','nav','N','pe','navigators','nifti_errors','nifti','parameters','gains','mrd_sha256')} for n,s in scans.items()})
    for n,s in scans.items():summary['scans'][n]['b_values']=s['b'].tolist()
    measurements(scans,summary)
    if '--metrics-only' not in sys.argv:figures(scans)
    (DATA/'physical_scanner_analysis_2026-10-07.json').write_text(json.dumps(summary,indent=2))
    print('Generated Oct 7 measurements and comparison figures for',len(scans),'scans')

if __name__=='__main__':main()
