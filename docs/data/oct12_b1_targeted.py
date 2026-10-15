#!/usr/bin/env python
"""Focused B1/B0 sensitivity run for the 2026-10-12 ss-MGOT scanner result.

The fast EPG sweep covers kappa=0.30..2.00. The event-level Bloch model is run at a
small set of relevant transmit scales and offsets on a reduced spatial grid. This is
intended as sensitivity analysis, not a measured B1 map or a causal decomposition.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import oct12_b1_bloch as B  # noqa: E402
import oct12_b1_epg as E  # noqa: E402

OUT_JSON = HERE / "oct12_b1_targeted.json"
OUT_CSV = HERE / "oct12_b1_targeted.csv"
OUT_FIG = ROOT / "docs/figures/physical_scanner_2026-10-12/oct12_b1_targeted.svg"
OUT_PNG = ROOT / "docs/figures/physical_scanner_2026-10-12/oct12_b1_targeted.png"
CACHE = ROOT / "runs/oct12_b1/bloch_targeted_cache.json"

K_GRID = np.round(np.arange(0.30, 2.0001, 0.01), 2)
K_BLOCH = (0.40, 0.45, 0.50, 0.60, 0.70, 0.85, 1.00, 1.10, 1.20, 1.50)
B0_OFFSETS = (50.0, 100.0, 200.0)
NZ, NY = 250, 32
T1, T2 = B.T1_DEFAULT, B.T2_DEFAULT
REFOCUS_EVENT = 166.4


def interp_cross(x, y, target, lo=0.3, hi=2.0):
    vals = np.log(np.asarray(y)) - np.log(target)
    roots = []
    for i in range(len(x) - 1):
        if vals[i] == 0:
            roots.append(float(x[i]))
        elif vals[i] * vals[i + 1] < 0:
            # Interpolate linearly in log amplitude across the fine 0.01-kappa EPG grid.
            roots.append(float(x[i] + (x[i + 1] - x[i]) * (-vals[i]) / (vals[i + 1] - vals[i])))
    return roots


def main():
    epg = {"kappa": K_GRID.tolist(), "models": {}}
    for model, ref in (("epg180", 180.0), ("epg166", REFOCUS_EVENT)):
        c = np.array([E.conventional_epg(k, T1, T2, refocus_deg=ref) for k in K_GRID])
        s = np.array([E.ssmgot_epg(k, T1, T2) for k in K_GRID])
        ratio = s[:, 0] / c[:, 0]
        epg["models"][model] = {
            "v183_echo1": c[:, 0].tolist(), "ssmgot_echo1": s[:, 0].tolist(),
            "ratio_echo1": ratio.tolist(),
            "ratio_mean_echoes1_8": (s.mean(axis=1) / c.mean(axis=1)).tolist(),
            "ratio_at_kappa_1": float(np.interp(1.0, K_GRID, ratio)),
            "kappa_for_ratio_0.5": interp_cross(K_GRID, ratio, 0.5),
            "kappa_for_ratio_0.05": interp_cross(K_GRID, ratio, 0.05),
            "kappa_for_ratio_0.25": interp_cross(K_GRID, ratio, 0.25),
        }

    # Confirm the factor of one-half belongs to the stored/recalled branch itself.
    parts = E.ssmgot_epg(1.0, T1, T2, return_parts=True)[1]
    prepared = float(parts["prep_echo"])
    ideal = {
        "twist_factor": 0.5,
        "prepared_echo_before_tipup_M0": prepared,
        "stored_M0_after_twist_and_T1_storage": float(parts["stored"]),
        "stored_over_prepared": float(parts["stored"] / prepared),
        "note": "The factor 0.5 applies to the prepared branch; full image ratio also includes re-excitation, variable refocusing, timings, and comparison with v1.83.",
    }

    jobs = []
    # One transmit sweep at B0=0, then a compact offset check at two transmit levels.
    for ver in ("v183", "v1912"):
        for k in K_BLOCH:
            jobs.append(B.make_job(ver, kappa=k, nz=NZ, ny=NY if ver == "v1912" else 1))
        for k in (0.70, 1.00):
            for df in B0_OFFSETS:
                for sign in (-1, 1):
                    jobs.append(B.make_job(ver, kappa=k, df=sign * df, nz=NZ,
                                           ny=NY if ver == "v1912" else 1))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache = B.run_jobs(jobs, CACHE, workers=6, verbose=True)
    bloch_rows = []
    for ver in ("v183", "v1912"):
        for k in K_BLOCH:
            j = B.make_job(ver, kappa=k, nz=NZ, ny=NY if ver == "v1912" else 1)
            bloch_rows.append({"ver": ver, "kappa": k, "b0_hz": 0.0, "echoes": B.get_echoes(cache, j).tolist()})
    for k in (0.70, 1.00):
        for df in (-200.0, -100.0, -50.0, 50.0, 100.0, 200.0):
            for ver in ("v183", "v1912"):
                j = B.make_job(ver, kappa=k, df=df, nz=NZ, ny=NY if ver == "v1912" else 1)
                bloch_rows.append({"ver": ver, "kappa": k, "b0_hz": df, "echoes": B.get_echoes(cache, j).tolist()})

    by_ver = {v: {r["kappa"]: np.asarray(r["echoes"]) for r in bloch_rows
                  if r["ver"] == v and r["b0_hz"] == 0.0} for v in ("v183", "v1912")}
    for r in bloch_rows:
        k, df = r["kappa"], r["b0_hz"]
        c0 = by_ver["v183"][k]
        s0 = by_ver["v1912"][k]
        if df == 0:
            c, s = c0, s0
        else:
            c = next(x["echoes"] for x in bloch_rows if x["ver"] == "v183" and x["kappa"] == k and x["b0_hz"] == df)
            s = next(x["echoes"] for x in bloch_rows if x["ver"] == "v1912" and x["kappa"] == k and x["b0_hz"] == df)
        c, s = np.asarray(c), np.asarray(s)
        r.update(ratio_echo1=float(s[0] / c[0]), ratio_mean_echoes1_8=float(s.mean() / c.mean()),
                 v183_echo1_relative_to_B0zero=float(c[0] / c0[0]),
                 ssmgot_echo1_relative_to_B0zero=float(s[0] / s0[0]),
                 ratio_echo1_relative_to_B0zero=float((s[0] / c[0]) / (s0[0] / c0[0])))

    epg_mappings = {}
    for model, d in epg["models"].items():
        ratios = np.asarray(d["ratio_echo1"])
        rmax_i = int(np.argmax(ratios))
        mappings = []
        for kr in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1):
            rr = float(np.interp(kr, K_GRID, ratios))
            roots = interp_cross(K_GRID, ratios, 1.6 * rr)
            left = [x for x in roots if x > kr]
            mappings.append({"kappa_right": kr, "ratio_right": rr,
                             "kappa_left_for_ratio_1.6": left[0] if left else None,
                             "transmit_scale_difference_percent": (100 * (left[0] / kr - 1)) if left else None})
        depth = []
        for ks in (0.9, 1.0, 1.1, 1.2, 1.3, 1.5):
            rs = float(np.interp(ks, K_GRID, ratios))
            roots = interp_cross(K_GRID, ratios, 0.1 * rs)
            lower = [x for x in roots if x < ks]
            depth.append({"kappa_surface": ks, "ratio_surface": rs,
                          "kappa_at_one_tenth_ratio": lower[-1] if lower else None,
                          "relative_B1_drop_percent": (100 * (1-lower[-1]/ks)) if lower else None})
        observed_norm_lr = 1.625 / 0.82  # midpoint of interim ss-MGOT L/R 1.55-1.70, normalized by v1.83 L/R 0.82
        normalized_lr = []
        for kr in (0.4, 0.5, 0.6, 0.7, 0.8):
            rr = float(np.interp(kr, K_GRID, ratios))
            roots = interp_cross(K_GRID, ratios, observed_norm_lr * rr)
            left = [x for x in roots if x > kr]
            normalized_lr.append({"kappa_right": kr, "ratio_right_ssmgot_over_v183": rr,
                                  "kappa_left_for_observed_normalized_LR": left[0] if left else None,
                                  "transmit_scale_difference_percent": (100 * (left[0] / kr - 1)) if left else None})
        epg_mappings[model] = {"max_ratio_on_0.30_to_2.00": float(ratios[rmax_i]),
                               "kappa_at_max_ratio": float(K_GRID[rmax_i]),
                               "observed_normalized_LR_target": observed_norm_lr,
                               "normalized_LR_assumption": "(ss-MGOT L/R)/(v1.83 L/R), using interim midpoint 1.625/0.82; same receive-profile factor assumed to cancel.",
                               "B1_difference_for_normalized_LR_target": normalized_lr,
                               "left_right_1.6_mappings": mappings,
                               "one_tenth_ratio_mappings": depth}

    # Full per-model numeric table for convenient plotting/review.
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "model", "kappa", "b0_hz", "v183_echo1_M0", "ssmgot_echo1_M0",
                    "ratio_echo1", "ratio_mean_echoes1_8", *[f"v183_echo{i}" for i in range(1, 9)],
                    *[f"ssmgot_echo{i}" for i in range(1, 9)]])
        for k in K_GRID:
            for model in ("epg180", "epg166"):
                d = epg["models"][model]
                i = int(round((k - 0.30) / 0.01))
                c = E.conventional_epg(k, T1, T2, refocus_deg=180 if model == "epg180" else REFOCUS_EVENT)
                s = E.ssmgot_epg(k, T1, T2)
                w.writerow(["EPG", model, f"{k:.2f}", 0, f"{c[0]:.8g}", f"{s[0]:.8g}",
                            f"{d['ratio_echo1'][i]:.8g}", f"{d['ratio_mean_echoes1_8'][i]:.8g}",
                            *[f"{x:.8g}" for x in c], *[f"{x:.8g}" for x in s]])
        for r in bloch_rows:
            if r["ver"] != "v183":
                continue
            # Pair signals are evaluated at equal κ and equal global off-resonance.
            c = next(x["echoes"] for x in bloch_rows if x["ver"] == "v183" and x["kappa"] == r["kappa"] and x["b0_hz"] == r["b0_hz"])
            s = next(x["echoes"] for x in bloch_rows if x["ver"] == "v1912" and x["kappa"] == r["kappa"] and x["b0_hz"] == r["b0_hz"])
            w.writerow(["Bloch", "event_model", r["kappa"], r["b0_hz"], c[0], s[0], s[0]/c[0],
                        np.mean(s)/np.mean(c), *c, *s])

    input_provenance = {}
    for ver, paths in B.CASES.items():
        input_provenance[ver] = {}
        for label, path in paths.items():
            input_provenance[ver][label] = {
                "path": str(path.relative_to(ROOT)),
                "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            }

    b0_summary = []
    for k in (0.70, 1.00):
        for df in B0_OFFSETS:
            for sign in (-1, 1):
                r = next(x for x in bloch_rows if x["ver"] == "v183" and x["kappa"] == k and x["b0_hz"] == sign*df)
                b0_summary.append({"kappa": k, "b0_hz": sign*df,
                                   "ratio_echo1": r["ratio_echo1"],
                                   "ratio_relative_to_B0zero": r["ratio_echo1_relative_to_B0zero"],
                                   "v183_echo1_relative": r["v183_echo1_relative_to_B0zero"],
                                   "ssmgot_echo1_relative": r["ssmgot_echo1_relative_to_B0zero"]})
    out = {
        "metadata": {
            "description": "Focused Oct-12 B1 sensitivity simulation; EPG full sweep and reduced-grid event-level Bloch points.",
            "T1_s": T1, "T2_s": T2, "TE_ms": 44, "ESP_ms": 11, "TR_s": 2.0,
            "event_bloch_grid": {"z_points": NZ, "z_span_mm": 5.0, "y_points_ssmgot": NY,
                                 "phase_axis_fov_mm": 35.0/128, "rf_substep": "event-model default"},
            "kappa_definition": "B1+ scale relative to nominal sequence calibration; uniform scale applied to all RF events.",
            "sequence_input_provenance": input_provenance,
            "no_measured_B1_map": True,
            "interpretation_limit": "The simulated transmit scale is a sensitivity parameter, not a measured spatial field. B0, receive sensitivity, motion, slice/profile and tissue differences are not causally separated by this calculation."
        },
        "ideal_twist": ideal,
        "epg": epg,
        "epg_inverse_sensitivity": epg_mappings,
        "event_bloch_targeted": bloch_rows,
        "event_bloch_B0_summary": b0_summary,
        "event_bloch_notes": "250 z points over 5 mm and 32 phase-axis points (v1.912). Point grid chosen for focused sensitivity; do not treat as a converged spatial map.",
        "cache": str(CACHE.relative_to(ROOT)),
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # Dependency-free vector panel: ideal EPG full curves with targeted Bloch points.
    W, H = 900, 560
    L, R, TOP, BOT = 88, 28, 74, 94
    PW, PH = W-L-R, H-TOP-BOT
    ymin, ymax = 0.005, 1.1
    def xp(k): return L + (k - 0.3) / 1.7 * PW
    def yp(y): return TOP + (np.log(ymax) - np.log(max(y, ymin))) / (np.log(ymax)-np.log(ymin)) * PH
    def curve_segments(ys):
        segments = []
        for i in range(len(K_GRID)-1):
            x0, x1 = float(K_GRID[i]), float(K_GRID[i+1])
            y0, y1 = float(ys[i]), float(ys[i+1])
            above0, above1 = y0 >= ymin, y1 >= ymin
            if not above0 and not above1:
                continue
            if above0 and not above1:
                ly0, ly1 = np.log(y0), np.log(max(y1, 1e-300))
                x1 = x0 + (x1-x0) * (np.log(ymin)-ly0)/(ly1-ly0)
                y1 = ymin
            elif not above0 and above1:
                ly0, ly1 = np.log(max(y0, 1e-300)), np.log(y1)
                x0 = x0 + (x1-x0) * (np.log(ymin)-ly0)/(ly1-ly0)
                y0 = ymin
            segments.append((x0, y0, x1, y1))
        return segments
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           '<rect width="100%" height="100%" fill="#fcfcfb"/>',
           '<style>text{font-family:Arial,sans-serif;fill:#171717} .grid{stroke:#deddd9;stroke-width:1} .axis{stroke:#555;stroke-width:1.2}</style>',
           f'<text x="{W/2}" y="30" text-anchor="middle" font-size="18">Transmit-scale sensitivity of the modeled protocol pair</text>',
           f'<line class="axis" x1="{L}" y1="{TOP}" x2="{L}" y2="{TOP+PH}"/><line class="axis" x1="{L}" y1="{TOP+PH}" x2="{L+PW}" y2="{TOP+PH}"/>']
    for y in (0.02, 0.05, 0.1, 0.2, 0.5, 1.0):
        yy = yp(y)
        svg.append(f'<line class="grid" x1="{L}" y1="{yy:.1f}" x2="{L+PW}" y2="{yy:.1f}"/>')
        svg.append(f'<text x="{L-12}" y="{yy+4:.1f}" text-anchor="end" font-size="12">{y:g}</text>')
    for k in (0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 2.0):
        xx = xp(k)
        svg.append(f'<line class="grid" x1="{xx:.1f}" y1="{TOP}" x2="{xx:.1f}" y2="{TOP+PH}"/>')
        svg.append(f'<text x="{xx:.1f}" y="{TOP+PH+22}" text-anchor="middle" font-size="12">{k:.1f}</text>')
    for model, d, color, label in (("epg180", epg["models"]["epg180"], "#2672b8", "EPG, v1.83 refocus 180°"),
                                   ("epg166", epg["models"]["epg166"], "#e36b2c", "EPG, v1.83 refocus 166.4°")):
        paths = " ".join(f"M {xp(x0):.2f} {yp(y0):.2f} L {xp(x1):.2f} {yp(y1):.2f}"
                          for x0, y0, x1, y1 in curve_segments(d["ratio_echo1"]))
        svg.append(f'<path d="{paths}" fill="none" stroke="{color}" stroke-width="2.5"/>')
    bx = np.array(K_BLOCH)
    br = np.array([next(r["ratio_echo1"] for r in bloch_rows if r["ver"] == "v183" and r["kappa"] == k and r["b0_hz"] == 0)
                   for k in K_BLOCH])
    for k, y in zip(bx, br):
        svg.append(f'<circle cx="{xp(k):.2f}" cy="{yp(y):.2f}" r="4.5" fill="#1b9a70" stroke="#fff" stroke-width="1"/>')
    for y, color, dash, label in ((0.5, "#555", "7 5", "observed near-surface ~0.5"),
                                  (0.05, "#777", "2 5", "observed deep ~0.05")):
        yy = yp(y)
        svg.append(f'<line x1="{L}" y1="{yy:.2f}" x2="{L+PW}" y2="{yy:.2f}" stroke="{color}" stroke-dasharray="{dash}"/>')
    svg.append(f'<text x="{L+PW/2}" y="{H-22}" text-anchor="middle" font-size="14">Transmit scale κ = B1+ / nominal</text>')
    svg.append(f'<text x="23" y="{TOP+PH/2}" transform="rotate(-90 23 {TOP+PH/2})" text-anchor="middle" font-size="14">ss-MGOT / v1.83 echo-1 magnitude</text>')
    # Compact, explicit legend.
    legend = [("#2672b8", "EPG, v1.83 refocus 180°"),
              ("#e36b2c", "EPG, v1.83 refocus 166.4°"),
              ("#1b9a70", "Event Bloch, B0=0 (reduced grid)"),
              ("#555", "observed ratios ~0.5 and ~0.05")]
    svg.append(f'<rect x="{L+4}" y="{TOP+4}" width="650" height="46" rx="3" fill="#fcfcfb" fill-opacity="0.94"/>')
    for i, (color, label) in enumerate(legend):
        col, row = i//2, i%2
        xx, yy = L+12+col*320, TOP+17+row*22
        if i == 2:
            svg.append(f'<circle cx="{xx+4}" cy="{yy-4}" r="4" fill="{color}"/>')
        else:
            svg.append(f'<line x1="{xx}" y1="{yy-4}" x2="{xx+24}" y2="{yy-4}" stroke="{color}" stroke-width="2.5" stroke-dasharray="{"7 5" if i==3 else "none"}"/>')
        svg.append(f'<text x="{xx+31}" y="{yy}" font-size="11">{label}</text>')
    svg.append('</svg>')
    OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    OUT_FIG.write_text("\n".join(svg), encoding="utf-8")

    # High-resolution raster twin for Markdown and PDF embedding. Draw from the
    # same numeric arrays and chart geometry as the SVG, using bundled Pillow.
    from PIL import Image, ImageDraw, ImageFont
    scale = 3
    image = Image.new("RGB", (W*scale, H*scale), "#fcfcfb")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    def font(sz):
        return ImageFont.truetype(str(font_path), sz*scale) if font_path.exists() else ImageFont.load_default()
    def xy_px(k, y):
        return (round(xp(k)*scale), round(yp(y)*scale))
    grid_col, ink, ink2 = "#deddd9", "#171717", "#555555"
    for y in (0.02, 0.05, 0.1, 0.2, 0.5, 1.0):
        yy = round(yp(y)*scale)
        draw.line((L*scale, yy, (L+PW)*scale, yy), fill=grid_col, width=scale)
        draw.text(((L-12)*scale, yy), f"{y:g}", font=font(12), fill=ink2, anchor="rm")
    for k in (0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 2.0):
        xx = round(xp(k)*scale)
        draw.line((xx, TOP*scale, xx, (TOP+PH)*scale), fill=grid_col, width=scale)
        draw.text((xx, (TOP+PH+22)*scale), f"{k:.1f}", font=font(12), fill=ink2, anchor="mt")
    draw.line((L*scale, TOP*scale, L*scale, (TOP+PH)*scale), fill=ink2, width=4)
    draw.line((L*scale, (TOP+PH)*scale, (L+PW)*scale, (TOP+PH)*scale), fill=ink2, width=4)
    for y, color, dash in ((0.5, "#555555", True), (0.05, "#777777", False)):
        yy = round(yp(y)*scale)
        seg, gap = (15*scale, 10*scale) if dash else (3*scale, 8*scale)
        start, end = L*scale, (L+PW)*scale
        while start < end:
            draw.line((start, yy, min(start+seg, end), yy), fill=color, width=3)
            start += seg+gap
    for model, d, color in (("epg180", epg["models"]["epg180"], "#2672b8"),
                            ("epg166", epg["models"]["epg166"], "#e36b2c")):
        for x0, y0, x1, y1 in curve_segments(d["ratio_echo1"]):
            draw.line((xy_px(x0, y0), xy_px(x1, y1)), fill=color, width=7)
    for k, y in zip(bx, br):
        xx, yy = xy_px(k, y)
        rad = 7*scale
        draw.ellipse((xx-rad, yy-rad, xx+rad, yy+rad), fill="#1b9a70", outline="#ffffff", width=2*scale)
    draw.text((W*scale//2, (H-22)*scale), "Transmit scale κ = B1+ / nominal", font=font(14), fill=ink, anchor="mm")
    ylabel = Image.new("RGBA", (360*scale, 28*scale), (0, 0, 0, 0))
    ImageDraw.Draw(ylabel).text((180*scale, 14*scale), "ss-MGOT / v1.83 echo-1 magnitude", font=font(14), fill=ink, anchor="mm")
    ylabel = ylabel.rotate(90, expand=True)
    image.paste(ylabel, (2*scale, (TOP+PH//2)*scale-ylabel.height//2), ylabel)
    draw.text((W*scale//2, 30*scale), "Transmit-scale sensitivity of the modeled protocol pair", font=font(18), fill=ink, anchor="mm")
    legend = [("#2672b8", "EPG, v1.83 refocus 180°", "line"),
              ("#e36b2c", "EPG, v1.83 refocus 166.4°", "line"),
              ("#1b9a70", "Event Bloch, B0=0 (reduced grid)", "dot"),
              ("#555555", "observed ratios ~0.5 and ~0.05", "dash")]
    draw.rounded_rectangle(((L+4)*scale, (TOP+4)*scale, (L+654)*scale, (TOP+50)*scale), radius=3*scale,
                           fill="#fcfcfb", outline="#fcfcfb")
    for i, (color, label, kind) in enumerate(legend):
        col, row = i//2, i%2
        xx, yy = (L+12+col*320)*scale, (TOP+17+row*22)*scale
        if kind == "dot":
            draw.ellipse((xx, yy-5*scale, xx+9*scale, yy+4*scale), fill=color)
        else:
            dashlen = 16*scale if kind == "dash" else 24*scale
            draw.line((xx, yy, xx+dashlen, yy), fill=color, width=7 if kind == "line" else 3)
        draw.text((xx+31*scale, yy), label, font=font(11), fill=ink, anchor="lm")
    image.save(OUT_PNG, format="PNG", dpi=(300, 300), optimize=True)
    print(f"Wrote {OUT_PNG}")
    print(f"Wrote {OUT_JSON}, {OUT_CSV}, {OUT_FIG}")


if __name__ == "__main__":
    main()
