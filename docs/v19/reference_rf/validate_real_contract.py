"""Measure complete quantized RF rotation basis and realizable phase compensation.

No console timing, extra ramp, RF gate or calibration is inferred by this test.
"""
from pathlib import Path
import json, hashlib
import numpy as np
from validate_rf import evolve, GAMMA, ROOT

def zrotation(z,cycles):
    a=-2*np.pi*cycles*z
    r=np.broadcast_to(np.eye(3),z.shape+(3,3)).copy()
    r[:,0,0]=r[:,1,1]=np.cos(a)
    r[:,0,1]=np.sin(a);r[:,1,0]=-np.sin(a)
    return r

def run():
    manifest=json.loads((ROOT/'real_rf_contract.json').read_text())
    result={'status':'quantized_numerical_RF_only_not_played_PPL',
      'convention':'rows initial Mx/My/Mz; columns output; dM=-2pi(B cross M)',
      'sample_time':'centers of complete piecewise constant 10us rectangles',
      'gamma_Hz_T':GAMMA,'phase_reference':'RF real positive=phase0; phase180 reverses B1; phase270 negative imaginary B1',
      'compensation_scope':'fitted at B0=0 over imaging6mm; physical pre/post gradient cycles/m with no ramps; gradient correction must include separately scheduled actual ramps',
      'pulses':{}}
    z=np.linspace(-.015,.015,3000);mask=abs(z)<=.003
    for name,p in manifest['pulses'].items():
        s=np.loadtxt(ROOT/p['numerical_csv'],delimiter=',');r=evolve(s,z,0)
        flip=p['flip_deg'];net=GAMMA*np.mean(np.diff(s[:,0]))*s[:,3].sum()
        if flip==90:
            ia=np.unwrap(np.angle(r[:,0,2]+1j*r[:,1,2]))
            oa=np.unwrap(np.angle(r[:,2,0]+1j*r[:,2,1]))
            ic=np.polyfit(z[mask],ia[mask],1);oc=np.polyfit(z[mask],oa[mask],1)
            pre=-ic[0]/(2*np.pi);post=oc[0]/(2*np.pi)
        else:
            # A matched symmetric pair cancels under refocusing conjugation.
            pre=post=-net/2;ic=oc=np.array([0.,0.])
        corrected=zrotation(z,pre)@r@zrotation(z,post)
        center=evolve(s,0,0)
        target=center # center is exactly nominal calibrated rotation
        e=corrected-target
        selected=corrected[:,1,2] if flip==90 else corrected[:,1,1]
        leak=corrected[:,0,2] if flip==90 else corrected[:,0,1]
        f=np.linspace(-600,200,801);water=(f>=-128)&(f<=128);fat=(f>=-549)&(f<=-306)
        spec=evolve(s,0,f)
        spectral_phase_compensation={}
        if flip==90:
            spectral_axis=np.unwrap(np.angle(spec[:,0,2]+1j*spec[:,1,2]))
            sf=np.polyfit(f[water],spectral_axis[water],1)
            sa=np.polyval(sf,f)
            ss=spec[:,0,2]*np.cos(sa)+spec[:,1,2]*np.sin(sa)
            sq=-spec[:,0,2]*np.sin(sa)+spec[:,1,2]*np.cos(sa)
            spectral_phase_compensation={'scope':'diagnostic linear input time/phase reference fitted across water at z0; not independent programmable B0 correction',
              'effective_input_time_s':float(sf[0]/(2*np.pi)),
              'water_selected_storage_range':[float(ss[water].min()),float(ss[water].max())],
              'water_unwanted_storage_absmax':float(abs(sq[water]).max()),
              'fat_selected_storage_range':[float(ss[fat].min()),float(ss[fat].max())],
              'fat_unwanted_storage_absmax':float(abs(sq[fat]).max()),
              'water_axis_phase_residual_deg':float(abs(spectral_axis[water]-sa[water]).max()*180/np.pi)}
        b1results={}
        for scale in [.8,1.]:
            rb=zrotation(z,pre)@evolve(s,z,0,scale)@zrotation(z,post)
            b1results[str(scale)]={'max_basis_component_error_in_6mm':float(abs(rb[mask]-target).max()),
                'Mz_to_Mxy_abs_range':[float(np.linalg.norm(rb[mask,2,:2],axis=1).min()),float(np.linalg.norm(rb[mask,2,:2],axis=1).max())]}
        entry={'source_sha256':p['numerical_csv_sha256'],'RFphase0_center_basis':center.tolist(),
          'net_RF_gradient_cycles_m':float(net),'pre_RF_correction_cycles_m':float(pre),
          'post_RF_correction_cycles_m':float(post),
          'adaptation_pre_RF_correction_cycles_m':float(pre*6),
          'adaptation_post_RF_correction_cycles_m':float(post*6),
          'max_basis_component_error_in_6mm':float(abs(e[mask]).max()),
          'Mz_to_Mxy_abs_range_in_6mm':[float(np.linalg.norm(corrected[mask,2,:2],axis=1).min()),float(np.linalg.norm(corrected[mask,2,:2],axis=1).max())],
          'phase0_My_to_Mz_range_in_6mm':[float(corrected[mask,1,2].min()),float(corrected[mask,1,2].max())],
          'phase0_Mx_to_Mz_absmax_in_6mm':float(abs(corrected[mask,0,2]).max()),
          'phase0_Mx_retained_range_in_6mm':[float(corrected[mask,0,0].min()),float(corrected[mask,0,0].max())],
          'phase0_My_remaining_transverse_absmax_in_6mm':float(np.linalg.norm(corrected[mask,1,:2],axis=1).max()),
          'orthogonality_error':float(abs(r@np.swapaxes(r,1,2)-np.eye(3)).max()),
          'input_phase_fit_intercept_rad':float(ic[1]),'output_phase_fit_intercept_rad':float(oc[1]),
          'spectral_z0_raw_water_My_to_Mz_range':[float(spec[water,1,2].min()),float(spec[water,1,2].max())],
          'spectral_z0_raw_fat_My_to_Mz_absmax':float(abs(spec[fat,1,2]).max()),
          'B1_sensitivity_fixed_nominal_compensation':b1results}
        entry['spectral_linear_input_phase_reference']=spectral_phase_compensation
        np.savez_compressed(ROOT/(name+'_basis_transfer.npz'),z_m=z,raw_basis=r,
           corrected_basis=corrected,f_Hz=f,raw_spectral_basis=spec,
           pre_RF_correction_cycles_m=pre,post_RF_correction_cycles_m=post)
        result['pulses'][name]=entry
    # Cross-compare independently computed continuous piecewise ODE matrices.
    check=ROOT.parent/'physics_validation/candidate_long_independent_ode.json'
    if check.exists():
        independent=json.loads(check.read_text());s=np.loadtxt(ROOT/'candidate_long_t_B1realT_B1imagT_GzTm.csv',delimiter=',')
        errors=[]
        for c in independent['cases']:
            r=evolve(s,c['z_m'],c['b0_hz'],c['b1'])
            errors.append(float(abs(r-np.array(c['continuous_piecewise_ode_matrix_rows_initial_basis'])).max()))
        result['long_candidate_independent_continuous_ODE_comparison']={'cases':len(errors),'max_component_error':max(errors),
           'independent_file':str(check),'independent_file_sha256':hashlib.sha256(check.read_bytes()).hexdigest()}
    (ROOT/'real_rf_transfer_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':run()
