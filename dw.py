#!/usr/bin/env python3
"""
dw.py - one command for the DW-FSE pipeline:  generate -> view -> simulate -> plot -> compare.

    python dw.py run base                          # PPR -> seq -> view -> simulate -> plots in runs/base/
    python dw.py run te60 --set te=60              # same with one PPR parameter changed
    python dw.py run b1 --b1 0.8 0.9 1.0 1.1       # B1 sweep
    python dw.py run ex3 --seq examples/ex3_cpmg_train.seq    # any existing .seq
    python dw.py compare runs/base runs/te60       # overlay the results

Single steps:
    python dw.py gen OUT.seq [--set k=v ...] [--params f.json] [--ppr f.ppr] [--full] [--report]
    python dw.py view SEQ [--out DIR] [--blocks A B | --t0 MS --t1 MS] [--mark B ...]
    python dw.py sim SEQ [--out DIR] [--b1 ...] [--b0 ...] [--T1 --T2 --T2p --n] [--snaps adc|rf|none|blocks:3,7|times:18.5]
    python dw.py plot RUN_DIR [--snaps 1 2]
    python dw.py epg SEQ [mrzero options]          # echo-pathway (EPG/PDG) analysis, needs MRzeroCore
    python dw.py rf [--out DIR]                    # RF pulse models and slice profiles

Generator parameters are the PPR variable names (see README.md); `run` and `gen` make the
reduced simulation cut by default (one slice, one b-value row, one shot, timing per TR unchanged);
add --full for the whole protocol.
"""
import argparse
import json
import os
import shutil
import sys

import matplotlib

if not os.environ.get('DISPLAY') and sys.platform.startswith('linux'):
    matplotlib.use('Agg')

from dwfse import generate, results, simulate, view  # noqa: E402

RUNS = 'runs'


# ------------------------------------------------------------------ argument groups
def add_gen_args(ap):
    g = ap.add_argument_group('sequence generation (from the PPR)')
    g.add_argument('--ppr', help='PPR file (default scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppr)')
    g.add_argument('--params', help='JSON file of parameter overrides')
    g.add_argument('--set', action='append', default=[], metavar='KEY=VALUE',
                   help='override one parameter (lists: a,b,c or JSON); repeatable')
    g.add_argument('--full', action='store_true', help='whole protocol instead of the reduced simulation cut')


def add_sim_args(ap):
    g = ap.add_argument_group('simulation')
    g.add_argument('--b1', type=float, nargs='+', default=[1.0], help='B1 scale(s)')
    g.add_argument('--b0', type=float, nargs='+', default=[0.0], help='global off-resonance(s) [Hz]')
    g.add_argument('--T1', type=float, default=1.5, help='[s]')
    g.add_argument('--T2', type=float, default=0.08, help='[s]')
    g.add_argument('--T2p', type=float, default=0.03, help="T2' (intravoxel B0 spread) [s]")
    g.add_argument('--n', type=int, default=20000, help='isochromats')
    g.add_argument('--snaps', default='adc',
                   help="snapshots: adc (every echo centre), rf (end of every RF block), none, "
                        "blocks:3,7,11 or times:18.5,54.9 (ms)")


def overrides(a):
    ov = {}
    if a.params:
        with open(a.params) as f:
            ov.update(json.load(f))
    ov.update(dict(generate.parse_set(s) for s in a.set))
    return ov


def make_seq(a, out_seq):
    C = generate.load_params(a.ppr, overrides(a))
    seq, C, D, log = generate.build_sequence(C, reduced=not a.full)
    ok, rep = seq.check_timing()
    seq.write(out_seq)
    base = os.path.splitext(out_seq)[0]
    with open(base + '.params.json', 'w') as f:
        json.dump(generate.params_dict(C), f, indent=1, default=str)
    txt = generate.report(C, D) + f"\ncheck_timing: {'PASS' if ok else 'FAIL ' + str(rep[:3])}" \
        + f"\nduration {seq.duration()[0]:.6f} s, {len(seq.block_events)} blocks"
    with open(base + '.gen.txt', 'w') as f:
        f.write(txt + '\n')
    return txt


def run_sim(a, seq_path, out_dir):
    r = simulate.run(seq_path, b1=a.b1, b0=a.b0, T1=a.T1, T2=a.T2, T2prime=a.T2p, n=a.n, snaps=a.snaps)
    os.makedirs(out_dir, exist_ok=True)
    simulate.save_npz(os.path.join(out_dir, 'results.npz'), r)
    with open(os.path.join(out_dir, 'sim_settings.json'), 'w') as f:
        json.dump(dict(seq=seq_path, b1=a.b1, b0=a.b0, T1=a.T1, T2=a.T2, T2prime=a.T2p, n=a.n, snaps=a.snaps), f, indent=1)


