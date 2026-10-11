"""Build 10-10-2026_report.pptx from the 09-10 / 09-29 report decks (same theme, tables, fonts).

Run: python docs/data/oct10_build_slides.py
Inputs: 09-10-2026_report.pptx, 09-29-2026_report.pptx (templates, not modified),
docs/data/oct10_slide_numbers.json, docs/figures/oct10_slides/*.png.
"""
from pathlib import Path
import copy, json
from pptx import Presentation
from pptx.util import Inches, Emu
from pptx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT/'docs/figures/oct10_slides'
N = json.loads((ROOT/'docs/data/oct10_slide_numbers.json').read_text())
prs = Presentation(ROOT/'09-10-2026_report.pptx')
ref = Presentation(ROOT/'09-29-2026_report.pptx')
ORIGINAL = list(prs.slides)
BLANK = next(l for l in prs.slide_layouts if l.name == 'BLANK')


def new_slide(src=None, layout=None):
    """New slide; copy non-picture shapes (tables, text boxes, placeholders) from src."""
    s = prs.slides.add_slide(layout or (src.slide_layout if src is not None and src.part.package is prs.part.package else BLANK))
    for ph in list(s.placeholders):
        ph._element.getparent().remove(ph._element)
    if src is not None:
        for sh in src.shapes:
            if sh.shape_type != 13:
                s.shapes._spTree.append(copy.deepcopy(sh._element))
    return s


def shape(s, name):
    return next(sh for sh in s.shapes if sh.name == name)


def set_text(tf_or_cell, lines):
    """Replace text keeping the first run's formatting; one paragraph per line."""
    tf = tf_or_cell.text_frame if hasattr(tf_or_cell, 'text_frame') else tf_or_cell
    paras = tf.paragraphs
    lines = [lines] if isinstance(lines, str) else lines
    tmpl = copy.deepcopy(paras[0]._p)
    for p in paras[1:]:
        p._p.getparent().remove(p._p)
    p0 = paras[0]
    runs = p0.runs
    for r in runs[1:]:
        r._r.getparent().remove(r._r)
    runs[0].text = lines[0]
    for line in lines[1:]:
        p = copy.deepcopy(tmpl)
        for r in p.findall(qn('a:r'))[1:]:
            p.remove(r)
        p.find(qn('a:r')).find(qn('a:t')).text = line
        tf._txBody.append(p)


def resize_table(tbl, rows, col_widths_in):
    """Set row/column counts by cloning the first data row/cell; widths in inches."""
    t = tbl._tbl
    grid = t.find(qn('a:tblGrid'))
    trs = t.findall(qn('a:tr'))
    for tr in trs[2:]:
        t.remove(tr)
    while len(t.findall(qn('a:tr'))) < rows:
        t.append(copy.deepcopy(t.findall(qn('a:tr'))[-1]))
    while len(t.findall(qn('a:tr'))) > rows:
        t.remove(t.findall(qn('a:tr'))[-1])
    cols = grid.findall(qn('a:gridCol'))
    while len(grid.findall(qn('a:gridCol'))) < len(col_widths_in):
        grid.append(copy.deepcopy(cols[-1]))
        for tr in t.findall(qn('a:tr')):
            tr.append(copy.deepcopy(tr.findall(qn('a:tc'))[-1]))
    while len(grid.findall(qn('a:gridCol'))) > len(col_widths_in):
        grid.remove(grid.findall(qn('a:gridCol'))[-1])
        for tr in t.findall(qn('a:tr')):
            tr.remove(tr.findall(qn('a:tc'))[-1])
    for gc, w in zip(grid.findall(qn('a:gridCol')), col_widths_in):
        gc.set('w', str(int(Inches(w))))


def fill_table(gf, data, col_widths_in, row_h_in=None):
    resize_table(gf.table, len(data), col_widths_in)
    for r, row in enumerate(data):
        for c, val in enumerate(row):
            set_text(gf.table.cell(r, c), val)
        if row_h_in:
            gf.table.rows[r].height = Inches(row_h_in)
    gf.width = Inches(sum(col_widths_in))


def picture(s, name, x, y, w=None, h=None):
    kw = {}
    if w: kw['width'] = Inches(w)
    if h: kw['height'] = Inches(h)
    return s.shapes.add_picture(str(FIG/name), Inches(x), Inches(y), **kw)


