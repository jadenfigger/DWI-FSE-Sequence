#!/usr/bin/env python3
"""Build audited Oct 12 baseline SNR and normalized-efficiency slide figures."""
from __future__ import annotations
import csv, json, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs" / "data"
FIG = ROOT / "docs" / "figures" / "physical_scanner_2026-10-12"
FIG.mkdir(parents=True, exist_ok=True)
AUDIT = json.loads((DATA / "oct12_quant_audit.json").read_text(encoding="utf-8"))
SIGNALS = list(csv.DictReader((DATA / "oct12_roi_signals.csv").open(newline="", encoding="utf-8")))
eff_rows = {(r["scan"], r["roi"]): r for r in AUDIT["snr_efficiency_rows"]}
times = {}
for row in SIGNALS:
    if row["scan"] not in times:
        times[row["scan"]] = float(row["t_vol_s"])

# case, scan key, data scan, ROI, group, display label, canonical ROI label
cases = [
    ("Q", "Q", "Q", "ex_vivo", "Q", "Q"),
    ("R", "R", "R", "ex_vivo", "R", "R"),
    ("test0", "epi0", "epi0", "ex_vivo", "EPI test0", "test0"),
    ("iA", "iA", "iA", "in_vivo", "iA", "iA"),
    ("iB", "iB", "iB", "in_vivo", "iB", "iB"),
    ("invivoA", "epiA", "epiA", "in_vivo", "EPI invivoA", "invivoA"),
]
rows = []
for key, scan, data_scan, group, label, case in cases:
    rois = [("ex_pbs", "PBS"), ("ex_brain", "Whole brain")] if group == "ex_vivo" else [("iv_brain", "Whole brain")]
    for roi, roi_label in rois:
        if scan == "R":
            metric = AUDIT["r_geometry"]["metrics"][roi]
            snr = float(metric["R_b10_snr_geometry_roi"])
            voxel = float(AUDIT["r_geometry"]["voxel_ul"])
            source = "oct12_quant_audit.json:r_geometry.metrics"
        else:
            metric = eff_rows[(scan, roi)]
            snr = float(metric["snr"])
            voxel = float(metric["voxel_ul_stored"])
            source = "oct12_quant_audit.json:snr_efficiency_rows"
        t = times[data_scan]
        b = 0 if scan.startswith("epi") else 10
        rows.append({
            "case": case, "display_label": label, "sequence": {"Q":"v1.83", "R":"ss-MGOT", "test0":"EPI", "iA":"v1.83", "iB":"v1.912", "invivoA":"EPI"}[case], "group": group,
            "roi": roi, "roi_label": roi_label, "reference_b": b,
            "snr": snr, "volume_time_s": t, "nominal_voxel_ul": voxel,
            "normalized_efficiency": snr / math.sqrt(t) / voxel,
            "efficiency_units": "SNR/sqrt(s)/uL",
            "source": source,
        })

csv_path = DATA / "oct12_slide_snr.csv"
with csv_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

# Render crisp, slide-ready 16:9 raster charts with Pillow (no plotting dependencies).
W, H = 3200, 1800
BG = "#ffffff"
INK = "#17212b"
MUTED = "#576575"
GRID = "#dbe2e8"
COLORS = {"Q": "#2a78d6", "R": "#eb6834", "test0": "#1baf7a",
          "iA": "#2a78d6", "iB": "#eb6834", "invivoA": "#1baf7a"}
PALE = {"Q": "#b9d4f3", "R": "#f5c5b2", "test0": "#b9e6d6"}
FONT_PATH = "C:/Windows/Fonts/arial.ttf"
BOLD_PATH = "C:/Windows/Fonts/arialbd.ttf"
def font(size, bold=False):
    return ImageFont.truetype(BOLD_PATH if bold else FONT_PATH, size)
def txt(d, xy, s, size, fill=INK, bold=False, anchor=None):
    d.text(xy, s, font=font(size, bold), fill=fill, anchor=anchor)
def rounded(d, box, radius=24, fill="#ffffff", outline="#e4e9ee", width=2):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
def draw_hatched_bar(im, x0, y0, x1, y1, base, outline):
    d = ImageDraw.Draw(im)
    d.rectangle((x0, y0, x1, y1), fill=base, outline=outline, width=3)
    # 45-degree diagonal hatch, clipped to the bar area.
    span = (x1-x0) + (y1-y0)
    for k in range(-span, span, 26):
        # segment equation x+y = constant within the rectangle
        pts=[]
        for x in (x0, x1):
            y=k-(x-x0)+y0
            if y0 <= y <= y1: pts.append((x,y))
        for y in (y0, y1):
            x=x0+(k-(y-y0))
            if x0 <= x <= x1: pts.append((x,y))
        if len(pts)>=2:
            d.line((pts[0],pts[1]), fill=outline, width=3)