# ------------------------------------------------------------------ commands
def cmd_gen(a):
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    txt = make_seq(a, a.out)
    if a.report:
        print(txt)
    print(f'wrote {a.out} (+ .params.json, .gen.txt)')


def cmd_view(a):
    out = a.out or os.path.splitext(a.seq)[0] + '_view'
    txt = view.view(a.seq, out=out, blocks=a.blocks, t0=a.t0, t1=a.t1, marks=a.mark, show=a.show)
    print(txt)
    print(f'\nwrote {out}/view.txt, diagram.png, kspace.png')


def cmd_sim(a):
    out = a.out or os.path.splitext(a.seq)[0] + '_sim'
    run_sim(a, a.seq, out)
    results.plot_run(out)
    print(results.summary_text(out))
    print(f'\nwrote {out}/results.npz and plots')


def cmd_plot(a):
    names = results.plot_run(a.run_dir, snaps=a.snaps)
    print(results.summary_text(a.run_dir))
    print('wrote', ', '.join(f'{n}.png' for n in names))


def cmd_run(a):
    d = os.path.join(RUNS, a.name)
    os.makedirs(d, exist_ok=True)
    seq_path = os.path.join(d, 'seq.seq')
    if a.seq:
        shutil.copyfile(a.seq, seq_path)
        print(f'[1/4] copied {a.seq}')
    else:
        txt = make_seq(a, seq_path)
        print('[1/4] generated', seq_path, '\n      ' + '\n      '.join(txt.splitlines()[-6:]))
    view.view(seq_path, out=d)
    print(f'[2/4] viewed  -> {d}/view.txt, diagram.png, kspace.png')
    print('[3/4] simulating ...')
    run_sim(a, seq_path, d)
    results.plot_run(d)
    summ = results.summary_text(d)
    with open(os.path.join(d, 'summary.txt'), 'w') as f:
        f.write(summ + '\n')
    print(f'[4/4] plotted -> {d}/signal.png, echoes.png, snapshots.png\n')
    print(summ)


def cmd_compare(a):
    out = results.compare(a.runs, a.out)
    print('wrote', out)


def cmd_epg(a):
    from dwfse import epg
    epg.main([a.seq] + a.rest)


def cmd_rf(a):
    from dwfse import rf_pulses
    rf_pulses.main(a.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('run', help='generate (or copy) + view + simulate + plot into runs/NAME/')
    p.add_argument('name')
    p.add_argument('--seq', help='use this .seq instead of generating one')
    add_gen_args(p)
    add_sim_args(p)
    p.set_defaults(f=cmd_run)

    p = sub.add_parser('gen', help='PPR -> .seq')
    p.add_argument('out')
    add_gen_args(p)
    p.add_argument('--report', action='store_true', help='print the PPL-style report')
    p.set_defaults(f=cmd_gen)

    p = sub.add_parser('view', help='diagram with numbered blocks + timing/moment/b/k-space checks')
    p.add_argument('seq')
    p.add_argument('--out')
    p.add_argument('--blocks', nargs=2, type=int)
    p.add_argument('--t0', type=float)
    p.add_argument('--t1', type=float)
    p.add_argument('--mark', nargs='*', type=int, default=[])
    p.add_argument('--show', action='store_true', help='open the figures')
    p.set_defaults(f=cmd_view)

    p = sub.add_parser('sim', help='Bloch-simulate a .seq')
    p.add_argument('seq')
    p.add_argument('--out')
    add_sim_args(p)
    p.set_defaults(f=cmd_sim)

    p = sub.add_parser('plot', help='re-plot a run / sim folder')
    p.add_argument('run_dir')
    p.add_argument('--snaps', nargs='*', type=int)
    p.set_defaults(f=cmd_plot)

    p = sub.add_parser('compare', help='overlay results of several runs')
    p.add_argument('runs', nargs='+')
    p.add_argument('--out')
    p.set_defaults(f=cmd_compare)

    p = sub.add_parser('epg', help='echo-pathway analysis (MRzeroCore)')
    p.add_argument('seq')
    p.add_argument('rest', nargs=argparse.REMAINDER)
    p.set_defaults(f=cmd_epg)

    p = sub.add_parser('rf', help='RF pulse models and slice profiles')
    p.add_argument('--out', default='rf')
    p.set_defaults(f=cmd_rf)

    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
