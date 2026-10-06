"""Full rotation-basis transfer for actual captured MATLAB sample coefficients.

Research design validation only. These are not events played by PPL until
scanner encoding, physical calibration and scheduled RF-gating are verified.
"""
from pathlib import Path
import hashlib, json
import numpy as np
from scipy.integrate import solve_ivp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
GAMMA=42.576e6

def evolve(samples,z,f,b1=1):
    z,f=np.broadcast_arrays(np.asarray(z),np.asarray(f))
    shape=z.shape; z=z.ravel(); f=f.ravel()
    dt=float(np.diff(samples[:,0]).mean())
    m=np.broadcast_to(np.eye(3),(len(z),3,3)).copy()
    for row in samples:
        b=np.stack([np.full(len(z),row[1]*b1*GAMMA),
                    np.full(len(z),row[2]*b1*GAMMA),row[3]*GAMMA*z+f],axis=1)
        norm=np.linalg.norm(b,axis=1)
        k=np.divide(b,norm[:,None],out=np.zeros_like(b),where=norm[:,None]!=0)
        angle=-2*np.pi*norm*dt
        c=np.cos(angle)[:,None,None]; s=np.sin(angle)[:,None,None]
        m=m*c+np.cross(k[:,None,:],m)*s+k[:,None,:]*np.sum(k[:,None,:]*m,axis=2)[:,:,None]*(1-c)
    return m.reshape(shape+(3,3))

def compensated_storage(r,z):
    """Fit realizable linear input phase plus global axis; assess residual.

    This maximizes transverse-to-Mz transfer at B0=0 over imaging |z|<=3mm.
    It is a fitted RF compensation proposal, not inferred scanner scheduling.
    """
    axis=np.unwrap(np.angle(r[:,0,2]+1j*r[:,1,2]))
    mask=np.abs(z)<=0.003
    coef=np.polyfit(z[mask],axis[mask],1)
    theta=np.polyval(coef,z)
    storage=r[:,0,2]*np.cos(theta)+r[:,1,2]*np.sin(theta)
    quadrature=-r[:,0,2]*np.sin(theta)+r[:,1,2]*np.cos(theta)
    return coef,storage,quadrature,axis-theta

def ode_check(samples):
    dt=float(np.diff(samples[:,0]).mean()); duration=len(samples)*dt
    z=np.array([-0.003,0,0.003]); f=np.array([-128,0,128])
    def rhs(t,y):
        row=samples[min(int(t/dt),len(samples)-1)]
        b=np.stack([np.full(3,row[1]*GAMMA),np.full(3,row[2]*GAMMA),row[3]*GAMMA*z+f],1)
        return (-2*np.pi*np.cross(b[:,None,:],y.reshape(3,3,3))).ravel()
    # Continuous RK solver has different implementation from sampled Rodrigues.
    sol=solve_ivp(rhs,[0,duration],np.broadcast_to(np.eye(3),(3,3,3)).ravel(),
                  rtol=2e-9,atol=2e-11,max_step=dt/2)
    return float(np.max(np.abs(sol.y[:,-1].reshape(3,3,3)-evolve(samples,z,f))))