def label(s, src_shape, text, x=None, y=None, w=None, h=None):
    """Copy a styled text box from a template slide and set its text/position."""
    el = copy.deepcopy(src_shape._element)
    s.shapes._spTree.append(el)
    sh = s.shapes[-1]
    set_text(sh.text_frame, text)
    if x is not None: sh.left = Inches(x)
    if y is not None: sh.top = Inches(y)
    if w is not None: sh.width = Inches(w)
    if h is not None: sh.height = Inches(h)
    return sh


SCANS = N['seven_b_scans']
fmt_adc = lambda v: f'{v:.4e}'
fmt_pct = lambda v: f'{v:+.2f}%'
x3 = lambda v: f'{v*1e3:.2f}'

# ---- 1. protocol table (09-29 slide 1 format) ----
s = new_slide(ref.slides[0], layout=prs.slides[0].slide_layout)
title = shape(s, 'Google Shape;28;p4')
runs = title.text_frame.paragraphs[0].runs
runs[0].text, runs[1].text, runs[2].text = 'Test A / B ', 'v1.81 vs v1.911', ': FSE DWI: Water Phantom'
fill_table(shape(s, 'Google Shape;27;p4'), [
    ['Total Scan Time', '~4.5 minutes (7 b-values)'],
    ['TR, TE, esp', '2000 ms / 54 ms / 14 ms (v1.911: 13 ms)'],
    ['PE_order', '1'],
    ['ETL / Averages', '8 / 1'],
    ['FOV', '35'],
    ['b-values', '0, 100, 500, 1000, 2000, 3000, 6000 s/mm²'],
    ['Diffusion Directions', '1 (x-axis)'],
    ['Small / Big Delta', '4 ms / 40 ms'],
    ['diff_tcrush / tcrush', '1000 us / 1000 us'],
    ['diff_tcrush_amplitude / t_crush_amplitude', '-5482 DAC units / -8223 DAC units'],
], [3.6, 4.6])

# ---- 2. ADC by direction (09-10 slide 2 format) ----
s = new_slide(ORIGINAL[1])
rowsE, rowsG = N['directions']['E']['rows'], N['directions']['G']['rows']
names = {'+x': 'Positive x', '-x': 'Negative x', '+y': 'Positive y', '+z': 'Positive z'}
data = [['Direction', 'v1.81 ADC', 'v1.81 % diff', 'v1.911 ADC', 'v1.911 % diff']]
for k, n in names.items():
    data.append([n, fmt_adc(rowsE[k]['adc_nominal']), fmt_pct(rowsE[k]['adc_nominal_pct_diff_from_mean']),
                 fmt_adc(rowsG[k]['adc_nominal']), fmt_pct(rowsG[k]['adc_nominal_pct_diff_from_mean'])])
data.append(['Mean', fmt_adc(N['directions']['E']['mean_adc_nominal']), '0.00%', fmt_adc(N['directions']['G']['mean_adc_nominal']), '0.00%'])
fill_table(shape(s, 'Google Shape;59;p14'), data, [1.6, 1.7, 1.55, 1.7, 1.55])

# ---- 3. two fit graphs (09-10 slide 4 format) ----
s = new_slide(ORIGINAL[3])
picture(s, 'fit_v18_C.png', 0.29, 1.00, w=4.62)
picture(s, 'fit_v181_A.png', 5.09, 1.00, w=4.62)

# ---- 4. apparent ADC vs b (09-10 slide 5 format) ----
s = new_slide(ORIGINAL[4])
picture(s, 'apparent_adc_nominal.png', 0.88, 0.17, w=8.25)

# ---- 5. b-value accuracy: true b and ADC tables ----
s = new_slide(ORIGINAL[1])
hdr = ref.slides[1].shapes[2]          # 'b = 0 s/mm²' header style (Times New Roman bold grey)
t1 = shape(s, 'Google Shape;59;p14')
fill_table(t1, [['Nominal b', 'v1.8 (+x)', 'v1.8 (-x)', 'v1.81 (±x)'],
                ['0', '12', '12', '4'], ['100', '165', '59', '104'],
                ['1000', '1176', '842', '1001'], ['6000', '6398', '5579', '5981']], [1.25, 1.2, 1.2, 1.25])
t1.left, t1.top = Inches(0.35), Inches(0.9)
t2 = s.shapes._spTree.append(copy.deepcopy(t1._element)) or s.shapes[-1]
fill_table(t2, [['Sequence', 'Nominal b', 'Effective b']] +
           [[SCANS[k]['version'], x3(SCANS[k]['fit_nominal_b100_3000']['adc']), x3(SCANS[k]['fit_effective_b100_3000']['adc'])]
            for k in ('C', 'A', 'D', 'B')], [1.25, 1.2, 1.2])
