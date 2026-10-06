"""Independent ideal mechanism checks, NEVER a PPL/event/RF validation.

Run: python examples/v19_physics_review.py
Uses exact spatially gated hard rotations. Gates are ideal boxes, not slice
profiles; gradients are instantaneous moments. No scanner RF asset is inferred.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import expm

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/v19/physics_validation"
SLICE = 0.006
SLAB = 0.018


def rotation(m, phase_deg, flip_deg, mask=None):
    """M cross B convention: x+90 maps +z to +y; free xy exp(-i phi)."""
    p = np.deg2rad(phase_deg)
    k = np.array([np.cos(p), np.sin(p), 0.])
    theta = -np.deg2rad(flip_deg)
    out = m * np.cos(theta) + np.cross(k, m) * np.sin(theta)
    out += np.sum(m * k, axis=-1)[..., None] * k * (1-np.cos(theta))
    return out if mask is None else np.where(mask[..., None], out, m)


def moment(m, phase):
    xy = (m[..., 0] + 1j*m[..., 1]) * np.exp(-1j*phase)
    return np.stack([xy.real, xy.imag, m[..., 2]], axis=-1)


def mechanism(method, phase=45., b1=1., b0=0., nz=3000, ny=64, cycles=2., first_pre_adjust_cycles=0.):
    z = (np.arange(nz)+.5)/nz*.030-.015
    y = (np.arange(ny)+.5)/ny*0.001-.0005
    m = np.zeros((nz, ny, 3)); m[..., 2] = 1
    local = np.zeros((nz, 3)); local[:, 2] = 1
    slice_mask = np.abs(z) < SLICE/2
    prep_mask = np.abs(z) < (SLAB if method == "ss_mgot" else SLICE)/2
    tip_mask = np.abs(z) < (0.010 if method == "ss_mgot" else SLICE)/2
    profile = {}

    def rf(phase_rf, flip, mask):
        nonlocal m, local
        m = rotation(m, phase_rf, flip*b1, mask[:, None])
        local = rotation(local, phase_rf, flip*b1, mask)

    def grad(phz=0., phy=0., dt=0.):
        nonlocal m, local
        m = moment(m, 2*np.pi*(phz*z[:, None]+phy*y[None, :]+b0*dt))
        local = moment(local, 2*np.pi*(phz*z+b0*dt))

    def snap(label):
        profile[label] = {"mean_y": m.mean(axis=1).copy(), "local_y0": local.copy()}

    rf(phase, 90., prep_mask)
    # Symmetric ideal spin echo: B0 cancels; no diffusion/motion attenuation.
    grad(dt=.018); rf(270., 180., prep_mask); grad(dt=.018)
    snap("A_before_added_dephasing")
    d = cycles/SLICE
    grad(phz=d); snap("B_after_added_dephasing")
    rf(180. if method == "ss_mgot" else 270., 90., tip_mask)
    snap("after_tip")
    if method == "ss_mgot":
        grad(phy=8/0.001)
        snap("after_spoiler")
        rf(0., 90., slice_mask)
        snap("after_reexcitation_ideal_no_compensation_needed")
    snap("preparation_endpoint_before_leading_crusher")
    adc = []
    for echo in range(1, 9):
        # Chosen diagnostic ordinary crusher: 1 cycle across 6 mm, distinct
        # from added modulation d. These are not sampled PPL gradient events.
        grad(phz=(1+(first_pre_adjust_cycles if echo==1 else 0))/SLICE, dt=.008)
        if echo == 1:
            snap("immediately_pre_RF_after_leading_crusher")
        rf(270., 180., slice_mask)
        grad(phz=1/SLICE+d, dt=.008)
        # Instantaneous toy echo landmark, not a real ADC middle sample.
        adc.append(complex(np.mean((m[..., 0]+1j*m[..., 1])[slice_mask])))
        if echo in (1, 2, 8):
            snap(f"ideal_echo_{echo}_center")
        grad(phz=-d)
    return z, profile, adc


def independent_rotation_checks():
    # Independent continuous ODE / matrix exponential checks, including finite
    # uniform rectangular pulses. They test math, not published/selective RF.
    checks=[]
    for phase in (0., 180., 270.):
        for b1 in (1., .8):
            duration=.0002
            p=np.deg2rad(phase)
            b=np.array([b1*1250*np.cos(p), b1*1250*np.sin(p), 128.])
            bx,by,bz=2*np.pi*b
            a=np.array([[0,bz,-by],[-bz,0,bx],[by,-bx,0]])
            m0=np.array([.3,.4,np.sqrt(.75)])
            exact=expm(a*duration)@m0
            ode=solve_ivp(lambda t,m:a@m, [0,duration], m0, method="DOP853",
                          rtol=1e-11, atol=1e-13, max_step=5e-6).y[:,-1]
            assert np.max(np.abs(exact-ode))<1e-10
            convergence=[]
            for dt in (20e-6, 10e-6, 5e-6):
                steps=round(duration/dt); h=duration/steps; m=m0.copy()
                for _ in range(steps):
                    k1=a@m; k2=a@(m+h*k1/2); k3=a@(m+h*k2/2); k4=a@(m+h*k3)
                    m += h*(k1+2*k2+2*k3+k4)/6
                convergence.append(float(np.max(np.abs(m-exact))))
            assert convergence[-1]<convergence[0] and convergence[-1]<1e-6
            checks.append(dict(phase_deg=phase,b1=b1,b0_hz=128,
                              max_ode_matrix_error=float(np.max(np.abs(exact-ode))),
                              rk4_steps_us=[20,10,5],rk4_errors=convergence))
    return checks


def vendor_checks():
    """Independent raw-byte checks and finite baseline RF study, not PPL mapping."""
    # Parse offsets independently, without vendor_seq.decode. Only known
    # rfstd44/g3040 schemas are interpreted here, with an exact sinc oracle.
    directory=ROOT/"scanner/utilities"
    allframes={}
    for fn in ("rfstd44.seq","g3040_15.seq"):
        data=(directory/fn).read_bytes()
        kind,nframes,_=struct.unpack_from("<BHH",data)
        pointers=struct.unpack_from("<"+"I"*nframes,data,5)
        parsed={}
        for offset in pointers:
            wait,words,name_length,name_ptr,raw_ptr=struct.unpack_from("<HHBII",data,offset)
            name=data[name_ptr:name_ptr+name_length-1].decode("ascii")
            nchan=4 if kind==6 else 2
            records=np.frombuffer(data[raw_ptr:raw_ptr+4*words],"<u2").reshape(-1,nchan).copy()
            parsed[name]=(wait,records)
        allframes[fn]=parsed
    wait,records=allframes["rfstd44.seq"]["3lobe_sinc_3kHz"]
    amp=(records[:,0]&4095).astype(int);amp[amp>=2048]-=4096
    oracle=np.rint(2047*np.sinc((np.arange(666)-333)*2/333)).astype(int)
    assert np.array_equal(amp[1:-1],oracle) and amp[0]==amp[-1]==0
    # Compare root's separate codec to independently decoded bytes, not just
    # to its own encode output; the sinc expression supplies an extra oracle.
    sys.path.insert(0,str(ROOT))
    from dwfse.vendor_seq import decode
    comparisons=[]
    for fn,frames in allframes.items():
        library=decode(directory/fn)
        for name,(w,rec) in frames.items():
            f=library.frame(name)
            assert w==f.wait_ticks and np.array_equal(rec,f.records)
        comparisons.append(dict(file=fn,frame_count=len(frames),independent_raw_records_match=True,
          sha256=hashlib.sha256((directory/fn).read_bytes()).hexdigest()))
    ramp_stats=[]
    for name,(w,rec) in allframes["g3040_15.seq"].items():
        v=rec.view(np.int16)
        ramp_stats.append(dict(name=name,wait_ticks=w,record_count=len(v),
              mean_primary=float(v[:,0].mean()),mean_secondary=float(v[:,1].mean()),
              endpoint_primary=[int(v[0,0]),int(v[-1,0])],
              endpoint_secondary=[int(v[0,1]),int(v[-1,1])]))
    # Nominal flip-normalized waveform: this is NOT absolute scanner B1
    # calibration. Source p90_mul=rfcal; p180_mul=rfcal*185/100 at protocol.
    dt=wait*1e-7
    rf_hz=amp/(4*float(amp.sum())*dt)
    # Actual baseline integer selector arithmetic, gs_var=-1377, no_views_2=1,
    # bw_override71, rfnum1 bandwidth3000Hz, grad_var[0]=25447Hz/mm.
    dac=int(-1377*(71*3000//100)/1070)
    g_hz_per_m=dac*25447/32767*1000
    z=(np.arange(3000)+.5)/3000*.010-.005
    data_out={"z_m":z,"raw_amplitude_dac":amp,"rf_nominal90_hz":rf_hz}
    ode_checks=[]
    for phase in (0.,180.,270.):
        p=np.deg2rad(phase)
        for b1 in (1.,.8):
            # Columns of transfer matrix are initial unit vectors. Rotation
            # solution uses matrix exponential independently at three z values.
            transfer=np.broadcast_to(np.eye(3),(len(z),3,3)).copy()
            for a in rf_hz:
                b=np.stack([np.full(len(z),b1*a*np.cos(p)),np.full(len(z),b1*a*np.sin(p)),g_hz_per_m*z],axis=-1)
                bn=np.linalg.norm(b,axis=1);k=b/np.where(bn>0,bn,1)[:,None]
                theta=-2*np.pi*bn*dt;c=np.cos(theta)[:,None,None];s=np.sin(theta)[:,None,None]
                cross=np.cross(k[:,None,:],transfer,axis=-1)
                transfer=transfer*c+cross*s+np.sum(transfer*k[:,None,:],axis=-1)[...,None]*k[:,None,:]*(1-c)
            label=f"axis{int(phase)}_b1{int(b1*100)}"
            data_out[label]=transfer
            for zi in (0,1500,2999):
                # Continuous piecewise-constant Bloch ODE follows each actual
                # sample dwell, without Rodrigues or RF averaging.
                state=np.eye(3)
                for a in rf_hz:
                    bx,by,bz=2*np.pi*np.array([b1*a*np.cos(p),b1*a*np.sin(p),g_hz_per_m*z[zi]])
                    mat=np.array([[0,bz,-by],[-bz,0,bx],[by,-bx,0]])
                    sol=solve_ivp(lambda t,v:(v.reshape(3,3)@mat.T).ravel(),[0,dt],state.ravel(),
                                  method="DOP853",rtol=1e-10,atol=1e-12)
                    state=sol.y[:,-1].reshape(3,3)
                err=float(np.max(abs(state-transfer[zi])))
                assert err<1e-9
                ode_checks.append(dict(axis_deg=phase,b1=b1,z_m=float(z[zi]),max_component_error=err))
    OUT.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(OUT/"baseline_decoded_rf_transfer.npz",**data_out)
    summary=dict(scope="Actual vendor baseline waveform decode/finite transfer only; no v191/v192 PPL event mapping or scanner calibration validation",
       independently_decoded_libraries=comparisons,sinc_formula_exact_quantized_match=True,
       sinc_records=len(amp),dwell_us=dt*1e6,full_sample_duration_us=len(amp)*dt*1e6,
       source_declared_rf_duration_us=1332,guard_zero_records=2,
       signed_amplitude_encoding="low12bits two's-complement; high control bits retained separately",
       phase_control_note="ordinary word0x2000 and terminal0x6000 share low phase bits0; terminal0x4000 is a control flag, not180degree phase",
       ramp_sample_statistics=ramp_stats,finite_transfer_geometry_mm=10,
       selector_dac=dac,selector_hz_per_m=g_hz_per_m,
       rf_scale_assumption="Full668sample signed integral normalized to90degree on resonance; no absolute calibrated B1 asserted",
       compensation="No post-RF gradient compensation in isolated transfer matrices; raw pulse transfer includes spatial phase",
       independent_piecewise_continuous_ode_checks=ode_checks)
    (OUT/"vendor_independent_decode.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps({"status":"independent actual baseline byte/RF transfer checks passed",
                      "independent_ode_checks":len(ode_checks),"scope":summary["scope"]},indent=2))


def candidate_ode_checks():
    path=ROOT/"docs/v19/reference_rf/candidate_long_t_B1realT_B1imagT_GzTm.csv"
    samples=np.loadtxt(path,delimiter=",")
    dt=float(np.diff(samples[:,0]).mean())
    assert np.max(abs(np.diff(samples[:,0])-dt))<1e-12
    assert abs(samples[0,0]-dt/2)<1e-12
    gamma=42.576e6
    results=[]
    for b1 in (1.,.8):
        for z,df in ((0.,0.),(0.,-128.),(0.,128.),(-.003,0.),(.003,0.),(-.003,128.),(.003,-128.)):
            ode=np.eye(3);exact=np.eye(3)
            for _,rx,ry,gz in samples:
                bx,by,bz=2*np.pi*np.array([gamma*b1*rx,gamma*b1*ry,gamma*gz*z+df])
                mat=np.array([[0,bz,-by],[-bz,0,bx],[by,-bx,0]])
                solution=solve_ivp(lambda t,v:(v.reshape(3,3)@mat.T).ravel(),[0,dt],ode.ravel(),
                                   method="DOP853",rtol=1e-11,atol=1e-13)
                assert solution.success
                ode=solution.y[:,-1].reshape(3,3)
                exact=exact@expm(mat*dt).T
            error=float(np.max(abs(ode-exact)))
            assert error<1e-9
            results.append(dict(z_m=z,b0_hz=df,b1=b1,
                continuous_piecewise_ode_matrix_rows_initial_basis=ode.tolist(),
                matrix_exponential_result=exact.tolist(),max_component_error=error))
    summary=dict(scope="Independent research spectral-spatial RF candidate only; not vendor AP format, PPL timing/events, or storage acceptance",
        source=str(path.relative_to(ROOT)),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        dwell_us=dt*1e6,duration_ms=len(samples)*dt*1e3,gamma_hz_per_t=gamma,
        input_interpretation="sample-center uniform rectangles; nominal B1 CSV unchanged; no compensation or extra phase fitted",
        convention="dM=2pi(M cross B); transfer rows initialMx/My/Mz and columns outputMx/My/Mz",
        cases=results)
    (OUT/"candidate_long_independent_ode.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps({"status":"candidate independent ODE/exponential checks passed","cases":len(results),
                      "max_error":max(r["max_component_error"] for r in results),"scope":summary["scope"]},indent=2))


def mapped_tip_checks():
    """Partial direct PPL-macro mapping: decoded RF + slice list, not full shot."""
    sys.path.insert(0,str(ROOT))
    from dwfse.vendor_seq import decode
    source=ROOT/"scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl"
    params=source.with_suffix(".ppr")
    text=source.read_text(encoding="cp1252")
    required=("v192_tip_gcomp=(IntToLong(gs_var_rescale)*IntToLong(crush_rf_flat+tramp))/2L/IntToLong(tref+tramp)",
              "NEGPULSE_SEC(tref,clock)","POSPULSE(crush_rf_flat,clock)",
              "MR3031_RFSTART(rfnum,tsel90,p90_mul,v192_tip_rf_pred,rf_on)")
    assert all(x in text for x in required),"Tip mapping requires re-review after source revision"
    ptext=params.read_text(encoding="cp1252")
    def param(name):
        return int(re.search(rf":VAR {name},\s*(-?\d+)",ptext).group(1))
    r=param("tramp");tref=4*param("tref_setup");rfdelay=param("rfdelay")
    gsl=int(re.search(r":SLICE_THICKNESS gs_var,\s*(-?\d+)",ptext).group(1))
    calibration=int(re.search(r":GRADIENT_STRENGTH grad_var,\s*4,\s*(\d+)",ptext).group(1))
    g=int(gsl*2130/1070)
    # Inherited independent-crusher flat-rounding arithmetic, actual RF1 gate.
    flat=int(np.ceil((1332+2*rfdelay)/(r/10))*(r/10))
    pad=flat-1332;pred=r+pad/2
    gc=int(int(g*(flat+r)/2)/(tref+r))
    library=decode(ROOT/"scanner/utilities/g3040_15.seq")
    gr=lambda name,channel:library.frame(name).samples[:,channel]
    primary=np.r_[gr("0_max",0),np.full(round(flat*50/r),32767),gr("max_0",0)]
    secondary=np.r_[gr("0_mn_sec",1),np.full(round(tref*50/r),-32767),gr("mn_0_sec",1)]
    gdwell=r/50*1e-6
    comp_area=float(secondary.sum()*gdwell*gc*calibration/32767**2*1000)
    # Subdivide constant gradient sample holds at the native RF raster.
    rf=decode(ROOT/"scanner/utilities/rfstd44.seq").frame("3lobe_sinc_3kHz")
    dt=rf.wait_ticks*1e-7;assert abs(gdwell/dt-round(gdwell/dt))<1e-12
    gradient=np.repeat(primary,round(gdwell/dt))*g*calibration/32767**2*1000
    amplitude=rf.samples/(4*rf.samples.sum()*dt)
    z=(np.arange(3000)+.5)/3000*.030-.015;inside=np.abs(z)<.0005
    transfers={};metrics=[]
    for gate in ("native_full1336us","declared_gate1332us"):
        nrf=len(amplitude) if gate.startswith("native") else round(1332e-6/dt)
        bfield=np.zeros(len(gradient));first=round(pred*1e-6/dt)
        bfield[first:first+nrf]=amplitude[:nrf]
        for b1 in (1.,.8):
            for df in (-128.,0.,128.):
                matrix=np.broadcast_to(np.eye(3),(len(z),3,3)).copy()
                # Vector rows represent the three independent input bases.
                matrix=moment(matrix,2*np.pi*(comp_area*z[:,None]+df*len(secondary)*gdwell))
                for a,gz in zip(bfield,gradient):
                    b=np.stack([np.zeros(len(z)),np.full(len(z),-b1*a),gz*z+df],axis=-1)
                    bn=np.linalg.norm(b,axis=1);k=b/np.where(bn>0,bn,1)[:,None]
                    theta=-2*np.pi*bn*dt;c=np.cos(theta)[:,None,None];s=np.sin(theta)[:,None,None]
                    matrix=matrix*c+np.cross(k[:,None,:],matrix,axis=-1)*s+np.sum(matrix*k[:,None,:],axis=-1)[...,None]*k[:,None,:]*(1-c)
                matrix=moment(matrix,2*np.pi*(comp_area*z[:,None]+df*len(secondary)*gdwell))
                label=f"{gate}_b1{int(100*b1)}_df{int(df)}"
                transfers[label]=matrix
                metrics.append(dict(gate=gate,b1=b1,b0_hz=df,
                    in_slice_rms_retainedMy_error=float(np.sqrt(np.mean((matrix[inside,1,1]-1)**2))),
                    in_slice_rms_unwantedMx_fromMy=float(np.sqrt(np.mean(matrix[inside,1,0]**2))),
                    in_slice_rms_residualMx_fromMx=float(np.sqrt(np.mean(matrix[inside,0,0]**2))),
                    in_slice_mean_storedMz_fromMx=float(np.mean(matrix[inside,0,2]))))
    OUT.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(OUT/"v192_mapped_tip_transfer.npz",z_m=z,**transfers)
    fig,axes=plt.subplots(2,2,figsize=(10,6),sharex=True,sharey=True)
    for col,b1 in enumerate((1.,.8)):
        matrix=transfers[f"native_full1336us_b1{int(100*b1)}_df0"]
        for row,basis in enumerate((1,0)):
            ax=axes[row,col]
            for component,color in enumerate(("tab:red","tab:blue","tab:green")):
                ax.plot(z*1000,matrix[:,basis,component],color=color,lw=1,
                        label=("output Mx","output My","output Mz")[component])
            ax.axvline(-.5,color="k",ls=":",lw=.8);ax.axvline(.5,color="k",ls=":",lw=.8)
            ax.set_xlim(-1.5,1.5);ax.set_ylim(-1.05,1.05)
            ax.set_ylabel("Initial "+("My" if basis==1 else "Mx"))
            if row==0:ax.set_title(f"B1 {100*b1:g}%")
            if row==1:ax.set_xlabel("z (mm)")
    axes[0,1].legend(fontsize=8,loc="lower right")
    fig.suptitle("Actual decoded Alsop candidate tip + compensation, on resonance\n"
                 "Partial macro/list mapping; nominal RF calibration assumption; no compiled event verification",fontsize=10)
    fig.tight_layout(rect=(0,0,1,.91));fig.savefig(OUT/"v192_mapped_tip_transfer.png",dpi=160);plt.close(fig)
    result=dict(scope="Partial source-derived Alsop tip macro/list mapping ONLY; complete PPL event and compiler verification unavailable",
       source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),ppr_sha256=hashlib.sha256(params.read_bytes()).hexdigest(),
       source_params=dict(tramp_us=r,tref_us=tref,rfdelay_us=rfdelay,rf_flat_us=flat,
                          rf_pred_us=pred,selector_dac=g,compensation_dac=gc,
                          exact_sampled_compensation_area_cycles_per_m=comp_area),
       assumptions="MR3040 constant sample holds at tramp/50 dwell; pure delays include B0; no physical gradient delay or instruction time; nominal90 integral B1 calibration; compare fullRF frame and declared RF gate boundaries",
       finite_tip_metrics=metrics)
    (OUT/"v192_mapped_tip_results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))


def new_disk_rf_checks():
    path=ROOT/"scanner/rf/v19_research_rf.seq"
    data=path.read_bytes();kind,nf,_=struct.unpack_from("<BHH",data);assert kind==6 and nf==6
    offsets=struct.unpack_from("<"+"I"*nf,data,5)
    manifest=json.loads((ROOT/"docs/v19/rf_library_manifest.json").read_text())
    numeric=np.load(ROOT/"docs/v19/reference_rf/real_rf_contract.npz")
    # Independently parse the stock calibration waveform too.
    stock=(ROOT/"scanner/utilities/rfstd44.seq").read_bytes()
    off=struct.unpack_from("<16I",stock,5)[6]
    wd,nwords,_,_,rawptr=struct.unpack_from("<HHBII",stock,off)
    stockwords=np.frombuffer(stock[rawptr:rawptr+4*nwords],"<u2").reshape(-1,4)
    signed=(stockwords[:,0]&4095).astype(int);signed[signed>=2048]-=4096
    stock_integral=float(signed[1:-1].sum()/2047*wd*1e-7)
    assert abs(stock_integral-manifest["stock_rf_integral_s"])<1e-14
    result=[]
    for off in offsets:
        wait,words,nlen,nptr,rptr=struct.unpack_from("<HHBII",data,off)
        name=data[nptr:nptr+nlen-1].decode("ascii")
        records=np.frombuffer(data[rptr:rptr+4*words],"<u2").reshape(-1,4)
        amplitude=(records[:,0]&4095).astype(int);amplitude[amplitude>=2048]-=4096
        assert np.array_equal(amplitude,numeric[name+"_dac"])
        assert np.all((records[:,0]&0xF000)==0x3000)
        assert np.all(records[:,1]==0xD000) and np.all(records[:,3]==0x1000)
        assert np.all(records[:-1,2]==0x2000) and records[-1,2]==0x6000
        m=manifest["pulse_frames"][name];dt=wait*1e-7
        multiplier=(594*m["rfcal_scale_numerator"])//m["rfcal_scale_denominator"]
        b1hz=amplitude/2047*(multiplier/594)/(4*stock_integral)
        gz=np.asarray(numeric[name+"_Gz_Tm"])*42.576e6
        cases=[]
        for z,df in ((0.,0.),(-.003,128.),(.003,-128.)):
            matrix=np.eye(3);ode=np.eye(3)
            for a,g in zip(b1hz,gz):
                bx,by,bz=2*np.pi*np.array([a,0.,g*z+df])
                mat=np.array([[0,bz,-by],[-bz,0,bx],[by,-bx,0]])
                solution=solve_ivp(lambda t,v:(v.reshape(3,3)@mat.T).ravel(),[0,dt],ode.ravel(),
                                  method="DOP853",rtol=1e-11,atol=1e-13)
                assert solution.success
                ode=solution.y[:,-1].reshape(3,3);matrix=matrix@expm(mat*dt).T
            error=float(np.max(abs(matrix-ode)));assert error<1e-9
            cases.append(dict(z_m=z,b0_hz=df,raw_transfer_matrix=matrix.tolist(),max_ode_matrix_error=error))
        result.append(dict(name=name,dwell_us=dt*1e6,records=len(amplitude),
             exact_contract_sample_match=True,real_control_words_match_known_template=True,
             rfcal594_inferred_multiplier=multiplier,inferred_on_resonance_flip_deg=float(b1hz.sum()*dt*360),
             cases=cases))
    summary=dict(scope="Independent actual new binary RF readback and finite Bloch test; RF calibration inferred, selector gradient from numerical contract; no full PPL events or scanner acceptance",
        actual_rf_library_sha256=hashlib.sha256(data).hexdigest(),stock_calibration_integral_s=stock_integral,
        pulses=result,known_profile_limitations="SLRprep180 was area-renormalized and changes original SLR profile; realtip has no spectral selection; imaging edge/phase errors and elimination edge leakage remain per referenceRF report")
    (OUT/"new_disk_rf_independent_results.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps({"status":"new binary RF independent sample/control/finite checks passed","frames":len(result),
      "max_ode_error":max(c["max_ode_matrix_error"] for p in result for c in p["cases"]),
      "scope":summary["scope"]},indent=2))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    inputs={}
    for rel in ("scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl",
                "scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl",
                "scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl",
                "tmp/pdfs/Gibbons_2017.txt",
                "tmp/pdfs/mrm26971-sup-0001-suppinfo01.txt",
                "examples/v19_physics_review.py"):
        f=ROOT/rel
        if f.exists(): inputs[rel]=hashlib.sha256(f.read_bytes()).hexdigest()
    results=[]
    for method in ("alsop", "ss_mgot"):
        for phase in (0.,45.,90.):
            for b1 in (1.,.8):
                for b0 in (-128.,0.,128.):
                    z,p,adc=mechanism(method,phase,b1,b0)
                    endpoint=p["preparation_endpoint_before_leading_crusher"]
                    mask=np.abs(z)<SLICE/2
                    results.append(dict(method=method,initial_excitation_phase_deg=phase,b1=b1,
                        b0_hz=b0,ideal_echo_complex=[[s.real,s.imag] for s in adc],
                        ideal_echo_magnitudes=[abs(s) for s in adc],
                        endpoint_mean_y_rms_mx=float(np.sqrt(np.mean(endpoint["mean_y"][mask,0]**2))),
                        endpoint_local_rms_mx=float(np.sqrt(np.mean(endpoint["local_y0"][mask,0]**2)))))
                    if b1==1.:
                        assert np.max(np.abs(np.abs(adc)-.5))<1e-12
                        assert np.max(np.abs(endpoint["mean_y"][mask,0]))<1e-12
        z,p,adc=mechanism(method)
        labels=list(p)
        display={"A_before_added_dephasing":"A: before added\ndephasing",
                 "B_after_added_dephasing":"B: after added\ndephasing",
                 "after_tip":"After tip",
                 "after_spoiler":"After spoiler",
                 "after_reexcitation_ideal_no_compensation_needed":"After ideal\nre-excitation",
                 "preparation_endpoint_before_leading_crusher":"Preparation endpoint\nbefore crusher",
                 "immediately_pre_RF_after_leading_crusher":"Before first RF\nafter crusher"}
        np.savez_compressed(OUT/f"{method}_ideal_profiles.npz",z_m=z,
                           **{f"{label}__{view}":v for label,d in p.items() for view,v in d.items()})
        fig,axes=plt.subplots(len(labels),2,figsize=(11,2.05*len(labels)),sharex=True,sharey=True)
        for row,label in enumerate(labels):
            for col,view in enumerate(("local_y0","mean_y")):
                ax=axes[row,col]
                for k,c in enumerate(("tab:red","tab:blue","tab:green")):
                    ax.plot(z*1000,p[label][view][:,k],color=c,label=("Mx","My","Mz")[k],lw=.8)
                ax.axvline(-3,color="k",ls=":",lw=.5); ax.axvline(3,color="k",ls=":",lw=.5)
                ax.set_ylim(-1.05,1.05)
                ax.set_ylabel(display.get(label,label.replace("_"," ")),fontsize=8)
                if row==0:ax.set_title("Local y=0" if col==0 else "Coherent mean across y")
                if row==0 and col==1:ax.legend(ncol=3,fontsize=7)
        for ax in axes[-1]:ax.set_xlabel("z (mm)")
        fig.suptitle(f"{method}: ideal hard-pulse mechanism ONLY; phase 45°, nominal B1\n"
                     "Box gates and instantaneous moments; no PPL/RF/ADC fidelity",fontsize=11)
        fig.tight_layout(rect=(0,0,1,.97)); fig.savefig(OUT/f"{method}_ideal_profiles.png",dpi=140);plt.close(fig)
    coarse=mechanism("ss_mgot",nz=3000,ny=64)[2]
    dense=mechanism("ss_mgot",nz=6000,ny=128)[2]
    spatial_error=float(np.max(np.abs(np.asarray(coarse)-dense)))
    assert spatial_error<1e-12
    # Independent scalar identity for half-signal: projection gives cosine
    # modulation, recall selects one of its two complex Fourier coefficients.
    z=(np.arange(600)+.5)/600*SLICE-SLICE/2
    phi=np.deg2rad(45.)
    scalar=np.mean(1j*np.cos(phi+2*np.pi*2/SLICE*z)*np.exp(-1j*2*np.pi*2/SLICE*z))
    vector=coarse[0]
    assert abs(scalar-vector)<1e-12
    wrong_first=mechanism("ss_mgot",first_pre_adjust_cycles=-2.)[2][0]
    assert abs(wrong_first)<1e-12
    _,profiles,_=mechanism("ss_mgot")
    endpoint=profiles["preparation_endpoint_before_leading_crusher"]["mean_y"]
    pre_rf=profiles["immediately_pre_RF_after_leading_crusher"]["mean_y"]
    z_all=(np.arange(3000)+.5)/3000*.030-.015
    predicted=moment(endpoint,2*np.pi*z_all/SLICE)
    crusher_error=float(np.max(np.abs(pre_rf-predicted)))
    assert crusher_error<1e-12
    summary=dict(scope="IDEAL MECHANISM ONLY: no published RF fidelity, compiler, PPL mapping, sampled ADC, diffusion, relaxation, images, or PSF validation",
      convention="dM/dt=2*pi*(M cross B); +x90: +Mz to +My; xy free precession exp(-i phi)",
      reference_geometry=dict(nz=3000,z_extent_mm=30,slice_mm=6,ss_mgot_slab_mm=18,tip_box_mm=10),
      ideal_test_settings=dict(echoes=8,esp_ms=16,added_cycles_across_slice=2,ordinary_crusher_cycles=1,
                               spoiler_cycles_across_1mm_y=8,T1_T2="infinite; no relaxation"),
      declared_departures="Ideal box hard RF, instantaneous moments, eight 16-ms echoes; not Gibbons Figure 3/4/S1 reproduction nor v18 adaptation validation",
      b0_justification="±128 Hz is the paper water spectral passband; here only ideal off-resonance phase/rephasing is tested, not spectral selectivity",
      ideal_correct_tip_axes=dict(alsop_deg=270,ss_mgot_deg=180,reexcitation_deg=0,refocus_deg=270),
      independent_uniform_rectangular_ode_checks=independent_rotation_checks(),
      spatial_convergence_complex_echo_error=spatial_error,
      scalar_fourier_vector_echo_error=float(abs(scalar-vector)),
      wrong_first_fused_pre_crusher_echo_magnitude=float(abs(wrong_first)),
      first_crusher_contract="First pre C / post C+D; restoration -D after ADC then ordinary pre C combines into LATER pre C-D / post C+D. Initial pre C-D is incorrect for this ideal initial ±D modulation.",
      precrusher_to_preRF_complex_prediction_error=crusher_error,
      exact_snapshot_adc_agreement="No physical ADC exists in this study: toy echo-center means are read from the same exact states and are not an ADC agreement test",
      inputs_sha256=inputs,cases=results)
    (OUT/"ideal_mechanism_results.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps({"status":"ideal mechanism checks passed","cases":len(results),
                      "spatial_error":spatial_error,"scope":summary["scope"]},indent=2))


if __name__=="__main__":
    if "--vendor-only" in sys.argv:vendor_checks()
    elif "--candidate-ode-only" in sys.argv:candidate_ode_checks()
    elif "--tip-only" in sys.argv:mapped_tip_checks()
    elif "--new-rf-only" in sys.argv:new_disk_rf_checks()
    else:main()
