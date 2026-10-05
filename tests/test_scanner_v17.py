import re
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pypulseq as pp

from dwfse import crushers
from dwfse.btensor import calculate, export, integrate_interval
from dwfse.generate import PPLAbort, build_sequence, derive, load_params, read_ppr
from dwfse.simulate import read_seq
from examples.audit_pe_memory import replay

ROOT = Path(__file__).resolve().parents[1]
STEM = ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.7'
PPR = str(STEM) + '.ppr'
BASE = dict(views_per_seg=8, no_views=16, te=36, esp=16,
            acq_b=[0, 1000] + [0]*510, no_diff_acq=2, no_experiments=2,
            acq_x=[1000, 1000] + [0]*510, sim_reduced_shots=[1])


def experimental_ppr(suffix):
    # Protocols were moved into the dated scanner experiment folders.
    name = f'FSE_dwi_CPMG_non_CPMG_twoTE-1.7{suffix}.ppr'
    candidates = [STEM.parent/name, *sorted((ROOT/'experiments').glob(f'*/{name}'))]
    return next(p for p in candidates if p.is_file())


class CrusherScheduleTests(unittest.TestCase):
    def test_exact_schedules_and_signed_half_up_rounding(self):
        up = [2754, 5482, 7675, 9868, 12060, 14253, 16446, 18639]
        expected = [[2754] + [5482]*7, up,
                    [2754, -5482, 5482, -5482, 5482, -5482, 5482, -5482],
                    [v*(-1 if k%2 else 1) for k,v in enumerate(up)],
                    [2754] + up[1:][::-1]]
        for mode, values in enumerate(expected):
            self.assertEqual(crushers.schedule(8,2754,5482,mode,40), values)
        custom = [100,100,171,83,137,213,109,191] + [0]*56
        expected_irregular = [2754,5482,9374,4550,7510,11677,5975,10471]
        self.assertEqual(crushers.schedule(8,2754,5482,5,0,8,custom),expected_irregular)
        self.assertEqual(crushers.schedule(2,-1,-1,5,0,2,[150,-150]+[0]*62),[-2,2])

    def test_etl_one_two_and_capacity_without_repeat(self):
        for mode in range(5):
            self.assertEqual(crushers.schedule(1,2754,5482,mode,40),[2754])
            self.assertEqual(crushers.schedule(2,2754,5482,mode,40),
                             [2754,-5482 if mode in (2,3) else 5482])
        self.assertEqual(len(crushers.schedule(1024,0,1,1,1)),1024)
        for etl in (0,-1,1025,1.5):
            with self.subTest(etl=etl), self.assertRaises(ValueError):
                crushers.schedule(etl,1,1)
        for count, table, etl in [(7,[100]*64,8),(8,[100]*8,8),(65,[100]*64,65)]:
            with self.assertRaises(ValueError):
                crushers.schedule(etl,1,1,5,0,count,table)

    def test_rejection_precedes_overflow_and_hardware_clipping(self):
        with self.assertRaises(ValueError):
            crushers.schedule(1024,32767,32767,1,1000)
        cases = [dict(first=-32768),dict(mode=6),dict(step_pct=-1),
                 dict(max_dac=2000),dict(slew_dac_100us=100),dict(ramp_us=205),
                 dict(mode=1,step_pct=1000)]
        for change in cases:
            args = dict(etl=8,first=2754,train=5482)
            args.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                crushers.schedule(**args)
        # Guard itself tested where a representable factor would overflow.
        with self.assertRaisesRegex(ValueError,'overflow'):
            crushers.rounded_magnitude(32767,65539)

    def test_matrix_pair_alternation_final_pulse_and_reset(self):
        values = crushers.schedule(8,2754,5482,3,40)
        trace = crushers.matrix_trace(values,trains=12)
        for shot in range(12):
            pairs = [x for x in trace if x[0]==shot and x[1]=='pair']
            self.assertEqual([x[2] for x in pairs],[21,22]*4)
            self.assertEqual([x[3][1] for x in pairs],values)
            self.assertTrue(all(x[3][1]==x[3][2] for x in pairs))
            updates = [x for x in trace if x[0]==shot and x[1]=='prepare_under_aq']
            self.assertEqual(len(updates),7)
            self.assertEqual([x[3] for x in updates],values[1:])

    def test_adc_window_is_repartitioned_without_duration_change(self):
        original = crushers.acquisition_budget(128,0,500,0)
        scheduled = crushers.acquisition_budget(128,0,500,1)
        self.assertEqual(scheduled[0]-original[0],10000)
        self.assertEqual(original[1]-scheduled[1],1)
        self.assertEqual(original[2],scheduled[2])
        for period in (100,200):
            with self.assertRaises(ValueError):
                crushers.acquisition_budget(64,0,period,1)


