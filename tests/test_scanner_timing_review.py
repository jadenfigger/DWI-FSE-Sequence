"""Regression checks for the v1.7 timer/diffusion review, using EVO semantics."""
import unittest
from pathlib import Path

from dwfse.generate import PPLAbort, build_sequence, derive, load_params
from dwfse.scanner_checks import (
    POST_ADC_ALLOWANCE_TICKS, POST_ADC_DISPATCH_RESERVE_TICKS,
    POST_ADC_EXPRESSION_TICKS, diffusion_components, post_adc_targets,
    refocus_timer_targets, scaled_diffusion_dac,
)

ROOT = Path(__file__).resolve().parents[1]
PPL = ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.7.ppl'
PPR = PPL.with_suffix('.ppr')


class TimerReviewTests(unittest.TestCase):
    def test_critical_window_from_actual_source(self):
        source = PPL.read_text(encoding='ascii')
        critical = source.split('ret = gettimer()+250;', 1)[1].split('waittimer(ret-25);', 1)[0]
        self.assertIn('templ3 = templ3-ret;', critical)
        for forbidden in ('if (', '*', 'IntToLong', 'te_balance', 'crush_post_pad'):
            self.assertNotIn(forbidden, critical)
        pre_sample = source.split('ret = gettimer()+250;', 1)[0]
        self.assertIn('templ3 = post_adc_train_ticks;', pre_sample)
        setup = source.split('post_adc_base_ticks=te_balance_bl_temp2*10L;', 1)[1]
        self.assertLess(setup.index('post_adc_train_ticks='), setup.index('crusher_setup_ticks = gettimer();'))
        self.assertLess(POST_ADC_EXPRESSION_TICKS + POST_ADC_DISPATCH_RESERVE_TICKS,
                        POST_ADC_ALLOWANCE_TICKS)

    def test_absolute_balance_preserved_for_every_echo_and_final_path(self):
        for base_us, train_us, delta in [(1000, 5000, 0), (600, 1733, 120), (700, 900, -120)]:
            targets = post_adc_targets(base_us, train_us, delta)
            for etl in (1, 2, 8, 1024):
                for echo in range(1, etl + 1):
                    target = targets[int(echo < etl)]
                    for sampled_elapsed in (200, 500, 900):
                        ret = sampled_elapsed + 250
                        remaining = target - ret
                        self.assertEqual(ret + remaining, target)
                        old = (base_us + (train_us + delta if echo < etl else 0)) * 10 - ret
                        self.assertEqual(remaining, old)

    def test_waittimer_argument_boundaries_before_narrowing(self):
        # With ramp=100, delay=17, gate=23, post is the larger target.
        self.assertEqual(refocus_timer_targets(6467,100,0,0,17,23)[1],65500)
        with self.assertRaises(ValueError):
            refocus_timer_targets(6468,100,0,0,17,23)
        with self.assertRaises(ValueError):
            refocus_timer_targets(5000,1000,2060,2060,60,23)
        with self.assertRaisesRegex(PPLAbort,'timer range'):
            derive(load_params(PPR, {'diff_tcrush':10000}))

    def test_setup_expansion_accounted_in_tr_and_absolute_start(self):
        old = load_params()
        new = load_params(PPR)
        self.assertEqual(new.sim_pre90_us-old.sim_pre90_us,1150)
        self.assertEqual(derive(new).tr_min_us-derive(old).tr_min_us,1150)
        self.assertEqual(load_params(PPR, {'sim_pre90_us':12345}).sim_pre90_us,12345)

    def test_imaging_adc_midpoints_and_esp_in_model(self):
        for mode in (0,1,3):
            seq,c,d,log = build_sequence(ppr=PPR,reduced=True,overrides={
                'te':54, 'esp':14, 'views_per_seg':8, 'no_views':16,
                'crusher_schedule':mode, 'crusher_step_pct':40})
            self.assertTrue(seq.check_timing()[0])
            train=log[0]['train']
            centres=[rf['start']+rf['dur']/2 for rf in train.rf[1:]]
            adc=[a['start']+a['n']*a['dwell']/2 for a in train.adc]
            self.assertEqual([b-a for a,b in zip(centres[1:-1],centres[2:])], [c.esp*10000]*6)
            for k in range(1,7):
                self.assertEqual(adc[k],(centres[k]+centres[k+1])/2)


class DiffusionReviewTests(unittest.TestCase):
    def test_scale_overflow_and_limits_precede_int_conversion(self):
        self.assertEqual(scaled_diffusion_dac(15000,200),30000)
        self.assertEqual(scaled_diffusion_dac(30000,100),30000)
        for dac,pct in [(20000,200),(32767,200),(30001,100),(-1,100),(1,99)]:
            with self.assertRaises(ValueError):
                scaled_diffusion_dac(dac,pct)
        with self.assertRaises(PPLAbort):
            derive(load_params(PPR, {'b_input_mode':0, 'acq_grad':[20000]*512,
                                    'diff_grad_scale':200}))
        source=PPL.read_text(encoding='ascii')
        self.assertLess(source.index('diffusion_scale_check:'),source.index('diff_acq_loop:'))
        self.assertIn('scale(acq_grad[diff_acq_cnt], diff_scale_saved, 100)',source)

    def test_oblique_b0_workaround_and_signed_ties(self):
        for direction,expected in [((577,577,577),(1,0,0)),
                                   ((-577,577,577),(-1,0,0)),
                                   ((0,-707,707),(0,-1,0)),
                                   ((100,200,-970),(0,0,-1))]:
            self.assertEqual(diffusion_components(1,direction,True),expected)
            self.assertEqual(diffusion_components(1,direction,False),(0,0,0))
        self.assertEqual(diffusion_components(1000,(-577,577,577),True),(-577,577,577))
        c=load_params(PPR, {'acq_x':[577]*512,'acq_y':[577]*512,'acq_z':[577]*512})
        self.assertEqual(derive(c).diff_rps[0],(1,0,0))

    def test_nominal_row_report_uses_quantized_direction(self):
        axis=derive(load_params(PPR, {'acq_b':[1000]*512}))
        short=derive(load_params(PPR, {'acq_b':[1000]*512,'acq_x':[950]*512}))
        # Keep the calibration/search approximation but report what is played.
        self.assertEqual(axis.diff_grad,short.diff_grad)
        self.assertLess(short.acq_b_nominal[0], .92*axis.acq_b_nominal[0])


if __name__ == '__main__':
    unittest.main()