def draw_chart(path, metric, title, max_y, ticks, ylabel, footer, is_eff=False):
    im = Image.new("RGB", (W,H), BG)
    d = ImageDraw.Draw(im)
    # header
    txt(d,(150,90),title,64,INK,True)
    txt(d,(150,178),"Audited centre-slice ROI values",31,MUTED)
    # panels
    panels=[(130,280,1870,1485,"Ex vivo"),(1930,280,3070,1485,"In vivo")]
    series = [
        [r for r in rows if r["group"]=="ex_vivo"],
        [r for r in rows if r["group"]=="in_vivo"],
    ]
    for pi, ((x0,y0,x1,y1,ptitle), data) in enumerate(zip(panels,series)):
        txt(d,(x0+48,y0+34),ptitle,39,INK,True)
        left=x0+130; right=x1-58; top=y0+130; bottom=y1-170
        # grid/ticks
        for tick in ticks:
            y=bottom-(tick/max_y)*(bottom-top)
            d.line((left,y,right,y),fill=GRID,width=2)
            txt(d,(left-22,y),str(tick),24,MUTED,False,"rm")
        txt(d,(x0+36,(top+bottom)//2),ylabel,23,MUTED,False,"mm")
        groups=(["Q","R","test0"] if pi==0 else ["iA","iB","invivoA"])
        centers=[left+(i+0.5)*(right-left)/len(groups) for i in range(len(groups))]
        if pi==0:
            bw=74; gap=18
            for center,case in zip(centers,groups):
                vals=[next(r for r in data if r["case"]==case and r["roi"]=="ex_pbs"),
                      next(r for r in data if r["case"]==case and r["roi"]=="ex_brain")]
                for j,row in enumerate(vals):
                    value=row[metric]
                    x0b=center-(bw+gap/2) if j==0 else center+gap/2
                    x1b=x0b+bw
                    y=bottom-(value/max_y)*(bottom-top)
                    if j==0:
                        draw_hatched_bar(im,int(x0b),int(y),int(x1b),int(bottom),PALE[case],COLORS[case])
                    else:
                        d.rectangle((int(x0b),int(y),int(x1b),int(bottom)),fill=COLORS[case],outline=COLORS[case])
                    txt(d,(center+(-bw/2-gap/2 if j==0 else bw/2+gap/2),max(top+2,y-38)),f"{value:.1f}",24,INK,True,"ms")
                seq={"Q":"v1.83","R":"ss-MGOT","test0":"EPI"}[case]; txt(d,(center,bottom+15),seq,23,INK,False,"mt"); txt(d,(center,bottom+45),case,27,INK,True,"mt")
        else:
            bw=105
            for center,case in zip(centers,groups):
                row=next(r for r in data if r["case"]==case)
                value=row[metric]
                y=bottom-(value/max_y)*(bottom-top)
                d.rectangle((int(center-bw/2),int(y),int(center+bw/2),int(bottom)),fill=COLORS[case],outline=COLORS[case])
                txt(d,(center,max(top+2,y-42)),f"{value:.1f}",27,INK,True,"ms")
                seq={"iA":"v1.83","iB":"v1.912","invivoA":"EPI"}[case]; txt(d,(center,bottom+15),seq,23,INK,False,"mt"); txt(d,(center,bottom+45),case,27,INK,True,"mt")
    # footer and legends
    if not is_eff:
        # legend explaining hatch/solid and sequence colors
        y=1540
        draw_hatched_bar(im,190,y+27,250,y+82,"#d9e3ed","#718092")
        txt(d,(270,y+54),"PBS (hatched)",25,INK,False,"lm")
        d.rectangle((500,y+27,560,y+82),fill="#718092")
        txt(d,(580,y+54),"Whole brain (solid)",25,INK,False,"lm")
        for i,(case,color,label) in enumerate([("Q",COLORS["Q"],"Q"),("R",COLORS["R"],"R"),("test0",COLORS["test0"],"EPI test0")]):
            xx=980+i*230
            d.rectangle((xx,y+28,xx+52,y+80),fill=color)
            txt(d,(xx+66,y+54),label,24,INK,False,"lm")
        for i,(case,color,label) in enumerate([("iA",COLORS["iA"],"iA"),("iB",COLORS["iB"],"iB"),("invivoA",COLORS["invivoA"],"EPI invivoA")]):
            xx=1680+i*300
            d.rectangle((xx,y+28,xx+52,y+80),fill=color)
            txt(d,(xx+66,y+54),label,24,INK,False,"lm")
        txt(d,(150,1694),footer,23,MUTED)
    else:
        y=1515
        draw_hatched_bar(im,190,y+12,250,y+67,"#d9e3ed","#718092")
        txt(d,(270,y+40),"PBS (hatched)",25,INK,False,"lm")
        d.rectangle((500,y+12,560,y+67),fill="#718092")
        txt(d,(580,y+40),"Whole brain (solid)",25,INK,False,"lm")
        txt(d,(150,1603),footer,22,MUTED)
        txt(d,(150,1648),"EPI native acquired voxel = 0.1139323 uL; R geometry-corrected voxel = 0.06646 uL.",22,MUTED)
    im.save(path,format="PNG",optimize=True,dpi=(300,300))

draw_chart(FIG/"slide_snr_baseline.png","snr","Baseline centre-slice SNR",150,[0,30,60,90,120,150],"SNR",
           "FSE uses b=10; EPI uses b=0. Ex vivo bars: PBS and whole brain. In vivo bars: whole brain.")
draw_chart(FIG/"slide_snr_efficiency.png","normalized_efficiency","Normalized SNR efficiency",300,[0,60,120,180,240,300],"SNR / sqrt(s) / uL",
           "SNR / sqrt(volume time) / nominal voxel volume; EPI native grid; protocols differ.",True)
print(json.dumps({"csv":str(csv_path),"baseline":str(FIG/"slide_snr_baseline.png"),
                  "efficiency":str(FIG/"slide_snr_efficiency.png"),
                  "rows":rows},indent=2))
