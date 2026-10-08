"""Fast regression checks of the v191/v192 PPLs through the source-level event mapper.

These test the generated PPL source under the repository's nominal instruction-
cost model (dwfse/ppl). They are not compiler or console validation.
"""
from pathlib import Path
import hashlib
import json
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events, load_program  # noqa: E402
from dwfse.ppl.ledger import build_ledger  # noqa: E402
from dwfse.ppl.events import rf_pulses  # noqa: E402
from dwfse.ppl.preprocess import Preprocessor  # noqa: E402

SC = ROOT / "scanner"
V18 = SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl"
CTRL = ROOT / "experiments/FSE-DWI_10-05-2026_v18_test1e/FSE-DWI_10-05-2026_v18_test1.ppr"
V191 = SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl"
V192 = SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl"
MODEL = {"stmt_cost_us": 0.0, "expr_costs": True, "expr_scale": 0.8}


def rf_sig(it):
    rf = [p for p in rf_pulses(it) if p.get("library")]
    t0 = rf[0]["t_go"]
    return [(round(p["t_go"] - t0, 3), p["frame"], p["mul"], p["phase_units"]) for p in rf]


class V19MapperTests(unittest.TestCase):
    def test_console_cpp_compatibility(self):
        for ppl in (V191, V192):
            source = ppl.read_text(encoding='latin-1')
            self.assertNotRegex(source, r'^\s*#define V19_\w+\(', ppl.name)
            for line in source.splitlines():
                self.assertIsNone(re.match(r'\s*#define V19_\w+\(', line))
            params = source[source.index('SCROLLBAR "V19 method ON"'):source.index('DSP_ROUTINE "c:')]
            self.assertNotIn('//', params)
            self.assertNotIn('/*', params)
            self.assertNotIn('*/', params)
            toks = Preprocessor([SC / 'utilities', SC]).run(ppl)
            computational, i = [], 0
            while i < len(toks):
                if toks[i].value == 'printf' and toks[i + 1].value == '(':
                    if toks[i + 2].value.startswith('"V19'):
                        self.assertLessEqual(len(toks[i + 2].value[1:-1]), 48)
                    i += 2
                    depth = 1
                    while depth:
                        if toks[i].kind != 'str':
                            depth += (toks[i].value == '(') - (toks[i].value == ')')
                        i += 1
                    self.assertEqual(toks[i].value, ';')
                    i += 1
                else:
                    self.assertFalse(toks[i].value.startswith('v19_') and toks[i + 1].value == '(', toks[i])
                    computational.append((toks[i].kind, toks[i].value))
                    i += 1
            self.assertNotRegex(source, r'==-32768(?![\w])')

    def test_setup_reduction_preserves_pulse_gradient_and_adc_events(self):
        def relative(items, sync):
            return [(round(row[0] - sync, 6), *row[1:]) for row in items if row[0] >= sync]
        for label, ppl in (('v191', V191), ('v192', V192)):
            prior = ROOT / f'docs/v19/compiler_compatibility/pre_scratch_{label}.ppl.txt'
            for overrides in ({}, {'rfcal': 550}, {'v19_comp_flat': 800},
                              {'crush_amp': -8173, 'diff_crush_amp': -5427}):
                old = map_events(prior, ppl.with_suffix('.ppr'), overrides=overrides, max_shots=1, **MODEL)
                new = map_events(ppl, ppl.with_suffix('.ppr'), overrides=overrides, max_shots=1, **MODEL)
                self.assertEqual(rf_sig(old), rf_sig(new))
                self.assertEqual([round(a['t_init'] - old.sync_t, 6) for a in old.adc],
                                 [round(a['t_init'] - new.sync_t, 6) for a in new.adc])
                # List ids shift because CHESS/MTC setup lists are no longer
                # compiled; the played waveforms below must not change.
                for axis in old.grad.ch:
                    def segments(it):
                        return [(round(a-it.sync_t, 6), round(b-it.sync_t, 6), p, q)
                                for a,b,p,q in it.grad.ch[axis].segments if b >= it.sync_t]
                    self.assertEqual(segments(old), segments(new))
                for name in old.vars:
                    # v19_l_* hold gradient-list handles, renumbered with the list ids.
                    if name.startswith('v19_') and not name.startswith('v19_l_'):
                        if name == 'v19_mul':
                            self.assertEqual(old.vars[name].value[:8], new.vars['crusher_dac'].value[:8])
                        else:
                            self.assertEqual(old.vars[name].value, new.vars[name].value, (label, name, overrides))

    def test_compact_failure_handler_and_array_overlay(self):
        for ppl in (V191, V192):
            source = ppl.read_text(encoding='latin-1')
            self.assertIn('#define v19_mul crusher_dac', source)
            self.assertNotIn('v19_mul[64];', source)
            self.assertEqual(source.count('v19_fail:'), 1)
            self.assertIn('printf("Duration=%ld\\n", tr * templ1 * no_experiments);', source)
            for ov in ({'v19_cycles': 4}, {'te': 52}, {'crusher_schedule': 1}):
                it = map_events(ppl, ppl.with_suffix('.ppr'), overrides=ov, max_shots=1, **MODEL)
                self.assertEqual(len(it.adc), 0)
                self.assertTrue(any('V19 error E' in msg for _, msg in it.out), ov)

    def test_method_only_rejects_control_mode_and_large_tables(self):
        # The v18 path is not compiled in: v19_on=0 must stop before any
        # calculation, never fall into the method shot without its setup.
        for ppl in (V191, V192):
            source = ppl.read_text(encoding='latin-1')
            self.assertNotIn('v19_mode==1) goto v19_mat_window', source)
            self.assertIn('#define MAX_DIFF_ACQ 64', source)
            self.assertIn('#define MAX_CRUSHER_ETL 64', source)
            for name in ('acq_b', 'acq_grad', 'acq_x', 'acq_y', 'acq_z'):
                self.assertRegex(source, r'VAR_ARRAY [^\n]*,' + name + r', 64;')
                self.assertRegex(ppl.with_suffix('.ppr').read_text(encoding='latin-1'),
                                 r':VAR_ARRAY ' + name + r', 64,')
            for ov in ({'v19_on': 0}, {'v19_on': 2}, {'no_diff_acq': 65}, {'no_diff_acq': 0}):
                it = map_events(ppl, ppl.with_suffix('.ppr'), overrides=ov, max_shots=1, **MODEL)
                self.assertEqual(len(it.adc), 0, ov)
                self.assertEqual(len([p for p in rf_pulses(it) if p.get("library")]), 0, ov)
                self.assertNotEqual(it.vars['v19_error_code'].value, 0, ov)
                self.assertEqual(it.vars['v19_mode'].value, 0, ov)

    def test_successful_validator_report_preserved(self):
        ref = map_events(V18, CTRL, overrides={'validate': 1}, max_shots=1, **MODEL)
        expected = [msg for _,msg in ref.out if msg.startswith('Duration=')]
        self.assertTrue(expected)
        for ppl in (V191, V192):
            it = map_events(ppl, ppl.with_suffix('.ppr'), overrides={'validate': 1}, max_shots=1, **MODEL)
            self.assertEqual([msg for _,msg in it.out if msg.startswith('Duration=')], expected)
            self.assertEqual(it.vars['v19_error_code'].value, 0)
            self.assertEqual(len(it.adc), 0)

    def test_forward_label_references_fit_pplc(self):
        # PPLC raised E106 at the 147th forward goto in every failing build;
        # v18 compiles with 145. Keep a wide margin below that.
        for ppl in (V18, V191, V192):
            toks = Preprocessor([SC / 'utilities', SC]).run(ppl)
            labels = {}
            for i, t in enumerate(toks[:-1]):
                if (t.kind == 'id' and toks[i + 1].value == ':' and
                        toks[i - 1].value in (';', '}', '{', ':')):
                    labels.setdefault(t.value, i)
            gotos = [(i, toks[i + 1].value) for i, t in enumerate(toks) if t.value == 'goto']
            self.assertTrue(all(name in labels for _, name in gotos), ppl.name)
            forward = sum(labels[name] > i for i, name in gotos)
            self.assertLessEqual(forward, 145 if ppl is V18 else 40, ppl.name)

    def test_long_to_int_warnings_match_v18(self):
        # PPLC counts warnings toward its 20-message abort. W008 (long passed to
        # an int parameter) and W007 (long delay) must not grow beyond v18's.
        def warnings(ppl):
            program = load_program(ppl)[0]
            types = {}
            def collect(n):
                if isinstance(n, dict):
                    n = list(n.values())
                if isinstance(n, tuple) and n and n[0] == 'decl':
                    types.update((name.lower(), n[1]) for name, _, _ in n[3])
                if isinstance(n, (tuple, list)):
                    for x in n:
                        collect(x)
            collect(program)
            def is_long(e):
                k = e[0]
                if k == 'num': return e[2]
                if k in ('var', 'index'): return types.get(e[1].lower()) == 'long'
                if k == 'call': return e[1].lower() in ('inttolong', 'unsignedtolong')
                if k == 'un': return e[1] != '!' and is_long(e[2])
                if k == 'bin': return e[1] not in ('==', '!=', '<', '>', '<=', '>=', '&&', '||') and (is_long(e[2]) or is_long(e[3]))
                return k == 'assign' and is_long(e[1])
            found = []
            long_params = {'delay32': 0, 'scale': 0, 'loword': 0, 'hiword': 0}
            def walk(n):
                if isinstance(n, dict):
                    n = list(n.values())
                if isinstance(n, tuple) and n and n[0] == 'call' and n[1].lower() != 'printf':
                    found.extend((n[1].lower(), i) for i, a in enumerate(n[2])
                                 if is_long(a) and long_params.get(n[1].lower()) != i)
                if isinstance(n, (tuple, list)):
                    for x in n:
                        walk(x)
            walk(program)
            return sorted(found)
        reference = warnings(V18)
        self.assertEqual(len(reference), 11)
        for ppl in (V191, V192):
            found = warnings(ppl)
            # Method-only builds keep a subset of v18's own warnings.
            self.assertTrue(all(found.count(w) <= reference.count(w) for w in found), ppl.name)

    def test_conditional_blocks_fit_branch_range(self):
        # The .fth stage rejected the conditional branch over a 3230-node method
        # setup ("error branch is out of range"); v18's largest body is 369.
        def size(n):
            if isinstance(n, tuple):
                if n and n[0] in ('label', 'decl', 'nop'):
                    return 0
                return 1 + sum(size(x) for x in n if isinstance(x, (tuple, list)))
            return sum(size(x) for x in n) if isinstance(n, list) else 0
        def largest(ppl):
            sizes = []
            def walk(n):
                if isinstance(n, dict):
                    n = list(n.values())
                if isinstance(n, tuple) and n:
                    if n[0] == 'if':
                        sizes.extend(size(b) for b in n[2:4] if b is not None)
                    elif n[0] in ('do', 'for'):
                        sizes.append(size(n[1] if n[0] == 'do' else n[2]))
                if isinstance(n, (tuple, list)):
                    for x in n:
                        walk(x)
            walk(load_program(ppl)[0])
            return max(sizes)
        limit = largest(V18) * 11 // 10
        for ppl in (V191, V192):
            self.assertLessEqual(largest(ppl), limit, ppl.name)

    def test_rf_libraries_store_vendor_user_expressions(self):
        # WavEd shows a frame from its expression; empty expressions displayed
        # blank. Each research pulse is stored like the vendor opt90_as.seq.
        from dwfse.vendor_seq import decode, user_files
        for ppl in (V191, V192):
            uses = re.findall(r'#use RF1 "g:\\J_Figger\\seqlib\\(v19_\w+\.seq)" pf(\d+)',
                              ppl.read_text(encoding='latin-1'))
            self.assertEqual(len(uses), 6, ppl.name)
            for name, alias in uses:
                lib = decode(SC / 'rf' / name)
                self.assertEqual(len(lib.frames), 1)
                frame = lib.frames[0]
                self.assertEqual(frame.name + '.seq', name)
                (text_name, text), = user_files(lib)
                n = len(frame.samples)
                self.assertEqual(frame.expressions[0], f'{n},user("{text_name}");\0'.encode())
                values = text.decode('ascii').split('\r\n')
                self.assertEqual(values[0], f'{n} 1')
                self.assertEqual([int(v) for v in values[1:-1]], frame.samples.tolist())

    def test_v18_unchanged(self):
        self.assertEqual(hashlib.sha256(V18.read_bytes()).hexdigest(),
                         "3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2")

    def test_method_only_image_below_v18(self):
        # The combined v18+method image overflowed the 64K RTX image (pplsim
        # "step math opcodes", corrupted parameters). Bound the method-only
        # image by v18's: code from AST size at the bytes/node of the console
        # .fth files, plus near arrays and string bytes.
        def size(n):
            if isinstance(n, tuple):
                if n and n[0] in ('label', 'decl', 'nop'):
                    return 0
                return 1 + sum(size(x) for x in n if isinstance(x, (tuple, list)))
            return sum(size(x) for x in n) if isinstance(n, list) else 0
        def image(ppl):
            program = load_program(ppl)[0]
            arrays, strings = 0, 0
            def walk(n):
                nonlocal arrays, strings
                if isinstance(n, dict):
                    n = list(n.values())
                if isinstance(n, tuple) and n:
                    if n[0] == 'decl':
                        for _, dim, _ in n[3]:
                            if dim is not None:
                                arrays += 2 * dim[1]
                    if n[0] == 'str':
                        strings += len(n[1]) + 3
                if isinstance(n, (tuple, list)):
                    for x in n:
                        walk(x)
            walk(program)
            code = sum(size(body) for _, body in program[1].values())
            self.assertGreater(code, 10000, ppl.name)
            return 2.6 * code + arrays + strings
        budget = image(V18) - 4096
        for ppl in (V191, V192):
            self.assertLess(image(ppl), budget, ppl.name)

    def test_method_rf_centres_and_no_hazards(self):
        expect = {V192: [0, 27000, 54000, 61000, 75000], V191: [0, 27000, 54000, 59716, 66716]}
        for ppl, centres in expect.items():
            it = map_events(ppl, ppl.with_suffix(".ppr"), max_shots=1, **MODEL)
            led = build_ledger(it, 1)
            c = [p["t_center"] for p in led["rf"]]
            got = [x - c[0] for x in c[:5]]
            for g, e in zip(got, centres):
                self.assertLess(abs(g - e), 10.0, (ppl.name, got))
            self.assertEqual(len(led["adc"]), 8)
            self.assertFalse([f for f in it.flags if f["kind"] == "timer_overrun"])
            self.assertFalse([f for f in it.flags if "ignored" in f["msg"]])

    def test_rejections_before_events(self):
        for ppl in (V191, V192):
            for ov in ({"te": 52}, {"crush_amp": -2741}, {"no_slices": 2}, {"v19_cycles": 4},
                       {"diff_crush_amp": -1500}, {"diff_crush_amp": -12000},
                       {"crush_amp": -7700}, {"diff_crush_amp": 5482},
                       {"crush_amp": 8223, "diff_crush_amp": 5482}):
                it = map_events(ppl, ppl.with_suffix(".ppr"), overrides=ov, max_shots=1, **MODEL)
                self.assertEqual(len([p for p in rf_pulses(it) if p.get("library")]), 0, ov)
                self.assertEqual(len(it.adc), 0, ov)


if __name__ == "__main__":
    unittest.main()