class ScannerIntegrationTests(unittest.TestCase):
    def build(self, **extra):
        return build_sequence(ppr=PPR,reduced=True,overrides=dict(BASE,**extra))

    def test_pprs_match_native_storage_and_keep_calibration(self):
        old = read_ppr(ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppr')
        for name,mode in [('',0),('-increasing',1),('-increasing-alternating',3)]:
            path = Path(PPR) if not name else experimental_ppr(name)
            new = read_ppr(path)
            self.assertEqual(len(new['crusher_custom_pct']),64)
            self.assertEqual(new['crusher_schedule'],mode)
            for key in ('rfnum','p180_scale','rfcal','alpha','phase_cycle','phcor0','rfdelay'):
                self.assertEqual(new[key],old[key])
            if mode:
                d = derive(load_params(path))
                self.assertGreater(d.diff_grad[1],0)
                self.assertEqual(d.diff_grad[0],1)  # preserve b=0 workaround

    def test_ppl_directive_identifies_a_renamed_protocol(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'water.ppr'
            path.write_bytes(Path(PPR).read_bytes())
            c = load_params(path)
        self.assertEqual(c.scanner_version,'1.7')
        self.assertTrue(c.sim_fix_refocus_centering)

    def test_single_echo_playback_uses_only_special_baseline(self):
        for mode in range(5):
            seq,c,d,log = self.build(views_per_seg=1,no_views=2,PE_order=5,
                                     crusher_schedule=mode,crusher_step_pct=40,
                                     sim_reduced_shots=[0])
            self.assertTrue(seq.check_timing()[0])
            self.assertEqual(d.train_crusher_amplitudes_dac,[2754])
            payload,_ = calculate(seq)
            self.assertEqual(len(payload['echoes']),2)

    def test_defaults_equal_baseline_apart_from_intentional_centering(self):
        _,_,old,old_log = build_sequence(reduced=True,overrides=BASE)
        _,_,new,new_log = self.build()
        a,b = old_log[0]['train'],new_log[0]['train']
        self.assertEqual([(r['start'],r['dur'],r['phase'],r['flip']) for r in a.rf],
                         [(r['start'],r['dur'],r['phase'],r['flip']) for r in b.rf])
        self.assertEqual(a.adc,b.adc)
        self.assertEqual(a.g['r'][0],b.g['r'][0])
        self.assertEqual(a.g['r'][3:],b.g['r'][3:])
        for before,after in zip(a.g['r'][1:3],b.g['r'][1:3]):
            self.assertEqual([(t-600,v) for t,v in before],after)
        self.assertEqual(a.g['p'],b.g['p'])
        self.assertEqual(old.crush_pre_pad+old.crush_post_pad,
                         new.crush_pre_pad+new.crush_post_pad)
        for x,y in zip(a.g['s'][1:9],b.g['s'][1:9]):
            self.assertEqual([v for _,v in x],[v for _,v in y])
            self.assertEqual([t-600 for t,_ in x],[t for t,_ in y])
        self.assertEqual(tuple(t-600 for t in a.l1),b.l1)
        self.assertEqual(tuple(t-600 for t in a.l2),b.l2)
        # The independent pads are the sole intentional waveform difference.
        seq,_,_,log = self.build(sim_fix_refocus_centering=False)
        self.assertEqual(log[0]['train'].g,a.g)
        self.assertTrue(seq.check_timing()[0])

    def test_matching_lobes_and_centres_for_all_native_modes(self):
        _,_,_,baseline = self.build()
        for mode in range(1,6):
            extra = dict(crusher_schedule=mode,crusher_step_pct=40)
            if mode == 5:
                extra.update(crusher_custom_count=8,
                             crusher_custom_pct=[100,100,171,83,137,213,109,191]+[0]*56)
            seq,c,d,log = self.build(**extra)
            self.assertTrue(seq.check_timing()[0])
            train = log[0]['train']
            self.assertEqual(train.rf,baseline[0]['train'].rf)
            self.assertEqual(train.adc,baseline[0]['train'].adc)
            for k,(segment,amp) in enumerate(zip(train.g['s'][1:9],d.train_crusher_amplitudes_dac)):
                pre,post = segment[:4],segment[-4:]
                self.assertEqual([v for _,v in pre],[v for _,v in post])
                self.assertEqual([t-pre[0][0] for t,_ in pre],
                                 [t-post[0][0] for t,_ in post])
                self.assertEqual(pre[1][1],amp)
            self.assertEqual(train.g['r'],baseline[0]['train'].g['r'])
            self.assertEqual(train.g['p'],baseline[0]['train'].g['p'])

    def test_generator_rejects_conflicting_controls_and_limits(self):
        for extra in [dict(crusher_schedule=1,crusher_max_dac=1000),
                      dict(crusher_schedule=1,crusher_slew_dac_100us=100),
                      dict(crusher_schedule=1,sim_train_crusher_scales=[1]*8),
                      dict(crusher_schedule=1,crush_independent_on=0),
                      dict(crusher_schedule=5,crusher_custom_count=7),
                      dict(hw_max_grad_hz_per_m=0),
                      dict(hw_max_slew_hz_per_m_per_s=float('inf'))]:
            with self.subTest(extra=extra),self.assertRaises(PPLAbort):
                self.build(**extra)
        for extra in (dict(hw_max_grad_hz_per_m=1),dict(hw_max_slew_hz_per_m_per_s=1)):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.build(**extra)

    def test_full_protocol_resets_dummies_slices_rows_experiments(self):
        seq,c,d,log = build_sequence(ppr=PPR,reduced=False,overrides=dict(
            BASE,crusher_schedule=3,crusher_step_pct=40,no_disacq=1,no_slices=2,
            no_experiments=4))
        self.assertTrue(seq.check_timing()[0])
        self.assertGreater(len(log),8)
        self.assertEqual({x['pos'] for x in log},{0,1})
        self.assertEqual({x['row'] for x in log},{0,1})
        for item in log:
            train = item['train']
            self.assertEqual([s[1][1] for s in train.g['s'][1:9]],
                             d.train_crusher_amplitudes_dac)
        payload,_ = calculate(seq)
        self.assertEqual(len(payload['echoes']),sum(not item['dummy'] for item in log)*8*2)

    def test_navigator_train_resets_same_schedule(self):
        seq,c,d,log = build_sequence(ppr=PPR,reduced=False,overrides=dict(
            BASE,crusher_schedule=1,crusher_step_pct=40,no_disacq=0,nav_on=1,no_views=24))
        self.assertTrue(seq.check_timing()[0])
        self.assertEqual({x['nav'] for x in log},{False,True})
        for item in log:
            self.assertEqual([s[1][1] for s in item['train'].g['s'][1:9]],
                             d.train_crusher_amplitudes_dac)

    def test_source_execution_contract_and_include_macro_collision(self):
        source = (Path(str(STEM)+'.ppl')).read_text(encoding='latin-1')
        # Every new variable has explicit scanner-language storage. This also
        # catches misspelled names which a source-string hook test would miss.
        code = re.sub(r'/\*.*?\*/|//[^\n]*|\\\\[^\n]*','',source,flags=re.S)
        code = re.sub(r'"(?:[^"\\]|\\.)*"','',code)
        used = set(re.findall(r'\bcrusher_\w+\b',code))
        declared = set()
        for declaration in re.findall(r'\b(?:int|long)\s+([^;]+);',code):
            declared.update(re.findall(r'\bcrusher_\w+\b',declaration))
        labels = set(re.findall(r'\b(crusher_\w+):',code))
        self.assertEqual(used-declared-labels,set())
        self.assertNotRegex(source,r'\brefocus_mat\b(?! as macro)')
        macro = source.split('#define PREPARE_NEXT_CRUSHER ',1)[1].split('\n\n',1)[0]
        self.assertIn('total_echo_cnt<crusher_etl',macro)
        self.assertIn('crusher_dac[total_echo_cnt]',macro)
        self.assertEqual(macro.count('delay(caldelay,us)'),2)
        self.assertIn('CREATE_MATRIX(crusher_play_mat+256',macro)
        self.assertNotIn('MR3040_SelectMatrix',macro)
        adc = source.split('initiate(sample_period);',1)[1].split('complete();',1)[0]
        self.assertLess(adc.index('total_echo_cnt = total_echo_cnt+1'),adc.index('PREPARE_NEXT_CRUSHER'))
        self.assertIn('if (crusher_schedule!=0) ret=CRUSHER_ADC_TICKS',adc)
        benchmark = source.index('crusher_update_benchmark:')
        self.assertLess(benchmark,source.index('/* [MERGE-2TE] M1'))
        self.assertLess(benchmark,source.index('initiate(sample_period);'))
        # Gradient lists retain two identical SEC macros around the primary.
        for label in ('slice_180_refocus =','slice_180_refocus_diff ='):
            block = source.split(label,1)[1].split('\n\telse',1)[0]
            lobes = re.findall(r'POSPULSE_SEC\((\w+), clock\)',block)
            self.assertEqual(len(lobes),2)
            self.assertEqual(lobes[0],lobes[1])

    def test_setup_guard_reserves_timer_overhead_without_extending_window(self):
        source = Path(str(STEM)+'.ppl').read_text(encoding='latin-1')
        self.assertRegex(source, r'\bint crusher_setup_ticks;')
        setup = source.split('// [CRUSH-SCHED] DWI setup creates',1)[1].split('resync();',1)[0]
        self.assertEqual(setup.count('gettimer()'),1)
        self.assertIn('crusher_setup_ticks = gettimer();',setup)
        self.assertIn('if ((crusher_setup_ticks<0)||(crusher_setup_ticks>24500))',setup)
        self.assertIn('goto end;',setup)
        self.assertIn('waittimer(30000);',setup)
        self.assertLess(setup.index('goto end;'),setup.index('waittimer(30000);'))
        self.assertNotIn('18000',setup)
        benchmark = source.split('crusher_update_benchmark:',1)[1].split('pos_index=pos_index+1;',1)[0]
        self.assertIn('if ((crusher_update_ticks<0L)||(crusher_update_ticks>CRUSHER_UPDATE_MAX_TICKS))',benchmark)


class ScratchAndTensorTests(unittest.TestCase):
    def test_pe0_all_reserved_region_boundaries_and_replayed_corruption(self):
        crushers.pe0_capacity(128,4,1024)
        crushers.pe0_capacity(255,1,510)
        for args in [(256,2,1024),(512,1,1024),(4,256,1024),(3,1,6)]:
            with self.assertRaises(ValueError):
                crushers.pe0_capacity(*args)
        with self.assertRaisesRegex(ValueError,'DWI'):
            crushers.pe0_capacity(8,1,16,True)
        self.assertEqual(replay()['mismatch_count'],3)

    def test_analytic_ramp_tensor_including_off_diagonals(self):
        gradient = np.array([2e4,-1e4,3e4])
        duration = .002
        q,b = integrate_interval(np.zeros(3),np.zeros(3),gradient,duration)
        expected = np.pi**2 * np.outer(gradient,gradient)*duration**3/5*1e-6
        np.testing.assert_allclose(b,expected,rtol=1e-14,atol=1e-15)
        np.testing.assert_allclose(q,np.pi*gradient*duration)
        self.assertLess(b[0,1],0)

    def test_refocusing_sign_cancels_equal_lobes_and_excitation_resets_tensor(self):
        system = pp.Opts(max_grad=1e6,grad_unit='Hz/m',max_slew=1e10,slew_unit='Hz/m/s',
                         rf_dead_time=0,rf_ringdown_time=0,adc_dead_time=0)
        seq = pp.Sequence(system)
        lobe = pp.make_trapezoid('x',amplitude=10000,rise_time=.0001,
                                flat_time=.001,fall_time=.0001,system=system)
        for _ in range(2):
            seq.add_block(pp.make_block_pulse(np.pi/2,duration=10e-6,use='excitation',system=system))
            seq.add_block(lobe)
            seq.add_block(pp.make_delay(.003))
            seq.add_block(pp.make_block_pulse(np.pi,duration=10e-6,use='refocusing',system=system))
            seq.add_block(pp.make_delay(.003))
            seq.add_block(lobe)
            seq.add_block(pp.make_adc(10,dwell=1e-6,system=system))
        payload,_ = calculate(seq)
        echoes = [x for x in payload['echoes'] if x['convention']=='centre']
        self.assertEqual([x['train'] for x in echoes],[1,2])
        for echo in echoes:
            np.testing.assert_allclose(echo['q_rad_m'],[0,0,0],atol=1e-9)
            self.assertGreater(echo['B_s_mm2'][0][0],0)
            self.assertEqual(echo['B_s_mm2'][1][1],0)
        np.testing.assert_allclose(echoes[0]['B_s_mm2'],echoes[1]['B_s_mm2'],atol=1e-9)

    def test_complete_tensor_is_symmetric_psd_and_echo_dependent(self):
        seq,_,_,_ = build_sequence(ppr=experimental_ppr('-increasing'),reduced=True,
                                   overrides={'sim_reduced_shots':[1]})
        payload,(times,left,right) = calculate(seq)
        centres = [x for x in payload['echoes'] if x['convention']=='centre']
        self.assertEqual(len(centres),8)
        for echo in centres:
            b = np.array(echo['B_s_mm2'])
            np.testing.assert_allclose(b,b.T,atol=1e-10)
            self.assertGreater(np.linalg.eigvalsh(b).min(),-1e-9)
        self.assertAlmostEqual(centres[0]['trace_s_mm2'],1119.548,places=2)
        self.assertAlmostEqual(centres[-1]['trace_s_mm2'],1236.771,places=2)
        self.assertGreater(abs(centres[-1]['B_s_mm2'][0][2]),20)
        self.assertGreater(np.max(abs(left[:,0])),0)  # diffusion/read
        self.assertGreater(np.max(abs(left[:,1])),0)  # imaging PE
        self.assertGreater(np.max(abs(left[:,2])),0)  # slice/crushers
        self.assertAlmostEqual(times[-1],2.0)  # complete TR exported

    def test_waveform_export_after_readback_preserves_sample_and_slice_context(self):
        import json
        seq,_,_,_ = build_sequence(ppr=experimental_ppr('-increasing'),reduced=True)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'sequence.seq'
            seq.write(str(path))
            payload = export(read_seq(path),Path(folder)/'tensor')
            saved = json.loads((Path(folder)/'tensor/btensor.json').read_text())
            self.assertEqual(payload,saved)
            self.assertTrue((Path(folder)/'tensor/waveform.csv').is_file())
        centres = [x for x in payload['echoes'] if x['convention']=='centre']
        samples = [x for x in payload['echoes'] if x['convention']=='sample']
        self.assertTrue(all(x['labels']['SLC']==0 for x in centres))
        self.assertEqual(len(centres),8)
        np.testing.assert_allclose([s['time_s']-c['time_s'] for s,c in zip(samples,centres)],
                                   [25e-6]*8,atol=1e-12)


if __name__ == '__main__':
    unittest.main()
