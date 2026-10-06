"""Quantize nominally calibrated real RF samples; no waveform deployment.

Uses newly designed sampled RF, with disclosed source deviations. The manifest
defines the digital sample/area contract for a independently verified .seq codec.
"""
from pathlib import Path
import hashlib,json,numpy as np
ROOT=Path(__file__).resolve().parent
GAMMA=42.576e6
def main():
    definitions=[('v19_slrprep90','slr_prep90_3p2ms.csv',90,18,18,3.55),
                 ('v19_slrprep180','slr_prep180_3p2ms.csv',180,18,18,3.55),
                 ('v19_slrtip90','slr_elim90_3p2ms.csv',90,6,10,3.55),
                 ('v19_slrelim90','slr_elim90_3p2ms.csv',90,6,6,3.55),
                 ('v19_reexc90','windowed_reexc90_1p2ms.csv',90,6,6,1.54),
                 ('v19_imaging180','windowed_reexc90_1p2ms.csv',180,6,6,1.54)]
    manifest={'status':'research_scanner_RF_contract_not_console_verified',
              'Gibbons_original_coefficients':False,'spectral_spatial_tip':False,
              'gamma_Hz_T':GAMMA,'reference_imaging_width_mm':6,
              'adapted_imaging_width_mm':1,'gradient_spatial_scale_to_adaptation':6,
              'ADC_PPL_verification':False,'pulses':{}}
    arrays={}
    for frame,source,flip,oldwidth,newwidth,tbw in definitions:
        path=ROOT/source;s=np.loadtxt(path,delimiter=',');dt=float(np.diff(s[:,0]).mean())
        ratio=(flip*np.pi/180)/(2*np.pi*GAMMA*dt*s[:,1].sum())
        r=s[:,1]*ratio; g=s[:,3]*oldwidth/newwidth
        # Tiny imaginary roundoff is intentionally dropped and quantified.
        q=np.round(r/np.abs(r).max()*2047).astype(np.int16)
        integral=dt*float(q.sum())/2047
        peak_for_angle=(flip*np.pi/180)/(2*np.pi*GAMMA*integral)
        rq=q/2047*peak_for_angle
        numerical=np.column_stack([s[:,0],rq,np.zeros(len(rq)),g])
        target=ROOT/(frame+'.csv');np.savetxt(target,numerical,delimiter=',',fmt='%.17g')
        arrays[frame+'_dac']=q;arrays[frame+'_time_s']=s[:,0];arrays[frame+'_B1_T']=rq;arrays[frame+'_Gz_Tm']=g
        manifest['pulses'][frame]={
            'source':source,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'numerical_csv':target.name,'numerical_csv_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
            'duration_us':round(len(q)*dt*1e6),'sample_count':len(q),'dwell_us':round(dt*1e6),
            'wait_ticks':round(dt/1e-7),'flip_deg':flip,'bandwidth_Hz':tbw/(len(q)*dt),
            'width_mm':newwidth,'TBW':tbw,'reference_Gz_mTm':float(g[0]*1e3),
            'adapted_Gz_mTm':float(g[0]*6e3),'nominal_peak_B1_uT':float(peak_for_angle*1e6),
            'signed_normalized_integral_s':integral,'integer_sample_sum':int(q.sum()),
            'max_removed_imaginary_T':float(np.max(np.abs(s[:,2]*ratio))),
            'real_quantization_max_error_T':float(np.max(np.abs(rq-r))),
            'source_area_normalization_scale':float(ratio),
            'rf_unit':'signed_int11_DAC_peak2047','gradient_RFsamples_only_ramps_separate':True,
            'amplitude_calibration':'Use signed integral, target flip and measured peakB1-per-board-multiplier. No calibration in rfcal counts is assumed.'}
    np.savez_compressed(ROOT/'real_rf_contract.npz',**arrays)
    manifest['contract_npz_sha256']=hashlib.sha256((ROOT/'real_rf_contract.npz').read_bytes()).hexdigest()
    (ROOT/'real_rf_contract.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