t2.left, t2.top = Inches(5.75), Inches(0.9)
label(s, hdr, 'Effective b-value (s/mm²)', x=0.35, y=0.45, w=4.9)
label(s, hdr, 'ADC (×10⁻³ mm²/s)', x=5.75, y=0.45, w=3.65)

# ---- 6. apparent ADC: nominal vs true b ----
s = new_slide(ORIGINAL[4])
picture(s, 'adc_nominal_vs_effective.png', 0.2, 0.8, w=9.6)

# ---- 7. v1.81 vs v1.911 images (09-29 slide 2 format) ----
src = ref.slides[1]
s = new_slide(src, layout=BLANK)
P = N['image_panels']
snr = lambda k: round(P[k]['snr']) if isinstance(P[k], dict) else round(P[k])
set_text(shape(s, 'Google Shape;34;p5').text_frame, ['v1.81', f'SNR {snr("img_A_b0")} / {snr("img_A_b1000")}'])
set_text(shape(s, 'Google Shape;35;p5').text_frame, ['v1.911', f'SNR {snr("img_B_b0")} / {snr("img_B_b1000")}'])
set_text(shape(s, 'Google Shape;36;p5').text_frame, 'b = 0 s/mm²')
set_text(shape(s, 'Google Shape;39;p5').text_frame, 'b = 1000 s/mm²')
for name, x, y in [('img_A_b0.png', 1.83, 0.34), ('img_A_b1000.png', 5.04, 0.34), ('img_B_b0.png', 1.83, 3.00), ('img_B_b1000.png', 5.04, 3.00)]:
    picture(s, name, x, y, w=3.13, h=2.60)

# ---- 8. echo train + summary table ----
s = new_slide(ORIGINAL[1])
A, B = SCANS['A'], SCANS['B']
a0, b0 = A['navigator_echo1_noise_sub_amp'][0], B['navigator_echo1_noise_sub_amp'][0]
t = shape(s, 'Google Shape;59;p14')
fill_table(t, [['', 'v1.81', 'v1.911'],
               ['ESP', '14 ms', '13 ms'],
               ['First echo', '54 ms', '72.7 ms'],
               ['b0 signal', '1.00', f'{b0/a0:.2f}'],
               ['b1000 / b0', f"{A['S_corrected'][3]/A['S_corrected'][0]:.3f}", f"{B['S_corrected'][3]/B['S_corrected'][0]:.3f}"],
               ['ADC (×10⁻³ mm²/s)', x3(A['fit_effective_b100_3000']['adc']), x3(B['fit_effective_b100_3000']['adc'])],
               ['Slices', 'Multi', 'Single only']], [1.55, 0.85, 1.15], row_h_in=0.5)
t.left, t.top = Inches(0.25), Inches(0.85)
picture(s, 'echo_train.png', 3.95, 0.8, w=5.85)

# ---- 9. sequence diagrams ----
s = new_slide(ORIGINAL[4])
if (FIG/'sequence_both.png').exists():
    pic = picture(s, 'sequence_both.png', 0.2, 0.1, h=5.4)
    pic.left = int((prs.slide_width-pic.width)/2)
else:
    print('WARNING: sequence_both.png missing')

# ---- 10. next steps (09-10 slide 6 format) ----
s = new_slide(ORIGINAL[5])
body = shape(s, 'Google Shape;84;p18')
set_text(body.text_frame, ['Use b ≈ 10 instead of b = 0 on v1.81 (echo-1 s0 artifact)',
                           'Calibrate z-axis b-value (acquire ±z; z reads ~6% high)',
                           'Fix off-centre slice phase for multi-slice v1.81',
                           'Repeat on ex-vivo brain (v1.81 main, v1.911 comparison)',
                           'Motion test v1.81 vs v1.911 to choose the in-vivo sequence'])
for p in body.text_frame.paragraphs[1:]:
    p._p.get_or_add_pPr()
    spc = p._p.pPr.find(qn('a:spcBef'))
    if spc is not None:
        spc.find(qn('a:spcPts')).set('val', '1200')

# ---- drop the template slides ----
sldIdLst = prs.slides._sldIdLst
for sl in ORIGINAL:
    for sid in list(sldIdLst):
        if prs.part.related_part(sid.rId) is sl.part:
            prs.part.drop_rel(sid.rId); sldIdLst.remove(sid)
out = ROOT/'10-10-2026_report.pptx'
prs.save(out)
print('wrote', out, len(prs.slides), 'slides')
