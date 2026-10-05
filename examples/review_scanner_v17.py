"""Export compact source/model checks: python examples/review_scanner_v17.py.

No vendor compilation or scanner instruction simulation is performed here.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse.generate import build_sequence, load_params
from dwfse.scanner_checks import (POST_ADC_ALLOWANCE_TICKS,
    POST_ADC_DISPATCH_RESERVE_TICKS, POST_ADC_EXPRESSION_TICKS)


def main():
    ppl = ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.7.ppl'
    source = ppl.read_text(encoding='ascii')
    critical = source.split('ret = gettimer()+250;',1)[1].split('waittimer(ret-25);',1)[0]
    if any(x in critical for x in ('if (','*','IntToLong','te_balance')):
        raise RuntimeError('Expensive operation returned to the timer deadline window')
    result = dict(ppl_sha256=hashlib.sha256(ppl.read_bytes()).hexdigest(),
        vendor_compiled=False, vendor_instruction_simulated=False,
        timer=dict(allowance_ticks=POST_ADC_ALLOWANCE_TICKS,
            expression_ticks=POST_ADC_EXPRESSION_TICKS,
            dispatch_reserve_ticks=POST_ADC_DISPATCH_RESERVE_TICKS,
            estimate_only=True), protocols=[])
    protocols = [ppl.with_suffix('.ppr')]
    protocols += sorted((ROOT/'experiments').glob('*/*v17_test3.ppr'))
    for ppr in protocols:
        params=load_params(ppr)
        for mode in (0,1,3):
            seq,c,d,log = build_sequence(ppr=ppr,reduced=True,overrides={
                'views_per_seg':8,'no_views':16+8*params.nav_on,'te':54,'esp':14,
                'crusher_schedule':mode,'crusher_step_pct':40})
            ok,errors = seq.check_timing()
            if not ok:
                raise RuntimeError(errors)
            train = log[0]['train']
            rf = [x['start']+x['dur']/2 for x in train.rf[1:]]
            adc = [x['start']+x['n']*x['dwell']/2 for x in train.adc]
            spacings = [(b-a)/10 for a,b in zip(rf[1:-1],rf[2:])]
            residuals = [(adc[k]-(rf[k]+rf[k+1])/2)/10 for k in range(1,7)]
            if spacings != [c.esp*1000]*6 or any(residuals):
                raise RuntimeError('Model imaging timing changed')
            result['protocols'].append(dict(ppr=str(ppr.relative_to(ROOT)),
                schedule=mode, diffusion_dac=d.diff_grad, pulseq_timing_ok=ok,
                modeled_row=log[0]['row'],
                modeled_requested_b=c.acq_b[log[0]['row']],
                modeled_imaging_rf_spacing_us=spacings,
                modeled_adc_midpoint_residual_us=residuals))
    output=ROOT/'docs/data/scanner_v17_timing_review.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(f'{len(result["protocols"])} source/model cases passed; results: {output}')
    print('Vendor compilation and simulator timing must be checked separately.')


if __name__ == '__main__':
    main()