def run():
    results={"status":"research_RF_samples_only","rotation_convention":"left_handed_Mx_plus_iMy",
             "gamma_Hz_T":GAMMA,"original_Gibbons_coefficients":False,"pulses":{}}
    files=['candidate_t_B1realT_B1imagT_GzTm.csv','candidate_long_t_B1realT_B1imagT_GzTm.csv',
           'slr_prep90_3p2ms.csv','slr_prep180_3p2ms.csv','slr_elim90_3p2ms.csv','windowed_reexc90_1p2ms.csv']
    for name in files:
        path=ROOT/name
        if not path.exists(): continue
        samples=np.loadtxt(path,delimiter=','); dt=float(np.diff(samples[:,0]).mean())
        z=np.linspace(-0.015,0.015,3000); r=evolve(samples,z,0)
        coef,stored,leak,residual=compensated_storage(r,z)
        mask=np.abs(z)<=0.003
        f=np.linspace(-600,200,801)
        spec=evolve(samples,0,f)
        theta=coef[1]
        specstored=spec[:,0,2]*np.cos(theta)+spec[:,1,2]*np.sin(theta)
        specquad=-spec[:,0,2]*np.sin(theta)+spec[:,1,2]*np.cos(theta)
        water=(f>=-128)&(f<=128); fat=(f>=-549)&(f<=-306)
        rf=samples[:,1]+1j*samples[:,2]
        entry={"sample_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"samples":len(samples),
               "duration_s":len(samples)*dt,"peak_B1_uT":float(np.max(np.abs(rf))*1e6),
               "peak_Gz_mTm":float(np.max(np.abs(samples[:,3]))*1e3),
               "peak_slew_Tm_s":float(np.max(np.abs(np.diff(np.r_[0,samples[:,3],0])))/dt),
               "rf_area_rad":float(2*np.pi*GAMMA*dt*np.sum(samples[:,1])),
               "net_gradient_cycles_m":float(GAMMA*dt*np.sum(samples[:,3])),
               "fitted_input_axis_rad_intercept":float(coef[1]),
               "fitted_input_phase_cycles_m":float(coef[0]/(2*np.pi)),
               "in_6mm_storage_range":[float(stored[mask].min()),float(stored[mask].max())],
               "in_6mm_unwanted_storage_max":float(np.max(np.abs(leak[mask]))),
               "in_6mm_axis_residual_deg_max":float(np.max(np.abs(residual[mask]))*180/np.pi),
               "water_center_slice_storage_range":[float(specstored[water].min()),float(specstored[water].max())],
               "fat_center_slice_storage_range":[float(specstored[fat].min()),float(specstored[fat].max())],
               "water_center_unwanted_storage_max":float(np.max(np.abs(specquad[water]))),
               "rotation_orthogonality_error":float(np.max(np.abs(r@np.swapaxes(r,1,2)-np.eye(3))))}
        # Actual basis transfer, not scalar flip or magnitude alone.
        np.savez_compressed(ROOT/(path.stem+'_transfer.npz'),z_m=z,rotation_basis=r,
                            fitted_storage=stored,unwanted_storage=leak,axis_residual_rad=residual,
                            f_Hz=f,spectral_rotation_basis=spec,spectral_stored=specstored,spectral_unwanted=specquad)
        fig,ax=plt.subplots(2,2,figsize=(11,7),layout='constrained')
        ax[0,0].plot(z*1e3,stored,label='selected transverse to Mz');ax[0,0].plot(z*1e3,leak,label='quadrature to Mz')
        ax[0,0].set(xlabel='z (mm)',ylabel='signed transfer'); ax[0,0].legend(fontsize=8)
        ax[0,1].plot(z*1e3,residual*180/np.pi);ax[0,1].set(xlabel='z (mm)',ylabel='axis error after linear fit (deg)',xlim=(-3,3))
        ax[1,0].plot(f,specstored,label='selected to Mz');ax[1,0].plot(f,specquad,label='quadrature to Mz');ax[1,0].axvspan(-128,128,color='green',alpha=.1);ax[1,0].axvspan(-549,-306,color='orange',alpha=.1);ax[1,0].set(xlabel='B0 offset (Hz), z=0',ylabel='signed transfer');ax[1,0].legend(fontsize=8)
        ax[1,1].plot(samples[:,0]*1e3,np.real(rf)*1e6,label='B1 real');ax[1,1].plot(samples[:,0]*1e3,np.imag(rf)*1e6,label='B1 imag');ax[1,1].set(xlabel='time (ms)',ylabel='B1 (uT)');ax[1,1].legend(fontsize=8)
        fig.suptitle(path.stem+'\nNew design research sample; fitted compensation; NOT played-PPL verification',fontsize=10)
        fig.savefig(ROOT/(path.stem+'_transfer.png'),dpi=130);plt.close(fig)
        if name.startswith('candidate_long'):
            entry['independent_ODE_max_error']=ode_check(samples)
            # Test B1 effects with fixed nominal compensation; no per-condition refit.
            entry['B1_sensitivity']={}
            for scale in [0.8,1.0]:
                rb=evolve(samples,z,0,scale); theta_z=np.polyval(coef,z)
                a=rb[:,0,2]*np.cos(theta_z)+rb[:,1,2]*np.sin(theta_z)
                q=-rb[:,0,2]*np.sin(theta_z)+rb[:,1,2]*np.cos(theta_z)
                entry['B1_sensitivity'][str(scale)]={'selected_range':[float(a[mask].min()),float(a[mask].max())],'quadrature_max':float(np.max(np.abs(q[mask])))}
            entry['passes_published_B1_cap']=entry['peak_B1_uT']<=22.6
            entry['passes_published_duration']=entry['duration_s']<=5.64e-3
            entry['passes_water_signed_storage_at_center']=bool(np.all((specstored[water]>=.990)&(specstored[water]<=1.0)))
            entry['passes_fat_signed_storage_at_center']=bool(np.all((specstored[fat]>=.04)&(specstored[fat]<=.06)))
        results['pulses'][name]=entry
    (ROOT/'transfer_results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))

if __name__=='__main__':run()
